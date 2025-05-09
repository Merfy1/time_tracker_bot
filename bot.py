import logging
import random
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import TELEGRAM_TOKEN
from database import create_connection

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Функция получения случайного изображения
def get_random_image():
    dog_api = "https://random.dоg/woof.json"
    cat_api = "https://api.thecatapi.com/v1/images/search"
    try:
        response = requests.get(dog_api, timeout=5)
        if response.status_code == 200:
            image_url = response.json().get("url")
            if image_url:
                return image_url
    except Exception as e:
        logger.error(f"Ошибка с API собак: {e}")

    # Если API собак не работает, пробуем котиков
    try:
        response = requests.get(cat_api, timeout=5)
        if response.status_code == 200:
            image_url = response.json()[0].get("url")
            if image_url:
                return image_url
    except Exception as e:
        logger.error(f"Ошибка с API котов: {e}")

    # Если всё сломалось, возвращаем заглушку
    return "https://placekitten.com/400/400"

# Функция старта
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info(f"Пользователь {user.first_name} ({chat_id}) запустил бота.")

    buttons = [
        [KeyboardButton("✅ Регистрация")],
        [KeyboardButton("🔑 Войти")],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

    update.message.reply_text(
        f"Привет, {user.first_name}! Выбери действие:", reply_markup=reply_markup
    )

# Функция обработки сообщений
def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    text = update.message.text

    # Регистрация
    if text == "✅ Регистрация":
        update.message.reply_text("Введите ваше ФИО для регистрации:")
        context.user_data["is_registering"] = True
        return

    if context.user_data.get("is_registering"):
        full_name = update.message.text
        unique_code = f"CODE-{random.randint(1000, 9999)}"

        connection = create_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT * FROM employees WHERE full_name = ?", (full_name,))
            result = cursor.fetchone()

            if result:
                update.message.reply_text(
                    "Пользователь с таким ФИО уже существует! Попробуйте ввести другое ФИО или войти."
                )

                buttons = [[KeyboardButton("🔑 Войти")]]
                reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

                return  

            cursor.execute("INSERT INTO employees (full_name, unique_code) VALUES (?, ?)", (full_name, unique_code))
            connection.commit()

            update.message.reply_text(f"Регистрация завершена! Твой код: {unique_code}")

            buttons = [[KeyboardButton("🔑 Войти")]]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
            update.message.reply_text("Теперь можешь войти:", reply_markup=reply_markup)

            logger.info(f"Зарегистрирован новый пользователь: {full_name} (Код: {unique_code})")

            connection.close()
            context.user_data["is_registering"] = False
        except Exception as e:
            logger.error(f"Ошибка при регистрации: {e}")
            update.message.reply_text("Ошибка регистрации. Попробуй позже.")

        return

    # Вход
    if text == "🔑 Войти":
        update.message.reply_text("Введите ваш уникальный код:")
        context.user_data["is_logging_in"] = True
        return

    if context.user_data.get("is_logging_in"):
        entered_code = update.message.text
        connection = create_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT * FROM employees WHERE unique_code = ?", (entered_code,))
            result = cursor.fetchone()

            if result:
                update.message.reply_text(f"Привет, {result[1]}! Ты успешно вошел. Начинай смену!")

                # Получаем случайное изображение
                image_url = get_random_image()
                update.message.reply_photo(photo=image_url)

                logger.info(f"Пользователь {result[1]} вошел в систему (Код: {entered_code})")

            else:
                update.message.reply_text("Неверный код! Попробуй снова.")
                logger.warning(f"Неудачная попытка входа с кодом: {entered_code}")

            connection.close()
            context.user_data["is_logging_in"] = False
        except Exception as e:
            logger.error(f"Ошибка при входе: {e}")
            update.message.reply_text("Ошибка входа. Попробуй позже.")

# Основная функция запуска бота
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    logger.info("Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
