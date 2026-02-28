# config/settings.py
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@lru_cache()
def get_settings():
    return {
        # Bot
        "BOT_TOKEN": os.getenv("BOT_TOKEN", ""),
        "ADMIN_IDS": list(map(int, os.getenv("ADMIN_IDS", "0").split(","))),

        # Branding (white-label)
        "SALON_NAME": os.getenv("SALON_NAME", "Салон красоты"),
        "SALON_LOGO": os.getenv("SALON_LOGO", ""),
        "PRIMARY_COLOR": os.getenv("PRIMARY_COLOR", "#FF6B9D"),
        "WELCOME_TEXT": os.getenv("WELCOME_TEXT", "Добро пожаловать в {salon_name}! ✨"),

        # Channel
        "CHANNEL_ID": os.getenv("CHANNEL_ID", ""),
        "CHANNEL_LINK": os.getenv("CHANNEL_LINK", ""),

        # Database
        "DB_PATH": os.getenv("DB_PATH", "nail_bot.db"),

        # Time
        "TIMEZONE": os.getenv("TIMEZONE", "Europe/Moscow"),

        # Reminders
        "REMINDER_TEXT": os.getenv("REMINDER_TEXT", "Напоминаем о записи на {service} завтра в {time}!"),
    }
