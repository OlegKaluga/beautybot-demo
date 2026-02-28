# handlers/admin_slots.py
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import get_settings
from database.db import Database
import aiosqlite

router = Router()
settings = get_settings()

def is_admin(uid: int):
    return uid in settings["ADMIN_IDS"]


@router.callback_query(F.data.startswith("slots:"))
async def open_slots(cb: types.CallbackQuery, db: Database):
    """Открыть слоты по дате и залу"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    # slots:DATE:HALL_ID
    parts = cb.data.split(":")
    date = parts[1]
    hall_id = int(parts[2])
    
    hall_name = await db.get_hall_name(hall_id)
    slots = await db.get_available_slots(date, hall_id)
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    
    # Получаем записи
    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute(
            "SELECT time, name FROM bookings WHERE date = ? AND hall_id = ?",
            (date, hall_id)
        )
        bookings = {r[0]: r[1] for r in await cursor.fetchall()}
    
    kb = []
    for t in all_slots:
        if t in bookings:
            # Занято - показываем имя
            kb.append([InlineKeyboardButton(
                text=f"❌ {t} {bookings[t]}",
                callback_data=f"view:{date}:{all_slots.index(t)}:{hall_id}"
            )])
        elif t in slots:
            # Свободно
            kb.append([InlineKeyboardButton(
                text=f"✅ {t}",
                callback_data=f"toggle:{date}:{all_slots.index(t)}:{hall_id}"
            )])
        else:
            # Удалён
            kb.append([InlineKeyboardButton(
                text=f"⬜ {t}",
                callback_data=f"toggle:{date}:{all_slots.index(t)}:{hall_id}"
            )])
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"hall:{hall_id}")])
    
    await cb.message.edit_text(
        f"⏰ {date}\n{hall_name} зал\n\n✅ свободно | ❌ занято | ⬜ удалён",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@router.callback_query(F.data.startswith("toggle:"))
async def toggle_slot(cb: types.CallbackQuery, db: Database):
    """Переключить слот"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐", show_alert=True)
        return
    
    # toggle:DATE:TIME_IDX:HALL
    parts = cb.data.split(":")
    date = parts[1]
    time_idx = int(parts[2])
    hall_id = int(parts[3])
    
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    time = all_slots[time_idx]
    
    available = await db.get_available_slots(date, hall_id)
    if time in available:
        await db.remove_time_slot(date, time, hall_id)
    else:
        await db.add_time_slot(date, time, hall_id)
    
    # Перерисовываем
    await open_slots(cb, db)


@router.callback_query(F.data.startswith("aban:"))
async def ban_from_slot(cb: types.CallbackQuery, db: Database):
    """Забанить клиента из записи"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐", show_alert=True)
        return
    
    _, bid, user_id = cb.data.split(":")
    user_id = int(user_id)
    
    await db.add_to_blacklist(user_id, "Проблемный клиент")
    await db.cancel_booking(int(bid))
    
    # Отвечаем на callback
    await cb.answer(f"✅ Забанен", show_alert=True)
    
    # Отправляем сообщение с кнопкой разбана
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban_now:{user_id}")]
    ])
    
    await cb.message.answer(
        f"✅ Забанен: {user_id}\nНажми Разбанить",
        reply_markup=kb
    )


@router.callback_query(F.data == "slots_menu")
async def slots_menu(cb: types.CallbackQuery):
    """Вернуться к меню слотов"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐", show_alert=True)
        return
    
    await cb.answer("Выберите зал в меню", show_alert=True)


@router.callback_query(F.data.startswith("unban_now:"))
async def unban_now(cb: types.CallbackQuery, db: Database):
    """Разбанить клиента сразу после бана"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐", show_alert=True)
        return
    
    user_id = int(cb.data.split(":")[1])
    
    await db.remove_from_blacklist(user_id)
    
    await cb.answer(f"✅ {user_id} разблокирован", show_alert=True)
    
    await cb.message.edit_text(
        f"✅ Клиент разблокирован!\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Теперь может записываться снова",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("view:"))
async def view_booking(cb: types.CallbackQuery, db: Database):
    """Просмотр записи"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐", show_alert=True)
        return
    
    # view:DATE:TIME_IDX:HALL
    parts = cb.data.split(":")
    date = parts[1]
    time_idx = int(parts[2])
    hall_id = int(parts[3])
    
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    time = all_slots[time_idx]
    hall_name = await db.get_hall_name(hall_id)
    
    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute(
            "SELECT id, user_id, name, phone, service_name FROM bookings WHERE date = ? AND time = ? AND hall_id = ?",
            (date, time, hall_id)
        )
        booking = await cursor.fetchone()
    
    if not booking:
        await cb.answer("ℹ️ Нет записи", show_alert=True)
        return
    
    bid, user_id, name, phone, service = booking
    
    # Проверяем, в ЧС ли клиент
    blacklisted = await db.is_blacklisted(user_id)
    
    text = f"📋 {date} {time}\n{hall_name}\n{service}\n\n"
    text += f"👤 {name}\n📱 {phone}\n🆔 {user_id}\n\n"
    if blacklisted:
        text += f"⛔ <b>В ЧЁРНОМ СПИСКЕ</b>\nПричина: {blacklisted}"
    
    # Кнопки
    kb_buttons = []
    
    if blacklisted:
        # Если в ЧС — показываем кнопку разбана
        kb_buttons.append([
            InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban_now:{user_id}")
        ])
    else:
        # Если не в ЧС — показываем кнопку бана
        kb_buttons.append([
            InlineKeyboardButton(text="⛔ Забанить", callback_data=f"aban:{bid}:{user_id}")
        ])
    
    kb_buttons.append([
        InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"acancel:{bid}")
    ])
    kb_buttons.append([
        InlineKeyboardButton(text="🔙 Назад к слотам", callback_data=f"slots:{date}:{hall_id}")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
