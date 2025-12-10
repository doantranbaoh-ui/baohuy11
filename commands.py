from aiogram import Router, types
from database import ensure_user, get_balance
from config import ADMINS

router = Router()

@router.message()
async def auto_register(msg: types.Message):
    ensure_user(msg.from_user.id)

@router.message(commands=["start"])
async def start_cmd(msg: types.Message):
    await msg.answer("🌟 SHOP BOT\n\n/nap - nạp tiền\n/mua - mua tài khoản\n/acc - xem danh sách hàng")

@router.message(commands=["balance"])
async def balance_cmd(msg: types.Message):
    bal = get_balance(msg.from_user.id)
    await msg.answer(f"💰 Số dư: {bal}đ")
