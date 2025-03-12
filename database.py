import sqlite3

DB_NAME = 'time_tracking.db'

def create_connection():
    """Создает подключение к базе данных SQLite"""
    return sqlite3.connect(DB_NAME)

def create_tables():
    """Создает таблицы в базе данных, если они не существуют"""
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        unique_code TEXT NOT NULL UNIQUE,
                        telegram_id INTEGER UNIQUE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS shifts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id INTEGER,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        total_break_delay INTEGER DEFAULT 0,
                        FOREIGN KEY (employee_id) REFERENCES employees (id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS breaks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        shift_id INTEGER,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP,
                        delay_minutes INTEGER DEFAULT 0,
                        FOREIGN KEY (shift_id) REFERENCES shifts (id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS penalties (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id INTEGER,
                        shift_id INTEGER,
                        amount INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES employees (id),
                        FOREIGN KEY (shift_id) REFERENCES shifts (id))''')

    connection.commit()
    connection.close()

# Вызовем создание таблиц при старте
if __name__ == "__main__":
    create_tables()
