#!/usr/bin/env python3
import telebot, sqlite3, random, uuid, time, os
from telebot import types
from keep_alive import keep_alive   # chạy web server giữ bot sống khi host render

# ================== CẤU HÌNH ==================
TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"   # <--- thay vào token bot
ADMIN_ID = 5736655322      # ID admin để duyệt nạp

PRICE_RANDOM = 2000        # Giá bán random acc

# ================== KẾT NỐI DATABASE ==================
db = sqlite3.connect("db.sqlite", check_same_thread=False)
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


# ============ HÀM LẤY/VÀO TIỀN ===============
def add_balance(user_id, money):
    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (money, user_id))
    db.commit()

def reduce_balance(user_id, money):
    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (money, user_id))
    db.commit()

def get_balance(user_id):
    cur.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    x = cur.fetchone()
    return x[0] if x else 0


# ================== START ==================
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(msg):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)", (msg.from_user.id,))
    db.commit()
    
    bot.reply_to(msg,
f"""🌟 Chào **{msg.from_user.first_name}**
Bot bán acc Liên Quân Random

💰 Số dư: {get_balance(msg.from_user.id)}đ

🔰 /nap – Nạp tiền
🎁 /buy – Mua acc random {PRICE_RANDOM}đ
📦 /check – Xem số acc còn

👨‍💻 Liên hệ admin nếu cần hỗ trợ.""" , parse_mode="markdown")


# =================== NẠP TIỀN ===================
@bot.message_handler(commands=["nap"])
def nap(msg):
    bill_id = str(uuid.uuid4())[:8]
    bot.reply_to(msg,
f"""💳 Vui lòng chuyển khoản:
- STK: 0971487462
- Ngân hàng: MB BANK
- Nội dung: {bill_id}
- Số tiền: tối thiểu 10.000đ

📸 Sau khi chuyển, hãy gửi ảnh kèm nội dung:
`/xacnhan {bill_id}` + ẢNH

⏳ Bill có hiệu lực 20 phút.""", parse_mode="markdown")


@bot.message_handler(commands=["xacnhan"])
def xac(msg):
    text = msg.text.split()
    if len(text) < 2 or not msg.photo:
        return bot.reply_to(msg,"❗ Gửi đúng dạng:\n`/xacnhan mã_bill` kèm ảnh!",parse_mode="markdown")

    bill = text[1]
    file_id = msg.photo[-1].file_id

    cur.execute("INSERT INTO orders VALUES(?,?,?,?,?)",
                (bill, msg.from_user.id, 0, file_id, "pending"))
    db.commit()

    bot.reply_to(msg,"🕘 Đã gửi admin duyệt!")
    bot.send_message(ADMIN_ID,f"📩 Có bill mới: `{bill}` từ {msg.from_user.id}",parse_mode="markdown")
    bot.send_photo(ADMIN_ID,file_id,
f"""📌 Bill: `{bill}`
Reply lệnh:
 /duyet {bill} số_tiền""",parse_mode="markdown")


@bot.message_handler(commands=["duyet"])
def duyet(msg):
    if msg.from_user.id != ADMIN_ID: return
    
    text = msg.text.split()
    if len(text) < 3:
        return bot.reply_to(msg,"/duyet bill tiền")

    bill, money = text[1], int(text[2])

    cur.execute("SELECT user_id FROM orders WHERE id=? AND status='pending'",(bill,))
    row = cur.fetchone()
    if not row: return bot.reply_to(msg,"Bill không tồn tại!")

    user = row[0]
    add_balance(user,money)
    cur.execute("UPDATE orders SET status='done' WHERE id=?", (bill,))
    db.commit()

    bot.send_message(user,f"💳 Admin đã duyệt +{money}đ vào tài khoản!")
    bot.reply_to(msg,"✔ Duyệt thành công!")


# =================== BUY ===================
@bot.message_handler(commands=["buy"])
def buy(msg):
    user = msg.from_user.id
    bal = get_balance(user)

    if bal < PRICE_RANDOM:
        return bot.reply_to(msg,f"❗ Không đủ tiền!\nBạn có {bal}đ – cần {PRICE_RANDOM}đ\nDùng /nap để nạp tiền.")

    cur.execute("SELECT id,data FROM accounts ORDER BY RANDOM() LIMIT 1")
    acc = cur.fetchone()

    if not acc:
        return bot.reply_to(msg,"❗ Hết acc rồi! Liên hệ admin thêm.")

    reduce_balance(user,PRICE_RANDOM)
    cur.execute("DELETE FROM accounts WHERE id=?", (acc[0],))
    db.commit()

    bot.reply_to(msg,
f"""🎉 Mua thành công!

Tài khoản random Liên Quân:
`{acc[1]}`

💰 Số dư còn: {get_balance(user)}đ""",parse_mode="markdown")


# =================== ADMIN ADD ACC ===================
@bot.message_handler(commands=["addacc"])
def addacc(msg):
    if msg.from_user.id != ADMIN_ID: return
    try:
        data = msg.text.replace("/addacc ","")
        cur.execute("INSERT INTO accounts(data)VALUES(?)",(data,))
        db.commit()
        bot.reply_to(msg,"✔ Đã thêm acc!")
    except:
        bot.reply_to(msg,"Gõ dạng: /addacc user|pass")


@bot.message_handler(commands=["check"])
def check(msg):
    cur.execute("SELECT COUNT(*) FROM accounts")
    total = cur.fetchone()[0]
    bot.reply_to(msg,f"📦 Acc còn: {total}")



# =================== CHẠY BOT ===================
keep_alive()        # quan trọng cho Render!
bot.polling(none_stop=True)
