from flask import Flask
from werkzeug.urls import url_quote  # Додано для сумісності
from threading import Thread
import telebot
from telebot import types
import sqlite3
import time
import random
import string
import os

# Ініціалізація Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running!"

@app.route('/ping')
def ping():
    return "Pong", 200

# Конфігурація бота
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))

bot = telebot.TeleBot(BOT_TOKEN)
admin_id = ADMIN_ID

# База даних
def init_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 message_id INTEGER,
                 anon_id TEXT,
                 active INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

def generate_anon_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def send_to_admin(message, anon_id):
    try:
        info_msg = f"📨 Нове повідомлення від аноніма #{anon_id}\n👤 User ID: {message.from_user.id}\n📅 Час: {time.strftime('%Y-%m-%d %H:%M:%S')}"

        if message.content_type == 'text':
            bot.send_message(admin_id, info_msg)
            bot.send_message(admin_id, message.text)
        elif message.content_type == 'photo':
            bot.send_message(admin_id, info_msg)
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=message.caption)
        elif message.content_type == 'video':
            bot.send_message(admin_id, info_msg)
            bot.send_video(admin_id, message.video.file_id, caption=message.caption)
        elif message.content_type == 'voice':
            bot.send_message(admin_id, info_msg)
            bot.send_voice(admin_id, message.voice.file_id)
        elif message.content_type == 'audio':
            bot.send_message(admin_id, info_msg)
            bot.send_audio(admin_id, message.audio.file_id)
        elif message.content_type == 'document':
            bot.send_message(admin_id, info_msg)
            bot.send_document(admin_id, message.document.file_id, caption=message.caption)

        markup = types.InlineKeyboardMarkup()
        reply_btn = types.InlineKeyboardButton("💬 Відповісти", callback_data=f"reply_{anon_id}")
        markup.add(reply_btn)
        bot.send_message(admin_id, "Оберіть дію:", reply_markup=markup)

    except Exception as e:
        bot.send_message(admin_id, f"❌ Помилка при відправці: {e}")

# Обробники повідомлень
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('📢 Запропонувати новину')
    btn2 = types.KeyboardButton('📩 Потрібна реклама')
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "Виберіть опцію:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📢 Запропонувати новину')
def request_news(message):
    msg = bot.send_message(message.chat.id, "Надішліть вашу новину (текст, фото, відео, голосове чи файл):")
    bot.register_next_step_handler(msg, process_news_submission)

def process_news_submission(message):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        anon_id = generate_anon_id()
        c.execute("INSERT INTO user_messages (user_id, message_id, anon_id) VALUES (?, ?, ?)",
                 (message.from_user.id, message.message_id, anon_id))
        conn.commit()
        send_to_admin(message, anon_id)
        bot.send_message(message.chat.id, "✅ Ваше повідомлення відправлено!")
        conn.close()
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Помилка: {e}")

@bot.message_handler(func=lambda message: message.text == '📩 Потрібна реклама')
def handle_ad_request(message):
    bot.send_message(message.chat.id, "Для питань реклами звертайтесь до: @my_channel")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def handle_reply_callback(call):
    try:
        anon_id = call.data.split('_')[1]
        bot.answer_callback_query(call.id, f"Відповідаємо аноніму #{anon_id}")
        msg = bot.send_message(admin_id, f"Напишіть відповідь для #{anon_id}:")
        bot.register_next_step_handler(msg, lambda m: process_admin_reply(m, anon_id))
    except Exception as e:
        bot.send_message(admin_id, f"❌ Помилка: {e}")

def process_admin_reply(message, anon_id):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM user_messages WHERE anon_id=?", (anon_id,))
        result = c.fetchone()

        if result:
            user_id = result[0]
            if message.content_type == 'text':
                bot.send_message(user_id, f"📩 Відповідь адміна:\n\n{message.text}")
            elif message.content_type == 'photo':
                bot.send_photo(user_id, message.photo[-1].file_id, caption=f"📩 Відповідь адміна:\n\n{message.caption}")
            elif message.content_type == 'video':
                bot.send_video(user_id, message.video.file_id, caption=f"📩 Відповідь адміна:\n\n{message.caption}")
            elif message.content_type == 'voice':
                bot.send_voice(user_id, message.voice.file_id)
            elif message.content_type == 'audio':
                bot.send_audio(user_id, message.audio.file_id)
            elif message.content_type == 'document':
                bot.send_document(user_id, message.document.file_id, caption=f"📩 Відповідь адміна:\n\n{message.caption}")

            c.execute("UPDATE user_messages SET active=0 WHERE anon_id=?", (anon_id,))
            conn.commit()
            bot.send_message(admin_id, f"✅ Відповідь для #{anon_id} відправлена!")
        else:
            bot.send_message(admin_id, f"❌ Анонім #{anon_id} не знайдений")
        conn.close()
    except Exception as e:
        bot.send_message(admin_id, f"❌ Помилка: {e}")

@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'audio', 'document'])
def handle_all_messages(message):
    try:
        if message.text in ['/start', '/help', '📢 Запропонувати новину', '📩 Потрібна реклама']:
            return

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT anon_id FROM user_messages WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1", 
                 (message.from_user.id,))
        result = c.fetchone()

        if result:
            anon_id = result[0]
            c.execute("INSERT INTO user_messages (user_id, message_id, anon_id) VALUES (?, ?, ?)",
                     (message.from_user.id, message.message_id, anon_id))
            conn.commit()
            send_to_admin(message, anon_id)
            bot.send_message(message.chat.id, "✅ Повідомлення відправлено!")
        else:
            request_news(message)
        conn.close()
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Помилка: {e}")

def run_bot():
    init_db()
    print("🟢 Бот запущено!")
    bot.polling(none_stop=True, interval=1, timeout=60)

# Змінна для Gunicorn
app_instance = app

if __name__ == '__main__':
    run_bot()
wsgi_app = app  # Для Gunicorn
