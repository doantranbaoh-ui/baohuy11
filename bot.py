#!/usr/bin/env python3
# ================================================
# BOT BÁN ACC RANDOM LIÊN QUÂN – FULL FEATURE
# ================================================

import telebot, sqlite3, random, os
from telebot import types
from keep_alive import keep_alive   # <== chạy web để uptime
keep_alive()

# ====================== CONFIG ======================
TOKEN       = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"
ADMIN_ID    = 5736655322                  # sửa ID admin vào đây
PRICE       = 2000                       # giá mỗi lần /buy
ACC_FILE    = "acc.txt"
DB_FILE     = "db.sqlite"

bot = telebot.TeleBot(TOKEN)

# ====================== DATABASE ======================
con = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    total_topup INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS topup_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    img_id TEXT,
    status TEXT DEFAULT 'pending'
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    account TEXT
)""")

con.commit()


# ====================== HÀM PHỤ ======================
def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_balance(uid, amount):
    if not user_exists(uid): create_user(uid)
    cur.execute("UPDATE users SET balance = balance + ?, total_topup = total_topup + ? WHERE id=?",(amount,amount,uid))
    con.commit()

def minus_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, uid))
    con.commit()

def user_exists(uid):
    cur.execute("SELECT id FROM users WHERE id=?", (uid,))
    return cur.fetchone()

def create_user(uid):
    cur.execute("INSERT INTO users(id,balance,total_topup) VALUES(?,?,?)",(uid,0,0))
    con.commit()

def random_acc():
    if not os.path.exists(ACC_FILE): return None
    with open(ACC_FILE,'r') as f:
        lines=f.read().splitlines()
    if not lines: return None
    acc=random.choice(lines)
    new=[x for x in lines if x!=acc]
    open(ACC_FILE,'w').write("\n".join(new))
    return acc


# ====================== COMMAND ======================
@bot.message_handler(commands=['start'])
def start(m):
    uid=m.from_user.id
    if not user_exists(uid): create_user(uid)
    bot.reply_to(m,
f"""👋 Chào {m.from_user.first_name}!

💰 Tiền hiện có: {get_balance(uid)}đ
🎁 Lệnh dùng:
—————————————
/buy – Mua acc random {PRICE}đ
/nap – Hướng dẫn nạp
/top – Top nạp tiền
/history – Lịch sử mua

(Admin)
/addacc user|pass
/sendfile – Gửi acc.txt
""")


# ====================== MUA ACC ======================
@bot.message_handler(commands=['buy'])
def buy(m):
    uid=m.from_user.id
    balance=get_balance(uid)

    if balance < PRICE: 
        return bot.reply_to(m,f"❗ Bạn còn thiếu {PRICE-balance}đ để mua!")

    acc=random_acc()
    if not acc: return bot.reply_to(m,"❗ Hết acc rồi, đợi admin thêm!")

    minus_balance(uid, PRICE)
    cur.execute("INSERT INTO history(user_id,account) VALUES(?,?)",(uid,acc))
    con.commit()

    bot.reply_to(m,f"🎉 Mua thành công!\n🔑 Tài khoản: `{acc}`",parse_mode="Markdown")


# ====================== NẠP TIỀN ======================
@bot.message_handler(commands=['nap'])
def nap(m):
    bot.reply_to(m,
"""💳 NẠP TIỀN BANK (gửi ảnh chuyển khoản kèm caption)

📌 Cú pháp:
Gửi ảnh + ghi chú:  `nap 20000`

⏳ Admin sẽ duyệt trong vài phút.""")

@bot.message_handler(content_types=['photo'])
def photo(m):
    if not (m.caption and m.caption.startswith("nap")):
        return bot.reply_to(m,"📌 Gửi ảnh + ghi: nap số_tiền")

    try: amount=int(m.caption.split()[1])
    except: return bot.reply_to(m,"Sai cú pháp. VD: nap 20000")

    uid=m.from_user.id
    img=m.photo[-1].file_id

    cur.execute("INSERT INTO topup_requests(user_id,amount,img_id) VALUES(?,?,?)",(uid,amount,img))
    con.commit()

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✔ Duyệt", callback_data=f"ok_{uid}_{amount}"),
        types.InlineKeyboardButton("✖ Từ chối", callback_data=f"no_{uid}")
    )

    bot.send_photo(ADMIN_ID,img,
        f"💰 YÊU CẦU NẠP\nUser: {uid}\nSố tiền: {amount}đ",
        reply_markup=markup)

    bot.reply_to(m,"⏳ Đã gửi admin duyệt...")


# ====================== XỬ LÝ DUYỆT ======================
@bot.callback_query_handler(func=lambda c:True)
def cb(c):

    if c.from_user.id!=ADMIN_ID:
        return bot.answer_callback_query(c.id,"Bạn không phải admin!")

    # duyệt
    if c.data.startswith("ok"):
        _,uid,amount=c.data.split("_")
        add_balance(int(uid),int(amount))
        bot.send_message(uid,f"💳 Nạp {amount}đ thành công!")
        return bot.edit_message_caption(chat_id=c.message.chat.id,
            message_id=c.message.message_id,
            caption="✔ Đã duyệt giao dịch")

    # từ chối
    if c.data.startswith("no"):
        _,uid=c.data.split("_")
        bot.send_message(uid,"❗ Giao dịch nạp bị từ chối.")
        return bot.edit_message_caption(chat_id=c.message.chat.id,
            message_id=c.message.message_id,
            caption="✖ Đã từ chối yêu cầu")


# ====================== TOP & HISTORY ======================
@bot.message_handler(commands=['top'])
def top(m):
    cur.execute("SELECT id,total_topup FROM users ORDER BY total_topup DESC LIMIT 10")
    ranks=cur.fetchall()
    if not ranks: return bot.reply_to(m,"Chưa có ai nạp!")

    text="🏆 TOP NẠP TIỀN\n\n"
    for i,(uid,total) in enumerate(ranks,1):
        text+=f"{i}. {uid} – {total}đ\n"
    bot.reply_to(m,text)

@bot.message_handler(commands=['history'])
def his(m):
    uid=m.from_user.id
    cur.execute("SELECT account FROM history WHERE user_id=?",(uid,))
    data=cur.fetchall()
    if not data: return bot.reply_to(m,"Chưa mua lần nào!")
    text="\n".join([f"🔑 {x[0]}" for x in data[-10:]])
    bot.reply_to(m,"📝 Lịch sử 10 lần cuối:\n"+text)


# ====================== ADMIN TOOLS ======================
@bot.message_handler(commands=['addacc'])
def addacc(m):
    if m.from_user.id!=ADMIN_ID: return
    acc=m.text.replace("/addacc ","")
    open(ACC_FILE,'a').write(acc+"\n")
    bot.reply_to(m,"✔ Đã thêm acc!")

@bot.message_handler(commands=['sendfile'])
def sendfile(m):
    if m.from_user.id!=ADMIN_ID: return
    bot.send_document(m.chat.id, open(ACC_FILE,'rb'))


# ====================== RUN ======================
bot.infinity_polling()
