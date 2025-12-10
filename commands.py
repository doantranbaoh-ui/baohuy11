from aiogram import Router, types
from database import get_balance,add_balance
from acc_manager import sale_acc,get_acc_list,get_sold_list,add_acc
from config import ADMIN_ID

router = Router()

@router.message(commands=["start"])
async def start(msg:types.Message):
    await msg.answer("SHOP RANDOM 2K AUTO\n/balance\n/buy\n/nap\n/addacc(admin)")

@router.message(commands=["balance"])
async def bal(msg):
    await msg.answer(f"Số dư: {get_balance(msg.from_user.id)}đ")

@router.message(commands=["buy"])
async def buy(msg):
    if get_balance(msg.from_user.id)<2000:
        return await msg.answer("Không đủ tiền /nap")
    acc=sale_acc()
    if not acc: return await msg.answer("Hết acc")
    add_balance(msg.from_user.id,-2000)
    await msg.answer(f"Mua thành công:\n`{acc}`",parse_mode="Markdown")

@router.message(commands=["addacc"])
async def addacc(msg):
    if msg.from_user.id!=ADMIN_ID:return
    try:
        _,acc = msg.text.split(" ",1)
    except: return await msg.answer("/addacc user:pass")
    add_acc(acc)
    await msg.answer("Đã thêm")

@router.message(commands=["listacc"])
async def listacc(msg):
    if msg.from_user.id!=ADMIN_ID:return
    a=get_acc_list()
    await msg.answer("Acc:\n"+"\n".join(a))

@router.message(commands=["soldacc"])
async def sold(msg):
    if msg.from_user.id!=ADMIN_ID:return
    a=get_sold_list()
    await msg.answer("Đã bán:\n"+"\n".join(a))
