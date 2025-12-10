from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime,timedelta
from config import ADMIN_ID
from database import add_balance

router = Router()
nap_request = {}

@router.message(commands=["nap"])
async def nap_cmd(msg:types.Message):
    uid=msg.from_user.id
    nap_request[uid]=datetime.now()
    await msg.answer(
        f"💳 Nạp tiền\n"
        f"STK: 0971487462 - MB Bank\n"
        f"Nội dung: NAP {uid}\n"
        f"Tối thiểu 10k - Hiệu lực 20 phút\n"
        f"Gửi ảnh bill tại đây!"
    )

@router.message(lambda m:m.photo)
async def bill(msg:types.Message):
    uid=msg.from_user.id
    if uid not in nap_request: return await msg.answer("Bạn chưa dùng /nap")
    if datetime.now()>nap_request[uid]+timedelta(minutes=20):
        del nap_request[uid]
        return await msg.answer("Hết hạn 20 phút → /nap lại")

    kb=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✔ DUYỆT",callback_data=f"ok_{uid}"),
        InlineKeyboardButton(text="❌ TỪ CHỐI",callback_data=f"no_{uid}")
    ]])

    await msg.bot.send_photo(ADMIN_ID,msg.photo[-1].file_id,
        caption=f"Bill từ user {uid}",reply_markup=kb)
    await msg.answer("Đang chờ admin duyệt...")
    del nap_request[uid]

@router.callback_query(lambda q:q.data.startswith("ok_"))
async def accept(q:types.CallbackQuery):
    uid=int(q.data.split("_")[1])
    add_balance(uid,10000)
    await q.bot.send_message(uid,"+10.000đ – Bill duyệt!")
    await q.message.edit_caption("✔ ĐÃ DUYỆT")
    await q.answer()

@router.callback_query(lambda q:q.data.startswith("no_"))
async def deny(q:types.CallbackQuery):
    uid=int(q.data.split("_")[1])
    await q.bot.send_message(uid,"❌ Bill bị từ chối")
    await q.message.edit_caption("❌ ĐÃ TỪ CHỐI")
    await q.answer()
