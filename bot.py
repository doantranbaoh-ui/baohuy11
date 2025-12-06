#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback, os
from keep_alive import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"  # Thay bằng token của bạn
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60  # 24h

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= KEEP ALIVE =================
keep_alive()  # Giữ bot luôn online

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
    print(f"[{time.ctime()}] --- {tag} ---")
    traceback.print_exc()
    print("-----------")

def ensure_user(uid):
    with db_lock:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(str(uid),))

def get_balance(uid):
    ensure_user(uid)
    with db_lock:
        c.execute("SELECT balance FROM users WHERE user_id=?",(str(uid),))
        r=c.fetchone()
    return int(r[0]) if r else 0

def add_money(uid,amount):
    ensure_user(uid)
    with db_lock:
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,str(uid)))

def deduct(uid,amount):
    bal=get_balance(uid)
    if bal<amount: return False
    with db_lock:
        c.execute("UPDATE users SET balance=? WHERE user_id=?",(bal-amount,str(uid)))
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

# ================= START / HELP =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        ensure_user(m.from_user.id)
        msg = ("🎮 *SHOP ACC RANDOM*\n"
               "Chào bạn!\n\n"
               "Các lệnh có sẵn:\n"
               "/random - Mua ACC random\n"
               "/myacc - Xem ACC đã mua\n"
               "/sodu - Kiểm tra số dư\n"
               "/dice - Chơi Dice\n"
               "/slot - Chơi Slot\n"
               "/nap <số tiền> - Nạp tiền\n"
               "/redeem <code> - Nhập giftcode")
        bot.send_message(m.chat.id,msg,parse_mode="Markdown")
    except: log_exc("/start")

# ================= BALANCE =================
@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        bot.send_message(m.chat.id,f"💰 Số dư: *{get_balance(m.from_user.id)}đ*",parse_mode="Markdown")
    except: log_exc("/sodu")

# ================= MY ACC =================
@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    try:
        uid=str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
            rows=c.fetchall()
        if not rows: return bot.send_message(m.chat.id,"📭 Bạn chưa mua acc nào.")
        text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.send_message(m.chat.id,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except: log_exc("/myacc")

# ================= BUY RANDOM =================
@bot.message_handler(commands=["random","buyrandom"])
def cmd_random(m):
    try:
        uid = str(m.from_user.id)
        if not deduct(uid,PRICE_RANDOM):
            return bot.send_message(m.chat.id,"❌ Không đủ tiền")
        with db_lock:
            c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
            row=c.fetchone()
            if not row:
                add_money(uid,PRICE_RANDOM)
                return bot.send_message(m.chat.id,"⚠ Hết hàng, tiền đã hoàn lại")
            acc_id,acc_val=row
            c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
            c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
        bot.send_message(m.chat.id,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
    except:
        log_exc("cmd_random")
        add_money(str(m.from_user.id),PRICE_RANDOM)
        bot.send_message(m.chat.id,"Có lỗi, tiền đã hoàn lại")

# ================= NAP TIEN =================
@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    try:
        parts=m.text.split()
        if len(parts)<2: return bot.send_message(m.chat.id,"📌 /nap <số tiền>")
        amount=int(parts[1])
        txt=f"💳 Hướng dẫn nạp tiền:\n• STK: *0971487462*\n• Ngân hàng: MB\n• Nội dung: `{m.from_user.id}`\n• Số tiền: *{amount}đ*\nGửi ảnh bill vào chat để admin duyệt."
        bot.send_message(m.chat.id,txt,parse_mode="Markdown")
    except: log_exc("/nap")

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    try:
        uid=str(msg.from_user.id)
        file_id=msg.photo[-1].file_id
        with db_lock:
            c.execute("INSERT INTO bills(user_id,file_id,amount,status,created_at) VALUES(?,?,?,?,?)",(uid,file_id,0,"pending",time.ctime()))
            bill_id=c.lastrowid
        bot.send_message(msg.chat.id,f"⏳ Hoá đơn đã gửi, chờ admin duyệt. (Bill ID: {bill_id})")
        for ad in [OWNER_ID]:
            try:
                bot.send_message(int(ad),f"Bill #{bill_id} từ {uid} (dùng /setbill {bill_id} <amount> để duyệt)")
            except: pass
    except: log_exc("photo handler")

@bot.message_handler(commands=["setbill"])
def cmd_setbill(m):
    try:
        if not is_admin(m.from_user.id): return
        parts=m.text.split()
        if len(parts)<3: return bot.send_message(m.chat.id,"📌 /setbill <bill_id> <amount>")
        bill_id=int(parts[1]); amount=int(parts[2])
        with db_lock:
            c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
            r=c.fetchone()
            if not r: return bot.send_message(m.chat.id,"Bill không tồn tại")
            if r[1]!="pending": return bot.send_message(m.chat.id,"Bill đã xử lý")
            user_id=r[0]
            c.execute("UPDATE bills SET amount=?,status=? WHERE id=?",(amount,"approved",bill_id))
        add_money(user_id,amount)
        bot.send_message(m.chat.id,f"Đã duyệt bill #{bill_id}, cộng {amount}đ cho {user_id}")
        try: bot.send_message(int(user_id),f"✅ Bill #{bill_id} đã được duyệt. Nhận {amount}đ")
        except: pass
    except: log_exc("/setbill")

# ================= MINI GAMES =================
@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    try:
        roll=random.randint(1,6)
        reward=roll*200
        add_money(m.from_user.id,reward)
        bot.send_message(m.chat.id,f"🎲 Lắc ra *{roll}* → +{reward}đ",parse_mode="Markdown")
    except: log_exc("/dice")

@bot.message_handler(commands=["slot"])
def cmd_slot(m):
    try:
        icons=['🍒','💎','⭐','7️⃣']
        s=[random.choice(icons) for _ in range(3)]
        if s.count(s[0])==3:
            add_money(m.from_user.id,10000)
            bot.send_message(m.chat.id,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.send_message(m.chat.id,f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except: log_exc("/slot")

# ================= ADMIN: QUẢN LÝ KHO =================
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    if not is_admin(m.from_user.id): return
    data=m.text.replace("/addacc","").strip()
    if not data: return bot.send_message(m.chat.id,"📌 /addacc email:pass")
    with db_lock:
        c.execute("INSERT INTO stock_acc(acc) VALUES(?)",(data,))
    bot.send_message(m.chat.id,"➕ Đã thêm acc vào kho")

@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    if not is_admin(m.from_user.id): return
    with db_lock:
        c.execute("SELECT COUNT(*) FROM stock_acc")
        cnt=c.fetchone()[0]
    bot.send_message(m.chat.id,f"📦 Còn {cnt} ACC trong kho")

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
print("BOT STARTED!")
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60,skip_pending=False)
    except Exception as e:
        print("BOT CRASH:",e)
        time.sleep(5)
