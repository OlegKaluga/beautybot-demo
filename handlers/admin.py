# handlers/admin.py
from aiogram import Router, F, types
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import get_settings
from database.db import Database
from keyboards.main import admin_menu_kb, main_menu_kb
from keyboards.booking import calendar_kb, slots_kb, add_day_calendar_kb
from datetime import datetime
import logging
import aiosqlite

logger = logging.getLogger(__name__)

router = Router()
settings = get_settings()


def is_admin(uid: int):
    return uid in settings["ADMIN_IDS"]


class AdminFSM(StatesGroup):
    add_day = State()
    close_day = State()
    manage_slot = State()
    select_hall = State()
    message_select_date = State()
    message_select_client = State()
    message_write = State()
    review_write = State()
    add_day_calendar = State()


@router.message(Command("admin"))
async def admin_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("🔐 Доступ запрещён.")
        return
    await msg.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.message(F.text == "🔙 В меню")
async def admin_to_user(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("✅ Возврат в меню:", reply_markup=main_menu_kb())


@router.message(F.text == "➕ Добавить день")
async def admin_add_day(msg: types.Message, state: FSMContext, db: Database):
    if not is_admin(msg.from_user.id):
        return
    
    # Получаем уже добавленные даты
    working_days = await db.get_working_days(days_ahead=60)
    
    await state.set_state(AdminFSM.add_day_calendar)
    await state.update_data(selected_dates=working_days)
    
    await msg.answer(
        "📅 <b>Выберите даты для добавления</b>\n\n"
        "Нажмите на дату, чтобы добавить/удалить:\n"
        "✅ — уже добавлено\n"
        "🔵 — сегодня\n"
        "⬜ — не добавлено\n\n"
        "Или используйте кнопки:",
        reply_markup=add_day_calendar_kb(working_days),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("addday:"))
async def admin_toggle_add_day(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    date = cb.data.split(":")[1]

    working_days = await db.get_working_days(days_ahead=60)

    if date in working_days:
        # Удаляем дату полностью
        await db.remove_working_day(date)
        await cb.answer(f"❌ {date} удалён", show_alert=True)
    else:
        # Добавляем дату
        await db.add_working_day(date)
        await cb.answer(f"✅ {date} добавлен", show_alert=True)

    # Обновляем календарь
    working_days = await db.get_working_days(days_ahead=60)
    await state.update_data(selected_dates=working_days)

    # Получаем текущий отображаемый месяц из состояния
    data = await state.get_data()
    year = data.get("calendar_year", datetime.now().year)
    month = data.get("calendar_month", datetime.now().month)

    await cb.message.edit_text(
        "📅 <b>Выберите даты для добавления</b>\n\n"
        "Нажмите на дату, чтобы добавить/удалить:",
        reply_markup=add_day_calendar_kb(working_days, year, month),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("prev_month:"))
async def admin_prev_month(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    _, year, month = cb.data.split(":")
    year = int(year)
    month = int(month)

    # Переходим на предыдущий месяц
    month -= 1
    if month == 0:
        month = 12
        year -= 1

    await state.update_data(calendar_year=year, calendar_month=month)

    working_days = await db.get_working_days(days_ahead=365)
    await state.update_data(selected_dates=working_days)

    await cb.message.edit_text(
        f"📅 <b>Выберите даты для добавления</b>\n\n"
        f"Нажмите на дату, чтобы добавить/удалить:",
        reply_markup=add_day_calendar_kb(working_days, year, month),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("next_month:"))
async def admin_next_month(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    _, year, month = cb.data.split(":")
    year = int(year)
    month = int(month)

    # Переходим на следующий месяц
    month += 1
    if month == 13:
        month = 1
        year += 1

    await state.update_data(calendar_year=year, calendar_month=month)

    working_days = await db.get_working_days(days_ahead=365)
    await state.update_data(selected_dates=working_days)

    await cb.message.edit_text(
        f"📅 <b>Выберите даты для добавления</b>\n\n"
        f"Нажмите на дату, чтобы добавить/удалить:",
        reply_markup=add_day_calendar_kb(working_days, year, month),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "addall_days")
async def admin_add_all_days(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    # Добавляем 30 дней начиная с сегодня
    from datetime import timedelta
    today = datetime.now().date()
    added = []
    
    for i in range(30):
        date = (today + timedelta(days=i)).isoformat()
        working_days = await db.get_working_days(days_ahead=60)
        if date not in working_days:
            await db.add_working_day(date)
            added.append(date)
    
    working_days = await db.get_working_days(days_ahead=60)
    await state.update_data(selected_dates=working_days)
    
    await cb.message.edit_text(
        f"✅ <b>Добавлено {len(added)} дней</b>\n\n"
        f"Период: с {today} по {today + timedelta(days=29)}",
        reply_markup=add_day_calendar_kb(working_days),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "clear_days")
async def admin_clear_days(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    await cb.message.edit_text(
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Это удалит все рабочие дни и слоты!\n"
        "Все записи клиентов будут отменены!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Да, удалить всё", callback_data="confirm_clear_all")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_admin_menu")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm_clear_all")
async def admin_confirm_clear_all(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    # Получаем все даты
    working_days = await db.get_working_days(days_ahead=365)
    
    # Удаляем все записи и слоты
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute("DELETE FROM bookings")
        await conn.execute("DELETE FROM time_slots")
        await conn.execute("DELETE FROM working_days")
        await conn.commit()
    
    await cb.message.edit_text(
        "🗑 <b>Все данные очищены</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


@router.message(F.text == "❌ Закрыть день")
async def admin_close_day(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(AdminFSM.close_day)
    await msg.answer("📅 Дата для закрытия (ГГГГ-ММ-ДД):")


@router.message(AdminFSM.close_day)
async def admin_close_day_proc(msg: types.Message, state: FSMContext, db: Database):
    try:
        date = datetime.strptime(msg.text.strip(), "%Y-%m-%d").date().isoformat()
        await db.close_day(date, True)
        await msg.answer(f"✅ {date} закрыт.", reply_markup=admin_menu_kb())
    except:
        await msg.answer("❌ Формат: 2024-03-15")
        return
    await state.clear()


@router.message(F.text == "⏰ Слоты")
async def admin_slots(msg: types.Message, state: FSMContext, db: Database):
    if not is_admin(msg.from_user.id):
        return
    dates = await db.get_working_days(30)
    if not dates:
        await msg.answer("📭 Нет рабочих дней.", reply_markup=admin_menu_kb())
        return

    # Сначала выбор зала
    await state.set_state(AdminFSM.select_hall)
    halls = await db.get_halls()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"aslot_hall:{hid}")]
        for hid, name in halls
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])

    await msg.answer("🏛 <b>Выберите зал:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("aslot_hall:"))
async def admin_select_hall_for_slots(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    hall_id = int(cb.data.split(":")[1])
    hall_name = await db.get_hall_name(hall_id)

    # Получаем мастеров для этого зала
    masters = await db.get_masters_by_hall(hall_id)
    
    # Если мастер один — сразу показываем даты
    if len(masters) == 1:
        master_id, master_name = masters[0]
        dates = await db.get_working_days(30)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Su 1" if i == 0 else f"Mo 2" if i == 1 else d.split("-")[2],
                                  callback_data=f"slots:{d}:{master_id}")]
            for i, d in enumerate(dates[:14])
        ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_slots")]])

        await cb.message.edit_text(
            f"📅 <b>Выберите дату:</b>\n🏛 {hall_name}, 👤 {master_name}",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        # Если мастеров несколько — выбираем мастера
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=mname, callback_data=f"aslot_master:{mid}")]
            for mid, mname in masters
        ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_slots")]])

        await cb.message.edit_text(
            f"👤 <b>Выберите мастера:</b>\n🏛 {hall_name}",
            reply_markup=kb,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("aslot_master:"))
async def admin_select_master_for_slots(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    master_id = int(cb.data.split(":")[1])
    master_name = await db.get_master_name(master_id)

    dates = await db.get_working_days(30)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Su 1" if i == 0 else f"Mo 2" if i == 1 else d.split("-")[2],
                              callback_data=f"slots:{d}:{master_id}")]
        for i, d in enumerate(dates[:14])
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_slots")]])

    await cb.message.edit_text(
        f"📅 <b>Выберите дату:</b>\n👤 {master_name}",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("slots:"))
async def admin_view_slots(cb: types.CallbackQuery, db: Database):
    """Просмотр слотов для мастера"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    parts = cb.data.split(":")
    date = parts[1]
    master_id = int(parts[2])
    master_name = await db.get_master_name(master_id)

    slots = await db.get_available_slots(date, master_id)
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]

    # Получаем все записи на эту дату и мастера
    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute("""
            SELECT time, id, user_id, name, service_name
            FROM bookings
            WHERE date = ? AND master_id = ?
        """, (date, master_id))
        bookings = {r[0]: {"id": r[1], "user_id": r[2], "name": r[3], "service": r[4]} for r in await cursor.fetchall()}

    kb = []
    for t in all_slots:
        if t in bookings:
            # Есть запись — показываем кликабельным
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"❌ {t} ({bookings[t]['name']})",
                callback_data=f"aslot_report:{date}:{time_idx}:{master_id}"
            )])
        elif t in slots:
            # Свободный слот
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"✅ {t}",
                callback_data=f"aslot_toggle:{date}:{time_idx}:{master_id}"
            )])
        else:
            # Слот удалён
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"⬜ {t}",
                callback_data=f"aslot_toggle:{date}:{time_idx}:{master_id}"
            )])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_slots")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)

    await cb.message.edit_text(
        f"⏰ <b>Слоты на {date}</b>\n👤 {master_name}\n\n"
        f"✅ — свободно\n"
        f"❌ — занято (нажми чтобы посмотреть клиента)\n"
        f"⬜ — слот удалён (нажми чтобы добавить)\n\n"
        f"Всего: {len(slots)} из {len(all_slots)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("aslot_toggle:"))
async def admin_toggle_slot(cb: types.CallbackQuery, db: Database):
    """Переключение слота (добавить/удалить)"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    # Формат: aslot_toggle:DATE:TIME_IDX_MASTERID
    parts = cb.data.split(":", 3)
    date = parts[1]
    time_idx_master = parts[3]
    
    # Разбираем time_idx и master_id
    time_idx = int(time_idx_master)
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    time = all_slots[time_idx]
    
    # Получаем master_id из состояния или из callback
    # Для простоты - получаем из данных сообщения
    # На самом деле master_id нужно передавать в callback
    # Давайте переделаем формат: aslot_toggle:DATE:TIME_IDX:MASTER_ID
    
    # Парсим заново с правильным форматом
    parts = cb.data.split(":")
    date = parts[1]
    time_idx = int(parts[2])
    master_id = int(parts[3])
    
    time = all_slots[time_idx]
    master_name = await db.get_master_name(master_id)

    available = await db.get_available_slots(date, master_id)
    if time in available:
        await db.remove_time_slot(date, time, master_id)
        await cb.answer(f"🗑 {time} удалён", show_alert=True)
    else:
        await db.add_time_slot(date, time, master_id)
        await cb.answer(f"✅ {time} добавлен", show_alert=True)

    # Обновляем клавиатуру
    slots = await db.get_available_slots(date, master_id)

    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute("""
            SELECT time, id, user_id, name, service_name
            FROM bookings
            WHERE date = ? AND master_id = ?
        """, (date, master_id))
        bookings = {r[0]: {"id": r[1], "user_id": r[2], "name": r[3], "service": r[4]} for r in await cursor.fetchall()}

    kb = []
    for t in all_slots:
        if t in bookings:
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"❌ {t} ({bookings[t]['name']})",
                callback_data=f"aslot_report:{date}:{time_idx}:{master_id}"
            )])
        elif t in slots:
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"✅ {t}",
                callback_data=f"aslot_toggle:{date}:{time_idx}:{master_id}"
            )])
        else:
            time_idx = all_slots.index(t)
            kb.append([InlineKeyboardButton(
                text=f"⬜ {t}",
                callback_data=f"aslot_toggle:{date}:{time_idx}:{master_id}"
            )])

    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_slots")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)

    await cb.message.edit_text(
        f"⏰ <b>Слоты на {date}</b>\n👤 {master_name}\n\n"
        f"✅ — свободно\n"
        f"❌ — занято (нажми чтобы посмотреть клиента)\n"
        f"⬜ — слот удалён (нажми чтобы добавить)\n\n"
        f"Всего: {len(slots)} из {len(all_slots)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("aslot_report:"))
async def admin_slot_report(cb: types.CallbackQuery, db: Database):
    """Показать информацию о записи в слоте"""
    import logging
    logging.info(f"aslot_report callback: {cb.data}")

    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    # Формат: aslot_report:DATE:TIME_IDX:MASTER_ID
    parts = cb.data.split(":")
    if len(parts) < 4:
        logging.error(f"Неверный формат callback: {cb.data}")
        await cb.answer("❌ Ошибка формата", show_alert=True)
        return

    date = parts[1]
    time_idx = int(parts[2])
    master_id = int(parts[3])
    
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    time = all_slots[time_idx]

    logging.info(f"Date: {date}, Time: {time}, Master: {master_id}")

    master_name = await db.get_master_name(master_id)

    # Ищем запись в этом слоте
    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute("""
            SELECT id, user_id, name, phone, service_name, hall_id
            FROM bookings
            WHERE date = ? AND time = ? AND master_id = ?
        """, (date, time, master_id))
        booking = await cursor.fetchone()

    logging.info(f"Booking: {booking}")

    if not booking:
        await cb.answer("ℹ️ Нет записи на это время", show_alert=True)
        return

    bid, user_id, name, phone, service, hall_id = booking
    hall_name = await db.get_hall_name(hall_id)

    text = f"📋 <b>Запись на {date} {time}</b>\n"
    text += f"🏛 {hall_name}\n"
    text += f"👤 {master_name}\n"
    text += f"💇 {service}\n\n"
    text += f"👤 <b>Клиент:</b> {name}\n"
    text += f"📱 <code>{phone}</code>\n"
    text += f"🆔 <code>{user_id}</code>\n\n"
    text += f"<b>Действия:</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ Забанить", callback_data=f"aban:{bid}:{user_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"acancel:{bid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"slots:{date}:{master_id}")]
    ])

    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("aban:"))
async def admin_ban_from_slot(cb: types.CallbackQuery, db: Database):
    """Забанить клиента из записи"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    _, bid, user_id = cb.data.split(":")
    user_id = int(user_id)
    
    await db.add_to_blacklist(user_id, "Проблемный клиент (отмечен админом)")
    
    # Отменяем запись
    await db.cancel_booking(int(bid))
    
    await cb.answer(f"✅ Пользователь {user_id} добавлен в ЧС", show_alert=True)
    
    # Возвращаемся к слотам
    await cb.message.edit_text(
        f"✅ Клиент забанен и запись отменена\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Причина: Проблемный клиент",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_admin_slots")
async def admin_back_to_slots(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    halls = await db.get_halls()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"aslot_hall:{hid}")]
        for hid, name in halls
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])

    await cb.message.edit_text("🏛 <b>Выберите зал:</b>", reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "📋 Записи")
async def admin_bookings(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        return
    dates = await db.get_working_days(30)
    # Используем отдельный callback для записей
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Su 1" if i == 0 else f"Mo 2" if i == 1 else d.split("-")[2], 
                              callback_data=f"abook_date:{d}")]
        for i, d in enumerate(dates[:14])
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])
    await msg.answer("📅 <b>Выберите дату:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("abook_date:"))
async def admin_show_bookings(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    date = cb.data.split(":")[1]
    bookings = await db.get_bookings_for_date(date)
    if not bookings:
        await cb.answer("📭 Нет записей", show_alert=True)
        return

    text = f"📋 <b>{date}</b>:\n\n"
    for b in bookings:
        hall_name = await db.get_hall_name(b['hall_id'])
        master_name = await db.get_master_name(b['master_id'])
        text += f"⏰ {b['time']} | {hall_name} | {master_name}\n"
        text += f"   {b['name']} — {b['service']}\n"
        text += f"   📱 {b['phone']}\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ {b['time']}", callback_data=f"acancel:{b['id']}")]
        for b in bookings
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_bookings")]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "back_admin_bookings")
async def admin_back_bookings(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    dates = await db.get_working_days(30)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Su 1" if i == 0 else f"Mo 2" if i == 1 else d.split("-")[2], 
                              callback_data=f"abook_date:{d}")]
        for i, d in enumerate(dates[:14])
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])
    
    await cb.message.edit_text("📅 <b>Выберите дату:</b>", reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "📊 Общий отчёт")
async def admin_report(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        return
    
    from datetime import datetime
    now = datetime.now()
    report = await db.get_monthly_report(now.year, now.month)  # Общий отчёт
    
    text = f"📊 <b>ОБЩИЙ ОТЧЁТ за {now.month:02d}.{now.year}</b>\n\n"
    
    for hall_name, data in report["halls"].items():
        text += f"<b>🏛 {hall_name} зал:</b>\n"
        for svc in data["services"]:
            text += f"  • {svc['service']}: {svc['count']} шт. = {svc['total']}₽\n"
        text += f"  <b>Итого: {data['hall_total']}₽</b>\n\n"
    
    text += f"<b>💰 ОБЩАЯ ВЫРУЧКА: {report['grand_total']}₽</b>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Пред. месяц", callback_data=f"report_prev:{now.year}:{now.month}:0")],
        [InlineKeyboardButton(text="➡️ След. месяц", callback_data=f"report_next:{now.year}:{now.month}:0")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])
    
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "✂️ Стрижки")
async def admin_report_hair(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        return

    from datetime import datetime
    now = datetime.now()
    report = await db.get_monthly_report(now.year, now.month, hall_id=1)  # Стрижки

    text = f"✂️ <b>СТРИЖКИ — отчёт за {now.month:02d}.{now.year}</b>\n\n"

    if not report["halls"]:
        text += "<i>Нет записей за этот месяц</i>"
    else:
        for hall_name, data in report["halls"].items():
            for svc in data["services"]:
                text += f"• {svc['service']}: {svc['count']} шт. = {svc['total']}₽\n"
            text += f"\n<b>💰 ВЫРУЧКА: {data['hall_total']}₽</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Пред. месяц", callback_data=f"report_prev:{now.year}:{now.month}:1")],
        [InlineKeyboardButton(text="➡️ След. месяц", callback_data=f"report_next:{now.year}:{now.month}:1")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])

    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "💅 Ногти")
async def admin_report_nails(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        return

    from datetime import datetime
    now = datetime.now()
    report = await db.get_monthly_report(now.year, now.month, hall_id=2)  # Ногти

    text = f"💅 <b>НОГТИ — отчёт за {now.month:02d}.{now.year}</b>\n\n"

    if not report["halls"]:
        text += "<i>Нет записей за этот месяц</i>"
    else:
        for hall_name, data in report["halls"].items():
            for svc in data["services"]:
                text += f"• {svc['service']}: {svc['count']} шт. = {svc['total']}₽\n"
            text += f"\n<b>💰 ВЫРУЧКА: {data['hall_total']}₽</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Пред. месяц", callback_data=f"report_prev:{now.year}:{now.month}:2")],
        [InlineKeyboardButton(text="➡️ След. месяц", callback_data=f"report_next:{now.year}:{now.month}:2")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])

    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("report_"))
async def admin_report_month(cb: types.CallbackQuery, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    action, year, month, hall = cb.data.split(":")
    year = int(year)
    month = int(month)
    hall = int(hall)

    if action == "report_prev":
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    else:  # report_next
        month += 1
        if month == 13:
            month = 1
            year += 1

    # hall=0 — общий, hall=1 — стрижки, hall=2 — ногти
    hall_id = hall if hall > 0 else None
    report = await db.get_monthly_report(year, month, hall_id)

    if hall == 0:
        title = f"📊 ОБЩИЙ ОТЧЁТ за {month:02d}.{year}"
    elif hall == 1:
        title = f"✂️ СТРИЖКИ — отчёт за {month:02d}.{year}"
    else:
        title = f"💅 НОГТИ — отчёт за {month:02d}.{year}"

    text = f"<b>{title}</b>\n\n"

    if not report["halls"]:
        text += "<i>Нет записей за этот месяц</i>"
    else:
        for hall_name, data in report["halls"].items():
            if hall == 0:  # В общем отчёте показываем название зала
                text += f"<b>🏛 {hall_name}:</b>\n"
            for svc in data["services"]:
                text += f"• {svc['service']}: {svc['count']} шт. = {svc['total']}₽\n"
            text += f"\n<b>💰 ВЫРУЧКА: {data['hall_total']}₽</b>\n"

        if hall == 0:
            text += f"\n<b>💰 ОБЩАЯ ВЫРУЧКА: {report['grand_total']}₽</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Пред. месяц", callback_data=f"report_prev:{year}:{month}:{hall}")],
        [InlineKeyboardButton(text="➡️ След. месяц", callback_data=f"report_next:{year}:{month}:{hall}")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])

    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "⛔ Чёрный список")
async def admin_blacklist(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        return
    
    blacklist = await db.get_blacklist()
    
    if not blacklist:
        await msg.answer(
            "⛔ <b>Чёрный список пуст</b>\n\n"
            "Для добавления используйте:\n"
            "<code>/ban user_id причина</code>\n"
            "или ответом на сообщение пользователя",
            parse_mode="HTML"
        )
        return
    
    text = "⛔ <b>Чёрный список:</b>\n\n"
    for user_id, reason, added_at in blacklist:
        date = added_at.split("T")[0] if added_at else "?"
        text += f"👤 <code>{user_id}</code>\n"
        text += f"   Причина: {reason or 'Без причины'}\n"
        text += f"   Дата: {date}\n\n"
    
    text += "\nДля разблокировки: <code>/unban user_id</code>"
    
    await msg.answer(text, parse_mode="HTML")


@router.message(Command("ban"))
async def cmd_ban(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        await msg.answer("🔐 Доступ запрещён.")
        return
    
    # Если ответ на сообщение
    if msg.reply_to_message:
        user_id = msg.reply_to_message.from_user.id
        reason = msg.text.split(maxsplit=1)[1] if len(msg.text.split()) > 1 else "Без причины"
    else:
        # Парсим user_id из команды
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 2:
            await msg.answer(
                "Использование:\n"
                "<code>/ban user_id [причина]</code>\n"
                "или ответом на сообщение пользователя",
                parse_mode="HTML"
            )
            return
        try:
            user_id = int(parts[1])
            reason = parts[2] if len(parts) > 2 else "Без причины"
        except ValueError:
            await msg.answer("❌ Неверный user_id (должно быть число)")
            return
    
    await db.add_to_blacklist(user_id, reason)
    
    await msg.answer(
        f"✅ Пользователь <code>{user_id}</code> добавлен в ЧС\n"
        f"Причина: {reason}",
        parse_mode="HTML"
    )


@router.message(Command("unban"))
async def cmd_unban(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        await msg.answer("🔐 Доступ запрещён.")
        return
    
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(
            "Использование:\n"
            "<code>/unban user_id</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await msg.answer("❌ Неверный user_id (должно быть число)")
        return
    
    await db.remove_from_blacklist(user_id)
    
    await msg.answer(f"✅ Пользователь <code>{user_id}</code> разблокирован", parse_mode="HTML")


@router.message(Command("blacklist"))
async def cmd_blacklist(msg: types.Message, db: Database):
    if not is_admin(msg.from_user.id):
        await msg.answer("🔐 Доступ запрещён.")
        return
    
    blacklist = await db.get_blacklist()
    
    if not blacklist:
        await msg.answer("⛔ Чёрный список пуст")
        return
    
    text = "⛔ <b>Чёрный список:</b>\n\n"
    for user_id, reason, added_at in blacklist:
        date = added_at.split("T")[0] if added_at else "?"
        text += f"👤 <code>{user_id}</code> — {reason or 'Без причины'} ({date})\n"
    
    await msg.answer(text, parse_mode="HTML")


# ===== ОТПРАВКА СООБЩЕНИЙ КЛИЕНТАМ =====
@router.message(F.text == "✉️ Написать клиенту")
async def admin_message_start(msg: types.Message, state: FSMContext, db: Database):
    """Начало процесса отправки сообщения клиенту"""
    if not is_admin(msg.from_user.id):
        return
    
    await state.set_state(AdminFSM.message_select_date)
    dates = await db.get_working_days(7)  # Показываем 7 дней
    
    if not dates:
        await msg.answer("📭 Нет рабочих дней впереди.", reply_markup=admin_menu_kb())
        await state.clear()
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=d, callback_data=f"msgdate:{d}")]
        for d in dates[:7]
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])
    
    await msg.answer(
        "📅 <b>Выберите дату записи:</b>\n"
        "Покажу клиентов, записанных на этот день.",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("msgdate:"))
async def admin_message_select_date(cb: types.CallbackQuery, db: Database, state: FSMContext):
    """Выбор даты для отправки сообщения"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    date = cb.data.split(":")[1]
    bookings = await db.get_bookings_for_date(date)
    
    if not bookings:
        await cb.answer("📭 Нет записей на эту дату", show_alert=True)
        return
    
    await state.set_state(AdminFSM.message_select_client)
    
    text = f"📋 <b>Клиенты на {date}:</b>\n\n"
    kb = []
    for b in bookings:
        hall_name = await db.get_hall_name(b['hall_id'])
        text += f"⏰ {b['time']} | {hall_name} зал\n"
        text += f"   {b['name']} — {b['service']}\n"
        text += f"   📱 {b['phone']}\n\n"
        
        kb.append([InlineKeyboardButton(
            text=f"👤 {b['name']} ({b['time']})",
            callback_data=f"msgclient:{b['id']}:{date}"
        )])
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_message")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("msgclient:"))
async def admin_message_select_client(cb: types.CallbackQuery, db: Database, state: FSMContext):
    """Выбор клиента и начало ввода сообщения"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    parts = cb.data.split(":")
    booking_id = int(parts[1])
    date = parts[2]
    
    # Получаем информацию о записи
    async with aiosqlite.connect(db.db_path) as db_conn:
        cursor = await db_conn.execute(
            "SELECT id, user_id, name, phone, service_name, hall_id, date, time FROM bookings WHERE id = ?",
            (booking_id,)
        )
        booking = await cursor.fetchone()

    if not booking:
        await cb.answer("❌ Запись не найдена", show_alert=True)
        return

    bid, user_id, name, phone, service, hall_id, date, time = booking
    hall_name = await db.get_hall_name(hall_id) if hall_id else "Неизвестно"
    
    # Сохраняем в FSM контексте
    await state.update_data(
        booking_id=booking_id,
        user_id=user_id,
        name=name,
        date=date,
        time=time
    )
    await state.set_state(AdminFSM.message_write)
    
    text = f"✉️ <b>Отправка сообщения клиенту</b>\n\n"
    text += f"👤 <b>Клиент:</b> {name}\n"
    text += f"📱 <code>{phone}</code>\n"
    text += f"📅 <b>Запись:</b> {date} в {time}\n"
    text += f"💇 <b>Услуга:</b> {service}\n\n"
    text += f"📝 <b>Введите сообщение:</b>\n"
    text += f"<i>(Напишите текст, который получит клиент)</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin_message")]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(AdminFSM.message_write)
async def admin_message_send(msg: types.Message, state: FSMContext, db: Database):
    """Отправка сообщения клиенту"""
    if not is_admin(msg.from_user.id):
        return

    data = await state.get_data()
    user_id = data.get("user_id")
    name = data.get("name")
    date = data.get("date")
    time = data.get("time")

    if not user_id:
        await msg.answer("❌ Ошибка данных. Начните сначала.", reply_markup=admin_menu_kb())
        await state.clear()
        return

    message_text = msg.text
    bot = msg.bot

    logger.info(f"Отправка сообщения пользователю {user_id} от админа {msg.from_user.id}")
    logger.info(f"Текст: {message_text}")

    # Отправляем сообщение клиенту
    try:
        # Сначала проверим, существует ли чат
        chat = await bot.get_chat(user_id)
        logger.info(f"Чат найден: {chat.id}, username: {chat.username}")

        result = await bot.send_message(
            chat_id=user_id,
            text=f"📩 <b>Сообщение от администратора:</b>\n\n"
                 f"{message_text}\n\n"
                 f"<i>По поводу записи: {date} в {time}</i>",
            parse_mode="HTML"
        )

        logger.info(f"Сообщение отправлено: message_id={result.message_id}")

        await msg.answer(
            f"✅ <b>Сообщение отправлено!</b>\n\n"
            f"👤 Клиент: {name}\n"
            f"📱 ID: <code>{user_id}</code>\n\n"
            f"<i>Если клиент не получил сообщение, возможно он заблокировал бота.</i>",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
    except TelegramForbiddenError:
        logger.error(f"Пользователь {user_id} заблокировал бота")
        await msg.answer(
            f"❌ <b>Не удалось отправить сообщение</b>\n\n"
            f"Пользователь <b>заблокировал бота</b>.\n"
            f"Попробуйте позвонить по номеру из записи.",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        logger.error(f"Ошибка Telegram: {e}")
        await msg.answer(
            f"❌ <b>Ошибка Telegram</b>\n\n"
            f"{str(e)}\n\n"
            f"Возможно, пользователь никогда не запускал бота.",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {type(e).__name__}: {e}")
        await msg.answer(
            f"❌ <b>Ошибка: {type(e).__name__}</b>\n\n"
            f"<code>{str(e)}</code>",
            reply_markup=admin_menu_kb(),
            parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(F.data == "back_admin_message")
async def admin_message_back(cb: types.CallbackQuery, state: FSMContext):
    """Возврат из режима отправки сообщений"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    await state.clear()
    await cb.message.edit_text("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")


@router.message(Command("testsend"))
async def test_send(msg: types.Message, bot: Bot):
    """Тест отправки сообщения"""
    if not is_admin(msg.from_user.id):
        return
    
    try:
        # Отправляем самому себе
        await bot.send_message(
            chat_id=msg.from_user.id,
            text=f"✅ <b>Тест успешен!</b>\n\n"
                 f"Бот может отправлять сообщения.\n"
                 f"Твой ID: <code>{msg.from_user.id}</code>",
            parse_mode="HTML"
        )
        await msg.answer("✅ Проверь — должно прийти сообщение от бота")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {type(e).__name__}: {e}")


# ===== КОНЕЦ ОТПРАВКИ СООБЩЕНИЙ =====


# ===== УПРАВЛЕНИЕ ОТЗЫВАМИ =====
@router.message(F.text == "⭐ Отзывы")
async def admin_reviews(msg: types.Message, db: Database):
    """Админ-панель отзывов"""
    if not is_admin(msg.from_user.id):
        return

    stats = await db.get_average_rating()
    rating_stats = await db.get_rating_stats()

    text = f"⭐ <b>Управление отзывами</b>\n\n"
    text += f"Средний рейтинг: <b>{stats['avg']}/5</b>\n"
    text += f"Всего отзывов: <b>{stats['count']}</b>\n\n"

    text += "Распределение:\n"
    for star in [5, 4, 3, 2, 1]:
        count = rating_stats.get(star, 0)
        bar = "▮" * min(count, 10) + "▯" * (10 - min(count, 10))
        text += f"{star}⭐ {bar} {count}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все отзывы", callback_data="admin_reviews_all")],
        [InlineKeyboardButton(text="⭐ 5 звёзд", callback_data="admin_reviews_filter:5")],
        [InlineKeyboardButton(text="⚠️ 1-3 звезды", callback_data="admin_reviews_filter:low")],
        [InlineKeyboardButton(text="🗑 Удалить отзыв", callback_data="admin_reviews_delete")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])

    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin_reviews_all")
async def admin_reviews_all(cb: types.CallbackQuery, db: Database):
    """Показать все отзывы админу"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    reviews = await db.get_reviews(limit=20)

    if not reviews:
        await cb.answer("📭 Нет отзывов", show_alert=True)
        return

    text = "📋 <b>Все отзывы:</b>\n\n"
    for r in reviews:
        rid, uid, name, rating, review_text, booking_id, created_at = r
        date = created_at.split("T")[0] if created_at else "?"
        stars = "⭐" * rating
        text += f"{stars} <b>{name}</b> <i>({date})</i>\n"
        text += f"   ID: <code>{uid}</code>\n"
        if review_text:
            text += f"   «{review_text}»\n"
        text += f"   🗑 <code>/delreview {rid}</code>\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_reviews")]
    ])

    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_reviews_filter:"))
async def admin_reviews_filter(cb: types.CallbackQuery, db: Database):
    """Фильтр отзывов по оценке"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    filter_val = cb.data.split(":")[1]

    if filter_val == "low":
        # Низкие оценки 1-3
        reviews = await db.get_reviews(limit=20)
        reviews = [r for r in reviews if r[3] <= 3]  # rating = index 3
        filter_name = "1-3 звезды (критические)"
    else:
        rating = int(filter_val)
        reviews = await db.get_reviews(limit=20, rating_filter=rating)
        filter_name = f"{rating} звёзд"

    if not reviews:
        await cb.answer(f"📭 Нет отзывов с фильтром {filter_name}", show_alert=True)
        return

    text = f"📋 <b>Отзывы: {filter_name}</b>\n\n"
    for r in reviews:
        rid, uid, name, rating, review_text, booking_id, created_at = r
        date = created_at.split("T")[0] if created_at else "?"
        stars = "⭐" * rating
        text += f"{stars} <b>{name}</b> <i>({date})</i>\n"
        if review_text:
            text += f"   «{review_text}»\n"
        text += f"   🗑 <code>/delreview {rid}</code>\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_reviews")]
    ])

    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin_reviews_delete")
async def admin_reviews_delete_info(cb: types.CallbackQuery):
    """Информация об удалении отзывов"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    await cb.answer(
        "ℹ️ Для удаления отзыва используйте команду:\n"
        "/delreview ID_отзыва\n\n"
        "ID можно посмотреть в списке отзывов",
        show_alert=True
    )


@router.callback_query(F.data == "back_admin_reviews")
async def admin_reviews_back(cb: types.CallbackQuery, db: Database):
    """Возврат из отзывов"""
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    stats = await db.get_average_rating()
    rating_stats = await db.get_rating_stats()

    text = f"⭐ <b>Управление отзывами</b>\n\n"
    text += f"Средний рейтинг: <b>{stats['avg']}/5</b>\n"
    text += f"Всего отзывов: <b>{stats['count']}</b>\n\n"

    text += "Распределение:\n"
    for star in [5, 4, 3, 2, 1]:
        count = rating_stats.get(star, 0)
        bar = "▮" * min(count, 10) + "▯" * (10 - min(count, 10))
        text += f"{star}⭐ {bar} {count}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все отзывы", callback_data="admin_reviews_all")],
        [InlineKeyboardButton(text="⭐ 5 звёзд", callback_data="admin_reviews_filter:5")],
        [InlineKeyboardButton(text="⚠️ 1-3 звезды", callback_data="admin_reviews_filter:low")],
        [InlineKeyboardButton(text="🗑 Удалить отзыв", callback_data="admin_reviews_delete")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]
    ])

    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("delreview"))
async def admin_delete_review(msg: types.Message, db: Database):
    """Удалить отзыв по ID"""
    if not is_admin(msg.from_user.id):
        return

    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(
            "Использование:\n"
            "<code>/delreview ID_отзыва</code>\n\n"
            "ID можно посмотреть в списке отзывов",
            parse_mode="HTML"
        )
        return

    try:
        review_id = int(parts[1])
    except ValueError:
        await msg.answer("❌ Неверный ID (должно быть число)")
        return

    # Проверяем существование
    reviews = await db.get_reviews(limit=100)
    review_exists = any(r[0] == review_id for r in reviews)

    if not review_exists:
        await msg.answer("❌ Отзыв с таким ID не найден")
        return

    await db.delete_review(review_id)

    await msg.answer(
        f"✅ Отзыв <code>{review_id}</code> удалён",
        parse_mode="HTML"
    )


# ===== КОНЕЦ УПРАВЛЕНИЯ ОТЗЫВАМИ =====


@router.callback_query(F.data.startswith("acancel:"))
async def admin_cancel(cb: types.CallbackQuery, db: Database, scheduler):
    # Проверка на админа
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    bid = int(cb.data.split(":")[1])
    res = await db.cancel_booking(bid)
    if not res:
        await cb.answer("❌ Не найдено", show_alert=True)
        return
    scheduler.cancel(bid)
    await cb.answer("✅ Отменено", show_alert=True)
    # Обновляем список
    date = res["date"]
    bookings = await db.get_bookings_for_date(date)
    if bookings:
        text = f"📋 <b>{date}</b>:\n\n" + "\n".join(
            f"⏰ {b['time']} — {b['name']}" for b in bookings
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {b['time']}", callback_data=f"acancel:{b['id']}")]
            for b in bookings
        ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin")]])
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await cb.message.edit_text(f"📭 На {date} нет записей.", reply_markup=calendar_kb(await db.get_working_days(30)))


@router.callback_query(F.data == "back_admin")
async def admin_back(cb: types.CallbackQuery, db: Database):
    # Проверка на админа
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return

    dates = await db.get_working_days(30)
    await cb.message.edit_text("📅 Выберите:", reply_markup=calendar_kb(dates))


@router.callback_query(F.data == "back_admin_halls")
async def admin_back_halls(cb: types.CallbackQuery, state: FSMContext, db: Database):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    halls = await db.get_halls()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"ahall:{hid}")]
        for hid, name in halls
    ] + [[InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")]])
    
    await cb.message.edit_text("🏛 <b>Выберите зал:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "back_admin_menu")
async def admin_back_menu(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("🔐 Доступ запрещён", show_alert=True)
        return
    
    await cb.message.edit_text("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")
