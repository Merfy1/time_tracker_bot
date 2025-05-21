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

def get_random_image():
    dog_api = "https://random.dog/woof.json"
    cat_api = "https://api.thecatapi.com/v1/images/search"
    try:
        response = requests.get(dog_api, timeout=5)
        if response.status_code == 200:
            image_url = response.json().get("url")
            if image_url:
                return image_url
    except Exception as e:
        logger.error(f"Ошибка с API собак: {e}")
    try:
        response = requests.get(cat_api, timeout=5)
        if response.status_code == 200:
            image_url = response.json()[0].get("url")
            if image_url:
                return image_url
    except Exception as e:
        logger.error(f"Ошибка с API котов: {e}")
    return "https://placekitten.com/400/400"

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info(f"Пользователь {user.first_name} ({chat_id}) запустил бота.")
    buttons = [[KeyboardButton("✅ Регистрация")], [KeyboardButton("🔑 Войти")]]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(f"Привет, {user.first_name}! Выбери действие:", reply_markup=reply_markup)

def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    text = update.message.text

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
                update.message.reply_text("Пользователь с таким ФИО уже существует!")
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
                image_url = get_random_image()
                update.message.reply_photo(photo=image_url)
                logger.info(f"Пользователь {result[1]} вошел в систему (Код: {entered_code})")
                context.user_data["employee_id"] = result[0]
                buttons = [
                    [KeyboardButton("🔛 Начать смену"), KeyboardButton("📜 История смен")]
                ]
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

    if text == "🔛 Начать смену":
        employee_id = context.user_data.get("employee_id")
        if not employee_id:
            update.message.reply_text("Сначала нужно войти.")
            return
        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT * FROM shifts WHERE employee_id = ? AND end_time IS NULL", (employee_id,))
            if cursor.fetchone():
                update.message.reply_text("Ты уже на смене.")
                return
            cursor.execute("INSERT INTO shifts (employee_id, start_time) VALUES (?, ?)",
                           (employee_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            connection.commit()
            update.message.reply_text("Смена началась!")
            logger.info(f"Смена начата для сотрудника {employee_id}")

            # Кнопки при начале смены
            buttons = [
                [KeyboardButton("☕ Начать перерыв")],
                [KeyboardButton("🔚 Закончить смену")],
                [KeyboardButton("📜 История смен")]
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Выбери действие:", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при начале смены: {e}")
            update.message.reply_text("Не удалось начать смену.")
        finally:
            connection.close()
        return
    if text == "📜 История смен":
        employee_id = context.user_data.get("employee_id")
        if not employee_id:
            update.message.reply_text("Сначала нужно войти.")
            return
        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT start_time, end_time, total_break_delay 
                FROM shifts 
                WHERE employee_id = ? AND end_time IS NOT NULL
                ORDER BY start_time DESC
            """, (employee_id,))
            shifts = cursor.fetchall()
            if not shifts:
                update.message.reply_text("История смен пустая.")
                return

            total_earnings = 0
            message_lines = ["📜 *История смен:*"]
            for start_str, end_str, break_delay in shifts:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                duration = int((end_dt - start_dt).total_seconds() / 60)  # мин
                break_delay = break_delay or 0
                salary = (duration - break_delay) * 2
                total_earnings += salary
                message_lines.append(f"🕒 {start_dt.strftime('%d.%m.%Y %H:%M')} - {end_dt.strftime('%H:%M')}, "
                                     f"Длительность: {duration} мин, Перерывы: {break_delay} мин, Заработано: {salary} руб")

            message_lines.append(f"\n💰 *Всего заработано:* {total_earnings} руб")
            update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка при выводе истории смен: {e}")
            update.message.reply_text("Не удалось получить историю смен.")
        finally:
            connection.close()
        return

    if text == "☕ Начать перерыв":
        employee_id = context.user_data.get("employee_id")
        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id FROM shifts WHERE employee_id = ? AND end_time IS NULL", (employee_id,))
            shift = cursor.fetchone()
            if not shift:
                update.message.reply_text("Сначала начни смену.")
                return
            shift_id = shift[0]

            cursor.execute("SELECT * FROM breaks WHERE shift_id = ? AND end_time IS NULL", (shift_id,))
            if cursor.fetchone():
                update.message.reply_text("У тебя уже идёт перерыв.")
                return
            
            cursor.execute("INSERT INTO breaks (shift_id, start_time) VALUES (?, ?)",
                           (shift_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            connection.commit()
            update.message.reply_text("Перерыв начался!")
            logger.info(f"Перерыв начат для смены {shift_id}")

            # Показать кнопку "Закончить перерыв"
            buttons = [[KeyboardButton("🔁 Закончить перерыв")]]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Выбери действие:", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка начала перерыва: {e}")
            update.message.reply_text("Не удалось начать перерыв.")
        finally:
            connection.close()

    if text == "🔁 Закончить перерыв":
        employee_id = context.user_data.get("employee_id")
        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id FROM shifts WHERE employee_id = ? AND end_time IS NULL", (employee_id,))
            shift = cursor.fetchone()
            if not shift:
                update.message.reply_text("Сначала начни смену.")
                return
            shift_id = shift[0]

            cursor.execute("SELECT id, start_time FROM breaks WHERE shift_id = ? AND end_time IS NULL", (shift_id,))
            brk = cursor.fetchone()
            if not brk:
                update.message.reply_text("Активный перерыв не найден.")
                return
            break_id, start_time_str = brk
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds() / 60)

            cursor.execute("UPDATE breaks SET end_time = ?, delay_minutes = ? WHERE id = ?",
                           (end_time.strftime("%Y-%m-%d %H:%M:%S"), duration, break_id))
            connection.commit()
            update.message.reply_text(f"Перерыв завершён. Длительность: {duration} мин.")
            logger.info(f"Перерыв завершен для смены {shift_id}, длительность: {duration} мин.")

            # После окончания перерыва вернуть кнопки смены
            buttons = [
                [KeyboardButton("☕ Начать перерыв")],
                [KeyboardButton("🔚 Закончить смену")]
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Выбери действие:", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка окончания перерыва: {e}")
            update.message.reply_text("Не удалось закончить перерыв.")
        finally:
            connection.close()

    if text == "🔚 Закончить смену":
        employee_id = context.user_data.get("employee_id")
        if not employee_id:
            update.message.reply_text("Сначала нужно войти.")
            return
        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id, start_time FROM shifts WHERE employee_id = ? AND end_time IS NULL", (employee_id,))
            shift = cursor.fetchone()
            if not shift:
                update.message.reply_text("Активная смена не найдена.")
                return
            shift_id, start_time_str = shift
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.now()
            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            cursor.execute("SELECT SUM(delay_minutes) FROM breaks WHERE shift_id = ?", (shift_id,))
            total_break_delay = cursor.fetchone()[0] or 0
            salary = (duration_minutes - total_break_delay) * 2
            cursor.execute("UPDATE shifts SET end_time = ?, total_break_delay = ? WHERE id = ?",
                           (end_time.strftime("%Y-%m-%d %H:%M:%S"), total_break_delay, shift_id))
            connection.commit()
            update.message.reply_text(
                f"✅ Смена завершена.\n"
                f"🕒 Время на смене: {duration_minutes} мин\n"
                f"🧘 Перерывы: {total_break_delay} мин\n"
                f"💰 Заработано: {salary} руб"
            )
            buttons = [
                [KeyboardButton("🔛 Начать смену")],
                [KeyboardButton("📜 История смен")]
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            update.message.reply_text("Готов снова начать — нажми кнопку ниже.", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Ошибка при завершении смены: {e}")
            update.message.reply_text("Не удалось завершить смену.")
        finally:
            connection.close()
        return

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
