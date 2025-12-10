from aiogram import Router, types
from config import ADMINS
from database import get_balance, add_balance, add_history

router = Router()

ACC_FILE = "data/acc.txt"
SOLD = "data/sold_acc.txt"

@router.message(commands=["addacc"])
async def add_acc(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return await msg.answer("Bạn không phải admin")
    acc = msg.text.replace("/addacc ", "")
    with open(ACC_FILE, "a") as f: f.write(acc+"\n")
    await msg.answer("✔ Đã thêm acc")

@router.message(commands=["acc"])
async def list_acc(msg: types.Message):
    if not open(ACC_FILE).read().strip():
        return await msg.answer("⚠ Hết hàng")
    await msg.answer(open(ACC_FILE).read())

@router.message(commands=["mua"])
async def buy(msg: types.Message):
    price = 10000
    bal = get_balance(msg.from_user.id)
    if bal < price: return await msg.answer("❌ Không đủ tiền")

    lines = open(ACC_FILE).read().splitlines()
    acc = lines[0]
    open(ACC_FILE, "w").write("\n".join(lines[1:]))
    open(SOLD, "a").write(acc+"\n")
    add_balance(msg.from_user.id, -price)
    add_history(msg.from_user.id, f"Mua acc {acc}")
    await msg.answer(f"🛒 Acc của bạn:\n`{acc}`", parse_mode="markdown")
