import random
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import TELEGRAM_TOKEN
from database import create_connection

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id

    buttons = [
        [KeyboardButton("Регистрация")],
        [KeyboardButton("Войти")],
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)

    update.message.reply_text(
        f"Привет, {user.first_name}! Ты можешь зарегистрироваться или войти.",
        reply_markup=reply_markup
    )

def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    text = update.message.text

    if text == "Регистрация":
        update.message.reply_text("Введите ваше ФИО для регистрации:")
        context.user_data["is_registering"] = True
        return

    if context.user_data.get("is_registering"):
        full_name = update.message.text
        unique_code = f"CODE-{random.randint(1000, 9999)}"

        connection = create_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM employees WHERE full_name = ?", (full_name,))
        result = cursor.fetchone()

        if result:
            update.message.reply_text("Пользователь с таким ФИО уже существует. Введите другое ФИО.")
        else:
            cursor.execute("INSERT INTO employees (full_name, unique_code) VALUES (?, ?)",
                           (full_name, unique_code))
            connection.commit()

            update.message.reply_text(f"Регистрация завершена! Ваш уникальный код: {unique_code}")

            context.user_data["is_registering"] = False

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

    if text == "Войти":
        update.message.reply_text("Введите ваш уникальный код для входа:")
        context.user_data["is_logging_in"] = True
        return

    if context.user_data.get("is_logging_in"):
        entered_code = update.message.text
        connection = create_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM employees WHERE unique_code = ?", (entered_code,))
        result = cursor.fetchone()

        if result:
            update.message.reply_text(f"Привет, {result[1]}! Ты успешно вошел. Можешь начать смену.")

            random_dog_image_url = "https://random.dog/woof.json"
            response = requests.get(random_dog_image_url)
            if response.status_code == 200:
                dog_data = response.json()
                image_url = dog_data.get("url")
                update.message.reply_photo(photo=image_url)

            context.user_data["is_logging_in"] = False
        else:
            update.message.reply_text("Неверный код! Попробуй снова.")

        connection.close()

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
