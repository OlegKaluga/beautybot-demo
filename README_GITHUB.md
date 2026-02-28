# 🤖 BeautyBot Lite — Telegram-бот для записи клиентов

**Студия красоты «Luxe»** — современная система онлайн-записи для салонов красоты, барбершопов, студий маникюра и других бьюти-мастеров.

---

## ✨ Возможности

### Для клиентов:
- 📅 Запись на услуги в любое время
- 🔔 Напоминания о визите
- 📋 Просмотр своих записей
- ⭐ Оценка качества услуг

### Для администратора:
- 👥 Управление клиентами
- 📊 Просмотр всех записей
- 🕐 Управление слотами времени
- 📝 Чёрный список
- 📈 Статистика

---

## 🚀 Быстрый старт

### 1. Клонирование
```bash
git clone https://github.com/ТВОЙ_НИК/beautybot-lite-demo.git
cd beautybot-lite-demo
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка
Скопируйте `.env.example` в `.env` и заполните:
```bash
cp .env.example .env
```

Откройте `.env` и укажите:
- `BOT_TOKEN` — токен от @BotFather
- `ADMIN_IDS` — ваш Telegram ID (можно узнать у @userinfobot)

### 4. Запуск
```bash
python bot.py
```

---

## 📁 Структура проекта

```
beautybot_lite_v1/
├── bot.py              # Главный файл запуска
├── config/             # Конфигурация
│   └── settings.py
├── database/           # Работа с БД
│   └── db.py
├── handlers/           # Обработчики команд
│   ├── user.py         # Пользовательские команды
│   ├── admin.py        # Админские команды
│   ├── callbacks.py    # Callback-запросы
│   └── admin_slots.py  # Управление слотами
├── keyboards/          # Клавиатуры
│   └── main.py
├── middlewares/        # Промежуточное ПО
├── utils/              # Утилиты
│   └── scheduler.py    # Планировщик напоминаний
├── .env                # Переменные окружения
├── .env.example        # Пример конфигурации
├── requirements.txt    # Зависимости
└── nail_bot.db         # База данных SQLite
```

---

## 🌐 Размещение

### Render.com (бесплатно для демо)
См. [INSTRUCTION_RENDER.md](INSTRUCTION_RENDER.md)

### PythonAnywhere (платно)
См. [INSTRUCTION_PYTHONANYWHERE.md](INSTRUCTION_PYTHONANYWHERE.md)

---

## 📋 Требования

- Python 3.9+
- aiogram 3.x
- SQLite (встроен)
- Telegram Bot API

---

## 📞 Поддержка

Вопросы и предложения: [Контакты в документации]

---

## 📄 Лицензия

Коммерческое использование — по договорённости.
