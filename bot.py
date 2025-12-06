#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60

# ================= KEEP ALIVE =================
try:
    from keep_alive import keep_alive
except:
    def keep_alive():
        print("keep_alive not found, continuing without it")

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect("data.db", check_same_thread=False, isolation_level=None)
c = conn.cursor()
lock = threading.Lock()

def init_db():
    with lock:
        c.execute("CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY, balance INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS stock_acc(id INTEGER PRIMARY KEY AUTOINCREMENT, acc TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS purchases(user_id TEXT, acc TEXT, time TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, file_id TEXT, amount INTEGER, status TEXT, created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS giftcode(code TEXT PRIMARY KEY, amount INTEGER, used_by TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS admins(user_id TEXT PRIMARY KEY, level INTEGER DEFAULT 3)")
        c.execute("INSERT OR IGNORE INTO admins(user_id,level) VALUES (?,?)",(str(OWNER_ID),3))
init_db()

# ================= UTILS =================
def log_exc(tag="ERR"):
    print(f"--- {tag} ---")
    traceback.print_exc()
    print("-----------")

def ensure_user(uid):
    with lock: c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))

def get_balance(uid):
    ensure_user(uid)
    with lock:
        c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
        r=c.fetchone()
    return int(r[0]) if r else 0

def add_money(uid,amount):
    ensure_user(uid)
    with lock: c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,uid))

def deduct(uid,amount):
    bal=get_balance(uid)
    if bal<amount: return False
    with lock: c.execute("UPDATE users SET balance=? WHERE user_id=?",(bal-amount,uid))
    return True

def is_admin(uid):
    with lock:
        c.execute("SELECT level FROM admins WHERE user_id=?",(str(uid),))
        r=c.fetchone()
    return int(r[0])>=2 if r else False

def make_code(n=10):
    return ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(n))

# ================= COMMANDS =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    txt = ("🎮 *SHOP ACC RANDOM*\n\n"
           "/sodu - Số dư\n"
           "/random - Mua acc random\n"
           "/myacc - Xem acc đã mua\n"
           "/nap <sotien> - Nạp tiền\n"
           "/redeem <code> - Giftcode\n"
           "/dice - Chơi Dice\n"
           "/slot - Chơi Slot\n"
           "Admin: /addacc, /listacc, /delacc, /delall, /export, /addmoney, /makecode, /broadcast")
    bot.reply_to(m, txt, parse_mode="Markdown")

@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    bot.reply_to(m,f"💰 Số dư: *{get_balance(str(m.from_user.id))}đ*",parse_mode="Markdown")

@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    uid=str(m.from_user.id)
    with lock: c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
    rows=c.fetchall()
    if not rows: return bot.reply_to(m,"📭 Bạn chưa mua acc nào.")
    text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
    bot.reply_to(m,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")

@bot.message_handler(commands=["random"])
def cmd_random(m):
    uid=str(m.from_user.id)
    if not deduct(uid,PRICE_RANDOM): return bot.reply_to(m,"❌ Không đủ tiền")
    with lock:
        c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
        row=c.fetchone()
        if not row: add_money(uid,PRICE_RANDOM); return bot.reply_to(m,"⚠ Hết hàng, tiền đã hoàn lại")
        acc_id, acc_val=row
        c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
        c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
    bot.reply_to(m,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")

@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    parts=m.text.split()
    if len(parts)<2: return bot.reply_to(m,"📌 /nap <sotien>")
    amount=int(parts[1])
    txt=f"💳 Hướng dẫn nạp:\nSTK: 0971487462\nNội dung: {m.from_user.id}\nSố tiền: {amount}đ\nGửi ảnh bill vào chat."
    bot.reply_to(m,txt)

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    uid=str(msg.from_user.id)
    file_id=msg.photo[-1].file_id
    with lock: c.execute("INSERT INTO bills(user_id,file_id,amount,status,created_at) VALUES(?,?,?,?,?)",(uid,file_id,0,"pending",time.ctime()))
    bill_id=c.lastrowid
    bot.reply_to(msg,f"⏳ Hoá đơn đã gửi. Bill ID: {bill_id}")

@bot.message_handler(commands=["setbill"])
def cmd_setbill(m):
    if not is_admin(m.from_user.id): return
    parts=m.text.split()
    if len(parts)<3: return bot.reply_to(m,"📌 /setbill <bill_id> <amount>")
    bill_id=int(parts[1]); amount=int(parts[2])
    with lock:
        c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
        r=c.fetchone()
        if not r: return bot.reply_to(m,"Bill không tồn tại")
        if r[1]!="pending": return bot.reply_to(m,"Bill đã xử lý")
        user_id=r[0]
        c.execute("UPDATE bills SET amount=?,status=? WHERE id=?",(amount,"approved",bill_id))
    add_money(user_id,amount)
    bot.reply_to(m,f"✅ Bill #{bill_id} đã duyệt. Cộng {amount}đ cho {user_id}")
    try: bot.send_message(user_id,f"✅ Bill #{bill_id} đã duyệt. Nhận {amount}đ"); 
    except: pass

@bot.message_handler(commands=["makecode"])
def cmd_makecode(m):
    if not is_admin(m.from_user.id): return
    parts=m.text.split()
    if len(parts)<3: return bot.reply_to(m,"📌 /makecode <amount> <count>")
    amount=int(parts[1]); count=int(parts[2])
    codes=[]
    with lock:
        for _ in range(count):
            code=make_code(10)
            c.execute("INSERT INTO giftcode(code,amount,used_by) VALUES(?,?,?)",(code,amount,None))
            codes.append(code)
    bot.reply_to(m,"Tạo thành công:\n"+"\n".join(codes))

@bot.message_handler(commands=["redeem"])
def cmd_redeem(m):
    parts=m.text.split()
    if len(parts)<2: return bot.reply_to(m,"📌 /redeem <code>")
    code=parts[1].upper()
    with lock: c.execute("SELECT amount,used_by FROM giftcode WHERE code=?",(code,))
    r=c.fetchone()
    if not r: return bot.reply_to(m,"❌ Code không tồn tại")
    if r[1] is not None: return bot.reply_to(m,"⚠ Code đã sử dụng")
    amount=int(r[0]); uid=str(m.from_user.id)
    add_money(uid,amount)
    with lock: c.execute("UPDATE giftcode SET used_by=? WHERE code=?",(uid,code))
    bot.reply_to(m,f"🎉 Nhận {amount}đ từ giftcode `{code}`",parse_mode="Markdown")

@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    roll=random.randint(1,6)
    reward=roll*200
    add_money(str(m.from_user.id),reward)
    bot.reply_to(m,f"🎲 Lắc ra *{roll}* → +{reward}đ",parse_mode="Markdown")

@bot.message_handler(commands=["slot"])
def cmd_slot(m):
    icons=['🍒','💎','⭐','7️⃣']
    s=[random.choice(icons) for _ in range(3)]
    if s.count(s[0])==3:
        add_money(str(m.from_user.id),10000)
        bot.reply_to(m,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
    else: bot.reply_to(m,f"🎰 {' '.join(s)}\n😢 Thua rồi")

# ================= DAILY REPORT =================
def daily_report_thread():
    while True:
        try:
            with lock: c.execute("SELECT COUNT(*) FROM stock_acc")
            count=c.fetchone()[0]
            bot.send_message(OWNER_ID,f"📅 Báo cáo tự động: Còn {count} ACC trong kho")
        except: pass
        time.sleep(DAILY_REPORT_HOUR)
threading.Thread(target=daily_report_thread,daemon=True).start()

# ================= START BOT =================
if __name__ == "__main__":
    keep_alive()
    print("BOT STARTED!")
    while True:
        try: bot.infinity_polling(timeout=60,long_polling_timeout=60)
        except Exception as e:
            print("BOT CRASH:",e)
            time.sleep(5)
