import random
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import TELEGRAM_TOKEN
from database import create_connection

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id

    # Создаем кнопки с эмодзи
    buttons = [
        [KeyboardButton("Регистрация")],
        [KeyboardButton("Войти")],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)

    # Приветственное сообщение с кнопками
    update.message.reply_text(
        f"Привет, {user.first_name}! Ты можешь зарегистрироваться или войти.",
        reply_markup=reply_markup
    )

def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    text = update.message.text

    # Регистрация
    if text == "Регистрация":
        # Удаляем кнопки с регистрацией
        update.message.reply_text("Введите ваше ФИО для регистрации:")
        context.user_data["is_registering"] = True
        return

    # Если идет регистрация
    if context.user_data.get("is_registering"):
        full_name = update.message.text
        unique_code = f"CODE-{random.randint(1000, 9999)}"

        # Подключаемся к базе данных
        connection = create_connection()
        cursor = connection.cursor()

        # Проверяем, существует ли уже пользователь с таким ФИО
        cursor.execute("SELECT * FROM employees WHERE full_name = ?", (full_name,))
        result = cursor.fetchone()

        if result:
            # Если такой пользователь уже есть
            update.message.reply_text("Пользователь с таким ФИО уже существует. Введите другое ФИО.")
        else:
            # Если такого пользователя нет, регистрируем его
            cursor.execute("INSERT INTO employees (full_name, unique_code) VALUES (?, ?)",
                           (full_name, unique_code))
            connection.commit()

            # Отправляем уникальный код
            update.message.reply_text(f"Регистрация завершена! Ваш уникальный код: {unique_code}")

            # Завершаем процесс регистрации
            context.user_data["is_registering"] = False

            # Отправляем сообщение с навигацией
            buttons = [
                [KeyboardButton("Войти")],
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            update.message.reply_text(
                "Регистрация завершена. Для входа, пожалуйста, нажми кнопку 'Войти'.",
                reply_markup=reply_markup
            )

        connection.close()
        return

    # Вход
    if text == "Войти":
        update.message.reply_text("Введите ваш уникальный код для входа:")
        context.user_data["is_logging_in"] = True
        return

    # Если идет процесс входа
    if context.user_data.get("is_logging_in"):
        entered_code = update.message.text
        connection = create_connection()
        cursor = connection.cursor()

        # Проверяем, существует ли такой код
        cursor.execute("SELECT * FROM employees WHERE unique_code = ?", (entered_code,))
        result = cursor.fetchone()

        if result:
            # Успешный вход
            update.message.reply_text(f"Привет, {result[1]}! Ты успешно вошел. Можешь начать смену.")

            # Отправляем случайную картинку с собачкой
            random_dog_image_url = "https://random.dog/woof.json"
            response = requests.get(random_dog_image_url)
            if response.status_code == 200:
                dog_data = response.json()
                image_url = dog_data.get("url")
                update.message.reply_photo(photo=image_url)

            context.user_data["is_logging_in"] = False
        else:
            # Если код неверный
            update.message.reply_text("Неверный код! Попробуй снова.")

        connection.close()

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Хендлеры для команд
    dispatcher.add_handler(CommandHandler('start', start))

    # Хендлер для сообщений (регистрация и вход)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
