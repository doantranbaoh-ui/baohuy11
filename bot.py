#!/usr/bin/env python3
# ================== BOT SHOP ACC FULL - Hoàn chỉnh & ổn định ==================

import telebot
from telebot import types
import sqlite3, random, time, threading, traceback, string, secrets, os

# ================== CONFIG ==================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"           # token bot của bạn
ADMINS = ["5736655322"]             # ID admin dạng string
PRICE_RANDOM = 2000                # giá random acc
REPORT_TIME = 24*60*60             # báo cáo tồn kho 24h/lần

from keep_alive import keep_alive  # để chạy 24/7 trên render/replit

# ================== DATABASE ==================
DB = "data.db"
db = sqlite3.connect(DB, check_same_thread=False)
c = db.cursor()
lock = threading.Lock()

def setup():
    with lock:
        c.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, balance INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, acc TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS purchase (user TEXT, acc TEXT, time TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS giftcode (code TEXT PRIMARY KEY, amount INTEGER, used_by TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS bill (id INTEGER PRIMARY KEY AUTOINCREMENT,user TEXT,amount INTEGER,file TEXT,status TEXT,time TEXT)")
        db.commit()
setup()

def user_add(uid):
    with lock:
        c.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(uid,))
        db.commit()

def bal(uid):
    user_add(uid)
    with lock:
        c.execute("SELECT balance FROM users WHERE id=?", (uid,))
        return c.fetchone()[0]

def add(uid,amount):
    user_add(uid)
    with lock:
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount,uid)); db.commit()

def minus(uid,amount):
    if bal(uid)<amount: return False
    with lock:
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount,uid)); db.commit()
        return True

def admin(uid): return str(uid) in ADMINS

def menu(chat):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛍 Mua Random","📦 Acc đã mua")
    kb.add("💰 Số dư","🎲 Dice","🎰 Slot")
    kb.add("🎁 Giftcode","💳 Nạp tiền")
    return kb

bot = telebot.TeleBot(TOKEN,parse_mode="Markdown")

# ================== START ==================
@bot.message_handler(commands=["start","help"])
def start(m):
    user_add(str(m.from_user.id))
    bot.send_message(m.chat.id,
    "🎮 *SHOP TÀI KHOẢN RANDOM*\n"
    "• Mua acc random\n"
    "• Nạp tiền qua bill\n"
    "• Giftcode, minigame\n"
    "• Tự động lưu lịch sử mua\n",reply_markup=menu(m.chat.id))

# ================== SỐ DƯ ==================
@bot.message_handler(regexp="💰")
@bot.message_handler(commands=["sodu"])
def sodu(m): bot.reply_to(m,f"💰 Số dư hiện tại: *{bal(str(m.from_user.id))}đ*")

# ================== MUA ACC RANDOM ==================
@bot.message_handler(regexp="🛍")
@bot.message_handler(commands=["random"])
def buy_rand(m):
    kb=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(f"Mua {PRICE_RANDOM}đ",callback_data="buy_random"))
    bot.send_message(m.chat.id,"📦 Gói Random Account",reply_markup=kb)

@bot.callback_query_handler(func=lambda x:x.data=="buy_random")
def random_buy(c):
    uid=str(c.from_user.id)
    if not minus(uid,PRICE_RANDOM): return bot.answer_callback_query(c.id,"Thiếu tiền!",True)

    with lock:
        c.execute("SELECT id,acc FROM stock ORDER BY RANDOM() LIMIT 1")
        acc=c.fetchone()
        if not acc:
            add(uid,PRICE_RANDOM)
            return bot.answer_callback_query(c.id,"Hết hàng! hoàn tiền",True)
        c.execute("DELETE FROM stock WHERE id=?",(acc[0],))
        c.execute("INSERT INTO purchase VALUES(?,?,?)",(uid,acc[1],time.ctime()))
        db.commit()

    bot.send_message(uid,f"🛍 ACC của bạn:\n`{acc[1]}`")
    bot.answer_callback_query(c.id,"Mua thành công!")

# ================== XEM ACC ĐÃ MUA ==================
@bot.message_handler(regexp="📦")
@bot.message_handler(commands=["myacc"])
def myacc(m):
    with lock:
        c.execute("SELECT acc,time FROM purchase WHERE user=?",(str(m.from_user.id),))
        data=c.fetchall()
    if not data: return bot.reply_to(m,"📭 Chưa mua acc nào")
    bot.reply_to(m,"🧾 Lịch sử mua:\n"+"\n".join([f"`{i[0]}` | {i[1]}"for i in data]))

# ================== ADMIN QUẢN LÝ STOCK ==================
@bot.message_handler(commands=["addacc"])
def addacc(m):
    if not admin(m.from_user.id): return
    acc=m.text.replace("/addacc","").strip()
    if not acc: return bot.reply_to(m,"/addacc user:pass")
    with lock: c.execute("INSERT INTO stock(acc) VALUES(?)",(acc,)); db.commit()
    bot.reply_to(m,"✅ Đã thêm acc")

@bot.message_handler(commands=["stock"])
def stock(m):
    if not admin(m.from_user.id): return
    with lock: c.execute("SELECT COUNT(*) FROM stock"); n=c.fetchone()[0]
    bot.reply_to(m,f"📦 Kho còn: {n} acc")

# ================== GIFT CODE ==================
def code(): return ''.join(random.choice(string.ascii_uppercase+string.digits) for _ in range(10))

@bot.message_handler(commands=["makecode"])
def mk(m):
    if not admin(m.from_user.id): return
    _,money,count=m.text.split();money=int(money);count=int(count)
    codes=[]
    with lock:
        for _ in range(count):
            cde=code()
            c.execute("INSERT INTO giftcode VALUES(?,?,NULL)",(cde,money))
            codes.append(cde)
        db.commit()
    bot.reply_to(m,"🎁 Giftcode:\n"+"\n".join(codes))

@bot.message_handler(regexp="🎁")
@bot.message_handler(commands=["redeem"])
def redeem(m):
    if len(m.text.split())<2: return bot.reply_to(m,"/redeem CODE")
    code_in=m.text.split()[1].upper();uid=str(m.from_user.id)
    with lock:
        c.execute("SELECT amount,used_by FROM giftcode WHERE code=?",(code_in,))
        r=c.fetchone()
        if not r: return bot.reply_to(m,"❌ Code sai!")
        if r[1]: return bot.reply_to(m,"❌ Code đã dùng!")
        add(uid,r[0])
        c.execute("UPDATE giftcode SET used_by=? WHERE code=?", (uid,code_in));db.commit()
    bot.reply_to(m,f"🎉 +{r[0]}đ vào ví!")

# ================== NẠP TIỀN BILL ==================
@bot.message_handler(regexp="💳")
@bot.message_handler(commands=["nap"])
def nap(m):
    bot.reply_to(m,
    "💳 Nạp tiền – gửi ảnh bill để duyệt\n"
    "```ND chuyển khoản = ID Telegram của bạn```")

@bot.message_handler(content_types=["photo"])
def bill_img(m):
    uid=str(m.from_user.id)
    file=m.photo[-1].file_id
    with lock:
        c.execute("INSERT INTO bill(user,amount,file,status,time) VALUES(0,?,?,?,?)",(file,"pending",time.ctime()))
        db.commit();bid=c.lastrowid

    bot.reply_to(m,f"📨 Bill gửi (ID {bid}) – chờ duyệt")

    for ad in ADMINS:
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✔ +10k",callback_data=f"ok:{bid}:10000"),
               types.InlineKeyboardButton("✔ +20k",callback_data=f"ok:{bid}:20000"))
        kb.add(types.InlineKeyboardButton("❌",callback_data=f"no:{bid}"),
               types.InlineKeyboardButton("✏ Nhập",callback_data=f"set:{bid}"))
        bot.send_photo(ad,file,caption=f"Bill {bid} từ {uid}",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith(("ok","no","set")))
def bill_cb(cq):
    if not admin(cq.from_user.id): return bot.answer_callback_query(cq.id,"Không quyền")
    act,bid,*x=cq.data.split(":")

    if act=="ok":
        money=int(x[0])
        with lock:
            c.execute("SELECT user,status FROM bill WHERE id=?",(bid,))
            u=c.fetchone()
            if not u or u[1]!="pending": return cq.answer("Đã xử lý")
            uid=u[0];c.execute("UPDATE bill SET status='done',amount=? WHERE id=?",(money,bid));db.commit()
        add(uid,money);bot.send_message(uid,f"💰 Bill {bid} duyệt +{money}đ");return cq.answer("OK")

    if act=="no":
        with lock: c.execute("UPDATE bill SET status='fail' WHERE id=?",(bid,));db.commit()
        return cq.answer("Đã từ chối")

    if act=="set":
        bot.send_message(cq.from_user.id,f"/setbill {bid} <sotien>")
        return cq.answer("Nhập tay")

@bot.message_handler(commands=["setbill"])
def set_bill(m):
    if not admin(m.from_user.id): return
    _,bid,val=m.text.split();val=int(val)
    with lock:
        c.execute("SELECT user,status FROM bill WHERE id=?",(bid,))
        u=c.fetchone()
        if not u or u[1]!="pending":return bot.reply_to(m,"Đã xử lý")
        uid=u[0];c.execute("UPDATE bill SET status='done',amount=? WHERE id=?",(val,bid));db.commit()
    add(uid,val);bot.send_message(uid,f"Bill {bid} duyệt +{val}đ")

# ================== MINI GAME ==================
@bot.message_handler(regexp="🎲")
@bot.message_handler(commands=["dice"])
def dice(m):
    roll=random.randint(1,6)
    win=roll*200
    add(str(m.from_user.id),win)
    bot.reply_to(m,f"🎲 {roll} ➜ +{win}đ")

@bot.message_handler(regexp="🎰")
@bot.message_handler(commands=["slot"])
def slot(m):
    em=["🍒","⭐","💎","7️⃣"]
    s=[random.choice(em)for _ in range(3)]
    if len(set(s))==1:
        add(str(m.from_user.id),10000)
        bot.reply_to(m,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
    else: bot.reply_to(m,f"🎰 {' '.join(s)}\nHụt rồi")

# ================== AUTO REPORT STOCK ==================
def auto_report():
    while True:
        try:
            with lock:
                c.execute("SELECT COUNT(*) FROM stock");n=c.fetchone()[0]
            for ad in ADMINS: bot.send_message(ad,f"📢 Kho còn {n} acc")
        except: pass
        time.sleep(REPORT_TIME)

threading.Thread(target=auto_report,daemon=True).start()

# ================== RUN BOT ==================
if __name__ == "__main__":
    keep_alive()
    while True:
        try:
            print("BOT RUNNING...")
            bot.infinity_polling(skip_pending=True,timeout=60,long_polling_timeout=60)
        except Exception as e:
            print("Lỗi! Restart bot",e)
            time.sleep(3)
