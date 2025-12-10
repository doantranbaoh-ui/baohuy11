# nap.py
import os
import json
import time
from typing import Optional, Dict, Any
from aiogram import Router, types
from aiogram.filters import Command, Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMINS, PENDING_FILE
from database import add_balance, ensure_user

router = Router()

# ensure pending file exists
os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
if not os.path.exists(PENDING_FILE):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def _load_pending() -> Dict[str, Any]:
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_pending(d: Dict[str, Any]):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def create_request(user_id: int, amount: int) -> str:
    pending = _load_pending()
    rid = str(int(time.time() * 1000))
    pending[rid] = {
        "user_id": user_id,
        "amount": int(amount),
        "ts": time.time(),
        "photo": None
    }
    _save_pending(pending)
    return rid

def attach_photo_to_latest(user_id: int, file_id: str) -> Optional[str]:
    pending = _load_pending()
    # get latest req for user
    items = [(rid, v) for rid, v in pending.items() if v["user_id"] == user_id]
    if not items:
        return None
    items.sort(key=lambda x: x[1]["ts"], reverse=True)
    rid = items[0][0]
    pending[rid]["photo"] = file_id
    _save_pending(pending)
    return rid

def pop_request(rid: str) -> Optional[Dict[str, Any]]:
    pending = _load_pending()
    data = pending.pop(rid, None)
    _save_pending(pending)
    return data

@router.message(Command("nap"))
async def cmd_nap(msg: types.Message):
    await msg.answer(
        "💳 *Hướng dẫn nạp tiền*\n\n"
        "• Chuyển khoản: `MB - 0971487462`\n"
        f"• Nội dung: `NAP {msg.from_user.id}`\n\n"
        "Sau khi chuyển hãy dùng: `/pay <số tiền>` (ví dụ: `/pay 20000`)\n"
        "Hoặc gửi ảnh bill trực tiếp để attach vào yêu cầu (nếu đã dùng /pay).",
        parse_mode="Markdown"
    )

@router.message(Command("pay"))
async def cmd_pay(msg: types.Message):
    parts = msg.text.strip().split()
    if len(parts) < 2:
        return await msg.answer("❌ Dùng: /pay SOTIEN (ví dụ: /pay 20000)")
    try:
        amount = int(parts[1])
    except:
        return await msg.answer("❌ Số tiền không hợp lệ.")
    uid = msg.from_user.id
    ensure_user(uid)
    rid = create_request(uid, amount)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ DUYỆT", callback_data=f"nap_ok:{rid}"),
            InlineKeyboardButton("❌ TỪ CHỐI", callback_data=f"nap_no:{rid}")
        ]
    ])

    caption = (f"📩 *YÊU CẦU NẠP*\n\n"
               f"👤 User: `{msg.from_user.full_name}`\n"
               f"🆔 `{uid}`\n"
               f"💰 *{amount}đ*\n"
               f"ReqID: `{rid}`\n\n"
               "Attach ảnh hoặc bấm DUYỆT/TỪ CHỐI.")
    for admin in ADMINS:
        try:
            await msg.bot.send_message(admin, caption, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass

    await msg.answer("📤 Bill đã gửi admin, vui lòng chờ duyệt. (Bạn có thể gửi ảnh bill nếu muốn)")

@router.message(lambda m: m.photo and True)
async def photo_attach(msg: types.Message):
    # If user has any pending request, attach to latest
    uid = msg.from_user.id
    file_id = msg.photo[-1].file_id
    rid = attach_photo_to_latest(uid, file_id)
    if not rid:
        return await msg.answer("Bạn chưa có yêu cầu nạp. Dùng /pay SOTIEN trước hoặc /nap để xem hướng dẫn.")
    # Send photo to admins with same buttons
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ DUYỆT", callback_data=f"nap_ok:{rid}"),
            InlineKeyboardButton("❌ TỪ CHỐI", callback_data=f"nap_no:{rid}")
        ]
    ])
    caption = f"📸 Bill từ user `{uid}` — ReqID: `{rid}`"
    for admin in ADMINS:
        try:
            await msg.bot.send_photo(admin, file_id, caption=caption, reply_markup=kb)
        except Exception:
            pass
    await msg.answer("✅ Ảnh bill đã gửi admin. Vui lòng chờ duyệt.")

# CALLBACKS handled here to avoid circular imports
@router.callback_query(Text(startswith="nap_ok:"))
async def cb_accept(query: types.CallbackQuery):
    rid = query.data.split(":", 1)[1]
    req = _load_pending().get(rid)
    if not req:
        await query.answer("Yêu cầu không tồn tại hoặc đã xử lý.", show_alert=True)
        return
    user_id = int(req["user_id"])
    amount = int(req["amount"])
    add_balance(user_id, amount, reason=f"nap_approved_by_{query.from_user.id}")
    pop_request(rid)
    # edit admin message and notify user
    try:
        await query.message.edit_text((query.message.text or "") + "\n\n✅ ĐÃ DUYỆT")
    except Exception:
        pass
    try:
        await query.bot.send_message(user_id, f"🎉 Bill của bạn đã được duyệt! +{amount}đ")
    except Exception:
        pass
    await query.answer("Đã duyệt")

@router.callback_query(Text(startswith="nap_no:"))
async def cb_reject(query: types.CallbackQuery):
    rid = query.data.split(":", 1)[1]
    req = _load_pending().get(rid)
    if not req:
        await query.answer("Yêu cầu không tồn tại hoặc đã xử lý.", show_alert=True)
        return
    user_id = int(req["user_id"])
    pop_request(rid)
    try:
        await query.message.edit_text((query.message.text or "") + "\n\n❌ ĐÃ TỪ CHỐI")
    except Exception:
        pass
    try:
        await query.bot.send_message(user_id, "❌ Bill của bạn đã bị từ chối bởi admin.")
    except Exception:
        pass
    await query.answer("Đã từ chối")
