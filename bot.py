#!/usr/bin/env python3
import telebot, sqlite3, random, uuid, os
from telebot import types
from keep_alive import keep_alive

# ================== CẤU HÌNH ==================
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"        # <---- THAY TOKEN
ADMIN_ID = 5736655322           # <---- ID ADMIN
PRICE_RANDOM = 2000             # Giá mua acc random

DB_NAME = "db.sqlite"


# ================== CHECK + TẠO DB ==================
def check_db():
    if not os.path.exists(DB_NAME):
        return
    try:
        con = sqlite3.connect(DB_NAME)
        con.execute("SELECT name FROM sqlite_master")
        con.close()
    except:
        print("⚠ DB lỗi → Tạo mới")
        os.remove(DB_NAME)

check_db()


# ============ KẾT NỐI DATABASE ===============
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cur = db.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS orders(
    id TEXT,
    user_id INTEGER,
    amount INTEGER,
    img TEXT,
    status TEXT
)""")

db.commit()


# ====== HÀM XỬ LÝ TIỀN ======
def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    x = cur.fetchone()
    return x[0] if x else 0

def add_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    db.commit()

def reduce_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, uid))
    db.commit()


bot = telebot.TeleBot(TOKEN)


# ================== START ==================
@bot.message_handler(commands=["start"])
def start(msg):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(msg.from_user.id,))
    db.commit()

    bot.reply_to(msg,
f"""👋 Chào *{msg.from_user.first_name}*  

💰 Số dư hiện tại: *{get_balance(msg.from_user.id)}đ*

🛒 Lệnh sử dụng:
• /nap - Nạp tiền
• /buy - Mua acc random {PRICE_RANDOM}đ
• /check - Xem số acc còn
• /addacc user|pass (admin)
• /duyet bill tiền (admin)

Chúc bạn mua acc may mắn ❤️
""", parse_mode="Markdown")


# ================== NẠP TIỀN ==================
@bot.message_handler(commands=["nap"])
def nap(msg):
    bill_id = str(uuid.uuid4())[:8]

    bot.reply_to(msg,
f"""💳 Vui lòng chuyển khoản:

🏦 MB Bank  
🔢 STK: *0971487462*  
📝 Nội dung: `{bill_id}`  
💵 Số tiền: tối thiểu 10.000đ

📸 Sau khi chuyển, gửi ảnh kèm lệnh:
`/xacnhan {bill_id}` + ảnh chứng minh thanh toán

⏳ Bill có hiệu lực 20 phút.
""", parse_mode="Markdown")


@bot.message_handler(commands=["xacnhan"])
def confirm(msg):
    text = msg.text.split()

    if len(text) < 2 or not msg.photo:
        return bot.reply_to(msg,"❗ Dùng dạng:\n`/xacnhan bill` + kèm ảnh",parse_mode="Markdown")

    bill = text[1]
    img_id = msg.photo[-1].file_id

    cur.execute("INSERT INTO orders VALUES(?,?,?,?,?)",
                (bill,msg.from_user.id,0,img_id,"pending"))
    db.commit()

    bot.reply_to(msg,"⏳ Đã gửi bill, chờ admin duyệt!")
    bot.send_photo(
        ADMIN_ID,
        img_id,
f"""📩 Bill mới từ `{msg.from_user.id}`  
Mã bill: `{bill}`

Duyệt bằng lệnh:
`/duyet {bill} số_tiền`
""", parse_mode="Markdown")


# ================== ADMIN DUYỆT ==================
@bot.message_handler(commands=["duyet"])
def approve(msg):
    if msg.from_user.id != ADMIN_ID:
        return

    text = msg.text.split()
    if len(text) < 3:
        return bot.reply_to(msg,"Dạng: /duyet bill 20000")

    bill, money = text[1], int(text[2])
    cur.execute("SELECT user_id FROM orders WHERE id=? AND status='pending'", (bill,))
    row = cur.fetchone()

    if not row:
        return bot.reply_to(msg,"❗ Bill không tồn tại hoặc đã duyệt")

    uid = row[0]
    add_balance(uid,money)
    cur.execute("UPDATE orders SET status='done' WHERE id=?", (bill,))
    db.commit()

    bot.send_message(uid,f"💳 Nạp thành công +{money}đ vào tài khoản!")
    bot.reply_to(msg,"✔ Đã duyệt bill")


# ================== BUY ACC ==================
@bot.message_handler(commands=["buy"])
def buy(msg):
    uid = msg.from_user.id
    bal = get_balance(uid)

    if bal < PRICE_RANDOM:
        return bot.reply_to(msg,f"❗ Bạn còn {bal}đ, thiếu {PRICE_RANDOM-bal}đ\nDùng /nap để nạp")

    cur.execute("SELECT id,data FROM accounts ORDER BY RANDOM() LIMIT 1")
    acc = cur.fetchone()

    if not acc:
        return bot.reply_to(msg,"❗ Hết acc, hãy đợi admin thêm!")

    reduce_balance(uid,PRICE_RANDOM)
    cur.execute("DELETE FROM accounts WHERE id=?", (acc[0],))
    db.commit()

    bot.reply_to(msg,
f"""🎉 Mua thành công Acc Random Liên Quân!

🔑 Thông tin:
`{acc[1]}`

💰 Số dư còn: {get_balance(uid)}đ
""",parse_mode="Markdown")


# ================== ADMIN ADD ACC ==================
@bot.message_handler(commands=["addacc"])
def addacc(msg):
    if msg.from_user.id != ADMIN_ID:
        return

    data = msg.text.replace("/addacc ","")
    if "|" not in data:
        return bot.reply_to(msg,"Gõ dạng: /addacc user|pass")

    cur.execute("INSERT INTO accounts(data)VALUES(?)",(data,))
    db.commit()
    bot.reply_to(msg,"✔ Đã thêm acc vào kho")


# ================== CHECK ACC ==================
@bot.message_handler(commands=["check"])
def check(msg):
    cur.execute("SELECT COUNT(*) FROM accounts")
    total = cur.fetchone()[0]
    bot.reply_to(msg,f"📦 Kho còn: {total} acc")


# ================== RUN BOT ==================
keep_alive()            # giữ bot sống khi deploy Render/railway
bot.polling(none_stop=True)
