import telebot
from telebot import types
import google.generativeai as genai
import os
import time

# --- НАСТРОЙКИ ЧЕРЕЗ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ---
# На Render эти ключи задаются в разделе "Environment Variables"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("Ошибка: Не заданы переменные окружения TELEGRAM_TOKEN или GEMINI_API_KEY")
    exit(1)

# Инициализация Gemini API через официальный SDK
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Каналы для обязательной подписки
REQUIRED_CHANNELS = ['@focuspt18', '@focuspt']

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

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

# --- ЗАПУСК ---
if __name__ == '__main__':
    print("🚀 Бот запущен (режим Polling)")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Падение бота: {e}")
            time.sleep(5) # Ждем 5 сек перед перезапуском