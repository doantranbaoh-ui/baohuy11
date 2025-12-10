# bot.py
import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from commands import router as commands_router
from acc_manager import router as acc_router  # note: acc_manager also exposes router for admin commands
from nap import router as nap_router
from keep_alive import keep_alive

async def main():
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Please edit config.py and set TOKEN.")
        return

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(commands_router)
    dp.include_router(acc_router)
    dp.include_router(nap_router)

    keep_alive()
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
