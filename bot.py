#!/usr/bin/env python3
# ===== BOT SHOP LIÊN QUÂN FULL + AUTO DUYỆT NẠP =====

import telebot, sqlite3, os
from telebot import types
from keep_alive import keep_alive

TOKEN = "6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"
ADMIN_ID = 5736655322     # EDIT ID ADMIN

bot = telebot.TeleBot(TOKEN)

# ========== DATABASE ==========
if not os.path.exists("db.sqlite"):
    open("db.sqlite","w").close()

con = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    total_topup INTEGER DEFAULT 0
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    data TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS topup_requests(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    img TEXT,
    status TEXT DEFAULT 'pending'
)""")

con.commit()

# ========== FILE ACC ==========
if not os.path.exists("acc.txt"):
    open("acc.txt","w").close()

def get_acc():
    with open("acc.txt") as f:
        accs=f.read().strip().splitlines()
    if not accs:return None
    acc=accs[0]
    with open("acc.txt","w") as f:f.write("\n".join(accs[1:]))
    return acc

def reg(uid):
    cur.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(uid,))
    con.commit()

# ========== UI START ==========
@bot.message_handler(commands=["start"])
def start(m):
    reg(m.from_user.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Số dư","🛒 Mua acc","💳 Nạp tiền")
    markup.add("📜 Lịch sử","🏆 Top nạp")

    bot.reply_to(m,
f"""
🔥 *SHOP ACC LIÊN QUÂN – AUTO* 🔥

Chào {m.from_user.first_name} 👋
Chức năng bot:

💰 /balance — Xem tiền
💳 /nap — Hướng dẫn nạp
🛒 /buy — Mua acc random 2K
📜 /history — Lịch sử mua
🏆 /top — Top nạp tiền

👑 ADMIN:
`/addbalance id tiền`
`/addacc user|pass`
`/getacc`

Gửi ảnh + nội dung: `nap 20000` để nạp tiền!
""",parse_mode="Markdown",reply_markup=markup)

# Bắt phím menu nhanh
@bot.message_handler(func=lambda x:x.text=="💰 Số dư")
def x(m): balance(m)
@bot.message_handler(func=lambda x:x.text=="💳 Nạp tiền")
def x(m): nap(m)
@bot.message_handler(func=lambda x:x.text=="🛒 Mua acc")
def x(m): buy(m)
@bot.message_handler(func=lambda x:x.text=="📜 Lịch sử")
def x(m): hist(m)
@bot.message_handler(func=lambda x:x.text=="🏆 Top nạp")
def x(m): top(m)

# ========== BALANCE ==========
@bot.message_handler(commands=["balance"])
def balance(m):
    bal=cur.execute("SELECT balance FROM users WHERE id=?",(m.from_user.id,)).fetchone()[0]
    bot.reply_to(m,f"💰 Số dư hiện tại: *{bal}đ*",parse_mode="Markdown")

# ========== NẠP TIỀN ==========
@bot.message_handler(commands=["nap"])
def nap(m):
    bot.reply_to(m,
"""
💳 *HƯỚNG DẪN NẠP TIỀN*

🏦 MB BANK  
🔢 STK: *0971487462*  
📌 Nội dung: `NAP-{telegram_id}`  
💰 Tối thiểu 10.000đ

📸 Sau khi chuyển khoản, gửi ảnh + nội dung:
`nap số_tiền`

Ví dụ: gửi ảnh kèm caption: `nap 20000`
""".replace("{telegram_id}",str(m.from_user.id)),parse_mode="Markdown")

# ========== XỬ LÝ ẢNH NẠP ==========
@bot.message_handler(content_types=["photo"])
def img(m):
    if not (m.caption and m.caption.startswith("nap")):
        return bot.reply_to(m,"❗ Caption ảnh phải dạng `nap số tiền`")

    try: amount=int(m.caption.split()[1])
    except:return bot.reply_to(m,"Sai cú pháp! Ví dụ:\n`nap 20000`",parse_mode="Markdown")

    uid=m.from_user.id
    img=m.photo[-1].file_id

    cur.execute("INSERT INTO topup_requests(user_id,amount,img) VALUES(?,?,?)",(uid,amount,img))
    con.commit()

    # Gửi cho admin duyệt
    kb=types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✔ DUYỆT",callback_data=f"ok_{uid}_{amount}"),
        types.InlineKeyboardButton("✖ TỪ CHỐI",callback_data=f"no_{uid}")
    )
    bot.send_photo(ADMIN_ID,img,f"💸 YÊU CẦU NẠP\nUser `{uid}`\nSố tiền: *{amount}đ*",parse_mode="Markdown",reply_markup=kb)
    bot.reply_to(m,"📥 Đã gửi yêu cầu nạp, vui lòng chờ admin duyệt!")

# ========== CALLBACK DUYỆT ==========
@bot.callback_query_handler(func=lambda c:c.data.startswith(("ok","no")))
def cb(c):
    if c.from_user.id!=ADMIN_ID:
        return bot.answer_callback_query(c.id,"Không phải admin")

    # DUYỆT
    if c.data.startswith("ok"):
        _,uid,amount=c.data.split("_")
        uid,amount=int(uid),int(amount)

        cur.execute("UPDATE users SET balance=balance+?, total_topup=total_topup+? WHERE id=?",(amount,amount,uid))
        con.commit()
        bot.send_message(uid,f"🎉 Nạp *{amount}đ* thành công! Số dư đã được cộng.",parse_mode="Markdown")
        bot.answer_callback_query(c.id,"Đã duyệt")
        return

    # TỪ CHỐI
    if c.data.startswith("no"):
        uid=int(c.data.replace("no_",""))
        bot.send_message(uid,"❗ Giao dịch nạp bị từ chối!")
        bot.answer_callback_query(c.id,"Đã từ chối")

# ========== BUY ==========
@bot.message_handler(commands=["buy"])
def buy(m):
    PRICE=2000
    uid=m.from_user.id
    bal=cur.execute("SELECT balance FROM users WHERE id=?",(uid,)).fetchone()[0]

    if bal<PRICE: return bot.reply_to(m,"❗ Không đủ tiền!")

    acc=get_acc()
    if not acc:return bot.reply_to(m,"⚠ Hết hàng, liên hệ admin thêm")

    cur.execute("UPDATE users SET balance=balance-? WHERE id=?",(PRICE,uid))
    cur.execute("INSERT INTO history(user_id,action,data) VALUES(?,?,?)",(uid,"BUY",acc))
    con.commit()

    bot.reply_to(m,f"🎉 *MUA THÀNH CÔNG*\n`{acc}`",parse_mode="Markdown")

# ========== LỊCH SỬ ==========
@bot.message_handler(commands=["history"])
def hist(m):
    data=cur.execute("SELECT data,time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10",(m.from_user.id,)).fetchall()
    if not data:return bot.reply_to(m,"Chưa mua lần nào!")
    msg="\n".join([f"• `{d[0]}` ({d[1]})" for d in data])
    bot.reply_to(m,"📜 *LỊCH SỬ MUA:*\n"+msg,parse_mode="Markdown")

# ========== TOP ==========
@bot.message_handler(commands=["top"])
def top(m):
    data=cur.execute("SELECT id,total_topup FROM users ORDER BY total_topup DESC LIMIT 10").fetchall()
    if not data:return bot.reply_to(m,"Chưa ai nạp!")
    text="🏆 *TOP NẠP TIỀN*\n"
    for i,(uid,money) in enumerate(data,1):
        text+=f"{i}. `{uid}` — {money}đ\n"
    bot.reply_to(m,text,parse_mode="Markdown")

# ========== ADMIN ==========
@bot.message_handler(commands=["addbalance"])
def addbalance(m):
    if m.from_user.id!=ADMIN_ID:return
    try:
        uid,amount=m.text.split()[1],int(m.text.split()[2])
        cur.execute("UPDATE users SET balance=balance+?, total_topup=total_topup+? WHERE id=?",(amount,amount,uid))
        con.commit()
        bot.reply_to(m,"✔ Đã cộng tiền")
    except:bot.reply_to(m,"Dùng: /addbalance id tiền")

@bot.message_handler(commands=["addacc"])
def addacc(m):
    if m.from_user.id!=ADMIN_ID:return
    acc=m.text.replace("/addacc ","")
    with open("acc.txt","a")as f:f.write(acc+"\n")
    bot.reply_to(m,"✔ Đã thêm acc")

@bot.message_handler(commands=["getacc"])
def getacc(m):
    if m.from_user.id!=ADMIN_ID:return
    bot.send_document(m.chat.id,open("acc.txt","rb"))

# RUN + KEEP ALIVE
keep_alive()
bot.infinity_polling()
