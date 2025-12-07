#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot import types
import sqlite3
import random
import os
from keep_alive import keep_alive
import logging

# ==========================
# CẤU HÌNH
# ==========================
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"  # Thay bằng token của bạn
ADMIN_ID = 5736655322  # ID admin
PRICE_RANDOM_ACC = 2000  # Giá mỗi lượt random
ACC_FILE = "accs.txt"

# ==========================
# LOG DEBUG
# ==========================
logging.basicConfig(level=logging.DEBUG)
telebot.logger.setLevel(logging.DEBUG)

# ==========================
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ==========================
# DATABASE SỐ DƯ
# ==========================
def init_db():
    conn = sqlite3.connect("balance.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

init_db()

def get_balance(user_id):
    conn = sqlite3.connect("balance.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect("balance.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,balance) VALUES(?,0)", (user_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_balance(user_id, amount):
    bal = get_balance(user_id)
    if bal < amount:
        return False
    add_balance(user_id, -amount)
    return True

# ==========================
# RANDOM ACC
# ==========================
def random_acc_from_file():
    if not os.path.exists(ACC_FILE):
        return None
    with open(ACC_FILE, "r", encoding="utf-8") as f:
        accs = [line.strip() for line in f if line.strip()]
    if not accs:
        return None
    acc = random.choice(accs)
    accs.remove(acc)
    with open(ACC_FILE, "w", encoding="utf-8") as f:
        for a in accs:
            f.write(a + "\n")
    return acc

# ==========================
# HƯỚNG DẪN
# ==========================
HELP_TEXT = """
📘 *HƯỚNG DẪN SỬ DỤNG BOT*

🎲 /randomacc - Random ACC Liên Quân mất tiền mỗi lượt  
💳 /nap - Nạp tiền qua STK MB  
💰 /balance - Xem số dư hiện tại
"""

# ==========================
# START + MENU
# ==========================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎲 Random ACC", "💳 Nạp tiền")
    kb.row("💰 Số dư", "ℹ️ Hướng dẫn")
    bot.send_message(message.chat.id,
                     "Xin chào! 👋 Chọn thao tác bên dưới:",
                     reply_markup=kb)

# ==========================
# HELP
# ==========================
@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(message.chat.id, HELP_TEXT)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Hướng dẫn")
def help_button(message):
    bot.send_message(message.chat.id, HELP_TEXT)

# ==========================
# BALANCE
# ==========================
@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💰 Số dư")
def balance_cmd(message):
    bal = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f"💰 Số dư hiện tại: {bal}đ")

# ==========================
# NẠP TIỀN
# ==========================
pending_payments = {}  # user_id -> (file_id, amount)

@bot.message_handler(commands=["nap"])
@bot.message_handler(func=lambda m: m.text == "💳 Nạp tiền")
def nap_cmd(message):
    text = f"""
💳 *Hướng dẫn nạp tiền:*

• STK: `0971487462`  
• Ngân hàng: MB  
• Nội dung: `NAP-{message.from_user.id}`  
• Ghi rõ số tiền bạn nạp (VD: 10000, 50000,...)

📸 Gửi *ảnh bill* vào chat để admin duyệt.
"""
    bot.send_message(message.chat.id, text)

# ==========================
# NHẬN ẢNH BILL
# ==========================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    if message.caption:
        try:
            amount = int(message.caption.strip())
            pending_payments[user_id] = (message.photo[-1].file_id, amount)
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_{user_id}"),
                types.InlineKeyboardButton("❌ Từ chối", callback_data=f"reject_{user_id}")
            )
            bot.send_message(ADMIN_ID,
                             f"📸 Bill từ {user_id}\nSố tiền: {amount}đ",
                             reply_markup=markup)
            bot.send_message(user_id, "✅ Ảnh bill đã gửi cho admin duyệt.")
        except:
            bot.send_message(user_id, "❌ Gửi caption là số tiền nạp (ví dụ 10000).")
    else:
        bot.send_message(user_id, "❌ Vui lòng gửi số tiền nạp trong caption ảnh.")

# ==========================
# RANDOM ACC mất tiền
# ==========================
@bot.message_handler(commands=["randomacc"])
@bot.message_handler(func=lambda m: m.text == "🎲 Random ACC")
def randomacc_cmd(message):
    user_id = message.from_user.id
    bal = get_balance(user_id)
    if bal < PRICE_RANDOM_ACC:
        return bot.send_message(user_id,
                                f"❌ Bạn không đủ tiền để random!\n"
                                f"💰 Số dư hiện tại: {bal}đ\n"
                                f"💴 Giá mỗi lượt: {PRICE_RANDOM_ACC}đ\n"
                                f"👉 Hãy /nap để nạp tiền.")

    success = remove_balance(user_id, PRICE_RANDOM_ACC)
    if not success:
        return bot.send_message(user_id, "❌ Lỗi trừ tiền. Thử lại sau.")

    acc = random_acc_from_file()
    if acc is None:
        add_balance(user_id, PRICE_RANDOM_ACC)
        return bot.send_message(user_id, "❌ Kho acc đã hết. Đã hoàn lại tiền.")

    bot.send_message(user_id,
                     f"🎉 *Random thành công!*\n\n"
                     f"🔑 ACC của bạn:\n`{acc}`\n\n"
                     f"💸 Đã trừ: {PRICE_RANDOM_ACC}đ\n"
                     f"💰 Số dư còn lại: {get_balance(user_id)}đ")

# ==========================
# ADMIN DUYỆT BILL
# ==========================
@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def admin_approve(call):
    user_id = int(call.data.split("_")[1])
    if call.from_user.id != ADMIN_ID:
        return
    if call.data.startswith("approve_"):
        if user_id in pending_payments:
            _, amount = pending_payments.pop(user_id)
            add_balance(user_id, amount)
            bot.send_message(user_id, f"✅ Admin đã duyệt. Số dư cộng {amount}đ.")
            bot.edit_message_text("✅ Đã duyệt thanh toán", call.message.chat.id, call.message.message_id)
    elif call.data.startswith("reject_"):
        if user_id in pending_payments:
            pending_payments.pop(user_id)
            bot.send_message(user_id, f"❌ Thanh toán bị từ chối. Vui lòng thử lại.")
            bot.edit_message_text("❌ Đã từ chối thanh toán", call.message.chat.id, call.message.message_id)

# ==========================
# ADMIN THÊM ACC
# ==========================
@bot.message_handler(commands=["addacc"])
def addacc_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "⛔ Bạn không có quyền dùng lệnh này!")
    try:
        acc = message.text.split(" ", 1)[1].strip()
    except:
        return bot.send_message(message.chat.id, "❗ Dùng cú pháp: /addacc account|password")
    with open(ACC_FILE, "a", encoding="utf-8") as f:
        f.write(acc + "\n")
    bot.send_message(message.chat.id, f"✅ Đã thêm ACC:\n`{acc}`")

# ==========================
# CHẠY BOT VỚI KEEP_ALIVE
# ==========================
keep_alive()  # web server giữ bot sống
print("Bot đang chạy...")
try:
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
except Exception as e:
    logging.exception("Bot gặp lỗi, khởi động lại...")
