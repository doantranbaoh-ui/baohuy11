import os
import json
import time
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive  # chống sleep bot

# ============================
# CONFIG
# ============================
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"  # <-- Thay bằng token của bạn
ADMIN_ID = 5736655322
DATA_FOLDER = "data"
ACC_FILE = os.path.join(DATA_FOLDER, "acc.txt")
SOLD_FILE = os.path.join(DATA_FOLDER, "sold_acc.txt")
USER_DATA = os.path.join(DATA_FOLDER, "users.json")

os.makedirs(DATA_FOLDER, exist_ok=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ============================
# USER DATABASE
# ============================
def load_users():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        return {}
    if os.stat(USER_DATA).st_size == 0:
        return {}
    with open(USER_DATA, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            with open(USER_DATA, "w", encoding="utf-8") as fw:
                json.dump({}, fw, indent=4)
            return {}

def save_users(data):
    with open(USER_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

users = load_users()

def get_balance(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}  # tự động tạo user mới
        save_users(users)
    return users[uid]["balance"]

def add_balance(uid, amount):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}  # tự động tạo user mới
    users[uid]["balance"] += amount
    save_users(users)

# ============================
# ACC SYSTEM
# ============================
def get_acc():
    if not os.path.exists(ACC_FILE):
        return None
    with open(ACC_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None
    acc = lines[0]
    with open(ACC_FILE, "w", encoding="utf-8") as f:
        f.writelines(line + "\n" for line in lines[1:])
    return acc

def save_sold_acc(acc):
    with open(SOLD_FILE, "a", encoding="utf-8") as f:
        f.write(acc + "\n")

def get_acc_list():
    if not os.path.exists(ACC_FILE):
        return []
    with open(ACC_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_sold_acc_list():
    if not os.path.exists(SOLD_FILE):
        return []
    with open(SOLD_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# ============================
# NAP SYSTEM
# ============================
nap_requests = {}

# ============================
# COMMANDS
# ============================
@dp.message()
async def handle_message(msg: types.Message):
    uid = msg.from_user.id
    text = msg.text or ""

    if text.startswith("/start"):
        _ = get_balance(uid)  # tự động tạo user mới nếu chưa có
        await msg.answer(
            "🎉 *SHOP RANDOM 2K AUTO*\n\n"
            "Lệnh sử dụng:\n"
            "📌 /balance – xem số dư\n"
            "📌 /buy – mua acc 2.000đ\n"
            "📌 /nap – hướng dẫn nạp tiền (20 phút hiệu lực)\n"
            "📌 /addacc – admin thêm acc\n"
            "📌 /listacc – xem acc chưa bán (admin)\n"
            "📌 /soldacc – xem acc đã bán (admin)\n",
            parse_mode="Markdown"
        )
        return

    if text.startswith("/balance"):
        bal = get_balance(uid)
        await msg.answer(f"💰 Số dư của bạn: *{bal}đ*", parse_mode="Markdown")
        return

    if text.startswith("/nap"):
        nap_requests[uid] = time.time()
        await msg.answer(
            f"💳 *HƯỚNG DẪN NẠP TIỀN*\n\n"
            f"- STK: `0971487462`\n"
            f"- Ngân hàng: MB Bank\n"
            f"- Nội dung chuyển khoản: `NAP {uid}`\n"
            f"- Số tiền tối thiểu: *10.000đ*\n\n"
            f"📸 Bạn có 20 phút để gửi ảnh bill.",
            parse_mode="Markdown"
        )
        return

    if text.startswith("/buy"):
        bal = get_balance(uid)
        if bal < 2000:
            return await msg.answer("❌ Bạn không đủ tiền. Gõ /nap để nạp thêm.")
        acc = get_acc()
        if not acc:
            return await msg.answer("❌ SHOP HẾT ACC.\nVui lòng quay lại sau!")
        add_balance(uid, -2000)
        save_sold_acc(acc)
        await msg.answer(
            f"🎁 *MUA THÀNH CÔNG!*\n\n"
            f"🔐 Acc của bạn:\n`{acc}`\n\n"
            f"Chúc bạn may mắn!",
            parse_mode="Markdown"
        )
        return

    if text.startswith("/addacc") and uid == ADMIN_ID:
        try:
            _, acc_raw = text.split(" ", 1)
        except:
            return await msg.answer("❌ Sai cú pháp.\nDùng: /addacc user|pass")
        with open(ACC_FILE, "a", encoding="utf-8") as f:
            f.write(acc_raw.strip() + "\n")
        await msg.answer(f"✅ Đã thêm acc:\n`{acc_raw}`", parse_mode="Markdown")
        return

    if text.startswith("/listacc") and uid == ADMIN_ID:
        accs = get_acc_list()
        if not accs:
            return await msg.answer("📂 Kho acc trống!")
        await msg.answer("📂 Acc chưa bán:\n" + "\n".join(accs))
        return

    if text.startswith("/soldacc") and uid == ADMIN_ID:
        accs = get_sold_acc_list()
        if not accs:
            return await msg.answer("📂 Chưa có acc nào bán!")
        await msg.answer("📂 Acc đã bán:\n" + "\n".join(accs))
        return

# ============================
# HANDLE PHOTO (BILL)
# ============================
@dp.message(content_types=types.ContentType.PHOTO)
async def handle_photo(msg: types.Message):
    uid = msg.from_user.id
    now = time.time()
    if uid not in nap_requests:
        return await msg.answer("❌ Bạn chưa tạo lệnh /nap hoặc lệnh đã hết hạn.")
    if now - nap_requests[uid] > 20*60:
        del nap_requests[uid]
        return await msg.answer("❌ Lệnh nạp đã quá 20 phút, vui lòng tạo lại lệnh /nap.")

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ DUYỆT", callback_data=f"accept_{uid}"),
        InlineKeyboardButton("❌ TỪ CHỐI", callback_data=f"deny_{uid}")
    )

    await bot.send_message(ADMIN_ID, f"📨 *Có bill nạp từ user:* `{uid}`", parse_mode="Markdown")
    await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption="👉 Chọn hành động:", reply_markup=kb)
    await msg.answer("⏳ Bill của bạn đã gửi cho admin, vui lòng đợi duyệt.")
    del nap_requests[uid]

# ============================
# CALLBACK QUERY (ADMIN DUYỆT/TỪ CHỐI)
# ============================
@dp.callback_query(lambda c: c.data.startswith("accept_"))
async def accept_bill(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    add_balance(uid, 10000)
    await bot.send_message(uid, "🎉 *Bill của bạn đã được duyệt! +10.000đ*", parse_mode="Markdown")
    await callback.message.edit_caption("✅ ĐÃ DUYỆT")
    await callback.answer("Đã duyệt.")

@dp.callback_query(lambda c: c.data.startswith("deny_"))
async def deny_bill(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    await bot.send_message(uid, "❌ Bill của bạn đã bị từ chối.")
    await callback.message.edit_caption("❌ ĐÃ TỪ CHỐI")
    await callback.answer("Đã từ chối.")

# ============================
# RUN BOT
# ============================
async def main():
    keep_alive()  # chống sleep
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
