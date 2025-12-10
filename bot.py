import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from commands import router as cmd_router
from nap import router as nap_router
from keep_alive import keep_alive

async def main():
    bot=Bot(TOKEN)
    dp=Dispatcher()

    dp.include_router(cmd_router)
    dp.include_router(nap_router)

    keep_alive()         # nếu chạy Render/Replit
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
