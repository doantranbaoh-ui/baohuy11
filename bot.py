import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from config import TOKEN, ADMINS
from commands import router as commands_router
from nap import router as nap_router
from acc_manager import router as acc_router
from keep_alive import keep_alive

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Đăng ký router đã tách file
dp.include_router(commands_router)
dp.include_router(nap_router)
dp.include_router(acc_router)

# Lệnh /start cơ bản (nếu chưa có trong commands.py)
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🔰 *Chào mừng bạn đến SHOP!* \n"
        "📌 Dùng lệnh /menu để xem chức năng\n"
        "💳 Dùng /nap để nạp tiền\n"
        "🛒 Dùng /buy để mua tài khoản\n"
        , parse_mode="Markdown"
    )


async def main():
    print("🚀 Bot đang chạy...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    keep_alive()   # bật ping để không tắt Render
    asyncio.run(main())
