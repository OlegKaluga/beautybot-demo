# handlers/user.py
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config.settings import get_settings
from database.db import Database
from keyboards.main import (
    main_menu_kb, portfolio_kb, confirm_kb,
    halls_kb, services_kb, subscription_kb, masters_kb
)
from keyboards.booking import calendar_kb, slots_kb
from utils.scheduler import ReminderScheduler
from datetime import datetime
import pytz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
settings = get_settings()
tz = pytz.timezone(settings["TIMEZONE"])


class BookingFSM(StatesGroup):
    hall = State()
    master = State()
    service = State()
    date = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


class ReviewFSM(StatesGroup):
    rating = State()
    text = State()


@router.message(Command("start"))
async def start(msg: types.Message):
    salon = settings["SALON_NAME"]
    text = settings["WELCOME_TEXT"].format(salon_name=salon)
    await msg.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(Command("reviews"))
async def reviews_command(msg: types.Message, db: Database):
    """Показать ленту отзывов"""
    await show_reviews(msg, db)


@router.message(F.text == "⭐ Оставить отзыв")
async def leave_review_start(msg: types.Message, state: FSMContext, db: Database):
    """Начало процесса оставления отзыва"""
    # Проверяем, есть ли у пользователя завершённые записи
    user_id = msg.from_user.id
    
    # Можно оставить отзыв только если была запись
    has_booking = await db.has_user_reviewed(user_id)
    
    await state.set_state(ReviewFSM.rating)
    
    text = "⭐ <b>Оставьте отзыв о нашем салоне</b>\n\n"
    text += "Оцените качество услуг от 1 до 5 звёзд:\n\n"
    text += "5 ⭐⭐⭐⭐⭐ — Превосходно\n"
    text += "4 ⭐⭐⭐⭐ — Хорошо\n"
    text += "3 ⭐⭐⭐ — Нормально\n"
    text += "2 ⭐⭐ — Плохо\n"
    text += "1 ⭐ — Ужасно\n\n"
    text += "<i>Просто отправьте цифру от 1 до 5</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 ⭐⭐⭐⭐⭐", callback_data="rating:5")],
        [InlineKeyboardButton(text="4 ⭐⭐⭐⭐", callback_data="rating:4")],
        [InlineKeyboardButton(text="3 ⭐⭐⭐", callback_data="rating:3")],
        [InlineKeyboardButton(text="2 ⭐⭐", callback_data="rating:2")],
        [InlineKeyboardButton(text="1 ⭐", callback_data="rating:1")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")]
    ])
    
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("rating:"))
async def review_rating_selected(cb: types.CallbackQuery, state: FSMContext, db: Database):
    """Выбор оценки через кнопку"""
    rating = int(cb.data.split(":")[1])
    await save_review_rating(cb, state, db, rating)


@router.message(ReviewFSM.rating)
async def review_rating_input(msg: types.Message, state: FSMContext, db: Database):
    """Ввод оценки текстом"""
    try:
        rating = int(msg.text.strip())
        if rating < 1 or rating > 5:
            await msg.answer("❌ Пожалуйста, отправьте число от 1 до 5:")
            return
        await save_review_rating(msg, state, db, rating)
    except ValueError:
        await msg.answer("❌ Пожалуйста, отправьте число от 1 до 5:")
        return


async def save_review_rating(msg_or_cb, state: FSMContext, db: Database, rating: int):
    """Сохранение оценки и переход к тексту отзыва"""
    await state.update_data(rating=rating)
    await state.set_state(ReviewFSM.text)
    
    stars = "⭐" * rating
    
    text = f"{stars} <b>Спасибо за оценку {rating}!</b>\n\n"
    text += "Хотите оставить комментарий?\n\n"
    text += "<i>Напишите текст отзыва или отправьте «Пропустить»</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="review_skip_text")]
    ])
    
    if hasattr(msg_or_cb, 'answer'):
        await msg_or_cb.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "review_skip_text")
async def review_skip_text(cb: types.CallbackQuery, state: FSMContext, db: Database):
    """Пропуск текста отзыва"""
    await save_review(cb, state, db, "")


@router.message(ReviewFSM.text)
async def review_text_input(msg: types.Message, state: FSMContext, db: Database):
    """Ввод текста отзыва"""
    if msg.text.lower() in ["пропустить", "skip", "нет"]:
        await save_review(msg, state, db, "")
        return
    
    await save_review(msg, state, db, msg.text.strip())


async def save_review(msg_or_cb, state: FSMContext, db: Database, text: str):
    """Сохранение отзыва в базу"""
    data = await state.get_data()
    rating = data.get("rating", 5)
    user_id = msg_or_cb.from_user.id
    name = msg_or_cb.from_user.full_name or "Аноним"
    
    # Сохраняем отзыв
    review_id = await db.add_review(user_id, name, rating, text)
    
    text_response = f"✅ <b>Спасибо за отзыв!</b>\n\n"
    text_response += f"Ваша оценка: {'⭐' * rating}\n"
    if text:
        text_response += f"Комментарий: {text}\n"
    text_response += "\nМы ценим ваше мнение! 💕"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Посмотреть все отзывы", callback_data="reviews_all")]
    ])
    
    if hasattr(msg_or_cb, 'answer'):
        await msg_or_cb.answer(text_response, reply_markup=kb, parse_mode="HTML")
        # Если это callback query, редактируем сообщение
        if hasattr(msg_or_cb, 'message') and msg_or_cb.message:
            try:
                await msg_or_cb.message.delete()
            except:
                pass
    else:
        await msg_or_cb.answer(text_response, reply_markup=main_menu_kb(), parse_mode="HTML")
    
    await state.clear()
    
    # Уведомление админам о новом отзыве
    if rating <= 3:  # Только если оценка низкая
        for aid in settings["ADMIN_IDS"]:
            try:
                await msg_or_cb.bot.send_message(
                    aid,
                    f"⚠️ <b>Новый отзыв (оценка {rating}/5)</b>\n\n"
                    f"👤 {name}\n"
                    f"🆔 <code>{user_id}</code>\n"
                    f"{'⭐' * rating}\n"
                    f"Комментарий: {text or 'Без комментария'}",
                    parse_mode="HTML"
                )
            except:
                pass


@router.callback_query(F.data == "review_cancel")
async def review_cancel(cb: types.CallbackQuery, state: FSMContext):
    """Отмена оставления отзыва"""
    await state.clear()
    await cb.message.edit_text("❌ Отзыв не отправлен.", reply_markup=main_menu_kb())


async def show_reviews(msg: types.Message, db: Database, page: int = 0):
    """Показать ленту отзывов"""
    reviews = await db.get_reviews(limit=10)
    stats = await db.get_average_rating()
    rating_stats = await db.get_rating_stats()
    
    if not reviews:
        await msg.answer(
            "📭 <b>Пока нет отзывов</b>\n\n"
            "Будьте первыми — оставьте отзыв о нашем салоне!",
            parse_mode="HTML"
        )
        return
    
    # Статистика
    text = f"⭐ <b>Отзывы о салоне</b>\n\n"
    text += f"Средний рейтинг: <b>{stats['avg']}/5</b> ({stats['count']} отзывов)\n\n"
    
    # Распределение оценок
    text += "Распределение:\n"
    for star in [5, 4, 3, 2, 1]:
        count = rating_stats.get(star, 0)
        bar = "▮" * count + "▯" * (10 - count) if count else "▯" * 10
        text += f"{star}⭐ {bar} {count}\n"
    
    text += "\n" + "─" * 20 + "\n\n"
    
    # Последние отзывы
    for r in reviews[:5]:
        rid, uid, name, rating, review_text, booking_id, created_at = r
        date = created_at.split("T")[0] if created_at else "?"
        stars = "⭐" * rating
        text += f"{stars} <b>{name}</b> <i>({date})</i>\n"
        if review_text:
            # Обрезаем длинные отзывы
            if len(review_text) > 100:
                review_text = review_text[:100] + "..."
            text += f"   {review_text}\n"
        text += "\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data="review_start")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_main_menu")]
    ])
    
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "reviews_all")
async def reviews_all_callback(cb: types.CallbackQuery, db: Database):
    """Показать все отзывы"""
    await show_reviews(cb.message, db)


@router.callback_query(F.data == "review_start")
async def review_start_callback(cb: types.CallbackQuery, state: FSMContext):
    """Начать оставление отзыва"""
    await state.set_state(ReviewFSM.rating)
    
    text = "⭐ <b>Оставьте отзыв о нашем салоне</b>\n\n"
    text += "Оцените качество услуг от 1 до 5 звёзд:\n\n"
    text += "5 ⭐⭐⭐⭐⭐ — Превосходно\n"
    text += "4 ⭐⭐⭐⭐ — Хорошо\n"
    text += "3 ⭐⭐⭐ — Нормально\n"
    text += "2 ⭐⭐ — Плохо\n"
    text += "1 ⭐ — Ужасно\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 ⭐⭐⭐⭐⭐", callback_data="rating:5")],
        [InlineKeyboardButton(text="4 ⭐⭐⭐⭐", callback_data="rating:4")],
        [InlineKeyboardButton(text="3 ⭐⭐⭐", callback_data="rating:3")],
        [InlineKeyboardButton(text="2 ⭐⭐", callback_data="rating:2")],
        [InlineKeyboardButton(text="1 ⭐", callback_data="rating:1")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="review_cancel")]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "back_main_menu")
async def back_to_main_menu(cb: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    salon = settings["SALON_NAME"]
    text = settings["WELCOME_TEXT"].format(salon_name=salon)
    await cb.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(F.text == "💰 Прайсы")
async def prices(msg: types.Message, db: Database):
    halls = await db.get_halls()
    text = "<b>💰 Прайс-лист</b>\n\n"

    for hall_id, hall_name in halls:
        text += f"<b>{hall_name}:</b>\n"
        # Получаем мастеров для этого зала
        masters = await db.get_masters_by_hall(hall_id)
        if len(masters) > 1:
            # Показываем мастеров для зала
            for mid, mname in masters:
                text += f"  👤 {mname}:\n"
                services = await db.get_services_by_hall(hall_id)
                for svc_id, name, price, duration in services:
                    text += f"    • {name} — {price}₽ ({duration} мин)\n"
        else:
            services = await db.get_services_by_hall(hall_id)
            for svc_id, name, price, duration in services:
                text += f"  • {name} — {price}₽ ({duration} мин)\n"
        text += "\n"

    text += "<i>Цены актуальны на момент записи</i>"
    await msg.answer(text, parse_mode="HTML")


@router.message(F.text == "🖼 Портфолио")
async def portfolio(msg: types.Message):
    await msg.answer("✨ Наши работы:", reply_markup=portfolio_kb())


@router.message(F.text == "❓ Помощь")
async def help(msg: types.Message):
    await msg.answer(
        "<b>❓ Помощь</b>\n\n"
        "• Запись: нажмите «📅 Записаться»\n"
        "• Отмена: «🗓 Мои записи» → «Отменить»\n"
        "• Вопрос? Пишите администратору",
        parse_mode="HTML"
    )


@router.message(F.text == "📅 Записаться")
async def book_start(msg: types.Message, state: FSMContext, db: Database):
    # Проверка: одна активная запись
    existing = await db.get_user_active_booking(msg.from_user.id)
    if existing:
        hall = existing.get('hall', '')
        await msg.answer(
            f"⚠️ У вас уже есть запись:\n"
            f"🏛 {hall} зал\n"
            f"📅 {existing['date']} {existing['time']}\n"
            f"💇 {existing['service']}\n\n"
            f"Отмените её в «🗓 Мои записи».",
            reply_markup=main_menu_kb()
        )
        return
    
    await state.set_state(BookingFSM.hall)
    await msg.answer("🏛 <b>Выберите зал:</b>", reply_markup=halls_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("hall:"))
async def on_hall(cb: types.CallbackQuery, state: FSMContext, db: Database):
    hall_id = int(cb.data.split(":")[1])
    hall_name = await db.get_hall_name(hall_id)
    await state.update_data(hall_id=hall_id, hall_name=hall_name)

    # Получаем мастеров для этого зала
    masters = await db.get_masters_by_hall(hall_id)
    
    # Если мастер один (ногти) — сразу переходим к услугам
    if len(masters) == 1:
        master_id, master_name = masters[0]
        await state.update_data(master_id=master_id, master_name=master_name)
        services = await db.get_services_by_hall(hall_id)
        await state.set_state(BookingFSM.service)
        await cb.message.edit_text(
            f"💅 <b>Выберите услугу:</b>\n🏛 {hall_name}",
            reply_markup=services_kb(services, hall_id, master_id),
            parse_mode="HTML"
        )
    else:
        # Если мастеров несколько (стрижки) — выбираем мастера
        await state.set_state(BookingFSM.master)
        await cb.message.edit_text(
            f"✂️ <b>Выберите мастера:</b>\n🏛 {hall_name}",
            reply_markup=masters_kb(masters, hall_id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("master:"))
async def on_master(cb: types.CallbackQuery, state: FSMContext, db: Database):
    # Игнорируем пустые кнопки
    if cb.data == "master:empty:empty":
        await cb.answer()
        return
    
    _, hall_id, master_id = cb.data.split(":", 2)
    hall_id = int(hall_id)
    master_id = int(master_id)

    hall_name = await db.get_hall_name(hall_id)
    master_name = await db.get_master_name(master_id)
    await state.update_data(master_id=master_id, master_name=master_name)

    services = await db.get_services_by_hall(hall_id)
    await state.set_state(BookingFSM.service)
    await cb.message.edit_text(
        f"💇 <b>Выберите услугу:</b>\n🏛 {hall_name}, 👤 {master_name}",
        reply_markup=services_kb(services, hall_id, master_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("service:"))
async def on_service(cb: types.CallbackQuery, state: FSMContext, db: Database):
    # Игнорируем пустые кнопки
    if cb.data == "service:empty:empty":
        await cb.answer()
        return
    
    parts = cb.data.split(":")
    hall_id = int(parts[1])
    service_id = int(parts[-1])

    # Получаем master_id из данных состояния
    data = await state.get_data()
    master_id = data.get('master_id')

    service = await db.get_service(service_id)
    if not service:
        await cb.answer("❌ Услуга не найдена", show_alert=True)
        return

    svc_id, svc_name, price, duration, svc_hall_id = service
    await state.update_data(
        service_id=service_id,
        service_name=svc_name,
        price=price,
        duration=duration
    )

    await state.set_state(BookingFSM.date)
    dates = await db.get_working_days(90)  # Увеличили с 30 до 90 дней
    if not dates:
        await cb.answer("🚫 Нет свободных дат", show_alert=True)
        return

    await cb.message.edit_text(
        f"📅 <b>Выберите дату:</b>\n💇 {svc_name} ({price}₽)",
        reply_markup=calendar_kb(dates),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("date:"))
async def on_date(cb: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    master_id = data.get('master_id')
    date = cb.data.split(":")[1]
    await state.update_data(date=date)

    slots = await db.get_available_slots(date, master_id)
    
    # Отладка: логируем количество слотов
    import logging
    logging.info(f"Дата: {date}, Мастер: {master_id}, Слотов: {len(slots)}")
    
    if not slots:
        await cb.answer(f"❌ Нет слотов на {date}", show_alert=True)
        return

    await state.set_state(BookingFSM.time)
    await cb.message.edit_text(
        f"⏰ <b>Время на {date}:</b>",
        reply_markup=slots_kb(slots, date),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("slot:"))
async def on_slot(cb: types.CallbackQuery, state: FSMContext):
    # Игнорируем пустые кнопки
    if cb.data == "slot:empty:empty":
        await cb.answer()
        return
    
    _, date, time = cb.data.split(":", 2)
    await state.update_data(time=time)
    await state.set_state(BookingFSM.name)
    await cb.message.edit_text("✍️ <b>Ваше имя:</b>", parse_mode="HTML")


@router.message(BookingFSM.name)
async def on_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(BookingFSM.phone)
    await msg.answer("📱 <b>Номер телефона:</b>", parse_mode="HTML")


@router.message(BookingFSM.phone)
async def on_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    if not phone.replace("+","").replace("-","").replace(" ","").isdigit():
        await msg.answer("❌ Неверный формат. Попробуйте ещё раз:")
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingFSM.confirm)

    data = await state.get_data()
    summary = (
        f"🔍 <b>Проверьте запись:</b>\n\n"
        f"🏛 {data['hall_name']}\n"
        f"👤 {data.get('master_name', '')}\n"
        f"💇 {data['service_name']} ({data['price']}₽)\n"
        f"👤 {data['name']}\n📱 {data['phone']}\n"
        f"📅 {data['date']} в {data['time']}\n\n"
        f"Подтвердить?"
    )
    await msg.answer(summary, reply_markup=confirm_kb(), parse_mode="HTML")


@router.callback_query(F.data == "confirm")
async def on_confirm(cb: types.CallbackQuery, state: FSMContext, db: Database, scheduler: ReminderScheduler):
    data = await state.get_data()
    uid = cb.from_user.id

    ok = await db.book_slot(data["date"], data["time"], data["master_id"], uid)
    if not ok:
        await cb.answer("❌ Слот только что заняли", show_alert=True)
        await state.clear()
        dates = await db.get_working_days(30)
        await cb.message.edit_text("📅 Выберите дату:", reply_markup=calendar_kb(dates))
        return

    bid = await db.create_booking(
        uid, data["name"], data["phone"],
        data["service_id"], data["service_name"],
        data["hall_id"], data["hall_name"],
        data["master_id"], data.get("master_name", ""),
        data["date"], data["time"]
    )

    # Напоминание
    appt = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
    appt = tz.localize(appt)
    await scheduler.add(
        bid, uid, data["name"], data["service_name"],
        data["date"], data["time"], appt
    )

    # Уведомление админу
    master_info = f"👤 {data.get('master_name', '')}\n" if data.get('master_name') else ""
    for aid in settings["ADMIN_IDS"]:
        await cb.bot.send_message(aid,
            f"🔔 <b>Новая запись!</b>\n\n"
            f"🏛 {data['hall_name']}\n"
            f"{master_info}"
            f"💇 {data['service_name']}\n"
            f"👤 {data['name']} ({data['phone']})\n"
            f"📅 {data['date']} {data['time']}\n"
            f"💰 {data['price']}₽\n"
            f"🆔 {uid}",
            parse_mode="HTML")

    # В канал
    if settings["CHANNEL_ID"]:
        try:
            master_info_channel = f", {data.get('master_name', '')}" if data.get('master_name') else ""
            await cb.bot.send_message(settings["CHANNEL_ID"],
                f"✨ Запись на {data['date']} {data['time']} подтверждена!\n"
                f"🏛 {data['hall_name']}{master_info_channel}, 💇 {data['service_name']}",
                parse_mode="HTML")
        except:
            pass

    await cb.message.answer(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"🏛 {data['hall_name']}\n"
        f"👤 {data.get('master_name', '')}\n"
        f"💇 {data['service_name']}\n"
        f"📅 {data['date']} в {data['time']}\n"
        f"Ждём вас! 💅",
        reply_markup=main_menu_kb(), parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "cancel")
async def on_cancel(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("❌ Отменено.", reply_markup=main_menu_kb())
    await state.clear()


@router.callback_query(F.data == "back_main")
async def back_main(cb: types.CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    await cb.message.edit_text("📅 Выберите дату:", reply_markup=calendar_kb(await db.get_working_days(30)))


@router.callback_query(F.data == "back_halls")
async def back_halls(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(BookingFSM.hall)
    await cb.message.edit_text("🏛 <b>Выберите зал:</b>", reply_markup=halls_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("cal:"))
async def cal_page(cb: types.CallbackQuery, state: FSMContext, db: Database):
    page = int(cb.data.split(":")[1])
    dates = await db.get_working_days(90)  # Увеличили с 30 до 90 дней
    await cb.message.edit_text("📅 Выберите дату:", reply_markup=calendar_kb(dates, page))


@router.message(F.text == "🗓 Мои записи")
async def my_bookings(msg: types.Message, db: Database):
    logger.info(f"Мои записи: user_id={msg.from_user.id}")
    b = await db.get_user_active_booking(msg.from_user.id)
    logger.info(f"Запись найдена: {b}")
    if not b:
        await msg.answer("📭 Нет активных записей.", reply_markup=main_menu_kb())
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"ucancel:{b['id']}")]
    ])
    master_info = f"👤 {b.get('master', '')}\n" if b.get('master') else ""
    await msg.answer(
        f"📋 <b>Ваша запись:</b>\n"
        f"🏛 {b.get('hall', '')}\n"
        f"{master_info}"
        f"💇 {b['service']}\n"
        f"📅 {b['date']} {b['time']}",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("ucancel:"))
async def user_cancel(cb: types.CallbackQuery, db: Database, scheduler: ReminderScheduler):
    bid = int(cb.data.split(":")[1])
    res = await db.cancel_booking(bid, cb.from_user.id)
    if not res:
        await cb.answer("❌ Ошибка", show_alert=True)
        return
    scheduler.cancel(bid)
    await cb.answer("✅ Отменено", show_alert=True)
    await cb.message.answer("🗑 Запись отменена.", reply_markup=main_menu_kb())
