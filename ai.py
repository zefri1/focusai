import telebot
from telebot import types
import google.generativeai as genai
import os
from flask import Flask, request

# --- НАСТРОЙКИ ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Например: https://your-app.onrender.com

if not TELEGRAM_TOKEN or not GEMINI_API_KEY or not WEBHOOK_URL:
    print("Ошибка: Не заданы переменные окружения TELEGRAM_TOKEN, GEMINI_API_KEY или WEBHOOK_URL")
    exit(1)

# Инициализация Gemini API через официальный SDK
genai.configure(api_key=GEMINI_API_KEY)
# Используем актуальную модель Gemini 2.5 Flash
model = genai.GenerativeModel('gemini-2.5-flash')

# Каналы для обязательной подписки
REQUIRED_CHANNELS = ['@focuspt18', '@focuspt']

# Инициализация бота с отключением threaded для webhook
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# Инициализация Flask для webhook
app = Flask(__name__)

def ask_gemini(text):
    """Запрос к Gemini API через официальный SDK"""
    try:
        response = model.generate_content(text)
        return response.text
    except Exception as e:
        return f"❌ Ошибка API: {str(e)}"

def check_subscription(user_id):
    """Проверка подписки"""
    for channel in REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status in ['left', 'kicked']:
                return False
        except Exception as e:
            # Если бот не админ, он не может проверить. 
            # Логируем ошибку, но не блокируем пользователя (чтобы бот не падал)
            print(f"⚠️ Ошибка проверки канала {channel}: {e}")
            pass 
    return True

def create_subscription_keyboard():
    """Кнопки для подписки"""
    keyboard = types.InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        btn = types.InlineKeyboardButton(
            text=f"Подписаться на {channel}",
            url=f"https://t.me/{channel.replace('@', '')}"
        )
        keyboard.add(btn)
    keyboard.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
    return keyboard

# --- ОБРАБОТЧИКИ ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    if check_subscription(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "👋 Привет! Я готов работать. Задай мне вопрос!"
        )
    else:
        bot.send_message(
            message.chat.id,
            "🔒 Для доступа к боту подпишитесь на каналы:",
            reply_markup=create_subscription_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Спасибо! Подписка подтверждена. Можете спрашивать.")
    else:
        bot.answer_callback_query(call.id, "❌ Вы подписались не на все каналы!", show_alert=True)

@bot.message_handler(content_types=['text'])
def text_handler(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "🔒 Подписка обязательна:",
            reply_markup=create_subscription_keyboard()
        )
        return

    # Индикация "печатает..."
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Ответ нейросети
    answer = ask_gemini(message.text)
    
    # Разбиваем длинный ответ, если нужно (Telegram лимит 4096 символов)
    if len(answer) > 4000:
        for x in range(0, len(answer), 4000):
            bot.reply_to(message, answer[x:x+4000])
    else:
        bot.reply_to(message, answer)

# --- FLASK WEBHOOK ---

@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    """Обработка входящих обновлений от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403

@app.route('/')
def index():
    """Главная страница для проверки работоспособности"""
    return 'Bot is running!', 200

@app.route('/setwebhook')
def set_webhook():
    """Установка webhook (вызвать один раз после деплоя)"""
    webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    result = bot.set_webhook(url=webhook_url)
    if result:
        return f"Webhook установлен: {webhook_url}", 200
    else:
        return "Ошибка установки webhook", 500

# --- ЗАПУСК ---
if __name__ == '__main__':
    print("🚀 Бот запущен (режим Webhook)")
    
    # Удаляем старый webhook/polling и устанавливаем новый
    bot.remove_webhook()
    webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook установлен: {webhook_url}")
    
    # Запускаем Flask на порту, который предоставляет Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)