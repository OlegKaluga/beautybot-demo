#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт миграции базы данных для beautybot_lite

Изменения:
- Добавлена таблица masters (мастера)
- Таблица time_slots теперь привязана к master_id (вместо hall_id)
- Таблица bookings теперь содержит master_id и master_name
- Залы переименованы: "Стрижки" (2 мастера), "Ногти" (1 мастер)
"""

import sqlite3
import os
import sys
from datetime import datetime

# Устанавливаем кодировку UTF-8 для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DB_PATH = "nail_bot.db"

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), DB_PATH)
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("Сначала запустите бота для создания базы данных.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🔄 Начало миграции...")
        
        # 1. Создаём таблицу masters
        print("📝 Создание таблицы masters...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hall_id INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (hall_id) REFERENCES halls(id)
            )
        """)
        
        # 2. Проверяем, есть ли уже мастера
        cursor.execute("SELECT COUNT(*) FROM masters")
        masters_count = cursor.fetchone()[0]
        
        if masters_count == 0:
            print("👥 Добавление мастеров по умолчанию...")
            # Зал 1 (Стрижки) — 2 мастера
            # Зал 2 (Ногти) — 1 мастер
            cursor.execute("""
                INSERT INTO masters (name, hall_id, is_active) VALUES
                ('Мастер 1', 1, 1),
                ('Мастер 2', 1, 1),
                ('Мастер (ногти)', 2, 1)
            """)
        
        # 3. Обновляем названия залов
        print("🏷 Обновление названий залов...")
        cursor.execute("UPDATE halls SET name = 'Стрижки' WHERE id = 1")
        cursor.execute("UPDATE halls SET name = 'Ногти' WHERE id = 2")
        
        # 4. Обновляем услуги (привязываем к залам правильно)
        print("💇 Обновление услуг...")
        cursor.execute("DELETE FROM services")
        cursor.execute("""
            INSERT INTO services (name, hall_id, price, duration) VALUES
            ('Стрижка', 1, 800, 45),
            ('Стрижка бороды', 1, 500, 30),
            ('Комплекс (стрижка + борода)', 1, 1200, 75),
            ('Маникюр', 2, 1200, 90),
            ('Педикюр', 2, 1500, 90),
            ('Покрытие гель-лак', 2, 1800, 120),
            ('Дизайн ногтей', 2, 500, 30)
        """)
        
        # 5. Проверяем структуру time_slots
        print("⏰ Проверка таблицы time_slots...")
        cursor.execute("PRAGMA table_info(time_slots)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        
        if 'hall_id' in columns and 'master_id' not in columns:
            print("🔄 Миграция time_slots...")
            # Создаём новую таблицу с правильной структурой
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS time_slots_new (
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
            
            # Копируем данные, распределяя по мастерам (для каждого зала создаём слоты для всех мастеров)
            cursor.execute("SELECT DISTINCT date, time, hall_id, is_booked, booked_by FROM time_slots")
            old_slots = cursor.fetchall()
            
            for date, time, hall_id, is_booked, booked_by in old_slots:
                # Для зала 1 (стрижки) создаём слоты для мастеров 1 и 2
                # Для зала 2 (ногти) создаём слот для мастера 3
                if hall_id == 1:
                    for master_id in [1, 2]:
                        cursor.execute(
                            "INSERT OR IGNORE INTO time_slots_new (date, time, master_id, is_booked, booked_by) VALUES (?, ?, ?, ?, ?)",
                            (date, time, master_id, is_booked, booked_by)
                        )
                else:
                    cursor.execute(
                        "INSERT OR IGNORE INTO time_slots_new (date, time, master_id, is_booked, booked_by) VALUES (?, ?, ?, ?, ?)",
                        (date, time, 3, is_booked, booked_by)
                    )
            
            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE time_slots")
            cursor.execute("ALTER TABLE time_slots_new RENAME TO time_slots")
        
        # 6. Проверяем структуру bookings
        print("📋 Проверка таблицы bookings...")
        cursor.execute("PRAGMA table_info(bookings)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        
        if 'master_id' not in columns:
            print("🔄 Миграция bookings...")
            # Добавляем новые колонки
            cursor.execute("ALTER TABLE bookings ADD COLUMN master_id INTEGER")
            cursor.execute("ALTER TABLE bookings ADD COLUMN master_name TEXT")
            
            # Устанавливаем master_id по умолчанию для существующих записей
            # Для зала 1 (стрижки) — мастер 1, для зала 2 (ногти) — мастер 3
            cursor.execute("""
                UPDATE bookings 
                SET master_id = CASE 
                    WHEN hall_id = 1 THEN 1 
                    WHEN hall_id = 2 THEN 3 
                END
                WHERE master_id IS NULL
            """)
            
            # Обновляем master_name
            cursor.execute("""
                UPDATE bookings 
                SET master_name = (SELECT name FROM masters WHERE masters.id = bookings.master_id)
                WHERE master_name IS NULL
            """)
        
        # 7. Пересоздаём слоты для всех мастеров
        print("📅 Пересоздание слотов...")
        cursor.execute("SELECT DISTINCT date FROM time_slots")
        dates = [row[0] for row in cursor.fetchall()]
        
        # Очищаем старые слоты
        cursor.execute("DELETE FROM time_slots")
        
        # Создаём слоты 10:00-19:00 для каждого мастера на каждый день
        for date in dates:
            for master_id in [1, 2, 3]:  # 3 мастера
                for hour in range(10, 20):
                    time_str = f"{hour:02d}:00"
                    cursor.execute(
                        "INSERT OR IGNORE INTO time_slots (date, time, master_id) VALUES (?, ?, ?)",
                        (date, time_str, master_id)
                    )
        
        conn.commit()
        print("✅ Миграция завершена успешно!")
        print("\n📊 Структура после миграции:")
        print("  Залы: Стрижки (id=1), Ногти (id=2)")
        print("  Мастера: Мастер 1 (стрижки), Мастер 2 (стрижки), Мастер (ногти)")
        print(f"  Дней с слотами: {len(dates)}")
        print(f"  Всего слотов: {len(dates) * 3 * 10}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
