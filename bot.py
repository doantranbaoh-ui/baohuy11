from keep_alive import keep_alive
keep_alive()

import telebot, sqlite3, os

TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY" # <-- nhập token bot
ADMIN_ID = 5736655322    # <-- sửa ID admin

bot = telebot.TeleBot(TOKEN)

# ========================= DATABASE =========================
if not os.path.exists("data.db"):
    conn = sqlite3.connect("data.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )""")
    conn.commit()
else:
    conn = sqlite3.connect("data.db", check_same_thread=False)
    cur = conn.cursor()

# ========================= FUNCTION =========================
def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id,balance) VALUES(?,0)", (uid,))
    conn.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def set_balance(uid, amount):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (amount, uid))
    conn.commit()

def add_balance(uid, amount):
    new = get_balance(uid) + amount
    set_balance(uid, new)
    return new

# Lấy acc từ acc.txt
def get_account():
    if not os.path.exists("acc.txt"): return None
    with open("acc.txt","r",encoding="utf-8") as f:
        data = f.readlines()
    if len(data)==0: return None
    acc = data[0].strip()
    open("acc.txt","w",encoding="utf-8").write("".join(data[1:]))
    return acc

# ========================= COMMAND =========================
@bot.message_handler(commands=['start'])
def start(m):
    add_user(m.from_user.id)
    bot.reply_to(m,
"""
🔥 **SHOP ACC LIÊN QUÂN**  
Lệnh sử dụng:

💰 /balance — Xem số dư  
💳 /nap — Nạp tiền  
🎁 /buy <giá> — Mua acc random (VD: /buy 2000)  
📥 /addacc (admin) — Thêm acc vào kho bằng reply  
💵 /addmoney <id> <số tiền> (admin)  
""")

# xem số dư
@bot.message_handler(commands=['balance'])
def bal(m):
    bot.reply_to(m, f"💰 Số dư: {get_balance(m.from_user.id)}đ")

# nạp tiền
@bot.message_handler(commands=['nap'])
def nap(m):
    bot.send_message(m.chat.id,
"""
💳 *Hướng dẫn nạp tiền*

Chuyển khoản:

- STK: 0971487462
- MB BANK
- Nội dung: NAP {id_user}
- Số tiền: tùy ý

📸 Sau khi chuyển, gửi ảnh hóa đơn vào bot — admin sẽ duyệt & cộng tiền.
""".replace("{id_user}", str(m.from_user.id)))

# BOT NHẬN ẢNH BILL & GỬI ADMIN DUYỆT
@bot.message_handler(content_types=['photo'])
def bill(m):
    uid = m.from_user.id
    caption = f"🧾 Bill nạp tiền\nUser: {uid}\nReply tin này + số tiền để duyệt."
    bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=caption)
    bot.reply_to(m,"📨 Đã gửi yêu cầu, vui lòng đợi admin duyệt.")

# Admin thêm tiền
@bot.message_handler(commands=['addmoney'])
def addmoney(m):
    if m.from_user.id!=ADMIN_ID: return
    try:
        _, uid, amount = m.text.split()
        add_balance(int(uid), int(amount))
        bot.reply_to(m,"✔ Đã cộng tiền")
    except:
        bot.reply_to(m,"❗ Format: /addmoney <id> <số tiền>")

# Admin thêm acc qua reply
@bot.message_handler(commands=['addacc'])
def addacc(m):
    if m.from_user.id!=ADMIN_ID:
        return bot.reply_to(m,"Bạn không phải admin.")

    if not m.reply_to_message:
        return bot.reply_to(m,"Reply tin nhắn chứa acc dạng:\n`user|pass`")

    acc = m.reply_to_message.text.strip()
    with open("acc.txt","a",encoding="utf-8") as f: f.write(acc+"\n")

    bot.reply_to(m,"✔ Đã thêm vào kho acc.")

# mua acc
@bot.message_handler(commands=['buy'])
def buy(m):
    try:
        price = int(m.text.split()[1])
    except:
        return bot.reply_to(m,"❗ Dùng: /buy <giá>")

    uid=m.from_user.id
    bal=get_balance(uid)
    if bal < price:
        return bot.reply_to(m,"💸 Không đủ tiền!")

    acc=get_account()
    if not acc:
        return bot.reply_to(m,"❗ Hết hàng!")

    set_balance(uid, bal-price)
    bot.reply_to(m, f"🎉 Mua thành công!\nTài khoản: `{acc}`\nSố dư còn: {bal-price}đ", parse_mode="Markdown")

print("BOT RUNNING...")
bot.infinity_polling()
