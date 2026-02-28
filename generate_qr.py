import qrcode
from PIL import Image
import sys

# Ссылка на бота
BOT_USERNAME = "BotMyBeautySalon_Bot"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"

# Создаём QR-код
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=10,
    border=4,
)
qr.add_data(BOT_LINK)
qr.make(fit=True)

# Генерируем изображение с цветами
img = qr.make_image(fill_color="#2AABEE", back_color="white")

# Сохраняем
output_path = "qr_bot.png"
img.save(output_path)

# Вывод без эмодзи для Windows
print(f"QR-code created: {output_path}")
print(f"Link: {BOT_LINK}")
print(f"\nOpen file in Explorer:")
print(f"   C:\\Users\\Олег\\beautybot_lite\\{output_path}")

sys.stdout.flush()
