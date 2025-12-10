from aiogram import Router, types
from config import ADMINS
from database import add_balance, add_history

router = Router()

@router.message(commands=["nap"])
async def nap(msg: types.Message):
    await msg.answer("📤 Gửi ảnh bill chuyển khoản để nạp")

@router.message(content_types=["photo"])
async def bill(msg: types.Message):
    caption = f"User {msg.from_user.id} gửi yêu cầu nạp!"
    kb = [
        [types.InlineKeyboardButton(text="Duyệt +10k", callback_data=f"duyet:{msg.from_user.id}:10000")],
        [types.InlineKeyboardButton(text="Từ Chối", callback_data=f"cancel:{msg.from_user.id}")]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)

    for admin in ADMINS:
        await msg.bot.send_photo(admin, msg.photo[-1].file_id, caption=caption, reply_markup=markup)

    await msg.answer("⏳ Bill đã gửi admin duyệt")

@router.callback_query(lambda c: c.data.startswith("duyet"))
async def approve(call: types.CallbackQuery):
    _, uid, amount = call.data.split(":")
    amount = int(amount)
    add_balance(uid, amount)
    add_history(uid, f"+{amount}đ nạp thành công")
    await call.bot.send_message(uid, f"💳 Nạp {amount}đ thành công!")
    await call.answer("Đã duyệt")

@router.callback_query(lambda c: c.data.startswith("cancel"))
async def reject(call: types.CallbackQuery):
    _, uid = call.data.split(":")
    await call.bot.send_message(uid, "❌ Bill bị từ chối")
    await call.answer("Đã từ chối")
