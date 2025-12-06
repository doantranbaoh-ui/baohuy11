# ======================================
# Telegram Shop Bot FULL FINAL
# ======================================

import telebot, sqlite3, random, time, threading
from telebot import types
from keep_alive import keep_alive

# ===== CONFIG =====
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"       # <- THAY TOKEN!
ADMINS = ["5736655322"]             # ID ADMIN
PRICE_RANDOM = 2000                 # Giá random acc

bot = telebot.TeleBot(TOKEN)

# ===== DATABASE =====

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users(
 user_id TEXT PRIMARY KEY,
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
 code TEXT PRIMARY KEY,
 amount INTEGER,
 used_by TEXT
)""")

conn.commit()

# ===== SUPPORT FUNC =====

def ensure_user(uid):
    c.execute("INSERT OR IGNORE INTO users(user_id,balance) VALUES(?,0)",(uid,))
    conn.commit()

def get_balance(uid):
    ensure_user(uid)
    c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
    return c.fetchone()[0]

def add_money(uid,amount):
    ensure_user(uid)
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount,uid))
    conn.commit()

def deduct(uid,amount):
    ensure_user(uid)
    bal=get_balance(uid)
    if bal<amount:return False
    c.execute("UPDATE users SET balance=? WHERE user_id=?", (bal-amount,uid))
    conn.commit()
    return True

# ======================================
# USER COMMANDS
# ======================================

@bot.message_handler(commands=['start','help'])
def start(msg):
    ensure_user(str(msg.from_user.id))
    bot.reply_to(msg,
"""
🎮 *SHOP ACC RANDOM TG BOT*

🛍 Lệnh dành cho người dùng:
/random – Mua acc random (2.000đ)
/myacc – Xem tài khoản đã mua
/sodu – Kiểm tra số dư
/nap <sotien> – Nạp tiền
/redeem <giftcode> – Nhập code
/dice – Game xúc xắc
/slot – Quay hũ kiếm tiền

💰 Sau khi chuyển khoản → gửi ảnh bill vào bot!
""",parse_mode="Markdown")

@bot.message_handler(commands=['sodu'])
def sodu(msg):
    uid=str(msg.from_user.id)
    bot.reply_to(msg,f"💰 Số dư hiện tại: *{get_balance(uid)}đ*",parse_mode="Markdown")

@bot.message_handler(commands=['myacc'])
def myacc(msg):
    uid=str(msg.from_user.id)
    c.execute("SELECT acc,time FROM purchases WHERE user_id=?", (uid,))
    data=c.fetchall()
    if not data:return bot.reply_to(msg,"📦 Bạn chưa mua tài khoản nào!")
    text="\n".join([f"• `{i[0]}` | {i[1]}" for i in data])
    bot.reply_to(msg,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")

# ======================================
# NẠP TIỀN
# ======================================

@bot.message_handler(commands=['nap'])
def nap(msg):
    try: amount=int(msg.text.split()[1])
    except:return bot.reply_to(msg,"📌 /nap <sotien>")

    bot.reply_to(msg,f"""
💳 *Nạp tiền theo thông tin:*

• STK: **0971487462**
• Ngân hàng: **MB BANK**
• Nội dung: `{msg.from_user.id}`
• Số tiền: **{amount}đ**

📸 *Gửi ảnh hoá đơn để duyệt nạp*
""",parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def bill(msg):
    uid=str(msg.from_user.id)
    add_money(uid,10000)
    bot.reply_to(msg,"✔ Đã cộng *10.000đ* vào ví!",parse_mode="Markdown")

# ======================================
# MUA ACC
# ======================================

@bot.message_handler(commands=['random'])
def random_acc(msg):
    uid=str(msg.from_user.id)
    if not deduct(uid,PRICE_RANDOM):
        return bot.reply_to(msg,"❌ Không đủ số dư!")

    c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
    acc=c.fetchone()

    if not acc:
        add_money(uid,PRICE_RANDOM)
        return bot.reply_to(msg,"⚠ Hết hàng – tiền đã được hoàn!")

    c.execute("DELETE FROM stock_acc WHERE id=?", (acc[0],))
    c.execute("INSERT INTO purchases VALUES(?,?,?)",(uid,acc[1],time.ctime()))
    conn.commit()

    bot.reply_to(msg,f"🛍 Bạn nhận được tài khoản:\n`{acc[1]}`",parse_mode="Markdown")

# ======================================
# EVENT GAME
# ======================================

@bot.message_handler(commands=['dice'])
def dice(msg):
    roll=random.randint(1,6)
    reward=roll*200
    add_money(str(msg.from_user.id),reward)
    bot.reply_to(msg,f"🎲 Lắc ra *{roll}*\n💰 Nhận `{reward}đ`")

@bot.message_handler(commands=['slot'])
def slot(msg):
    items=['🍒','💎','⭐','7️⃣']
    s=[random.choice(items) for _ in range(3)]
    uid=str(msg.from_user.id)
    if s.count(s[0])==3:
        add_money(uid,10000)
        bot.reply_to(msg,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10.000đ")
    else:
        bot.reply_to(msg,f"🎰 {' '.join(s)}\n😢 Chúc may mắn")

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    try: code=msg.text.split()[1]
    except: return bot.reply_to(msg,"📌 /redeem <giftcode>")

    c.execute("SELECT amount,used_by FROM giftcode WHERE code=?", (code,))
    r=c.fetchone()
    if not r:return bot.reply_to(msg,"❌ Giftcode không tồn tại!")
    if r[1]!=None:return bot.reply_to(msg,"⚠ Code đã được sử dụng!")

    uid=str(msg.from_user.id)
    add_money(uid,r[0])
    c.execute("UPDATE giftcode SET used_by=? WHERE code=?", (uid,code))
    conn.commit()

    bot.reply_to(msg,f"🎁 Nhận `{r[0]}đ` thành công!")

# ======================================
# ADMIN PANEL
# ======================================

def is_admin(msg):return str(msg.from_user.id) in ADMINS

@bot.message_handler(commands=['addacc'])
def addacc(msg):
    if not is_admin(msg):return
    data=msg.text.replace("/addacc","").strip()
    if ":" not in data:return bot.reply_to(msg,"📌 /addacc email:pass")
    c.execute("INSERT INTO stock_acc(acc) VALUES(?)",(data,))
    conn.commit()
    bot.reply_to(msg,f"➕ Đã thêm `{data}`")

@bot.message_handler(commands=['stock'])
def stock(msg):
    if not is_admin(msg):return
    c.execute("SELECT COUNT(*) FROM stock_acc")
    bot.reply_to(msg,f"📦 Còn `{c.fetchone()[0]}` ACC trong kho")

@bot.message_handler(commands=['listacc'])
def listacc(msg):
    if not is_admin(msg):return
    c.execute("SELECT id,acc FROM stock_acc LIMIT 50")
    data="\n".join([f"{i[0]}. {i[1]}" for i in c.fetchall()])
    bot.reply_to(msg,f"📄 DANH SÁCH ACC:\n{data}\n\n/delacc <id>")

@bot.message_handler(commands=['delacc'])
def delacc(msg):
    if not is_admin(msg):return
    try:id=int(msg.text.split()[1])
    except:return bot.reply_to(msg,"📌 /delacc <id>")
    c.execute("DELETE FROM stock_acc WHERE id=?", (id,))
    conn.commit()
    bot.reply_to(msg,"🗑 Đã xoá acc")

@bot.message_handler(commands=['delall'])
def delall(msg):
    if not is_admin(msg):return
    c.execute("DELETE FROM stock_acc")
    conn.commit()
    bot.reply_to(msg,"🔥 Đã xoá toàn bộ kho!")

@bot.message_handler(commands=['export'])
def export_stock(msg):
    if not is_admin(msg):return
    c.execute("SELECT acc FROM stock_acc")
    with open("stock.txt","w") as f:
        f.write("\n".join([i[0] for i in c.fetchall()]))
    bot.send_document(msg.chat.id,open("stock.txt","rb"))

# ======================================
# AUTO BÁO CÁO
# ======================================

def daily_report():
    while True:
        c.execute("SELECT COUNT(*) FROM stock_acc")
        count=c.fetchone()[0]
        for ad in ADMINS:
            bot.send_message(ad,f"📅 Báo cáo tự động: Còn {count} ACC trong kho")
        time.sleep(86400)

threading.Thread(target=daily_report,daemon=True).start()

# ======================================
# RUN
# ======================================
keep_alive()
bot.infinity_polling()
