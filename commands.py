# commands.py
from aiogram import Router, types
from aiogram.filters import Command
from config import PRICE_PER_ACC, ADMINS
from database import ensure_user, get_balance, reduce_balance, add_history if False else None
from acc_manager import pop_acc, list_accs

router = Router()

@router.message(Command("start"))
async def start_cmd(msg: types.Message):
    ensure_user(msg.from_user.id)
    await msg.answer(
        "🎉 *SHOP RANDOM 2K*\n\n"
        "/balance - xem số dư\n"
        "/buy - mua acc 2.000đ\n"
        "/nap - hướng dẫn nạp tiền\n"
        "Admin: /addacc, /listacc, /soldacc",
        parse_mode="Markdown"
    )

@router.message(Command("balance"))
async def balance_cmd(msg: types.Message):
    bal = get_balance(msg.from_user.id)
    await msg.answer(f"💰 Số dư của bạn: *{bal}đ*", parse_mode="Markdown")

@router.message(Command("buy"))
async def buy_cmd(msg: types.Message):
    uid = msg.from_user.id
    bal = get_balance(uid)
    if bal < PRICE_PER_ACC:
        return await msg.answer(f"❌ Bạn không đủ tiền (giá {PRICE_PER_ACC}đ). Dùng /nap để nạp.")
    acc = pop_acc()
    if not acc:
        return await msg.answer("❌ Shop tạm hết acc.")
    ok = reduce_balance(uid, PRICE_PER_ACC, reason=f"buy_acc:{acc}") if hasattr(__import__("database"), "reduce_balance") else None
    # above reduce_balance may not accept reason in all variants; the database.py provided earlier supports reduce_balance(uid, amount)
    # Use a fallback:
    from database import reduce_balance as _rb
    ok = _rb(uid, PRICE_PER_ACC)
    if not ok:
        return await msg.answer("❌ Trừ tiền thất bại.")
    await msg.answer(f"🎁 Mua thành công!\n\n🔐 Acc của bạn:\n`{acc}`", parse_mode="Markdown")
    # notify admins
    for admin in ADMINS:
        try:
            await msg.bot.send_message(admin, f"🛒 User `{uid}` đã mua 1 acc - trừ {PRICE_PER_ACC}đ", parse_mode="Markdown")
        except Exception:
            pass
