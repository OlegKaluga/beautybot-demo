import sqlite3

conn = sqlite3.connect("nail_bot.db")
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Таблицы:", tables)

# Проверка таблицы reviews
if "reviews" in tables:
    cursor = conn.execute("SELECT * FROM reviews LIMIT 5")
    reviews = cursor.fetchall()
    print("\nОтзывы:", reviews if reviews else "Пока нет отзывов")
else:
    print("\nТаблица reviews ещё не создана")

conn.close()
