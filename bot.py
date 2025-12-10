import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from config import TOKEN, ADMIN_ID     # QUAN TRỌNG – đã fix đúng như lỗi bạn gặp

# Load Router từ file khác
from commands import router as commands_router
from nap import router as nap_router
from acc_manager import router as acc_router

from keep_alive import keep_alive


bot = Bot(token=TOKEN)
dp = Dispatcher()

# Đăng ký router
dp.include_router(commands_router)
dp.include_router(nap_router)
dp.include_router(acc_router)


# ================ BOT START ==================
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Chào bạn!\n"
        "Bot shop random auto\n"
        "Menu lệnh:\n"
        "/buy - mua acc\n"
        "/balance - xem số dư\n"
        "/nap - gửi yêu cầu nạp tiền\n"
        "/stock - xem số acc còn lại\n\n"
        f"Admin: {ADMIN_ID}"
    )


async def main():
    keep_alive()  # nếu deploy Render thì giữ bot online
    print("BOT STARTED!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
