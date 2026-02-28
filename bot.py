# bot.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config.settings import get_settings
from database.db import Database
from utils.scheduler import ReminderScheduler
from keyboards.main import subscription_kb
from handlers import user, admin, callbacks, admin_slots

settings = get_settings()

# Настройка логирования
log_file = os.path.join(os.path.dirname(__file__), "bot.log")

# Очищаем все handlers
logging.getLogger().handlers = []

file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

logging.getLogger().addHandler(file_handler)
logging.getLogger().addHandler(console_handler)
logging.getLogger().setLevel(logging.INFO)

async def main():
    bot = Bot(token=settings["BOT_TOKEN"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    db = Database(settings["DB_PATH"])
    await db.init()

    scheduler = ReminderScheduler(bot, db)
    await scheduler.start()

    # Middleware для проверки подписки и инъекции зависимостей
    @dp.update.outer_middleware
    async def middleware_handler(handler, event, data):
        data["db"] = db
        data["scheduler"] = scheduler
        data["bot"] = bot  # Добавляем bot в data

        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        
        # Пропускаем админов
        if user_id in settings["ADMIN_IDS"]:
            return await handler(event, data)
        
        # Пропускаем проверку подписки и ЧС для некоторых команд
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
        
        # Проверка на ЧС
        if user_id:
            blacklisted = await db.is_blacklisted(user_id)
            if blacklisted:
                # Блокируем всё кроме /start и /help
                if isinstance(event, types.Message):
                    if event.text in ["/start", "/help"]:
                        return await handler(event, data)
                    # Игнорируем все остальные сообщения
                    return
                elif isinstance(event, types.CallbackQuery):
                    # Блокируем все callback кроме check_sub
                    if event.data == "check_sub":
                        return await handler(event, data)
                    # Игнорируем
                    return

        # Проверка подписки
        if settings["CHANNEL_ID"]:
            try:
                member = await bot.get_chat_member(settings["CHANNEL_ID"], user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    kb = subscription_kb()
                    text = "🔔 <b>Для записи подпишитесь на канал</b>\n\nНажмите кнопку ниже:"
                    if isinstance(event, types.Message):
                        await event.answer(text, reply_markup=kb, parse_mode="HTML")
                        return
                    elif isinstance(event, types.CallbackQuery):
                        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
                        return
            except Exception as e:
                logging.warning(f"Subscription check error: {e}")
                kb = subscription_kb()
                text = "🔔 <b>Для записи подпишитесь на канал</b>\n\nНажмите кнопку ниже:"
                if isinstance(event, types.Message):
                    await event.answer(text, reply_markup=kb, parse_mode="HTML")
                    return
                elif isinstance(event, types.CallbackQuery):
                    await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
                    return

        return await handler(event, data)

    dp.include_router(user.router)
    dp.include_router(admin.router)
    dp.include_router(callbacks.router)
    dp.include_router(admin_slots.router)

    logging.info("🚀 BeautyBot Lite запущен!")
    await dp.start_polling(bot)

    scheduler.shutdown()
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Остановлен")
