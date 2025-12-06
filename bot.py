# ==========================================================
# Telegram Shop Bot - FULL VERSION
# ==========================================================

import telebot, sqlite3, random, time, threading, datetime
from telebot import types
from keep_alive import keep_alive

# ============ CONFIG ============

TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"
ADMINS = ["5736655322"]  # ID admin (thêm nhiều: ["id1","id2"])
PRICE_RANDOM = 2000      # Giá random acc

bot = telebot.TeleBot(TOKEN)

# ============ DATABASE ============

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users(
 user_id TEXT,
 balance INTEGER DEFAULT 0
)""")

c.execute("""CREATE TABLE IF NOT EXISTS purchases(
 user_id TEXT,
 acc TEXT,
 time TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 acc TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS giftcode(
 code TEXT,
 amount INTEGER,
 used_by TEXT
)""")

conn.commit()

# ============ HÀM HỖ TRỢ ============

def get_balance(uid):
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    return r[0] if r else 0

def add_money(uid, amount):
    bal = get_balance(uid) + amount
    c.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (uid, bal))
    conn.commit()

def deduct(uid, amount):
    bal = get_balance(uid)
    if bal < amount: return False
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (bal-amount,uid))
    conn.commit()
    return True

# ==========================================================
# COMMANDS USER
# ==========================================================

@bot.message_handler(commands=['start','help'])
def start(msg):
    bot.reply_to(msg,
"""
🎮 *Chào mừng đến Shop Acc Random!*

🛒 *Lệnh người dùng:*
/random - Mua acc random (2.000đ)
/myacc - Xem acc đã mua
/sodu - Kiểm tra số dư
/nap <sotien> - Nạp tiền
/dice - Game tung xúc xắc
/slot - Quay hũ nhận thưởng
/redeem <giftcode> - Nhập giftcode nhận tiền

💳 Sau khi /nap hãy gửi ảnh chuyển khoản
""", parse_mode="Markdown")

@bot.message_handler(commands=['sodu'])
def sodu(msg):
    uid = str(msg.from_user.id)
    bot.reply_to(msg,f"💰 Số dư: *{get_balance(uid)}đ*",parse_mode="Markdown")

@bot.message_handler(commands=['myacc'])
def myacc(msg):
    uid = str(msg.from_user.id)
    c.execute("SELECT acc,time FROM purchases WHERE user_id=?", (uid,))
    data = c.fetchall()
    if not data: return bot.reply_to(msg,"Bạn chưa mua gì!")
    text = "\n".join([f"• `{i[0]}` ({i[1]})" for i in data])
    bot.reply_to(msg,f"📦 Tài khoản đã mua:\n{text}",parse_mode="Markdown")

# ==========================================================
# NẠP TIỀN
# ==========================================================

@bot.message_handler(commands=['nap'])
def nap(msg):
    try:
        amount = int(msg.text.split()[1])
    except:
        return bot.reply_to(msg,"📌 /nap <sotien>")

    bot.reply_to(msg,f"""
💳 Vui lòng chuyển khoản:

• STK: *0971487462*
• Ngân hàng: *MB BANK*
• Nội dung: `{msg.from_user.id}`
• Số tiền: *{amount}đ*

📸 Gửi ảnh chuyển khoản sau khi thanh toán.
""", parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def check_bill(msg):
    uid = str(msg.from_user.id)
    add_money(uid,10000)  # admin duyệt tay: sửa theo ý
    bot.reply_to(msg,"✔ Đã cộng *10.000đ* vào ví!",parse_mode="Markdown")

# ==========================================================
# RANDOM ACC
# ==========================================================

@bot.message_handler(commands=['random'])
def random_acc(msg):
    uid = str(msg.from_user.id)
    if not deduct(uid, PRICE_RANDOM):
        return bot.reply_to(msg,"❌ Không đủ tiền!")

    c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
    acc = c.fetchone()

    if not acc:
        add_money(uid,PRICE_RANDOM)
        return bot.reply_to(msg,"Hết acc, hoàn tiền!")

    c.execute("DELETE FROM stock_acc WHERE id=?", (acc[0],))
    conn.commit()

    c.execute("INSERT INTO purchases VALUES(?,?,?)",(uid,acc[1],time.ctime()))
    conn.commit()

    bot.reply_to(msg,f"🛍 Bạn nhận được:\n`{acc[1]}`",parse_mode="Markdown")

# ==========================================================
# EVENT GAME
# ==========================================================

@bot.message_handler(commands=['dice'])
def dice(msg):
    uid = str(msg.from_user.id)
    roll = random.randint(1,6)
    reward = roll*200
    add_money(uid, reward)
    bot.reply_to(msg,f"🎲 Kết quả: *{roll}*\n+ Nhận `{reward}đ`!",parse_mode="Markdown")

@bot.message_handler(commands=['slot'])
def slot(msg):
    icons = ['🍒','💎','⭐','7️⃣']
    s = [random.choice(icons) for _ in range(3)]
    text = " ".join(s)

    uid=str(msg.from_user.id)
    if s[0]==s[1]==s[2]:
        add_money(uid,10000)
        bot.reply_to(msg,f"🎰 {text}\n🔥 JACKPOT +10.000đ")
    else:
        bot.reply_to(msg,f"🎰 {text}\n😢 Hụt rồi!")

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    try: code = msg.text.split()[1]
    except: return bot.reply_to(msg,"/redeem <giftcode>")

    c.execute("SELECT amount,used_by FROM giftcode WHERE code=?", (code,))
    r=c.fetchone()

    if not r: return bot.reply_to(msg,"❌ Giftcode sai!")
    if r[1]!=None: return bot.reply_to(msg,"⚠ Code đã dùng!")

    uid=str(msg.from_user.id)
    add_money(uid,r[0])
    c.execute("UPDATE giftcode SET used_by=? WHERE code=?", (uid,code))
    conn.commit()

    bot.reply_to(msg,f"🎁 Nhận +{r[0]}đ thành công!")

# ==========================================================
# QUẢN TRỊ KHO ACC
# ==========================================================

@bot.message_handler(commands=['addacc'])
def addacc(msg):
    if str(msg.from_user.id) not in ADMINS:return
    data=msg.text.replace("/addacc","").strip()
    if ":" not in data:return bot.reply_to(msg,"/addacc email:pass")
    c.execute("INSERT INTO stock_acc(acc) VALUES(?)",(data,))
    conn.commit()
    bot.reply_to(msg,f"✔ Đã thêm `{data}`",parse_mode="Markdown")

@bot.message_handler(commands=['stock'])
def stock(msg):
    if str(msg.from_user.id) not in ADMINS:return
    c.execute("SELECT COUNT(*) FROM stock_acc")
    bot.reply_to(msg,f"📦 Còn `{c.fetchone()[0]}` ACC")

@bot.message_handler(commands=['listacc'])
def listacc(msg):
    if str(msg.from_user.id) not in ADMINS:return
    c.execute("SELECT id,acc FROM stock_acc LIMIT 20")
    data="\n".join([f"{i[0]}. {i[1]}" for i in c.fetchall()])
    bot.reply_to(msg,"📋 Kho:\n"+data+"\n\n/delacc <id>")

@bot.message_handler(commands=['delacc'])
def delacc(msg):
    if str(msg.from_user.id) not in ADMINS:return
    try:_id=int(msg.text.split()[1])
    except:return bot.reply_to(msg,"/delacc <id>")
    c.execute("DELETE FROM stock_acc WHERE id=?",(_id,))
    conn.commit()
    bot.reply_to(msg,"🗑 Xóa thành công!")

@bot.message_handler(commands=['delall'])
def delall(msg):
    if str(msg.from_user.id) not in ADMINS:return
    c.execute("DELETE FROM stock_acc")
    conn.commit()
    bot.reply_to(msg,"🔥 Đã xóa toàn bộ kho!")

@bot.message_handler(commands=['export'])
def export_stock(msg):
    if str(msg.from_user.id) not in ADMINS:return
    c.execute("SELECT acc FROM stock_acc")
    with open("stock.txt","w") as f:
        f.write("\n".join([i[0] for i in c.fetchall()]))
    bot.send_document(msg.chat.id,open("stock.txt","rb"))

# ==========================================================
# BÁO CÁO KHO MỖI NGÀY
# ==========================================================

def daily_stock():
    while True:
        c.execute("SELECT COUNT(*) FROM stock_acc")
        count=c.fetchone()[0]
        for ad in ADMINS:
            bot.send_message(ad,f"📅 Báo cáo: Còn {count} ACC")
        time.sleep(86400)

threading.Thread(target=daily_stock,daemon=True).start()

# ==========================================================
# RUN
# ==========================================================

keep_alive()
bot.infinity_polling()
