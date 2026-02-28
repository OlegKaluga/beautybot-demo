# handlers/callbacks.py
from aiogram import Router, F, types
from config.settings import get_settings
from keyboards.main import subscription_kb, main_menu_kb

router = Router()
settings = get_settings()


@router.callback_query(F.data == "check_sub")
async def check_sub(cb: types.CallbackQuery):
    uid = cb.from_user.id
    try:
        member = await cb.bot.get_chat_member(settings["CHANNEL_ID"], uid)
        if member.status in ["member", "administrator", "creator"]:
            await cb.answer("✅ Подписка подтверждена!", show_alert=True)
            await cb.message.answer("✨ Теперь можно записываться:", reply_markup=main_menu_kb())
            return
    except:
        pass
    kb = subscription_kb()
    await cb.answer("❌ Вы не подписаны", show_alert=True)
    await cb.message.edit_text("🔔 Подпишитесь на канал:", reply_markup=kb)
