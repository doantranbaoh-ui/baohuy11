#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback
from telebot import types
try:
    from keep_alive import keep_alive
except:
    def keep_alive():
        print("keep_alive not provided, continuing without it")

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60  # 24h

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DB =================
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

def init_db():
    # Users
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )""")
    # Stock acc
    c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        acc TEXT
    )""")
    # Purchases
    c.execute("""CREATE TABLE IF NOT EXISTS purchases(
        user_id TEXT,
        acc TEXT,
        time TEXT
    )""")
    # Giftcode
    c.execute("""CREATE TABLE IF NOT EXISTS giftcode(
        code TEXT PRIMARY KEY,
        amount INTEGER,
        used_by TEXT
    )""")
    # Bills
    c.execute("""CREATE TABLE IF NOT EXISTS bills(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        file_id TEXT,
        amount INTEGER,
        status TEXT,
        created_at TEXT
    )""")
    # Admins
    c.execute("""CREATE TABLE IF NOT EXISTS admins(
        user_id TEXT PRIMARY KEY,
        level INTEGER DEFAULT 1
    )""")
    # Owner
    c.execute("INSERT OR IGNORE INTO admins(user_id,level) VALUES (?,?)",(str(OWNER_ID),3))
    conn.commit()
init_db()
db_lock = threading.Lock()

# ================= UTILS =================
def log_exc(tag="ERR"):
    print(f"--- {tag} ---")
    traceback.print_exc()
    print("-----------")

def ensure_user(uid:str):
    with db_lock:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))
        conn.commit()

def get_balance(uid:str):
    ensure_user(uid)
    with db_lock:
        c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
        r = c.fetchone()
    return int(r[0]) if r else 0

def add_money(uid:str,amount:int):
    ensure_user(uid)
    with db_lock:
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,uid))
        conn.commit()

def deduct(uid:str,amount:int):
    bal=get_balance(uid)
    if bal<amount: return False
    with db_lock:
        c.execute("UPDATE users SET balance=? WHERE user_id=?",(bal-amount,uid))
        conn.commit()
    return True

def get_role(uid):
    with db_lock:
        c.execute("SELECT level FROM admins WHERE user_id=?",(str(uid),))
        r = c.fetchone()
    return int(r[0]) if r else 0

def is_owner(uid): return get_role(uid)==3
def is_admin(uid): return get_role(uid)>=2
def is_support(uid): return get_role(uid)>=1

def send_main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛍 Mua Random","📦 Acc đã mua")
    kb.row("💰 Số dư","🎲 Dice")
    kb.row("🎰 Slot","🎁 Redeem")
    bot.send_message(chat_id,"Chọn chức năng:",reply_markup=kb)

# ================= COMMANDS =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        bot.reply_to(m,"🎮 *SHOP ACC RANDOM*\nChào bạn! Dùng menu bên dưới.",parse_mode="Markdown")
        send_main_menu(m.chat.id)
    except: log_exc("/start")

@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        bot.reply_to(m,f"💰 Số dư: *{get_balance(str(m.from_user.id))}đ*",parse_mode="Markdown")
    except: log_exc("/sodu")

# ================= MUA RANDOM =================
@bot.message_handler(commands=["random"])
def cmd_random(m):
    try:
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"Mua ngay ({PRICE_RANDOM}đ)",callback_data="buy_confirm"))
        bot.send_message(m.chat.id,"Bạn muốn mua 1 ACC random?",reply_markup=kb)
    except: log_exc("/random")

@bot.callback_query_handler(func=lambda c:c.data=="buy_confirm")
def cb_buy_confirm(call):
    try:
        uid=str(call.from_user.id)
        if not deduct(uid,PRICE_RANDOM):
            return bot.answer_callback_query(call.id,"❌ Không đủ tiền",show_alert=True)
        with db_lock:
            c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
            row=c.fetchone()
            if not row:
                add_money(uid,PRICE_RANDOM)
                return bot.answer_callback_query(call.id,"⚠ Hết hàng, tiền đã hoàn lại",show_alert=True)
            acc_id,acc_val=row
            c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
            c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
            conn.commit()
        bot.send_message(uid,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
        bot.answer_callback_query(call.id,"Giao dịch thành công")
    except:
        log_exc("cb_buy_confirm")
        add_money(str(call.from_user.id),PRICE_RANDOM)
        bot.answer_callback_query(call.id,"Có lỗi, tiền đã hoàn lại",show_alert=True)

@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    try:
        uid=str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
            rows=c.fetchall()
        if not rows:
            return bot.reply_to(m,"📭 Bạn chưa mua acc nào.")
        text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except: log_exc("/myacc")

# ================= GIFT CODE =================
def make_code(n=10):
    alphabet=string.ascii_uppercase+string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

@bot.message_handler(commands=["redeem"])
def cmd_redeem(m):
    try:
        parts=m.text.split()
        if len(parts)<2: return bot.reply_to(m,"📌 /redeem <code>")
        code=parts[1].upper()
        with db_lock:
            c.execute("SELECT amount,used_by FROM giftcode WHERE code=?",(code,))
            r=c.fetchone()
        if not r: return bot.reply_to(m,"❌ Code không tồn tại")
        if r[1] is not None: return bot.reply_to(m,"⚠ Code đã được sử dụng")
        uid=str(m.from_user.id)
        add_money(uid,int(r[0]))
        with db_lock:
            c.execute("UPDATE giftcode SET used_by=? WHERE code=?",(uid,code))
            conn.commit()
        bot.reply_to(m,f"🎉 Nhận {r[0]}đ từ giftcode `{code}`",parse_mode="Markdown")
    except: log_exc("/redeem")

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

# ================= ADMIN LEVEL =================
@bot.message_handler(commands=["addadmin"])
def cmd_addadmin(m):
    if not is_owner(m.from_user.id): return bot.reply_to(m,"⛔ Chỉ OWNER được thêm admin")
    try:
        _,uid,level=m.text.split()
        uid,level=int(uid),int(level)
        with db_lock:
            c.execute("INSERT OR REPLACE INTO admins(user_id,level) VALUES (?,?)",(str(uid),level))
            conn.commit()
        bot.reply_to(m,"✔ Thêm admin thành công")
    except:
        bot.reply_to(m,"❌ Sai cú pháp. Ví dụ:\n/addadmin 123456 2")

@bot.message_handler(commands=["deladmin"])
def cmd_deladmin(m):
    if not is_owner(m.from_user.id): return bot.reply_to(m,"⛔ Chỉ OWNER được xoá admin")
    try:
        _,uid=m.text.split()
        with db_lock:
            c.execute("DELETE FROM admins WHERE user_id=?",(uid,))
            conn.commit()
        bot.reply_to(m,"✔ Đã xoá admin")
    except:
        bot.reply_to(m,"❌ Sai cú pháp")

@bot.message_handler(commands=["listadmin"])
def cmd_listadmin(m):
    if not is_support(m.from_user.id): return bot.reply_to(m,"⛔ Bạn không đủ quyền")
    rows = c.execute("SELECT user_id,level FROM admins").fetchall()
    text="📜 Admin:\n"
    for i in rows:
        role={1:"Support",2:"Admin",3:"Owner"}[i[1]]
        text+=f"• `{i[0]}` - {role}\n"
    bot.reply_to(m,text,parse_mode="Markdown")

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
keep_alive()
print("BOT STARTED!")
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60,skip_pending=True)
    except Exception as e:
        print("⚠ BOT CRASH:",e)
        time.sleep(5)
