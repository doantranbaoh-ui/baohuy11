# commands.py
from aiogram import Router, types
from aiogram.filters import Command
from config import PRICE_PER_ACC, ADMINS
from database import ensure_user, get_balance, reduce_balance
from acc_manager import pop_acc, list_accs

router = Router()

# /start
@router.message(Command("start"))
async def start_cmd(msg: types.Message):
    ensure_user(msg.from_user.id)
    await msg.answer(
        "🎉 *SHOP ACC RANDOM 2K*\n\n"
        "📌 Lệnh người dùng:\n"
        "/balance - xem số dư\n"
        "/buy - mua acc giá 2.000đ\n"
        "/nap - hướng dẫn nạp tiền\n"
        "/pay <số tiền> - tạo bill chờ duyệt\n\n"
        "🔧 Admin:\n"
        "/addacc - thêm ACC vào kho\n"
        "/listacc - xem kho\n"
        "/soldacc - xem acc đã bán",
        parse_mode="Markdown"
    )

# /balance
@router.message(Command("balance"))
async def balance_cmd(msg: types.Message):
    bal = get_balance(msg.from_user.id)
    await msg.answer(f"💰 Số dư: *{bal}đ*", parse_mode="Markdown")

# /buy
@router.message(Command("buy"))
async def buy_cmd(msg: types.Message):
    uid = msg.from_user.id
    bal = get_balance(uid)

    if bal < PRICE_PER_ACC:
        return await msg.answer(f"❌ Không đủ tiền ({PRICE_PER_ACC}đ). Dùng /nap để nạp tiền")

    acc = pop_acc()
    if not acc:
        return await msg.answer("❌ Kho hết hàng, đợi admin thêm acc")

    ok = reduce_balance(uid, PRICE_PER_ACC)
    if not ok:
        return await msg.answer("⚠ Lỗi trừ tiền")

    await msg.answer(f"🎁 *Mua thành công!*\n\n🔐 Tài khoản của bạn:\n`{acc}`", parse_mode="Markdown")

    # Gửi thông báo admin
    for admin in ADMINS:
        try:
            await msg.bot.send_message(admin, f"🛒 User `{uid}` mua ACC - trừ {PRICE_PER_ACC}đ", parse_mode="Markdown")
        except:
            pass

# /listacc admin
@router.message(Command("listacc"))
async def listacc_cmd(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return
    data = list_accs()
    if not data:
        return await msg.answer("📦 Kho rỗng")
    text = "📦 ACC TRONG KHO:\n" + "\n".join(data[:50])
    await msg.answer(text)

# /addacc admin
@router.message(Command("addacc"))
async def addacc_cmd(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return
    await msg.answer("📥 Gửi danh sách ACC dạng text, mỗi dòng 1 acc.\nTự động thêm & lưu lại.")
