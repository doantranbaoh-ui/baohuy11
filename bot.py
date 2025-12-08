from keep_alive import keep_alive
keep_alive()

import telebot, sqlite3, os, datetime

TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"
ADMIN_ID = 5736655322
bot = telebot.TeleBot(TOKEN)

# ================= DB =================
if not os.path.exists("data.db"):
    conn = sqlite3.connect("data.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )""")
    conn.commit()
else:
    conn = sqlite3.connect("data.db", check_same_thread=False)
    cur = conn.cursor()

# ================ FUNCTION ================
def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id,balance) VALUES(?,0)", (uid,))
    conn.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    r=cur.fetchone(); return r[0] if r else 0

def set_balance(uid, amount):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (amount,uid))
    conn.commit()

def add_balance(uid, amount):
    set_balance(uid, get_balance(uid)+amount)

def get_acc():
    if not os.path.exists("acc.txt"): return None
    data=open("acc.txt","r",encoding="utf-8").readlines()
    if data == []: return None
    acc=data[0].strip()
    open("acc.txt","w",encoding="utf-8").write("".join(data[1:]))
    return acc

def save_history(uid,name,price,acc):
    t=datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    with open("history.txt","a",encoding="utf-8") as f:
        f.write(f"{uid} | {name} | {price} | {acc} | {t}\n")

def get_history(uid):
    if not os.path.exists("history.txt"): return []
    return [i for i in open("history.txt","r",encoding="utf-8").readlines() if i.startswith(str(uid))]

# ================= COMMAND =================
@bot.message_handler(commands=['start'])
def start(m):
    add_user(m.chat.id)
    bot.reply_to(m,
"""
🔥 SHOP ACC LIÊN QUÂN

💰 /balance — Xem tiền
💳 /nap — Hướng dẫn nạp
🎁 /buy <giá> — Mua acc random
📥 /addacc — Thêm acc (admin)
💵 /addmoney <id> <tiền> — Cộng tiền (admin)
📜 /history — Lịch sử mua
🏆 /top — Top tiền
📁 /getacc — Lấy file acc (admin)

Chúc bạn mua được acc ngon ❤️
""")

@bot.message_handler(commands=['balance'])
def bal(m):
    bot.reply_to(m,f"💰 Số dư: {get_balance(m.chat.id)}đ")

@bot.message_handler(commands=['nap'])
def nap(m):
    bot.reply_to(m,
f"""
💳 *NẠP TIỀN*

✔ STK: 0971487462
✔ MB Bank
✔ Nội dung: {m.chat.id}

📸 Sau chuyển khoản → gửi ảnh bill vào bot
""",parse_mode="Markdown")

# bill gửi admin duyệt
@bot.message_handler(content_types=['photo'])
def bill(m):
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id,
                  caption=f"📩 Bill từ user: {m.chat.id}\nReply số tiền để cộng")
    bot.reply_to(m,"⏳ Bill đã gửi admin, chờ duyệt...")

# admin reply tiền vào bill
@bot.message_handler(func=lambda m: m.reply_to_message and m.chat.id==ADMIN_ID)
def admin_duyet(m):
    try:
        money=int(m.text)
        uid=int(m.reply_to_message.caption.split()[3])
        add_balance(uid,money)
        bot.send_message(uid,f"💰 +{money}đ đã được cộng!")
        bot.reply_to(m,"✔ Duyệt thành công")
    except: pass

@bot.message_handler(commands=['addmoney'])
def addmoney(m):
    if m.chat.id!=ADMIN_ID:return
    try:
        _,uid,money=m.text.split()
        add_balance(int(uid),int(money))
        bot.reply_to(m,"✔ Đã cộng tiền")
    except:bot.reply_to(m,"/addmoney id tiền")

@bot.message_handler(commands=['addacc'])
def addacc(m):
    if m.chat.id!=ADMIN_ID:return bot.reply_to(m,"Không phải admin")
    if not m.reply_to_message:return bot.reply_to(m,"Reply tin ACC dạng user|pass")
    with open("acc.txt","a",encoding="utf-8") as f:f.write(m.reply_to_message.text+"\n")
    bot.reply_to(m,"✔ Đã thêm vào kho")

@bot.message_handler(commands=['buy'])
def buy(m):
    try:price=int(m.text.split()[1])
    except:return bot.reply_to(m,"/buy <giá>")
    if get_balance(m.chat.id)<price:return bot.reply_to(m,"❌ Không đủ tiền")
    acc=get_acc()
    if not acc:return bot.reply_to(m,"⚠ Hết hàng")
    set_balance(m.chat.id,get_balance(m.chat.id)-price)
    save_history(m.chat.id,m.from_user.username,price,acc)
    bot.reply_to(m,f"🎉 Mua thành công!\nACC: `{acc}`",parse_mode="Markdown")

@bot.message_handler(commands=['history'])
def history(m):
    h=get_history(m.chat.id)
    if h==[]:return bot.reply_to(m,"📭 Chưa có lịch sử mua")
    bot.reply_to(m,"📜 Lịch sử:\n\n"+"\n".join(h[-10:]))

@bot.message_handler(commands=['top'])
def top(m):
    cur.execute("SELECT id,balance FROM users ORDER BY balance DESC LIMIT 10")
    msg="🏆 TOP GIÀU NHẤT:\n\n"
    for i,(uid,money) in enumerate(cur.fetchall(),1):
        msg+=f"{i}. {uid} — {money}đ\n"
    bot.reply_to(m,msg)

# ⭐ lệnh mới chỉ dành cho ADMIN
@bot.message_handler(commands=['getacc'])
def getacc(m):
    if m.chat.id!=ADMIN_ID:return bot.reply_to(m,"⛔ Không có quyền!")
    if not os.path.exists("acc.txt"):return bot.reply_to(m,"📁 acc.txt không tồn tại")
    bot.send_document(m.chat.id,open("acc.txt","rb"))
    bot.reply_to(m,"📤 Đây là file acc hiện tại")

print("BOT RUNNING...")
bot.infinity_polling()
