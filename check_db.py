import asyncio
from database.db import Database

async def check():
    db = Database('nail_bot.db')
    await db.init()
    
    halls = await db.get_halls()
    print("Залы:", halls)
    
    days = await db.get_working_days()
    print("Рабочие дни:", days)
    
    if days:
        date = days[0]
        slots1 = await db.get_available_slots(date, 1)
        slots2 = await db.get_available_slots(date, 2)
        print(f"Слоты на {date} зал 1 (Мужской): {slots1}")
        print(f"Слоты на {date} зал 2 (Женский): {slots2}")
        
        # Проверим все слоты
        import aiosqlite
        async with aiosqlite.connect('nail_bot.db') as db_conn:
            cursor = await db_conn.execute("SELECT * FROM time_slots WHERE date = ?", (date,))
            all_slots = await cursor.fetchall()
            print(f"Все слоты в БД на {date}: {all_slots}")

asyncio.run(check())
