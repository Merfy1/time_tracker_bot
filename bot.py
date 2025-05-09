import logging
import random
import requests
from datetime import datetime
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

                # Сохраняем ID пользователя для дальнейших действий
                context.user_data["employee_id"] = result[0]

                buttons = [[KeyboardButton("🔛 Начать смену")]]
                reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
                update.message.reply_text("Нажми кнопку ниже, чтобы начать смену.", reply_markup=reply_markup)

            else:
                update.message.reply_text("Неверный код! Попробуй снова.")
                logger.warning(f"Неудачная попытка входа с кодом: {entered_code}")

            connection.close()
            context.user_data["is_logging_in"] = False
        except Exception as e:
            logger.error(f"Ошибка при входе: {e}")
            update.message.reply_text("Ошибка входа. Попробуй позже.")

    # Начать смену
    if text == "🔛 Начать смену":
        employee_id = context.user_data.get("employee_id")
        if not employee_id:
            update.message.reply_text("Сначала нужно войти.")
            return

        connection = create_connection()
        cursor = connection.cursor()

        try:
            # Проверяем, есть ли уже активная смена
            cursor.execute(
                "SELECT * FROM shifts WHERE employee_id = ? AND end_time IS NULL",
                (employee_id,)
            )
            existing_shift = cursor.fetchone()

            if existing_shift:
                update.message.reply_text("Ты уже на смене.")
                return

            # Создаем новую смену
            cursor.execute(
                "INSERT INTO shifts (employee_id, start_time) VALUES (?, ?)",
                (employee_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            connection.commit()

            update.message.reply_text("Смена началась!")

            logger.info(f"Смена начата для сотрудника {employee_id}")

            connection.close()

            buttons = [[KeyboardButton("🔚 Закончить смену")]]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Когда захочешь закончить смену, нажми кнопку ниже.", reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка при начале смены: {e}")
            update.message.reply_text("Не удалось начать смену.")

    # Закончить смену
    if text == "🔚 Закончить смену":
        employee_id = context.user_data.get("employee_id")
        if not employee_id:
            update.message.reply_text("Сначала нужно войти.")
            return

        connection = create_connection()
        cursor = connection.cursor()

        try:
            # Получаем активную смену
            cursor.execute(
                "SELECT id, start_time FROM shifts WHERE employee_id = ? AND end_time IS NULL",
                (employee_id,)
            )
            shift = cursor.fetchone()

            if not shift:
                update.message.reply_text("Активная смена не найдена.")
                return

            shift_id, start_time_str = shift
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.now()

            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            salary = duration_minutes * 2

            # Обновляем запись в БД
            cursor.execute(
                "UPDATE shifts SET end_time = ? WHERE id = ?",
                (end_time.strftime("%Y-%m-%d %H:%M:%S"), shift_id)
            )
            connection.commit()

            update.message.reply_text(
                f"✅ Смена завершена.\n"
                f"🕒 Время на смене: {duration_minutes} мин\n"
                f"💰 Заработано: {salary} руб"
            )

            buttons = [[KeyboardButton("🔛 Начать смену")]]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Готов снова начать — нажми кнопку ниже.", reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка при завершении смены: {e}")
            update.message.reply_text("Не удалось завершить смену.")

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
