import telebot, sqlite3, random, time, threading, traceback
from telebot import types
from keep_alive import keep_alive

# ================= CONFIG ==================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"
ADMINS = ["5736655322"]
PRICE_RANDOM = 2000

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

def sql(q, p=(), commit=False, fetch=False):
    try:
        c.execute(q,p)
        if commit: conn.commit()
        if fetch: return c.fetchall()
    except Exception as e:
        print("SQL Error:", e)

sql("""CREATE TABLE IF NOT EXISTS users(
user_id TEXT PRIMARY KEY, balance INTEGER DEFAULT 0)""", commit=True)

sql("""CREATE TABLE IF NOT EXISTS stock_acc(
id INTEGER PRIMARY KEY AUTOINCREMENT, acc TEXT)""", commit=True)

sql("""CREATE TABLE IF NOT EXISTS purchases(
user_id TEXT, acc TEXT, time TEXT)""", commit=True)

sql("""CREATE TABLE IF NOT EXISTS giftcode(
code TEXT PRIMARY KEY, amount INTEGER, used_by TEXT)""", commit=True)

sql("""CREATE TABLE IF NOT EXISTS bills(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id TEXT, file_id TEXT, status TEXT)""", commit=True)

# ================= FUNC =====================
def user(uid):
    sql("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,),commit=True)
def bal(uid):
    user(uid)
    return sql("SELECT balance FROM users WHERE user_id=?",(uid,),fetch=True)[0][0]
def add(uid,amount):
    user(uid)
    sql("UPDATE users SET balance = balance + ? WHERE user_id=?",(amount,uid),commit=True)
def deduct(uid,amount):
    if bal(uid)<amount: return False
    sql("UPDATE users SET balance = balance - ? WHERE user_id=?",(amount,uid),commit=True); return True
def admin(id): return str(id) in ADMINS

# ================= MENU =====================
def menu(chatid):
    btn = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn.row("🎲 Dice","🎰 Slot")
    btn.row("🛍 Random Acc","💰 Số dư")
    btn.row("🎁 Giftcode","📦 Acc đã mua")
    bot.send_message(chatid,"📌 Menu chính",reply_markup=btn)

# ================= START ====================
@bot.message_handler(commands=["start"])
def start(msg):
    user(str(msg.from_user.id))
    bot.reply_to(msg,"🎮 *SHOP ACC RANDOM*\nChọn chức năng bên dưới👇")
    menu(msg.chat.id)

# ================= USERS ====================
@bot.message_handler(func=lambda m:m.text=="💰 Số dư")
def _bal(msg):
    bot.reply_to(msg,f"💰 Số dư: *{bal(str(msg.from_user.id))}đ*")

@bot.message_handler(func=lambda m:m.text=="📦 Acc đã mua")
def _my(msg):
    uid=str(msg.from_user.id)
    data=sql("SELECT acc,time FROM purchases WHERE user_id=?",(uid,),fetch=True)
    if not data: return bot.reply_to(msg,"📭 Chưa mua acc nào!")
    text="\n".join([f"`{i[0]}` | {i[1]}" for i in data])
    bot.reply_to(msg,f"📄 Lịch sử mua:\n{text}")

# ================= Random Buy =================
@bot.message_handler(func=lambda m:m.text=="🛍 Random Acc")
def buy(msg):
    uid=str(msg.from_user.id)
    kb=types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(f"Mua ({PRICE_RANDOM}đ)",callback_data="confirm_buy"))
    bot.send_message(msg.chat.id,"Bạn có muốn mua ACC random?",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data=="confirm_buy")
def do_buy(cq):
    uid=str(cq.from_user.id)
    if not deduct(uid,PRICE_RANDOM):
        return bot.answer_callback_query(cq.id,"❌ Không đủ tiền!",show_alert=True)

    acc = sql("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1",fetch=True)
    if not acc:
        add(uid,PRICE_RANDOM)
        return bot.send_message(uid,"⚠ Hết hàng – hoàn tiền!")

    acc_id,acc_val = acc[0]
    sql("DELETE FROM stock_acc WHERE id=?",(acc_id,),commit=True)
    sql("INSERT INTO purchases VALUES(?,?,?)",(uid,acc_val,time.ctime()),commit=True)

    bot.send_message(uid,f"🛍 ACC của bạn:\n`{acc_val}`")

# ================= NẠP TIỀN ==================
@bot.message_handler(commands=["nap"])
def nap(msg):
    try: amount=msg.text.split()[1]
    except: return bot.reply_to(msg,"📌 /nap <sotien>")
    bot.reply_to(msg,f"""
💳 *Thông tin chuyển khoản*

• MB BANK — 0971487462  
• Nội dung: `{msg.from_user.id}`  
• Số tiền: *{amount}đ*

📌 Gửi ảnh bill để chờ duyệt
""")

@bot.message_handler(content_types=["photo"])
def bill(msg):
    uid=str(msg.from_user.id)
    file_id=msg.photo[-1].file_id
    sql("INSERT INTO bills(user_id,file_id,status) VALUES(?,'pending')",(uid,file_id,"pending"),commit=True)

    bot.reply_to(msg,"⏳ Bill đã gửi, chờ admin duyệt")

    for ad in ADMINS:
        kb=types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("✔ Duyệt +10k",callback_data=f"ok_{uid}"),
            types.InlineKeyboardButton("❌ Hủy",callback_data=f"no_{uid}")
        )
        bot.send_photo(ad,file_id,caption=f"Bill của {uid}",reply_markup=kb)

@bot.callback_query_handler(func=lambda c:c.data.startswith("ok_") or c.data.startswith("no_"))
def bill_action(cq):
    uid=cq.data[3:]
    if not admin(cq.from_user.id): return bot.answer_callback_query(cq.id,"No perm")

    if cq.data.startswith("ok_"):
        add(uid,10000)
        bot.send_message(uid,"💰 Bill duyệt +10.000đ")
        bot.answer_callback_query(cq.id,"✔ Done")
    else:
        bot.send_message(uid,"❌ Bill không hợp lệ")
        bot.answer_callback_query(cq.id,"Đã từ chối")

# ================= GAME ======================
@bot.message_handler(func=lambda m:m.text=="🎲 Dice")
def dice(msg):
    roll=random.randint(1,6)
    reward=roll*200
    add(str(msg.from_user.id),reward)
    bot.reply_to(msg,f"🎲 {roll} → +{reward}đ")

@bot.message_handler(func=lambda m:m.text=="🎰 Slot")
def slot(msg):
    s=[random.choice(["🍒","💎","⭐","7️⃣"]) for _ in range(3)]
    if s.count(s[0])==3:
        add(str(msg.from_user.id),10000)
        bot.reply_to(msg,f"{' '.join(s)}\n🔥 Nổ hũ +10k")
    else:
        bot.reply_to(msg,f"{' '.join(s)}\n😢 Hụt rồi")

# ================= ADMIN =====================
@bot.message_handler(commands=["addacc"])
def add_stock(msg):
    if not admin(msg.from_user.id):return
    acc=msg.text.replace("/addacc ","")
    sql("INSERT INTO stock_acc(acc) VALUES(?)",(acc,),commit=True)
    bot.reply_to(msg,"Thêm thành công!")

@bot.message_handler(commands=["stock"])
def stk(msg):
    if not admin(msg.from_user.id):return
    c=sql("SELECT COUNT(*) FROM stock_acc",fetch=True)[0][0]
    bot.reply_to(msg,f"📦 Kho: {c} acc")

# ================= RUN ======================
keep_alive()

print("BOT RUNNING...")
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60)
    except Exception as e:
        print("ERR:",e); time.sleep(3)
