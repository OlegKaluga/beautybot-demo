# keyboards/booking.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta


def calendar_kb(dates: list, page: int = 0):
    """Календарь с пагинацией по неделям (для записи клиентов)
    
    Показывает по 7 дней на странице с навигацией
    """
    # Разбиваем на недели по 7 дней
    weeks = [dates[i:i+7] for i in range(0, len(dates), 7)]
    
    if not weeks:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📭 Нет свободных дат", callback_data="empty")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ])

    page = max(0, min(page, len(weeks) - 1))
    week = weeks[page]

    keyboard = []
    row = []
    for d in week:
        dt = datetime.strptime(d, "%Y-%m-%d")
        day = dt.strftime("%a")[:2]
        num = dt.day
        row.append(InlineKeyboardButton(text=f"{day}\n{num}", callback_data=f"date:{d}"))
    keyboard.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"cal:{page-1}"))
    if page < len(weeks) - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"cal:{page+1}"))
    nav.append(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    keyboard.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def slots_kb(slots: list, date: str):
    """Выбор времени в виде сетки кнопок"""
    kb = []
    row = []
    
    # Все возможные слоты
    all_slots = [f"{h:02d}:00" for h in range(10, 20)]
    
    for t in all_slots:
        if t in slots:
            row.append(InlineKeyboardButton(
                text=f"⏰ {t}",
                callback_data=f"slot:{date}:{t}"
            ))
        else:
            row.append(InlineKeyboardButton(
                text="⬜",
                callback_data="empty_slot"
            ))
        
        # Новая строка каждые 4 слота
        if len(row) == 4:
            kb.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        kb.append(row)
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def add_day_calendar_kb(selected_dates: list = None, year: int = None, month: int = None):
    """Календарь для добавления дней админом
    
    Показывает месяц с возможностью выбора дат
    selected_dates: список уже добавленных дат (YYYY-MM-DD)
    year, month: год и месяц для отображения (по умолчанию текущий месяц)
    """
    if selected_dates is None:
        selected_dates = []
    
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    keyboard = []
    
    # Заголовок с месяцем и годом + навигация
    month_name = datetime(year, month, 1).strftime("%B %Y")
    nav_row = [
        InlineKeyboardButton(text="⬅️", callback_data=f"prev_month:{year}:{month}"),
        InlineKeyboardButton(text=f"📅 {month_name.capitalize()}", callback_data="cal_month_none"),
        InlineKeyboardButton(text="➡️", callback_data=f"next_month:{year}:{month}")
    ]
    keyboard.append(nav_row)
    
    # Дни недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(text=d, callback_data="cal_day_none") for d in weekdays])
    
    # Первый день месяца
    first_day = datetime(year, month, 1)
    # Смещение для понедельника (в Python понедельник=0)
    start_weekday = first_day.weekday()
    
    # Количество дней в месяце
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    days_in_month = (next_month - first_day).days
    
    # Пустые ячейки до первого дня
    rows = []
    for _ in range(start_weekday):
        rows.append(InlineKeyboardButton(text="⬜", callback_data="cal_empty_none"))
    
    # Дни месяца
    today = datetime.now().date()
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        # Проверяем, добавлена ли дата
        if date_str in selected_dates:
            emoji = "✅"  # Уже добавлено
        else:
            # Проверяем, сегодня ли
            if datetime(year, month, day).date() == today:
                emoji = "🔵"  # Сегодня
            else:
                emoji = "⬜"  # Обычный день
        
        rows.append(InlineKeyboardButton(
            text=f"{emoji}{day}",
            callback_data=f"addday:{date_str}"
        ))
        
        # Новая строка каждые 7 дней
        if len(rows) % 7 == 0:
            keyboard.append(rows)
            rows = []
    
    # Добавляем оставшиеся дни
    if rows:
        # Дополняем до 7 для красоты
        while len(rows) < 7:
            rows.append(InlineKeyboardButton(text="⬜", callback_data="cal_empty_none"))
        keyboard.append(rows)
    
    # Кнопки управления
    nav_row = [
        InlineKeyboardButton(text="➕ Добавить все", callback_data="addall_days"),
        InlineKeyboardButton(text="❌ Очистить", callback_data="clear_days")
    ]
    keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 В меню", callback_data="back_admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def confirm_add_days_kb(dates: list):
    """Клавиатура подтверждения добавления выбранных дат"""
    kb = []
    
    # Показываем до 5 дат за раз
    for date_str in dates[:10]:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        formatted = dt.strftime("%d.%m.%Y (%a)")
        kb.append([InlineKeyboardButton(
            text=f"✅ {formatted}",
            callback_data=f"confirm_add:{date_str}"
        )])
    
    kb.append([InlineKeyboardButton(
        text="➕ Добавить выбранные",
        callback_data="confirm_add_all"
    )])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)
