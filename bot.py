#!/usr/bin/env python3
# ============================
# BOT TELEGRAM SHOP RANDOM ACC 2K
# ============================

import telebot, sqlite3, random, time
from keep_alive import keep_alive   # nếu chạy local thì không cần, deploy thì để nguyên

TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"           # <<< TOKEN BOT
ADMIN = 5736655322                   # <<< ID ADMIN TELEGRAM

bot = telebot.TeleBot(TOKEN)

# ==================== DATABASE =====================
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS stock(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acc TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    acc TEXT,
    price INTEGER,
    time TEXT
)""")
conn.commit()

def create_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(uid,))
    conn.commit()

# ================= COMMANDS ======================

@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    create_user(uid)

    bot.reply_to(msg,
f"""👋 *Chào mừng đến SHOP RANDOM ACC 2K*

📌 Lệnh sử dụng:
/mua – Mua random {PRICE:=2000}đ
/stock – Kiểm tra số acc còn
/nap <số tiền> – Nạp tiền thủ công
/top – Top khách hàng
/gift <code> – Nhập giftcode

🎮 QUẢN TRỊ (ADMIN):
/addacc user|pass – Thêm acc
/setprice <giá> – Đặt giá random

🔥 Mua acc nhận ngay – giao tự động!
""", parse_mode="Markdown")


# ========= THAY ĐỔI GIÁ (ADMIN) =========
PRICE = 2000

@bot.message_handler(commands=['setprice'])
def set_price(msg):
    if msg.from_user.id != ADMIN:
        return bot.reply_to(msg,"❌ Bạn không phải admin.")
    try:
        global PRICE
        PRICE = int(msg.text.split()[1])
        bot.reply_to(msg,f"✅ Giá mới: {PRICE}đ")
    except:
        bot.reply_to(msg,"Dùng: /setprice 2000")


# ========= THÊM ACC =========
@bot.message_handler(commands=['addacc'])
def add_acc(msg):
    if msg.from_user.id != ADMIN:
        return bot.reply_to(msg,"❌ Bạn không phải admin.")
    acc = msg.text.replace("/addacc ","").strip()
    if "|" not in acc:
        return bot.reply_to(msg,"❌ Format: user|pass")

    cur.execute("INSERT INTO stock(acc) VALUES(?)",(acc,))
    conn.commit()
    bot.reply_to(msg,f"➕ Đã thêm acc:\n`{acc}`",parse_mode="Markdown")


# ===== STOCK =====
@bot.message_handler(commands=['stock'])
def stock(msg):
    cur.execute("SELECT COUNT(*) FROM stock")
    sl = cur.fetchone()[0]
    bot.reply_to(msg,f"📦 Kho còn *{sl} acc*",parse_mode="Markdown")


# ===== NẠP THỦ CÔNG =====
@bot.message_handler(commands=['nap'])
def nap(msg):
    try:
        uid = msg.from_user.id
        amount = int(msg.text.split()[1])
        create_user(uid)

        cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
        conn.commit()

        bot.reply_to(msg,f"💳 Nạp thành công +{amount}đ",parse_mode="Markdown")
    except:
        bot.reply_to(msg,"❌ Dùng: /nap 10000")


# ===== GIFT CODE =====
@bot.message_handler(commands=['gift'])
def gift(msg):
    try:
        code = msg.text.split()[1]
        uid = msg.from_user.id

        if code.upper()=="FREE2K":
            cur.execute("UPDATE users SET balance = balance + 2000 WHERE id=?", (uid,))
            conn.commit()
            return bot.reply_to(msg,"🎁 Giftcode +2000đ")

        bot.reply_to(msg,"❌ Giftcode không tồn tại")
    except:
        bot.reply_to(msg,"Dùng: /gift FREE2K")


# ===== MUA ACC RANDOM =====
@bot.message_handler(commands=['mua','random'])
def buy(msg):
    uid = msg.from_user.id
    create_user(uid)

    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    bal = cur.fetchone()[0]

    if bal < PRICE:
        return bot.reply_to(msg,f"❌ Không đủ tiền. Bạn có {bal}đ")

    cur.execute("SELECT id,acc FROM stock ORDER BY RANDOM() LIMIT 1")
    acc = cur.fetchone()

    if not acc:
        return bot.reply_to(msg,"❌ Kho acc đã hết")

    acc_id,acc_data = acc

    cur.execute("DELETE FROM stock WHERE id=?", (acc_id,))
    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (PRICE,uid))
    cur.execute("INSERT INTO history(user_id,acc,price,time) VALUES (?,?,?,?)",
                (uid,acc_data,PRICE,time.ctime()))
    conn.commit()

    bot.reply_to(msg,f"🎉 *MUA THÀNH CÔNG*\n`{acc_data}`",parse_mode="Markdown")


# ===== TOP USER =====
@bot.message_handler(commands=['top'])
def top(msg):
    cur.execute("SELECT user_id, COUNT(*) as buy FROM history GROUP BY user_id ORDER BY buy DESC LIMIT 5")
    data = cur.fetchall()

    text="🏆 *TOP MUA HÀNG*\n"
    for u,c in data:
        text += f"• `{u}` – {c} lần\n"

    bot.reply_to(msg,text,parse_mode="Markdown")


keep_alive()              # REMOVE nếu chạy local!
bot.polling(none_stop=True)
