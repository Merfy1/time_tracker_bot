import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ID администратора (тот, кто будет получать уведомления)
ADMIN_ID = os.getenv("ADMIN_ID")