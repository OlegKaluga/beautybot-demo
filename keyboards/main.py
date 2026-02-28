# keyboards/main.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import get_settings

settings = get_settings()


def main_menu_kb():
    kb = [
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="💰 Прайсы")],
        [KeyboardButton(text="🖼 Портфолио"), KeyboardButton(text="❓ Помощь")],
        [KeyboardButton(text="🗓 Мои записи"), KeyboardButton(text="⭐ Оставить отзыв")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_menu_kb():
    kb = [
        [KeyboardButton(text="➕ Добавить день"), KeyboardButton(text="❌ Закрыть день")],
        [KeyboardButton(text="⏰ Слоты"), KeyboardButton(text="📋 Записи")],
        [KeyboardButton(text="✉️ Написать клиенту")],
        [KeyboardButton(text="📊 Общий отчёт")],
        [KeyboardButton(text="✂️ Стрижки"), KeyboardButton(text="💅 Ногти")],
        [KeyboardButton(text="⭐ Отзывы"), KeyboardButton(text="⛔ Чёрный список")],
        [KeyboardButton(text="🔙 В меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True
    )


def portfolio_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✨ Смотреть портфолио",
            url="https://ru.pinterest.com/crystalwithluv/_created/"
        )]
    ])


def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def subscription_kb():
    link = settings["CHANNEL_LINK"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подписаться", url=link)],
        [InlineKeyboardButton(text="✅ Проверить", callback_data="check_sub")]
    ])


def halls_kb():
    """Выбор зала"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✂️ Стрижки", callback_data="hall:1")],
        [InlineKeyboardButton(text="💅 Ногти", callback_data="hall:2")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])


def masters_kb(masters: list, hall_id: int):
    """Выбор мастера для зала в виде сетки кнопок

    masters: [(id, name), ...]
    """
    kb = []
    row = []
    
    for master_id, name in masters:
        # Короткое имя для кнопки
        short_name = name.replace("Мастер ", "М.").replace(" (стрижки)", "")
        row.append(InlineKeyboardButton(
            text=short_name,
            callback_data=f"master:{hall_id}:{master_id}"
        ))
        
        # Новая строка каждые 2 кнопки
        if len(row) == 2:
            kb.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        if len(row) == 1:
            row.append(InlineKeyboardButton(text="⬜", callback_data="empty_master"))
        kb.append(row)
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_halls")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def services_kb(services: list, hall_id: int, master_id: int = None):
    """Выбор услуг для зала в виде сетки кнопок

    services: [(id, name, price, duration), ...]
    """
    kb = []
    row = []
    
    for svc_id, name, price, duration in services:
        callback_data = f"service:{hall_id}:{svc_id}"
        if master_id:
            callback_data = f"service:{hall_id}:{master_id}:{svc_id}"
        
        # Короткое название для кнопки
        short_name = name.replace("Комплекс (", "Компл.(").replace("Стрижка ", "Стр. ")
        row.append(InlineKeyboardButton(
            text=f"{short_name}\n{price}₽",
            callback_data=callback_data
        ))
        
        # Новая строка каждые 2 кнопки
        if len(row) == 2:
            kb.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        # Дополняем до 2 для красоты
        if len(row) == 1:
            row.append(InlineKeyboardButton(text="⬜", callback_data="empty_service"))
        kb.append(row)
    
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_halls")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
