# middlewares/subscription.py
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config.settings import get_settings
from keyboards.main import subscription_kb

settings = get_settings()


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        if user_id in settings["ADMIN_IDS"]:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        bot = data.get("bot")
        if bot and settings["CHANNEL_ID"]:
            try:
                member = await bot.get_chat_member(settings["CHANNEL_ID"], user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    await self._ask_sub(event)
                    return
            except:
                await self._ask_sub(event)
                return
        return await handler(event, data)

    async def _ask_sub(self, event):
        kb = subscription_kb()
        text = "🔔 <b>Для записи подпишитесь на канал</b>\n\nНажмите кнопку ниже:"
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
