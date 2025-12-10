import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from keep_alive import keep_alive  # Nếu bạn muốn chống sleep
from commands import router as commands_router
from nap import router as nap_router

# ==============================
# CHẠY BOT
# ==============================
async def main():
    print("🚀 Bot đang khởi động...")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Gắn module lệnh vào bot
    dp.include_router(commands_router)   # /start /buy /addacc /listacc ...
    dp.include_router(nap_router)        # /nap + xử lý bill duyệt

    # Chạy keep_alive nếu deploy Render/Replit
    try:
        keep_alive()
        print("🌍 Web server KeepAlive đã chạy...")
    except:
        print("⚠ Không tìm thấy keep_alive.py (bỏ qua nếu chạy VPS)")

    # Bắt đầu polling bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
