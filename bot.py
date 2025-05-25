import logging
from telegram import ParseMode
import random
import os
from config import ADMIN_ID
import requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import TELEGRAM_TOKEN
from database import create_connection
from dotenv import load_dotenv
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)


def get_random_image(query="office work team coffee"):
    access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": query,
        "client_id": access_key,
        "orientation": "landscape"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data['urls']['regular']
    except Exception as e:
        logger.error(f"Ошибка при получении изображения: {e}")
        return None

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    logger.info(f"Пользователь {user.first_name} ({chat_id}) запустил бота.")
    buttons = [[KeyboardButton("✅ Регистрация")], [KeyboardButton("🔑 Войти")]]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(f"Привет, {user.first_name}! Выбери действие:", reply_markup=reply_markup)

def send_shift_status(update, context):
    employee_id = context.user_data.get("employee_id")
    connection = create_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT id, start_time FROM shifts WHERE employee_id = ? AND end_time IS NULL", (employee_id,))
        shift = cursor.fetchone()
        if not shift:
            update.message.reply_text("У тебя сейчас нет активной смены.")
            return

        shift_id, start_time_str = shift
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        duration = int((now - start_time).total_seconds() / 60)

        cursor.execute("SELECT COUNT(*) FROM breaks WHERE shift_id = ? AND end_time IS NOT NULL", (shift_id,))
        break_count = cursor.fetchone()[0]

        message = (
            f"🕓 Смена началась: {start_time.strftime('%H:%M:%S')}\n"
            f"⏱ Длительность: {duration} мин\n"
            f"☕ Завершённых перерывов: {break_count}"
        )

        buttons = [
            [KeyboardButton("🔁 Закончить перерыв")] if context.user_data.get("on_break") else [KeyboardButton("☕ Начать перерыв")],
            [KeyboardButton("🔄 Обновить смену"), KeyboardButton("🔚 Закончить смену")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        update.message.reply_text(message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при получении статуса смены: {e}")
        update.message.reply_text("Не удалось получить данные смены.")
    finally:
        connection.close()

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
            update.message.reply_text(f"Регистрация завершена! Твой код:\n`{unique_code}`", parse_mode=ParseMode.MARKDOWN)
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
                image_url = get_random_image("office discipline")
                if image_url:
                    update.message.reply_photo(photo=image_url)
                logger.info(f"Пользователь {result[1]} вошел в систему (Код: {entered_code})")
                context.user_data["employee_id"] = result[0]
                context.user_data["is_logging_in"] = False  # Убираем только при успешном входе

                buttons = [
                    [KeyboardButton("🔛 Начать смену"), KeyboardButton("📜 История смен")]
                ]
                reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
                update.message.reply_text("Нажми кнопку ниже, чтобы начать смену.", reply_markup=reply_markup)
            else:
                update.message.reply_text("❌ Неверный код! Попробуй снова:")
                logger.warning(f"Неудачная попытка входа с кодом: {entered_code}")
        except Exception as e:
            logger.error(f"Ошибка при входе: {e}")
            update.message.reply_text("Ошибка входа. Попробуй позже.")
        finally:
            connection.close()
        return


    # В блоке "🔛 Начать смену":
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
                send_shift_status(update, context)  # Покажем текущую смену, если уже активна
                return

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO shifts (employee_id, start_time) VALUES (?, ?)", (employee_id, now))
            connection.commit()

            # Получаем имя сотрудника для сообщения админу
            cursor.execute("SELECT full_name FROM employees WHERE id = ?", (employee_id,))
            full_name = cursor.fetchone()[0]

            update.message.reply_text("Смена началась!")
            logger.info(f"Смена начата для сотрудника {employee_id}")

            # Уведомление админу
            context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=f"🔔 Сотрудник {full_name} начал смену."
            )

            # Отображаем статус смены и нужные кнопки
            send_shift_status(update, context)

        except Exception as e:
            logger.error(f"Ошибка при начале смены: {e}")
            update.message.reply_text("Не удалось начать смену.")
        finally:
            connection.close()
        return
    if text == "🔄 Обновить смену":
        send_shift_status(update, context)
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
        image_url = get_random_image("coffee break")
        if image_url:
            update.message.reply_photo(photo=image_url)
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

            # Сохраняем перерыв
            cursor.execute("UPDATE breaks SET end_time = ?, delay_minutes = ? WHERE id = ?",
                        (end_time.strftime("%Y-%m-%d %H:%M:%S"), duration, break_id))
            connection.commit()

            # Проверка на превышение 15 минут
            exceed = max(0, duration - 15)
            amount = exceed * 10  # 10 руб/минута

            if exceed > 0:
                # Получаем имя сотрудника и Telegram ID
                cursor.execute("SELECT full_name, telegram_id FROM employees WHERE id = ?", (employee_id,))
                emp_data = cursor.fetchone()
                full_name, employee_telegram = emp_data if emp_data else ("<Неизвестный>", None)

                # Добавляем штраф
                cursor.execute("""
                    INSERT INTO penalties (employee_id, shift_id, amount, reason)
                    VALUES (?, ?, ?, ?)
                """, (employee_id, shift_id, amount, f"Перерыв превышен на {exceed} минут"))
                connection.commit()

                # Уведомление сотруднику
                if employee_telegram:
                    context.bot.send_message(
                        chat_id=employee_telegram,
                        text=f"⚠️ Перерыв превышен на {exceed} мин.\nШтраф: {amount} руб"
                    )

                # Уведомление админу
                context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📣 Сотрудник {full_name} превысил перерыв на {exceed} мин.\nШтраф: {amount} руб"
                )

            # Ответ сотруднику
            if exceed > 0:
                update.message.reply_text(
                    f"Перерыв завершён.\nДлительность: {duration} мин.\n⚠️ Превышено: {exceed} мин\n💸 Штраф: {amount} руб"
                )
            else:
                update.message.reply_text(f"Перерыв завершён. Длительность: {duration} мин.")

            logger.info(f"Перерыв завершен для смены {shift_id}, длительность: {duration} мин.")

            # Кнопки после завершения перерыва
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
            cursor.execute("SELECT full_name FROM employees WHERE id = ?", (employee_id,))
            full_name = cursor.fetchone()[0]

            context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=f"🔔 Сотрудник {full_name} завершил смену."
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
