#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
bot.py - Full Telegram shop bot (user + admin)
Features:
 - /start, /help, user menu (random buy, balance, my acc, dice, slot, redeem, nap)
 - Admin: addacc, stock, listacc, delacc, delall, export, adduid, deluid, gcnew, gclist, approve nap bills
 - DB with sqlite3, commits after every write
 - Proper locking to avoid 'database is locked'
 - Handles image uploads (bills) for /nap
 - Robust error logging and auto-restart polling loop
"""

import os
import time
import sqlite3
import threading
import random
import string
import secrets
import traceback
from datetime import datetime
from io import BytesIO

import telebot
from telebot import types

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"  # <- <-- Thay token ở đây
OWNER_ID = 5736655322  # <-- Thay user_id của bạn (số nguyên)
PRICE_RANDOM = 2000
DB_FILE = "data.db"
KEEP_ALIVE = True  # nếu bạn có keep_alive server, set True và import keep_alive

# ================= BOT INIT =================
if not TOKEN:
    raise ValueError("Bạn chưa đặt TOKEN. Mở file và gán TOKEN = '...'")

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
db_lock = threading.Lock()

def init_db():
    with db_lock:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acc TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS purchases(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            acc TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS giftcode(
            code TEXT PRIMARY KEY,
            amount INTEGER,
            used_by TEXT DEFAULT ''
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS admins(
            user_id TEXT PRIMARY KEY,
            level INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            file_id TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )""")
        # ensure owner is admin (level 3)
        c.execute("INSERT OR IGNORE INTO admins(user_id, level) VALUES (?,?)", (str(OWNER_ID), 3))
        conn.commit()

init_db()

# ================= UTILITIES =================
def log_exc(tag="ERR"):
    print(f"\n--- {tag} ---")
    traceback.print_exc()
    print("-----------\n")

def db_commit_exec(query, params=(), fetch=False):
    try:
        with db_lock:
            c.execute(query, params)
            conn.commit()
            if fetch:
                return c.fetchall()
    except Exception:
        log_exc("DB_EXEC")
        return None

def ensure_user(uid):
    try:
        db_commit_exec("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (str(uid),))
    except Exception:
        log_exc("ensure_user")

def get_balance(uid):
    ensure_user(uid)
    r = db_commit_exec("SELECT balance FROM users WHERE user_id=?", (str(uid),), fetch=True)
    try:
        return int(r[0][0]) if r else 0
    except Exception:
        log_exc("get_balance")
        return 0

def add_money(uid, amount):
    try:
        ensure_user(uid)
        db_commit_exec("UPDATE users SET balance=balance+? WHERE user_id=?", (int(amount), str(uid)))
    except Exception:
        log_exc("add_money")

def deduct(uid, amount):
    try:
        bal = get_balance(uid)
        if bal < amount:
            return False
        db_commit_exec("UPDATE users SET balance=balance-? WHERE user_id=?", (int(amount), str(uid)))
        return True
    except Exception:
        log_exc("deduct")
        return False

def get_role(uid):
    try:
        r = db_commit_exec("SELECT level FROM admins WHERE user_id=?", (str(uid),), fetch=True)
        return int(r[0][0]) if r else 0
    except Exception:
        log_exc("get_role")
        return 0

def is_owner(uid): return get_role(uid) == 3
def is_admin(uid): return get_role(uid) >= 2
def is_support(uid): return get_role(uid) >= 1

def make_code(n=10):
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))

# ================= UI / MENU =================
def send_user_menu(chat_id):
    try:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("🛍 Mua Random", "📦 ACC đã mua")
        kb.row("💰 Số dư", "🎲 Dice")
        kb.row("🎰 Slot", "🎁 Redeem")
        kb.row("💳 Nạp tiền")
        bot.send_message(chat_id, "Chọn chức năng:", reply_markup=kb)
    except Exception:
        log_exc("send_user_menu")

# ================= COMMANDS - USER =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        ensure_user(m.from_user.id)
        text = (
            "🎮 *SHOP ACC RANDOM*\n\n"
            "Sử dụng menu hoặc các lệnh:\n"
            "/sodu - Xem số dư\n"
            "/myacc - Xem acc đã mua\n"
            "/random - Mua ACC random\n"
            "/dice - Chơi Dice\n"
            "/slot - Chơi Slot\n"
            "/redeem <code> - Nhập giftcode\n"
            "/nap <sotien> - Gửi yêu cầu nạp (gửi ảnh bill sau đó)\n"
        )
        bot.reply_to(m, text, parse_mode="Markdown")
        send_user_menu(m.chat.id)
    except Exception:
        log_exc("cmd_start")

@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        bal = get_balance(m.from_user.id)
        bot.reply_to(m, f"💰 Số dư: *{bal}đ*", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_sodu")

@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    try:
        uid = str(m.from_user.id)
        rows = db_commit_exec("SELECT acc, created_at FROM purchases WHERE user_id=?", (uid,), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Bạn chưa mua acc nào.")
            return
        text = "\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m, f"📄 ACC đã mua:\n{text}", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_myacc")

@bot.message_handler(commands=["random"])
def cmd_random(m):
    try:
        uid = str(m.from_user.id)
        if not deduct(uid, PRICE_RANDOM):
            bot.reply_to(m, "❌ Không đủ tiền")
            return
        row = db_commit_exec("SELECT id, acc FROM stock_acc ORDER BY RANDOM() LIMIT 1", (), fetch=True)
        if not row:
            add_money(uid, PRICE_RANDOM)
            bot.reply_to(m, "⚠ Hết hàng, tiền đã hoàn lại")
            return
        acc_id, acc_val = row[0]
        with db_lock:
            c.execute("DELETE FROM stock_acc WHERE id=?", (acc_id,))
            c.execute("INSERT INTO purchases(user_id, acc, created_at) VALUES(?,?,?)", (uid, acc_val, time.ctime()))
            conn.commit()
        bot.reply_to(m, f"🛍 Bạn nhận được ACC:\n`{acc_val}`", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_random")

@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    try:
        uid = str(m.from_user.id)
        roll = random.randint(1,6)
        reward = roll * 200
        add_money(uid, reward)
        bot.reply_to(m, f"🎲 Bạn lắc ra *{roll}* → +{reward}đ", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_dice")

@bot.message_handler(commands=["slot"])
def cmd_slot(m):
    try:
        uid = str(m.from_user.id)
        icons = ['🍒','💎','⭐','7️⃣']
        s = [random.choice(icons) for _ in range(3)]
        if s.count(s[0]) == 3:
            add_money(uid, 10000)
            bot.reply_to(m, f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.reply_to(m, f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except Exception:
        log_exc("cmd_slot")

@bot.message_handler(commands=["redeem"])
def cmd_redeem(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /redeem <code>")
            return
        uid = str(m.from_user.id)
        code = parts[1].upper()
        row = db_commit_exec("SELECT amount, used_by FROM giftcode WHERE code=?", (code,), fetch=True)
        if not row:
            bot.reply_to(m, "❌ Giftcode không tồn tại")
            return
        amount, used_by = row[0]
        if used_by and uid in used_by.split(","):
            bot.reply_to(m, "❌ Bạn đã dùng code này rồi")
            return
        new_used = uid if not used_by else used_by + "," + uid
        db_commit_exec("UPDATE giftcode SET used_by=? WHERE code=?", (new_used, code))
        add_money(uid, amount)
        bot.reply_to(m, f"✅ Nhận {amount}đ từ giftcode {code}")
    except Exception:
        log_exc("cmd_redeem")

@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /nap <sotien>")
            return
        amount = int(parts[1])
        txt = (
            f"💳 Hướng dẫn nạp tiền:\n"
            f"• STK: *0971487462*\n"
            f"• Ngân hàng: MB\n"
            f"• Nội dung: `{m.from_user.id}`\n"
            f"• Số tiền: *{amount}đ*\n"
            f"Gửi ảnh bill vào chat để admin duyệt."
        )
        bot.reply_to(m, txt, parse_mode="Markdown")
    except Exception:
        log_exc("cmd_nap")

# ================= HANDLE IMAGES (BILL UPLOAD) =================
@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    try:
        # only accept photo when user previously used /nap? We'll accept photo and create pending bill with amount 0 unless user wrote /nap before
        uid = str(m.from_user.id)
        # get largest photo size
        file_info = bot.get_file(m.photo[-1].file_id)
        file_id = m.photo[-1].file_id
        # try to parse amount from caption if user wrote e.g. "nap 10000"
        amount = 0
        if m.caption:
            # find number in caption
            import re
            found = re.findall(r'(\d{3,})', m.caption.replace(',', ''))
            if found:
                amount = int(found[0])
        created_at = time.ctime()
        db_commit_exec("INSERT INTO bills(user_id, file_id, amount, status, created_at) VALUES(?,?,?,?,?)",
                       (uid, file_id, int(amount), 'pending', created_at))
        bot.reply_to(m, "✅ Ảnh đã được gửi, admin sẽ kiểm tra và duyệt (status: pending).")
        # notify admins
        admins = db_commit_exec("SELECT user_id FROM admins", (), fetch=True)
        if admins:
            notif = f"📥 Bill mới từ user `{uid}`\nSố tiền (phán đoán): {amount}đ\nTime: {created_at}"
            for a in admins:
                try:
                    bot.send_message(int(a[0]), notif, parse_mode="Markdown")
                except Exception:
                    pass
    except Exception:
        log_exc("handle_photo")

# ================= ADMIN COMMANDS =================
# /addacc <acc>
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "📌 /addacc <acc>")
            return
        acc = parts[1].strip()
        db_commit_exec("INSERT INTO stock_acc(acc) VALUES(?)", (acc,))
        bot.reply_to(m, "✅ Đã thêm acc vào kho.")
    except Exception:
        log_exc("cmd_addacc")

# /stock - show count
@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        r = db_commit_exec("SELECT COUNT(*) FROM stock_acc", (), fetch=True)
        count = r[0][0] if r else 0
        bot.reply_to(m, f"📦 Kho hiện có {count} acc.")
    except Exception:
        log_exc("cmd_stock")

# /listacc - list first N accs
@bot.message_handler(commands=["listacc"])
def cmd_listacc(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        limit = 50
        if len(parts) >= 2:
            try:
                limit = min(200, int(parts[1]))
            except:
                pass
        rows = db_commit_exec("SELECT id, acc FROM stock_acc ORDER BY id ASC LIMIT ?", (limit,), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Kho rỗng.")
            return
        text = "\n".join([f"{r[0]} | `{r[1]}`" for r in rows])
        # send as text or file if too long
        if len(text) > 3500:
            bio = BytesIO(text.encode('utf-8'))
            bio.name = "listacc.txt"
            bot.send_document(m.chat.id, bio)
        else:
            bot.reply_to(m, f"📄 Danh sách acc (top {limit}):\n{text}", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_listacc")

# /delacc <id>
@bot.message_handler(commands=["delacc"])
def cmd_delacc(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /delacc <id>")
            return
        acc_id = int(parts[1])
        db_commit_exec("DELETE FROM stock_acc WHERE id=?", (acc_id,))
        bot.reply_to(m, f"✅ Đã xóa acc id={acc_id}")
    except Exception:
        log_exc("cmd_delacc")

# /delall
@bot.message_handler(commands=["delall"])
def cmd_delall(m):
    try:
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ Chỉ owner mới xóa toàn bộ kho.")
            return
        db_commit_exec("DELETE FROM stock_acc", ())
        bot.reply_to(m, "✅ Đã xóa toàn bộ kho.")
    except Exception:
        log_exc("cmd_delall")

# /export - export all accs as file
@bot.message_handler(commands=["export"])
def cmd_export(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_commit_exec("SELECT acc FROM stock_acc ORDER BY id", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Kho rỗng.")
            return
        text = "\n".join([r[0] for r in rows])
        bio = BytesIO(text.encode('utf-8'))
        bio.name = "stock_export.txt"
        bot.send_document(m.chat.id, bio)
    except Exception:
        log_exc("cmd_export")

# /adduid <id> <level>
@bot.message_handler(commands=["adduid"])
def cmd_adduid(m):
    try:
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ Chỉ owner mới được cấp quyền.")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "📌 /adduid <user_id> <level>")
            return
        uid = str(parts[1])
        level = int(parts[2])
        db_commit_exec("INSERT OR REPLACE INTO admins(user_id, level) VALUES(?,?)", (uid, level))
        bot.reply_to(m, f"✅ Đã set admin `{uid}` level={level}", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_adduid")

# /deluid <id>
@bot.message_handler(commands=["deluid"])
def cmd_deluid(m):
    try:
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔ Chỉ owner mới được xóa admin.")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /deluid <user_id>")
            return
        uid = str(parts[1])
        db_commit_exec("DELETE FROM admins WHERE user_id=?", (uid,))
        bot.reply_to(m, f"✅ Đã xóa admin `{uid}`", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_deluid")

# /gcnew <amount> - tạo giftcode mới
@bot.message_handler(commands=["gcnew"])
def cmd_gcnew(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền tạo giftcode.")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /gcnew <amount>")
            return
        amount = int(parts[1])
        code = make_code(8)
        db_commit_exec("INSERT INTO giftcode(code, amount, used_by) VALUES(?,?,?)", (code, amount, ''))
        bot.reply_to(m, f"✅ Tạo giftcode: `{code}` trị giá {amount}đ", parse_mode="Markdown")
    except Exception:
        log_exc("cmd_gcnew")

# /gclist
@bot.message_handler(commands=["gclist"])
def cmd_gclist(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_commit_exec("SELECT code, amount, used_by FROM giftcode ORDER BY ROWID DESC", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Chưa có giftcode nào.")
            return
        text = "\n".join([f"{r[0]} | {r[1]} | used_by: {r[2]}" for r in rows])
        bot.reply_to(m, f"🎟 Giftcodes:\n{text}")
    except Exception:
        log_exc("cmd_gclist")

# /bills - admin danh sách bills pending
@bot.message_handler(commands=["bills"])
def cmd_bills(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền xem bills.")
            return
        rows = db_commit_exec("SELECT id, user_id, amount, status, created_at FROM bills ORDER BY id DESC", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có bills.")
            return
        text = "\n".join([f"{r[0]} | user:{r[1]} | {r[2]}đ | {r[3]} | {r[4]}" for r in rows])
        bot.reply_to(m, f"📥 Bills:\n{text}")
    except Exception:
        log_exc("cmd_bills")

# /billview <id> - xem ảnh bill
@bot.message_handler(commands=["billview"])
def cmd_billview(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /billview <id>")
            return
        bid = int(parts[1])
        row = db_commit_exec("SELECT file_id, user_id, amount, status FROM bills WHERE id=?", (bid,), fetch=True)
        if not row:
            bot.reply_to(m, "❌ Bill không tồn tại.")
            return
        file_id, uid, amount, status = row[0]
        bot.send_message(m.chat.id, f"Bill {bid} | user:{uid} | {amount}đ | status:{status}")
        try:
            bot.send_photo(m.chat.id, file_id)
        except Exception:
            bot.reply_to(m, "⚠ Không thể hiển thị ảnh (file có thể đã bị xoá khỏi server Telegram).")
    except Exception:
        log_exc("cmd_billview")

# /billapprove <id> <approve|reject> [note]
@bot.message_handler(commands=["billapprove"])
def cmd_billapprove(m):
    try:
        if not is_support(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split(maxsplit=3)
        if len(parts) < 3:
            bot.reply_to(m, "📌 /billapprove <id> <approve|reject> [ghi chú]")
            return
        bid = int(parts[1])
        action = parts[2].lower()
        note = parts[3] if len(parts) >= 4 else ""
        row = db_commit_exec("SELECT user_id, amount, status FROM bills WHERE id=?", (bid,), fetch=True)
        if not row:
            bot.reply_to(m, "❌ Bill không tồn tại.")
            return
        user_id, amount, status = row[0]
        if status != 'pending':
            bot.reply_to(m, f"⚠ Bill hiện ở trạng thái {status}")
            return
        if action == 'approve':
            # credit user
            add_money(user_id, int(amount))
            db_commit_exec("UPDATE bills SET status=?, created_at=? WHERE id=?", ('approved', time.ctime(), bid))
            bot.reply_to(m, f"✅ Đã duyệt bill {bid} và cộng {amount}đ cho user {user_id}")
            try:
                bot.send_message(int(user_id), f"✅ Yêu cầu nạp của bạn đã được duyệt: +{amount}đ. Ghi chú: {note}")
            except Exception:
                pass
        elif action == 'reject':
            db_commit_exec("UPDATE bills SET status=?, created_at=? WHERE id=?", ('rejected', time.ctime(), bid))
            bot.reply_to(m, f"❌ Đã từ chối bill {bid}")
            try:
                bot.send_message(int(user_id), f"❌ Yêu cầu nạp của bạn bị từ chối. Ghi chú: {note}")
            except Exception:
                pass
        else:
            bot.reply_to(m, "📌 Hành động phải là approve hoặc reject")
    except Exception:
        log_exc("cmd_billapprove")

# ================= FALLBACK TEXT BUTTONS =================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def all_text_handler(m):
    text = m.text.strip()
    uid = m.from_user.id
    # quick keyboard buttons
    if text == "🛍 Mua Random":
        return cmd_random(m)
    if text == "📦 ACC đã mua":
        return cmd_myacc(m)
    if text == "💰 Số dư":
        return cmd_sodu(m)
    if text == "🎲 Dice":
        return cmd_dice(m)
    if text == "🎰 Slot":
        return cmd_slot(m)
    if text == "🎁 Redeem":
        bot.reply_to(m, "Dùng /redeem <code>")
        return
    if text == "💳 Nạp tiền":
        bot.reply_to(m, "Dùng /nap <sotien> rồi gửi ảnh bill (photo).")
        return

    # allow admin commands via normal messages if they typed slash already (handled above)
    # if message starts with slash but unknown -> reply help
    if text.startswith("/"):
        bot.reply_to(m, "Lệnh không hợp lệ hoặc chưa được hỗ trợ. Dùng /help để xem lệnh.")
        return

    # otherwise simple echo/help
    bot.reply_to(m, "Mình chưa hiểu. Dùng menu hoặc /help để xem lệnh.")

# ================= START BOT =================
if KEEP_ALIVE:
    try:
        from keep_alive import keep_alive
        keep_alive()
    except Exception:
        pass

print("BOT STARTED!")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        print("BOT CRASH:", e)
        log_exc("POLLING")
        time.sleep(3)
