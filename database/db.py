# database/db.py
import aiosqlite
from datetime import datetime, timedelta
import pytz
from config.settings import get_settings

settings = get_settings()
tz = pytz.timezone(settings["TIMEZONE"])


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Залы
            await db.execute("""
                CREATE TABLE IF NOT EXISTS halls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)
            # Мастера (привязаны к залу)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS masters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    hall_id INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (hall_id) REFERENCES halls(id)
                )
            """)
            # Услуги
            await db.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    hall_id INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    duration INTEGER DEFAULT 60,
                    FOREIGN KEY (hall_id) REFERENCES halls(id)
                )
            """)
            # Рабочие дни
            await db.execute("""
                CREATE TABLE IF NOT EXISTS working_days (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    is_closed INTEGER DEFAULT 0
                )
            """)
            # Временные слоты (привязаны к мастеру)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    master_id INTEGER NOT NULL,
                    is_booked INTEGER DEFAULT 0,
                    booked_by INTEGER,
                    UNIQUE(date, time, master_id),
                    FOREIGN KEY (master_id) REFERENCES masters(id)
                )
            """)
            # Записи клиентов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    service_id INTEGER,
                    service_name TEXT,
                    hall_id INTEGER,
                    hall_name TEXT,
                    master_id INTEGER,
                    master_name TEXT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reminder_sent INTEGER DEFAULT 0
                )
            """)
            # Задачи напоминаний
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminder_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER UNIQUE NOT NULL,
                    remind_at TEXT NOT NULL
                )
            """)

            # Чёрный список
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    added_at TEXT
                )
            """)

            # Отзывы
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                    text TEXT,
                    booking_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (booking_id) REFERENCES bookings(id)
                )
            """)

            # Добавим залы по умолчанию
            await db.execute("INSERT OR IGNORE INTO halls (name) VALUES ('Стрижки'), ('Ногти')")

            # Добавим мастеров по умолчанию (с проверкой)
            # Зал 1 (Стрижки) — 2 мастера
            # Зал 2 (Ногти) — 1 мастер
            await db.execute("""
                INSERT INTO masters (name, hall_id, is_active)
                SELECT 'Мастер 1', 1, 1
                WHERE NOT EXISTS (SELECT 1 FROM masters WHERE name = 'Мастер 1' AND hall_id = 1)
            """)
            await db.execute("""
                INSERT INTO masters (name, hall_id, is_active)
                SELECT 'Мастер 2', 1, 1
                WHERE NOT EXISTS (SELECT 1 FROM masters WHERE name = 'Мастер 2' AND hall_id = 1)
            """)
            await db.execute("""
                INSERT INTO masters (name, hall_id, is_active)
                SELECT 'Мастер (ногти)', 2, 1
                WHERE NOT EXISTS (SELECT 1 FROM masters WHERE name = 'Мастер (ногти)' AND hall_id = 2)
            """)

            # Добавим услуги по умолчанию (с проверкой)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Стрижка', 1, 800, 45
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Стрижка' AND hall_id = 1)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Стрижка бороды', 1, 500, 30
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Стрижка бороды' AND hall_id = 1)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Комплекс (стрижка + борода)', 1, 1200, 75
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Комплекс (стрижка + борода)' AND hall_id = 1)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Маникюр', 2, 1200, 90
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Маникюр' AND hall_id = 2)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Педикюр', 2, 1500, 90
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Педикюр' AND hall_id = 2)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Покрытие гель-лак', 2, 1800, 120
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Покрытие гель-лак' AND hall_id = 2)
            """)
            await db.execute("""
                INSERT INTO services (name, hall_id, price, duration)
                SELECT 'Дизайн ногтей', 2, 500, 30
                WHERE NOT EXISTS (SELECT 1 FROM services WHERE name = 'Дизайн ногтей' AND hall_id = 2)
            """)

            await db.commit()

    # ===== Halls & Masters & Services =====
    async def get_halls(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id, name FROM halls ORDER BY id")
            return await cursor.fetchall()

    async def get_masters_by_hall(self, hall_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name FROM masters WHERE hall_id = ? AND is_active = 1 ORDER BY id",
                (hall_id,)
            )
            return await cursor.fetchall()

    async def get_services_by_hall(self, hall_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name, price, duration FROM services WHERE hall_id = ? ORDER BY name",
                (hall_id,)
            )
            return await cursor.fetchall()

    async def get_service(self, service_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name, price, duration, hall_id FROM services WHERE id = ?",
                (service_id,)
            )
            return await cursor.fetchone()

    async def get_hall_name(self, hall_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM halls WHERE id = ?", (hall_id,))
            row = await cursor.fetchone()
            return row[0] if row else ""

    async def get_master_name(self, master_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM masters WHERE id = ?", (master_id,))
            row = await cursor.fetchone()
            return row[0] if row else ""

    # ===== Working Days =====
    async def add_working_day(self, date: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO working_days (date) VALUES (?)", (date,))
            # Авто-слоты 10:00-19:00 для каждого мастера
            masters = await self.get_all_masters()
            for master_id, _ in masters:
                for h in range(10, 20):
                    await db.execute(
                        "INSERT OR IGNORE INTO time_slots (date, time, master_id) VALUES (?, ?, ?)",
                        (date, f"{h:02d}:00", master_id)
                    )
            await db.commit()

    async def close_day(self, date: str, closed: bool = True):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO working_days (date, is_closed) VALUES (?, ?)",
                (date, 1 if closed else 0)
            )
            await db.execute(
                "UPDATE working_days SET is_closed = ? WHERE date = ?",
                (1 if closed else 0, date)
            )
            await db.commit()

    async def remove_working_day(self, date: str):
        """Полностью удалить рабочий день и все слоты"""
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем слоты
            await db.execute("DELETE FROM time_slots WHERE date = ?", (date,))
            # Удаляем дату из working_days
            await db.execute("DELETE FROM working_days WHERE date = ?", (date,))
            await db.commit()

    async def get_working_days(self, days_ahead: int = 30):
        async with aiosqlite.connect(self.db_path) as db:
            today = datetime.now(tz).date().isoformat()
            end = (datetime.now(tz) + timedelta(days=days_ahead)).date().isoformat()
            cursor = await db.execute(
                "SELECT date FROM working_days WHERE date >= ? AND date <= ? AND is_closed = 0 ORDER BY date",
                (today, end)
            )
            return [r[0] for r in await cursor.fetchall()]

    # ===== Time Slots =====
    async def add_time_slot(self, date: str, time: str, master_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO time_slots (date, time, master_id) VALUES (?, ?, ?)",
                (date, time, master_id)
            )
            await db.commit()

    async def remove_time_slot(self, date: str, time: str, master_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM time_slots WHERE date = ? AND time = ? AND master_id = ?",
                (date, time, master_id)
            )
            await db.commit()

    async def get_available_slots(self, date: str, master_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT time FROM time_slots WHERE date = ? AND master_id = ? AND is_booked = 0 ORDER BY time",
                (date, master_id)
            )
            return [r[0] for r in await cursor.fetchall()]

    async def book_slot(self, date: str, time: str, master_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE time_slots SET is_booked = 1, booked_by = ? WHERE date = ? AND time = ? AND master_id = ? AND is_booked = 0",
                (user_id, date, time, master_id)
            )
            await db.commit()
            return db.total_changes > 0

    async def release_slot(self, date: str, time: str, master_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE time_slots SET is_booked = 0, booked_by = NULL WHERE date = ? AND time = ? AND master_id = ?",
                (date, time, master_id)
            )
            await db.commit()

    async def get_all_masters(self):
        """Получить всех активных мастеров"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, name FROM masters WHERE is_active = 1 ORDER BY hall_id, id"
            )
            return await cursor.fetchall()

    # ===== Bookings =====
    async def create_booking(self, user_id: int, name: str, phone: str,
                            service_id: int, service_name: str,
                            hall_id: int, hall_name: str,
                            master_id: int, master_name: str,
                            date: str, time: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO bookings (user_id, name, phone, service_id, service_name,
                   hall_id, hall_name, master_id, master_name, date, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, name, phone, service_id, service_name, hall_id, hall_name, master_id, master_name, date, time)
            )
            await db.commit()
            return cursor.lastrowid

    async def cancel_booking(self, booking_id: int, user_id: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT date, time, user_id, hall_id, master_id FROM bookings WHERE id = ?",
                (booking_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            date, time, booked_uid, hall_id, master_id = row
            if user_id and booked_uid != user_id:
                return None
            await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            await db.execute(
                "UPDATE time_slots SET is_booked = 0, booked_by = NULL WHERE date = ? AND time = ? AND master_id = ?",
                (date, time, master_id)
            )
            await db.execute("DELETE FROM reminder_tasks WHERE booking_id = ?", (booking_id,))
            await db.commit()
            return {"date": date, "time": time}

    async def get_user_active_booking(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT id, date, time, service_name, hall_name, master_name FROM bookings
                   WHERE user_id = ? ORDER BY date DESC LIMIT 1""",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "date": row[1], "time": row[2], "service": row[3], "hall": row[4], "master": row[5]}
            return None

    async def get_booking(self, booking_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, user_id, name, phone, service_name, hall_id, master_id, date, time, reminder_sent
                FROM bookings WHERE id = ?
            """, (booking_id,))
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0], "user_id": row[1], "name": row[2],
                    "phone": row[3], "service": row[4], "hall_id": row[5],
                    "master_id": row[6], "date": row[7], "time": row[8], "reminder_sent": row[9]
                }
            return None

    async def get_bookings_for_date(self, date: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT id, user_id, name, phone, service_name, hall_id, master_id, time
                   FROM bookings WHERE date = ? ORDER BY time""",
                (date,)
            )
            return [
                {"id": r[0], "user_id": r[1], "name": r[2], "phone": r[3],
                 "service": r[4], "hall_id": r[5], "master_id": r[6], "time": r[7]}
                for r in await cursor.fetchall()
            ]

    # ===== Reminders =====
    async def add_reminder_task(self, booking_id: int, remind_at: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO reminder_tasks (booking_id, remind_at) VALUES (?, ?)",
                (booking_id, remind_at)
            )
            await db.commit()

    async def get_pending_reminders(self):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now(tz).isoformat()
            cursor = await db.execute("""
                SELECT rt.booking_id, b.user_id, b.name, b.service_name, b.date, b.time, rt.remind_at
                FROM reminder_tasks rt
                JOIN bookings b ON rt.booking_id = b.id
                WHERE rt.remind_at > ? AND b.reminder_sent = 0
            """, (now,))
            return await cursor.fetchall()

    async def mark_reminder_sent(self, booking_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE bookings SET reminder_sent = 1 WHERE id = ?", (booking_id,))
            await db.execute("DELETE FROM reminder_tasks WHERE booking_id = ?", (booking_id,))
            await db.commit()

    # ===== Отчёты =====
    async def get_monthly_report(self, year: int, month: int, hall_id: int = None):
        """Отчёт по залам и услугам за месяц
        
        Если hall_id не указан — общий отчёт по всем залам
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем все услуги с ценами
            cursor = await db.execute("SELECT id, name, price FROM services")
            services = {r[0]: {"name": r[1], "price": r[2]} for r in await cursor.fetchall()}
            
            # Получаем все залы
            cursor = await db.execute("SELECT id, name FROM halls")
            halls = {r[0]: r[1] for r in await cursor.fetchall()}
            
            # Получаем записи за месяц
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year+1}-01-01"
            else:
                end_date = f"{year}-{month+1:02d}-01"
            
            # Если указан hall_id — фильтруем по залу
            if hall_id:
                cursor = await db.execute("""
                    SELECT hall_id, service_id, COUNT(*) as count, 
                           SUM(COALESCE((SELECT price FROM services WHERE id = service_id), 0)) as total
                    FROM bookings 
                    WHERE date >= ? AND date < ? AND hall_id = ?
                    GROUP BY hall_id, service_id
                    ORDER BY service_id
                """, (start_date, end_date, hall_id))
            else:
                cursor = await db.execute("""
                    SELECT hall_id, service_id, COUNT(*) as count, 
                           SUM(COALESCE((SELECT price FROM services WHERE id = service_id), 0)) as total
                    FROM bookings 
                    WHERE date >= ? AND date < ?
                    GROUP BY hall_id, service_id
                    ORDER BY hall_id, service_id
                """, (start_date, end_date))
            
            rows = await cursor.fetchall()
            
            # Формируем отчёт
            report = {"halls": {}}
            for hall_id_row, service_id, count, total in rows:
                hall_name = halls.get(hall_id_row, "Неизвестно")
                if hall_name not in report["halls"]:
                    report["halls"][hall_name] = {"services": [], "hall_total": 0}
                
                service_info = services.get(service_id, {"name": "Неизвестно", "price": 0})
                report["halls"][hall_name]["services"].append({
                    "service": service_info["name"],
                    "count": count,
                    "total": total
                })
                report["halls"][hall_name]["hall_total"] += total
            
            report["grand_total"] = sum(h["hall_total"] for h in report["halls"].values())
            return report

    # ===== Чёрный список =====
    async def add_to_blacklist(self, user_id: int, reason: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO blacklist (user_id, reason, added_at) VALUES (?, ?, ?)",
                (user_id, reason, datetime.now(tz).isoformat())
            )
            await db.commit()

    async def remove_from_blacklist(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
            await db.commit()

    async def is_blacklisted(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT reason FROM blacklist WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_blacklist(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id, reason, added_at FROM blacklist ORDER BY added_at DESC")
            return await cursor.fetchall()

    # ===== Отзывы =====
    async def add_review(self, user_id: int, name: str, rating: int, text: str = "", booking_id: int = None):
        """Добавить отзыв"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO reviews (user_id, name, rating, text, booking_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, rating, text, booking_id)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_reviews(self, limit: int = 20, rating_filter: int = None):
        """Получить отзывы с фильтрацией"""
        async with aiosqlite.connect(self.db_path) as db:
            if rating_filter:
                cursor = await db.execute(
                    "SELECT id, user_id, name, rating, text, booking_id, created_at FROM reviews WHERE rating = ? ORDER BY created_at DESC LIMIT ?",
                    (rating_filter, limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT id, user_id, name, rating, text, booking_id, created_at FROM reviews ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            return await cursor.fetchall()

    async def get_average_rating(self, hall_id: int = None):
        """Получить средний рейтинг по залу или общий"""
        async with aiosqlite.connect(self.db_path) as db:
            if hall_id:
                cursor = await db.execute("""
                    SELECT AVG(r.rating) as avg_rating, COUNT(*) as count
                    FROM reviews r
                    JOIN bookings b ON r.booking_id = b.id
                    WHERE b.hall_id = ?
                """, (hall_id,))
            else:
                cursor = await db.execute("""
                    SELECT AVG(rating) as avg_rating, COUNT(*) as count FROM reviews
                """)
            row = await cursor.fetchone()
            if row and row[0]:
                return {"avg": round(row[0], 2), "count": row[1]}
            return {"avg": 0, "count": 0}

    async def get_rating_stats(self):
        """Статистика по оценкам (сколько каждой)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT rating, COUNT(*) as count FROM reviews GROUP BY rating ORDER BY rating DESC"
            )
            return {r[0]: r[1] for r in await cursor.fetchall()}

    async def delete_review(self, review_id: int):
        """Удалить отзыв"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
            await db.commit()

    async def has_user_reviewed(self, user_id: int, booking_id: int = None):
        """Проверил ли уже пользователь этот booking"""
        async with aiosqlite.connect(self.db_path) as db:
            if booking_id:
                cursor = await db.execute(
                    "SELECT id FROM reviews WHERE user_id = ? AND booking_id = ?",
                    (user_id, booking_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT id FROM reviews WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                    (user_id,)
                )
            row = await cursor.fetchone()
            return row is not None
