#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Telegram Shop Random Acc - Full package
Features:
- Auto create DB
- /start, /balance
- /nap <số_tiền> -> tạo yêu cầu nạp (bot trả mã), user gửi ảnh -> admin duyệt bằng nút
- /addacc (admin) -> thêm acc (có thể thêm loại 'random' bằng cách để game='random')
- /buy random2k (hoặc /buy <product>) -> mua theo lệnh, trừ coin, trả acc
- /stock, /top, /gift
- keep_alive support (import keep_alive.keep_alive)
"""
import os
import time
import random
import sqlite3
import telebot
from telebot import types

# ----------------- Cấu hình (Thay vào trước khi chạy) -----------------
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"      # <-- Thay token bot
ADMIN_ID = 5736655322               # <-- Thay ID admin (số)
DB_PATH = "shop.db"
COIN_TO_VND = 2000                 # 1 coin = 1000 VND (có thể chỉnh)
# -----------------------------------------------------------------------

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ---------- Tạo DB nếu chưa có ----------
if not os.path.exists(DB_PATH):
    open(DB_PATH, "w").close()

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topup (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount_vnd INTEGER,
    coin INTEGER,
    code TEXT,
    photo_file_id TEXT,
    status TEXT DEFAULT 'pending',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,         -- loại, ví dụ 'random'
    info TEXT,         -- nội dung tài khoản (user:pass hoặc thông tin)
    price INTEGER,     -- giá tính theo coin
    status TEXT DEFAULT 'available'  -- available / sold
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,       -- 'buy' / 'topup'
    detail TEXT,
    amount INTEGER,
    created_at INTEGER
);
""")
conn.commit()

# ---------- Utils ----------
def ensure_user(uid: int):
    cur.execute("INSERT OR IGNORE INTO users(user_id,balance) VALUES(?,?)", (uid, 0))
    conn.commit()

def get_balance(uid: int) -> int:
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else 0

def add_balance(uid: int, coin: int):
    ensure_user(uid)
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (coin, uid))
    conn.commit()
    # log
    cur.execute("INSERT INTO history (user_id,action,detail,amount,created_at) VALUES (?,?,?,?,?)",
                (uid, "topup_auto", f"admin_add {coin}", coin, int(time.time())))
    conn.commit()

def reduce_balance(uid: int, coin: int) -> bool:
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if not r or r[0] < coin:
        return False
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (coin, uid))
    conn.commit()
    return True

def create_topup_request(uid: int, amount_vnd: int):
    coin = amount_vnd // COIN_TO_VND
    code = f"PAY{random.randint(10000,99999)}"
    created_at = int(time.time())
    cur.execute("INSERT INTO topup (user_id, amount_vnd, coin, code, created_at) VALUES (?,?,?,?,?)",
                (uid, amount_vnd, coin, code, created_at))
    conn.commit()
    return cur.lastrowid, code, coin

def attach_photo_to_topup(uid: int, file_id: str):
    cur.execute("SELECT id FROM topup WHERE user_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1", (uid,))
    r = cur.fetchone()
    if not r:
        return None
    tid = r[0]
    cur.execute("UPDATE topup SET photo_file_id=? WHERE id=?", (file_id, tid))
    conn.commit()
    return tid

def get_topup(tid: int):
    cur.execute("SELECT id,user_id,amount_vnd,coin,code,photo_file_id,status,created_at FROM topup WHERE id=?", (tid,))
    return cur.fetchone()

def set_topup_status(tid: int, status: str):
    cur.execute("UPDATE topup SET status=? WHERE id=?", (status, tid))
    conn.commit()

def add_account(game: str, info: str, price_coin: int):
    cur.execute("INSERT INTO accounts (game, info, price) VALUES (?,?,?)", (game, info, price_coin))
    conn.commit()

def get_random_account(game: str):
    cur.execute("SELECT id, info, price FROM accounts WHERE status='available' AND game=? ORDER BY RANDOM() LIMIT 1", (game,))
    return cur.fetchone()

def mark_account_sold(acc_id: int):
    cur.execute("UPDATE accounts SET status='sold' WHERE id=?", (acc_id,))
    conn.commit()

def log_history(uid:int, action:str, detail:str, amount:int):
    cur.execute("INSERT INTO history (user_id,action,detail,amount,created_at) VALUES (?,?,?,?,?)",
                (uid, action, detail, amount, int(time.time())))
    conn.commit()

# ---------- BOT COMMANDS: Basic ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    ensure_user(uid)
    text = (
        f"👋 Chào {m.from_user.first_name or m.from_user.username}!\n\n"
        "📌 Hướng dẫn nhanh:\n"
        "- /balance — xem số dư (coin)\n"
        "- /nap <số_tiền_vnd> — tạo yêu cầu nạp (vd: /nap 10000)\n"
        "- Gửi ảnh chuyển khoản vào chat để xác nhận nạp\n"
        "- /stock — kiểm tra kho acc\n"
        "- /buy random2k — mua acc Random 2k (tương ứng price)\n"
        "- /addacc (admin) — thêm acc\n"
    )
    bot.reply_to(m, text)

@bot.message_handler(commands=["balance","bal"])
def cmd_balance(m):
    uid = m.from_user.id
    ensure_user(uid)
    bal = get_balance(uid)
    bot.reply_to(m, f"💰 Số dư của bạn: *{bal}* coin  (~{bal*COIN_TO_VND:,}₫)")

# ---------- NAP (tạo yêu cầu) ----------
@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    uid = m.from_user.id
    ensure_user(uid)
    parts = m.text.strip().split()
    if len(parts) < 2:
        return bot.reply_to(m, "Cách dùng: /nap <số_tiền_vnd>\nVí dụ: /nap 10000")
    try:
        amount_vnd = int(parts[1])
    except:
        return bot.reply_to(m, "Số tiền không hợp lệ. Ví dụ: /nap 10000")
    if amount_vnd < COIN_TO_VND:
        return bot.reply_to(m, f"Số tiền tối thiểu {COIN_TO_VND} VND (tương ứng 1 coin).")

    tid, code, coin = create_topup_request(uid, amount_vnd)
    # gửi hướng dẫn chuyển khoản (bạn có thể chỉnh nội dung)
    text = (
        f"💳 Hướng dẫn nạp tiền\n\n"
        f"- STK: *0971487462*\n"
        f"- Ngân hàng: *MB Bank*\n"
        f"- Nội dung chuyển khoản: *{code}*\n"
        f"- Số tiền: *{amount_vnd:,}₫*  (→ *{coin}* coin)\n\n"
        "📸 Sau khi chuyển khoản vui lòng gửi ảnh bill tại đây để admin duyệt.\n"
        f"🆔 Mã giao dịch: *{tid}*"
    )
    bot.reply_to(m, text, parse_mode="Markdown")
    # thông báo admin để tiện theo dõi
    bot.send_message(ADMIN_ID, f"🔔 Yêu cầu nạp mới: id={tid} user={uid} amount={amount_vnd:,}₫ → {coin} coin. Chờ ảnh bill.")

# ---------- Nhận ảnh bill (user gửi ảnh vào chat) ----------
@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    uid = msg.from_user.id
    file_id = msg.photo[-1].file_id
    tid = attach_photo_to_topup(uid, file_id)
    if not tid:
        return bot.reply_to(msg, "Không tìm thấy yêu cầu nạp đang chờ. Hãy dùng /nap <số_tiền> trước.")
    bot.reply_to(msg, "📥 Đã nhận ảnh. Đợi admin kiểm tra và duyệt...")
    # gửi ảnh cho admin kèm nút Duyệt / Từ chối
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_topup_{tid}"),
        types.InlineKeyboardButton("❌ Từ chối", callback_data=f"reject_topup_{tid}")
    )
    topup = get_topup(tid)
    if topup:
        _, user_id, amount_vnd, coin, code, photo, status, created_at = topup
        caption = (
            f"🔎 DUYỆT NẠP #{tid}\n"
            f"👤 User: {user_id}\n"
            f"💰 {amount_vnd:,}₫ → {coin} coin\n"
            f"🆔 Mã: {code}\n"
            f"Thời gian: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))}"
        )
        bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=markup)

# ---------- Xử lý nút duyệt/từ chối (admin) ----------
@bot.callback_query_handler(func=lambda q: q.data and (q.data.startswith("approve_topup_") or q.data.startswith("reject_topup_")))
def cb_topup_approve(q):
    data = q.data
    action, _, tid_s = data.partition("topup_")
    # q.data is like "approve_topup_5" or "reject_topup_5"
    if "approve_topup_" in q.data:
        tid = int(q.data.split("approve_topup_")[1])
        topup = get_topup(tid)
        if not topup:
            bot.answer_callback_query(q.id, "Yêu cầu không tồn tại.")
            return
        _, user_id, amount_vnd, coin, code, photo, status, created_at = topup
        if status != "pending":
            bot.answer_callback_query(q.id, "Yêu cầu đã xử lý.")
            return
        # cộng coin
        add_balance(user_id, coin)
        set_topup_status(tid, "approved")
        log_history(user_id, "topup", f"topup_id:{tid}", coin)
        # thông báo user + edit caption của admin message
        try:
            bot.edit_message_caption(chat_id=q.message.chat.id, message_id=q.message.message_id,
                                     caption=(q.message.caption or "") + "\n\n✔ Đã duyệt bởi admin.")
        except:
            pass
        bot.send_message(user_id, f"✅ Giao dịch nạp #{tid} đã được duyệt. +{coin} coin (~{coin*COIN_TO_VND:,}₫).")
        bot.answer_callback_query(q.id, "Đã duyệt và cộng coin.")
        return
    if "reject_topup_" in q.data:
        tid = int(q.data.split("reject_topup_")[1])
        topup = get_topup(tid)
        if not topup:
            bot.answer_callback_query(q.id, "Yêu cầu không tồn tại.")
            return
        _, user_id, amount_vnd, coin, code, photo, status, created_at = topup
        if status != "pending":
            bot.answer_callback_query(q.id, "Yêu cầu đã xử lý.")
            return
        set_topup_status(tid, "rejected")
        try:
            bot.edit_message_caption(chat_id=q.message.chat.id, message_id=q.message.message_id,
                                     caption=(q.message.caption or "") + "\n\n❌ Đã từ chối bởi admin.")
        except:
            pass
        bot.send_message(user_id, f"❌ Giao dịch nạp #{tid} bị từ chối bởi admin. Vui lòng kiểm tra bill.")
        bot.answer_callback_query(q.id, "Đã từ chối giao dịch.")
        return

# ---------- Admin commands ----------
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    if m.from_user.id != ADMIN_ID:
        return bot.reply_to(m, "Bạn không có quyền dùng lệnh này.")
    # format: /addacc <game>|<info>|<price_coin>
    payload = m.text.replace("/addacc", "", 1).strip()
    if not payload or "|" not in payload:
        return bot.reply_to(m, "Cú pháp: /addacc game|info|price\nVí dụ: /addacc random|user:pass|2")
    try:
        game, info, price_s = payload.split("|", 2)
        price = int(price_s.strip())
    except:
        return bot.reply_to(m, "Sai cú pháp hoặc giá không hợp lệ.")
    add_account(game.strip(), info.strip(), price)
    bot.reply_to(m, f"✔ Đã thêm account game='{game.strip()}' giá {price} coin.")

@bot.message_handler(commands=["listacc"])
def cmd_listacc(m):
    if m.from_user.id != ADMIN_ID:
        return
    cur.execute("SELECT id,game,price,status FROM accounts ORDER BY id DESC LIMIT 200")
    rows = cur.fetchall()
    if not rows:
        return bot.reply_to(m, "Kho trống.")
    text = ["📦 Danh sách acc (mới nhất trước):"]
    for r in rows:
        text.append(f"#{r[0]} | {r[1]} | {r[2]} coin | {r[3]}")
    bot.reply_to(m, "\n".join(text))

@bot.message_handler(commands=["listusers"])
def cmd_listusers(m):
    if m.from_user.id != ADMIN_ID:
        return
    cur.execute("SELECT user_id,balance FROM users ORDER BY user_id DESC LIMIT 200")
    rows = cur.fetchall()
    if not rows:
        return bot.reply_to(m, "Chưa có user.")
    text = ["👥 Danh sách user (mới nhất):"]
    for r in rows:
        text.append(f"{r[0]} — {r[1]} coin")
    bot.reply_to(m, "\n".join(text))

@bot.message_handler(commands=["addbalance"])
def cmd_addbalance(m):
    if m.from_user.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) < 3:
        return bot.reply_to(m, "Cú pháp: /addbalance <user_id> <coin>")
    try:
        uid = int(parts[1]); coin = int(parts[2])
    except:
        return bot.reply_to(m, "Tham số không hợp lệ.")
    add_balance(uid, coin)
    bot.reply_to(m, f"✔ Đã cộng {coin} coin cho {uid}")
    bot.send_message(uid, f"🔔 Admin đã cộng cho bạn +{coin} coin.")

# ---------- BUY command (mua theo lệnh) ----------
@bot.message_handler(commands=["buy"])
def cmd_buy(m):
    uid = m.from_user.id
    ensure_user(uid)
    parts = m.text.strip().split()
    if len(parts) < 2:
        return bot.reply_to(m, "Cú pháp: /buy <product>\nVí dụ: /buy random2k")
    product = parts[1].lower()

    # handle random2k specifically (product name 'random2k' maps to game='random' price 2 coin)
    if product == "random2k" or product == "random":
        # we expect admin inserted accounts with game='random' and price like 2 (coin)
        acc = get_random_account("random")
        if not acc:
            return bot.reply_to(m, "⛔ Hết acc random, vui lòng chờ admin nạp thêm.")
        acc_id, info, price = acc
        price = int(price)
        bal = get_balance(uid)
        if bal < price:
            return bot.reply_to(m, f"❗ Không đủ coin. Giá: {price} coin | Số dư: {bal} coin")
        # trừ tiền và chuyển acc
        ok = reduce_balance(uid, price)
        if not ok:
            return bot.reply_to(m, "❗ Trừ coin thất bại.")
        mark_account_sold(acc_id)
        log_history(uid, "buy", f"acc_id:{acc_id}", price)
        bot.reply_to(m, f"🎉 Mua thành công Random!\n\n🔑 Thông tin tài khoản:\n`{info}`")
        bot.send_message(ADMIN_ID, f"🔔 User {uid} đã mua RANDOM acc #{acc_id} giá {price} coin.")
        return

    # generic: treat product as game name, try to fetch an available acc of that game
    cur.execute("SELECT id, info, price FROM accounts WHERE status='available' AND game=? ORDER BY id ASC LIMIT 1", (product,))
    r = cur.fetchone()
    if not r:
        return bot.reply_to(m, "❗ Không tìm thấy sản phẩm này hoặc đã hết.")
    acc_id, info, price = r
    price = int(price)
    bal = get_balance(uid)
    if bal < price:
        return bot.reply_to(m, f"❗ Không đủ coin. Giá: {price} coin | Số dư: {bal} coin")
    if not reduce_balance(uid, price):
        return bot.reply_to(m, "❗ Trừ coin thất bại.")
    mark_account_sold(acc_id)
    log_history(uid, "buy", f"acc_id:{acc_id}", price)
    bot.reply_to(m, f"🎉 Mua thành công!\n\n🔑 Thông tin tài khoản:\n`{info}`")
    bot.send_message(ADMIN_ID, f"🔔 User {uid} đã mua acc #{acc_id} giá {price} coin.")
    return

# ---------- Shop /stock, /top ----------
@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    cur.execute("SELECT COUNT(*) FROM accounts WHERE status='available'")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM accounts WHERE status='available' AND game='random'")
    rnd = cur.fetchone()[0]
    bot.reply_to(m, f"📦 Tổng acc: {total} | Random: {rnd}")

@bot.message_handler(commands=["top"])
def cmd_top(m):
    cur.execute("SELECT user_id, COUNT(*) as cnt FROM history WHERE action='buy' GROUP BY user_id ORDER BY cnt DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows:
        return bot.reply_to(m, "Chưa có giao dịch mua nào.")
    text = "🏆 Top buyers:\n"
    for u,c in rows:
        text += f"• {u} — {c} lần\n"
    bot.reply_to(m, text)

@bot.message_handler(commands=["gift"])
def cmd_gift(m):
    parts = m.text.strip().split()
    if len(parts) < 2:
        return bot.reply_to(m, "Cú pháp: /gift <code>")
    code = parts[1].upper()
    uid = m.from_user.id
    # simple gift example
    if code == "FREE2K":
        add_balance(uid, 2)  # 2 coin (if you want 2000đ -> coin=2)
        bot.reply_to(m, "🎁 Giftcode thành công: +2 coin")
    else:
        bot.reply_to(m, "❌ Giftcode không hợp lệ.")

# ---------- Fallback ----------
@bot.message_handler(func=lambda m: True)
def fallback(m):
    text = (
        "Mình chưa hiểu. Các lệnh chính:\n"
        "/balance /nap /buy random2k /stock /top\n"
        "Admin: /addacc /listacc /listusers /addbalance"
    )
    bot.reply_to(m, text)

# ---------- Start polling ----------
if __name__ == "__main__":
    # nếu bạn muốn dùng keep_alive, import keep_alive.keep_alive() trước khi poll
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=5)
    except Exception as e:
        print("Bot error:", e)
