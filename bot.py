# ===============================
# BOT SHOP RANDOM 2K - AIROGRAM V3
# ===============================

import os
import json
import time
import shutil
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keep_alive import keep_alive  # chống sleep bot khi deploy

# ===============================
# CONFIG
# ===============================
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"   # <--- thay token
ADMIN_ID = 5736655322                                        # <--- ID admin

DATA_FOLDER = "data"
BACKUP_FOLDER = f"{DATA_FOLDER}/backup"
ACC_FILE = f"{DATA_FOLDER}/acc.txt"
SOLD_FILE = f"{DATA_FOLDER}/sold_acc.txt"
USER_DATA = f"{DATA_FOLDER}/users.json"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

bot = Bot(TOKEN)
dp = Dispatcher()

# ===============================
# USER SYSTEM
# ===============================
def load_users():
    if not os.path.exists(USER_DATA):
        save_users({})
        return {}
    try:
        return json.load(open(USER_DATA, "r", encoding="utf-8"))
    except:
        save_users({})
        return {}

def save_users(data):
    json.dump(data, open(USER_DATA, "w", encoding="utf-8"), indent=4, ensure_ascii=False)

users = load_users()

def get_balance(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}
    save_users(users)
    return users[uid]["balance"]

def add_balance(uid, amount):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}
    users[uid]["balance"] += amount
    save_users(users)

# ===============================
# ACC SYSTEM
# ===============================
def get_acc():
    if not os.path.exists(ACC_FILE):
        return None
    lines = [l.strip() for l in open(ACC_FILE, encoding="utf-8") if l.strip()]
    if not lines:
        return None
    acc = lines.pop(0)
    open(ACC_FILE, "w", encoding="utf-8").writelines([l+"\n" for l in lines])
    return acc

def save_sold_acc(acc):
    open(SOLD_FILE, "a", encoding="utf-8").write(acc+"\n")

def get_acc_list():
    return open(ACC_FILE,encoding="utf-8").read().splitlines() if os.path.exists(ACC_FILE) else []

def get_sold_acc_list():
    return open(SOLD_FILE,encoding="utf-8").read().splitlines() if os.path.exists(SOLD_FILE) else []

# ===============================
# BACKUP SYSTEM
# ===============================
def backup(file):
    if os.path.exists(file):
        t = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.basename(file)
        shutil.copy(file, f"{BACKUP_FOLDER}/{name}_{t}.bak")

async def daily_backup():
    while True:
        backup(USER_DATA)
        backup(ACC_FILE)
        backup(SOLD_FILE)
        await asyncio.sleep(86400)   # 24 giờ

# ===============================
# COMMANDS
# ===============================
@dp.message(Command("start"))
async def start(msg: types.Message):
    get_balance(msg.from_user.id)
    await msg.answer(
"🎉 *SHOP RANDOM 2K AUTO* 🔥\n\n"
"📌 /balance – xem số dư\n"
"📌 /buy – mua acc 2.000đ\n"
"📌 /nap – nạp tiền + gửi bill\n"
"📌 /addacc user|pass (admin)\n"
"📌 /listacc – xem acc chưa bán (admin)\n"
"📌 /soldacc – xem acc đã bán (admin)\n", parse_mode="Markdown"
)

@dp.message(Command("balance"))
async def balance(msg):
    await msg.answer(f"💰 Số dư hiện tại: *{get_balance(msg.from_user.id)}đ*", parse_mode="Markdown")

nap_requests = {}

@dp.message(Command("nap"))
async def nap(msg):
    uid = msg.from_user.id
    nap_requests[uid] = time.time()
    await msg.answer(
f"💳 *Hướng dẫn nạp tiền*\n\n"
f"🏦 MB Bank - STK: `0971487462`\n"
f"💬 Nội dung chuyển khoản: `NAP {uid}`\n"
f"⏳ Có 20 phút để gửi bill (ảnh chuyển khoản).", parse_mode="Markdown"
)

@dp.message(Command("buy"))
async def buy(msg):
    uid = msg.from_user.id
    if get_balance(uid) < 2000:
        return await msg.answer("❌ Không đủ tiền, dùng /nap để nạp!")
    acc = get_acc()
    if not acc:
        return await msg.answer("⛔ Shop tạm hết acc, quay lại sau!")
    add_balance(uid, -2000)
    save_sold_acc(acc)

    await msg.answer(
f"🎁 *MUA THÀNH CÔNG*\n\n🔐 Acc của bạn:\n`{acc}`\n\nChúc may mắn!",
parse_mode="Markdown"
)

@dp.message(Command("addacc"))
async def addacc(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        _, acc = msg.text.split(" ",1)
    except:
        return await msg.answer("❌ Dùng: /addacc user|pass")
    open(ACC_FILE,"a",encoding="utf-8").write(acc+"\n")
    await msg.answer(f"✔ Đã thêm acc:\n`{acc}`", parse_mode="Markdown")

@dp.message(Command("listacc"))
async def list_acc(msg):
    if msg.from_user.id != ADMIN_ID: return
    acc = get_acc_list()
    await msg.answer("📂 ACC Trong Kho:\n"+"\n".join(acc) if acc else "Trống kho.")

@dp.message(Command("soldacc"))
async def list_sold(msg):
    if msg.from_user.id != ADMIN_ID: return
    acc = get_sold_acc_list()
    await msg.answer("📦 ACC Đã Bán:\n"+"\n".join(acc) if acc else "Chưa có giao dịch.")

# ===============================
# HANDLE BILL PHOTO
# ===============================
@dp.message(F.photo)
async def bill(msg):
    uid = msg.from_user.id
    if uid not in nap_requests: 
        return await msg.answer("❌ Chưa /nap hoặc đã hết hạn.")
    if time.time() - nap_requests[uid] > 1200:
        del nap_requests[uid]
        return await msg.answer("⏳ Quá 20 phút, vui lòng /nap lại.")

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ DUYỆT", callback_data=f"ok_{uid}"),
        InlineKeyboardButton(text="❌ TỪ CHỐI", callback_data=f"no_{uid}")
    ]])

    await bot.send_message(ADMIN_ID,f"📩 Bill từ user `{uid}`",parse_mode="Markdown")
    await bot.send_photo(ADMIN_ID,msg.photo[-1].file_id,reply_markup=kb)
    await msg.answer("⏳ Bill đã gửi admin chờ duyệt...")
    del nap_requests[uid]

# ===============================
# CALLBACK
# ===============================
@dp.callback_query(F.data.startswith("ok_"))
async def ok(c):
    uid = int(c.data[3:])
    add_balance(uid,10000)
    await bot.send_message(uid,"🎉 Bill được duyệt! +10.000đ")
    await c.message.edit_caption("✔ ĐÃ DUYỆT BILL")
    await c.answer()

@dp.callback_query(F.data.startswith("no_"))
async def no(c):
    uid = int(c.data[3:])
    await bot.send_message(uid,"❌ Bill bị từ chối.")
    await c.message.edit_caption("❌ TỪ CHỐI BILL")
    await c.answer()

# ===============================
# RUN BOT
# ===============================
async def main():
    keep_alive()
    asyncio.create_task(daily_backup())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
