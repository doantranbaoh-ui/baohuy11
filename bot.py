#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback, os
from telebot import types
from keep_alive import keep_alive  # <-- import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"  # Thay bằng token mới
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DB =================
conn = sqlite3.connect("data.db", check_same_thread=False, isolation_level=None)
c = conn.cursor()
db_lock = threading.Lock()

def init_db():
    with db_lock:
        c.execute("""CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,balance INTEGER DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(id INTEGER PRIMARY KEY AUTOINCREMENT,acc TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS purchases(user_id TEXT,acc TEXT,time TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,file_id TEXT,amount INTEGER,status TEXT,created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS giftcode(code TEXT PRIMARY KEY,amount INTEGER,used_by TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS admins(user_id TEXT PRIMARY KEY,level INTEGER DEFAULT 3)""")
        c.execute("INSERT OR IGNORE INTO admins(user_id,level) VALUES (?,?)",(str(OWNER_ID),3))
init_db()

# ================= UTILS =================
def log_exc(tag="ERR"):
    print(f"--- {tag} ---")
    traceback.print_exc()
    print("-----------")

def ensure_user(uid): 
    with db_lock:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))

def get_balance(uid):
    ensure_user(uid)
    with db_lock:
        c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
        r=c.fetchone()
    return int(r[0]) if r else 0

def add_money(uid,amount):
    ensure_user(uid)
    with db_lock:
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,uid))

def deduct(uid,amount):
    bal=get_balance(uid)
    if bal<amount: return False
    with db_lock:
        c.execute("UPDATE users SET balance=? WHERE user_id=?",(bal-amount,uid))
    return True

def get_role(uid):
    with db_lock:
        c.execute("SELECT level FROM admins WHERE user_id=?",(str(uid),))
        r=c.fetchone()
    return int(r[0]) if r else 0

def is_owner(uid): return get_role(uid)==3
def is_admin(uid): return get_role(uid)>=2
def is_support(uid): return get_role(uid)>=1

def make_code(n=10):
    return ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(n))

# ================= HANDLER =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        bot.reply_to(m,"🎮 *SHOP ACC RANDOM*\nChào bạn!\n\nSử dụng lệnh:\n/random - Mua acc random\n/myacc - Xem acc đã mua\n/sodu - Xem số dư\n/dice - Mini game dice\n/slot - Mini game slot\n/nap - Nạp tiền\n/buy - Mua acc random",parse_mode="Markdown")
    except: log_exc("/start")

@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        bot.reply_to(m,f"💰 Số dư: *{get_balance(str(m.from_user.id))}đ*",parse_mode="Markdown")
    except: log_exc("/sodu")

@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    try:
        uid=str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
            rows=c.fetchall()
        if not rows: return bot.reply_to(m,"📭 Bạn chưa mua acc nào.")
        text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except: log_exc("/myacc")

# ================= RANDOM =================
@bot.message_handler(commands=["buy","random"])
def cmd_buy(m):
    try:
        uid=str(m.from_user.id)
        if not deduct(uid,PRICE_RANDOM):
            return bot.reply_to(m,"❌ Không đủ tiền")
        with db_lock:
            c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
            row=c.fetchone()
            if not row:
                add_money(uid,PRICE_RANDOM)
                return bot.reply_to(m,"⚠ Hết hàng, tiền đã hoàn lại")
            acc_id, acc_val = row
            c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
            c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
        bot.reply_to(uid,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
    except: log_exc("cmd_buy")

# ================= NẠP TIỀN =================
@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    try:
        parts=m.text.split()
        if len(parts)<2: return bot.reply_to(m,"📌 /nap <sotien>")
        amount=int(parts[1])
        txt=f"💳 Hướng dẫn nạp tiền:\n• STK: *0971487462*\n• Ngân hàng: MB\n• Nội dung: `{m.from_user.id}`\n• Số tiền: *{amount}đ*\nGửi ảnh bill vào chat để admin duyệt."
        bot.reply_to(m,txt,parse_mode="Markdown")
    except: log_exc("/nap")

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    try:
        uid=str(msg.from_user.id)
        file_id=msg.photo[-1].file_id
        with db_lock:
            c.execute("INSERT INTO bills(user_id,file_id,amount,status,created_at) VALUES(?,?,?,?,?)",(uid,file_id,0,"pending",time.ctime()))
            bill_id=c.lastrowid
        bot.reply_to(msg,f"⏳ Hoá đơn đã gửi, chờ admin duyệt. (Bill ID: {bill_id})")
        for ad in [OWNER_ID]:
            try:
                bot.send_photo(int(ad),file_id,caption=f"Bill #{bill_id} từ {uid}")
            except: pass
    except: log_exc("photo handler")

# ================= MINI GAMES =================
@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    try:
        roll=random.randint(1,6)
        reward=roll*200
        add_money(str(m.from_user.id),reward)
        bot.reply_to(m,f"🎲 Lắc ra *{roll}* → +{reward}đ",parse_mode="Markdown")
    except: log_exc("/dice")

@bot.message_handler(commands=["slot"])
def cmd_slot(m):
    try:
        icons=['🍒','💎','⭐','7️⃣']
        s=[random.choice(icons) for _ in range(3)]
        if s.count(s[0])==3:
            add_money(str(m.from_user.id),10000)
            bot.reply_to(m,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.reply_to(m,f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except: log_exc("/slot")

# ================= ADMIN: QUẢN LÝ KHO =================
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    if not is_admin(m.from_user.id): return
    data=m.text.replace("/addacc","").strip()
    if not data: return bot.reply_to(m,"📌 /addacc email:pass")
    with db_lock:
        c.execute("INSERT INTO stock_acc(acc) VALUES(?)",(data,))
    bot.reply_to(m,"➕ Đã thêm acc vào kho")

@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    if not is_admin(m.from_user.id): return
    with db_lock:
        c.execute("SELECT COUNT(*) FROM stock_acc")
        cnt=c.fetchone()[0]
    bot.reply_to(m,f"📦 Còn {cnt} ACC trong kho")

# ================= ADMIN: MONEY & BROADCAST =================
@bot.message_handler(commands=["addmoney"])
def cmd_addmoney(m):
    if not is_admin(m.from_user.id): return
    try:
        _,uid,amount=m.text.split()
        amount=int(amount)
        add_money(uid,amount)
        bot.reply_to(m,f"Đã cộng {amount}đ cho {uid}")
        try: bot.send_message(int(uid),f"✅ Admin đã cộng {amount}đ")
        except: pass
    except: log_exc("/addmoney")

# ================= DAILY REPORT =================
def daily_report_thread():
    while True:
        try:
            with db_lock:
                c.execute("SELECT COUNT(*) FROM stock_acc")
                count=c.fetchone()[0]
            bot.send_message(OWNER_ID,f"📅 Báo cáo tự động: Còn {count} ACC trong kho")
        except: log_exc("daily_report")
        time.sleep(DAILY_REPORT_HOUR)
threading.Thread(target=daily_report_thread,daemon=True).start()

# ================= START BOT =================
keep_alive()  # <-- chạy keep_alive.py
print("BOT STARTED!")
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60,skip_pending=True)
    except Exception as e:
        print("BOT CRASH:",e)
        time.sleep(5)
