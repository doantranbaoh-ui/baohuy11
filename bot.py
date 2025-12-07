#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback, os
from telebot import types
from keep_alive import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"  # Thay token thật
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
db_lock = threading.Lock()

def init_db():
    try:
        with db_lock:
            c.execute("""CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,balance INTEGER DEFAULT 0)""")
            c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(id INTEGER PRIMARY KEY AUTOINCREMENT,acc TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS purchases(user_id TEXT,acc TEXT,time TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,file_id TEXT,amount INTEGER,status TEXT,created_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS giftcode(code TEXT PRIMARY KEY,amount INTEGER,used_by TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS admins(user_id TEXT PRIMARY KEY,level INTEGER DEFAULT 3)""")
            c.execute("INSERT OR IGNORE INTO admins(user_id,level) VALUES (?,?)",(str(OWNER_ID),3))
    except Exception:
        traceback.print_exc()
init_db()

# ================= UTILS =================
def log_exc(tag="ERR"):
    print(f"--- {tag} ---")
    traceback.print_exc()
    print("-----------")

def ensure_user(uid):
    try:
        with db_lock:
            c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))
    except Exception:
        log_exc("ensure_user")

def get_balance(uid):
    ensure_user(uid)
    try:
        with db_lock:
            c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
            r=c.fetchone()
        return int(r[0]) if r else 0
    except Exception:
        log_exc("get_balance")
        return 0

def add_money(uid,amount):
    ensure_user(uid)
    try:
        with db_lock:
            c.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,uid))
    except Exception:
        log_exc("add_money")

def deduct(uid,amount):
    try:
        bal = get_balance(uid)
        if bal < amount: return False
        with db_lock:
            c.execute("UPDATE users SET balance=? WHERE user_id=?",(bal-amount,uid))
        return True
    except Exception:
        log_exc("deduct")
        return False

def get_role(uid):
    try:
        with db_lock:
            c.execute("SELECT level FROM admins WHERE user_id=?",(str(uid),))
            r=c.fetchone()
        return int(r[0]) if r else 0
    except Exception:
        log_exc("get_role")
        return 0

def is_owner(uid): return get_role(uid)==3
def is_admin(uid): return get_role(uid)>=2
def is_support(uid): return get_role(uid)>=1

def make_code(n=10):
    return ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(n))

# ================= USER MENU =================
def send_user_menu(chat_id):
    try:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("🛍 Mua Random","📦 ACC đã mua")
        kb.row("💰 Số dư","🎲 Dice")
        kb.row("🎰 Slot","🎁 Redeem")
        bot.send_message(chat_id,"Chọn chức năng:",reply_markup=kb)
    except Exception:
        log_exc("send_user_menu")

# ================= START / HELP =================
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        text = (
            "🎮 *SHOP ACC RANDOM*\n\n"
            "💡 Bạn có thể sử dụng **nút menu** hoặc gõ lệnh:\n"
            "/sodu - Xem số dư\n"
            "/myacc - Xem acc đã mua\n"
            "/random - Mua ACC random\n"
            "/dice - Chơi Dice\n"
            "/slot - Chơi Slot\n"
            "/redeem <code> - Nhập giftcode\n"
            "/nap <sotien> - Gửi yêu cầu nạp tiền\n"
            "/addacc <acc> - Admin thêm acc\n"
            "/stock - Admin xem kho\n"
            "/listacc - Admin xem danh sách acc\n"
            "/delacc <id> - Admin xóa acc\n"
            "/delall - Admin xóa toàn bộ kho\n"
            "/export - Admin xuất kho acc\n"
        )
        bot.reply_to(m,text,parse_mode="Markdown")
        send_user_menu(m.chat.id)
    except Exception:
        log_exc("/start")

# ================= USER COMMANDS =================
def cmd_sodu(m):
    try:
        uid = str(m.from_user.id)
        bal = get_balance(uid)
        bot.reply_to(m,f"💰 Số dư: *{bal}đ*", parse_mode="Markdown")
    except Exception:
        log_exc("/sodu")

def cmd_myacc(m):
    try:
        uid=str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
            rows=c.fetchall()
        if not rows:
            bot.reply_to(m,"📭 Bạn chưa mua acc nào.")
            return
        text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except Exception:
        log_exc("/myacc")

def cmd_random(m):
    try:
        uid = str(m.from_user.id)
        if deduct(uid, PRICE_RANDOM):
            with db_lock:
                c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
                row = c.fetchone()
                if not row:
                    add_money(uid, PRICE_RANDOM)
                    bot.reply_to(m,"⚠ Hết hàng, tiền đã hoàn lại")
                    return
                acc_id, acc_val = row
                c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
                c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
            bot.reply_to(m,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
        else:
            bot.reply_to(m,"❌ Không đủ tiền")
    except Exception:
        log_exc("/random")

def cmd_dice(m):
    try:
        uid = str(m.from_user.id)
        roll = random.randint(1,6)
        reward = roll*200
        add_money(uid, reward)
        bot.reply_to(m,f"🎲 Bạn lắc ra *{roll}* → +{reward}đ", parse_mode="Markdown")
    except Exception:
        log_exc("/dice")

def cmd_slot(m):
    try:
        uid = str(m.from_user.id)
        icons = ['🍒','💎','⭐','7️⃣']
        s = [random.choice(icons) for _ in range(3)]
        if s.count(s[0])==3:
            add_money(uid,10000)
            bot.reply_to(m,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.reply_to(m,f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except Exception:
        log_exc("/slot")

def cmd_redeem(m):
    try:
        parts = m.text.split()
        if len(parts)<2:
            bot.reply_to(m,"📌 /redeem <code>")
            return
        uid = str(m.from_user.id)
        code = parts[1].upper()
        with db_lock:
            c.execute("SELECT amount,used_by FROM giftcode WHERE code=?",(code,))
            row = c.fetchone()
            if not row:
                bot.reply_to(m,"❌ Giftcode không tồn tại")
                return
            amount, used_by = row
            if str(uid) in used_by.split(","):
                bot.reply_to(m,"❌ Bạn đã dùng code này rồi")
                return
            new_used = used_by+","+uid if used_by else uid
            c.execute("UPDATE giftcode SET used_by=? WHERE code=?",(new_used,code))
        add_money(uid, amount)
        bot.reply_to(m,f"✅ Nhận {amount}đ từ giftcode {code}")
    except Exception:
        log_exc("/redeem")

# ================= NẠP TIỀN + BILL =================
def cmd_nap(m):
    try:
        parts=m.text.split()
        if len(parts)<2:
            bot.reply_to(m,"📌 /nap <sotien>")
            return
        amount=int(parts[1])
        txt=f"💳 Hướng dẫn nạp tiền:\n• STK: *0971487462*\n• Ngân hàng: MB\n• Nội dung: `{m.from_user.id}`\n• Số tiền: *{amount}đ*\nGửi ảnh bill vào chat để admin duyệt."
        bot.reply_to(m,txt,parse_mode="Markdown")
    except Exception:
        log_exc("/nap")

# ================= AUTO LOAD HANDLERS =================
def load_handlers():
    # User commands
    bot.message_handler(commands=["start","help"])(cmd_start)
    bot.message_handler(commands=["sodu"])(cmd_sodu)
    bot.message_handler(commands=["myacc"])(cmd_myacc)
    bot.message_handler(commands=["random"])(cmd_random)
    bot.message_handler(commands=["dice"])(cmd_dice)
    bot.message_handler(commands=["slot"])(cmd_slot)
    bot.message_handler(commands=["redeem"])(cmd_redeem)
    bot.message_handler(commands=["nap"])(cmd_nap)
    # Admin commands (thêm full ở đây như addacc, stock, listacc,...)
    # ... (tương tự như phiên bản trước mình đã viết)

load_handlers()

# ================= KEEP ALIVE =================
keep_alive()

# ================= START BOT =================
print("BOT STARTED!")
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60,skip_pending=False)
    except Exception as e:
        print("BOT CRASH:",e)
        time.sleep(5)
