import telebot, sqlite3, threading, time, random, string, secrets, traceback
from telebot import types
from keep_alive import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAE7uL4iMtoRBkM-Y8GIHOYDD-04XBzaAWM"
OWNER_ID = 5736655322
PRICE_RANDOM = 2000

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
db_lock = threading.Lock()

def init_db():
    try:
        with db_lock:
            c.execute("""CREATE TABLE IF NOT EXISTS users(
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS stock_acc(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                acc TEXT
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS purchases(
                user_id TEXT,
                acc TEXT,
                time TEXT
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS giftcode(
                code TEXT PRIMARY KEY,
                amount INTEGER,
                used_by TEXT
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS admins(
                user_id TEXT PRIMARY KEY,
                level INTEGER DEFAULT 3
            )""")

            c.execute("INSERT OR IGNORE INTO admins(user_id,level) VALUES (?,?)",
                      (str(OWNER_ID),3))

            conn.commit()

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
            conn.commit()
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
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
            conn.commit()
    except Exception:
        log_exc("add_money")

def deduct(uid,amount):
    try:
        bal = get_balance(uid)
        if bal < amount:
            return False
        with db_lock:
            c.execute("UPDATE users SET balance=? WHERE user_id=?", (bal-amount, uid))
            conn.commit()
        return True
    except Exception:
        log_exc("deduct")
        return False

def get_role(uid):
    try:
        with db_lock:
            c.execute("SELECT level FROM admins WHERE user_id=?", (str(uid),))
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

# ================= HANDLER MENU TEXT =================
@bot.message_handler(func=lambda m: m.text == "💰 Số dư")
def _(m): cmd_sodu(m)

@bot.message_handler(func=lambda m: m.text == "🛍 Mua Random")
def _(m): cmd_random(m)

@bot.message_handler(func=lambda m: m.text == "📦 ACC đã mua")
def _(m): cmd_myacc(m)

@bot.message_handler(func=lambda m: m.text == "🎲 Dice")
def _(m): cmd_dice(m)

@bot.message_handler(func=lambda m: m.text == "🎰 Slot")
def _(m): cmd_slot(m)

@bot.message_handler(func=lambda m: m.text == "🎁 Redeem")
def _(m):
    bot.reply_to(m,"📌 Nhập lệnh: /redeem <code>")

# ================= COMMANDS =================
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        bot.reply_to(m,
            "🎮 *SHOP ACC RANDOM*\n"
            "Sử dụng menu hoặc gõ lệnh:\n"
            "/sodu - Xem số dư\n"
            "/random - Mua acc random\n"
            "/myacc - Xem acc đã mua\n"
            "/redeem <code> - Nhập code\n",
            parse_mode="Markdown"
        )
        send_user_menu(m.chat.id)
    except Exception:
        log_exc("/start")

def cmd_sodu(m):
    try:
        uid = str(m.from_user.id)
        bal = get_balance(uid)
        bot.reply_to(m,f"💰 Số dư của bạn: *{bal}đ*",parse_mode="Markdown")
    except: log_exc("sodu")

def cmd_myacc(m):
    try:
        uid=str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?", (uid,))
            rows=c.fetchall()
        if not rows:
            bot.reply_to(m,"📭 Bạn chưa mua acc nào.")
            return
        text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except: log_exc("myacc")

def cmd_random(m):
    try:
        uid = str(m.from_user.id)
        if not deduct(uid, PRICE_RANDOM):
            bot.reply_to(m,"❌ Không đủ tiền")
            return
        with db_lock:
            c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
            row = c.fetchone()
            if not row:
                add_money(uid, PRICE_RANDOM)
                bot.reply_to(m,"⚠ Hết hàng, hoàn tiền.")
                return
            acc_id, acc_val = row
            c.execute("DELETE FROM stock_acc WHERE id=?", (acc_id,))
            c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",
                      (uid, acc_val, time.ctime()))
            conn.commit()
        bot.reply_to(m,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
    except: log_exc("random")

def cmd_dice(m):
    try:
        uid = str(m.from_user.id)
        roll = random.randint(1,6)
        reward = roll * 200
        add_money(uid, reward)
        bot.reply_to(m,f"🎲 Lắc ra *{roll}* → +{reward}đ",parse_mode="Markdown")
    except: log_exc("dice")

def cmd_slot(m):
    try:
        uid = str(m.from_user.id)
        icons = ['🍒','💎','⭐','7️⃣']
        s = [random.choice(icons) for _ in range(3)]
        if s.count(s[0])==3:
            add_money(uid, 10000)
            bot.reply_to(m,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.reply_to(m,f"🎰 {' '.join(s)}\n❌ Thua rồi")
    except: log_exc("slot")

def cmd_redeem(m):
    try:
        parts = m.text.split()
        if len(parts)<2:
            bot.reply_to(m,"📌 /redeem <code>")
            return
        uid=str(m.from_user.id)
        code=parts[1].upper()
        with db_lock:
            c.execute("SELECT amount,used_by FROM giftcode WHERE code=?", (code,))
            r=c.fetchone()
            if not r:
                bot.reply_to(m,"❌ Code không tồn tại")
                return
            amount, used=r
            if used and uid in used.split(","):
                bot.reply_to(m,"❌ Bạn đã dùng code này")
                return
            new_used = f"{used},{uid}" if used else uid
            c.execute("UPDATE giftcode SET used_by=? WHERE code=?", (new_used, code))
            conn.commit()
        add_money(uid, amount)
        bot.reply_to(m,f"✅ Nhận {amount}đ từ code {code}")
    except:
        log_exc("redeem")

# ================= COMMAND BIND =================
bot.message_handler(commands=["start","help"])(cmd_start)
bot.message_handler(commands=["sodu"])(cmd_sodu)
bot.message_handler(commands=["myacc"])(cmd_myacc)
bot.message_handler(commands=["random"])(cmd_random)
bot.message_handler(commands=["dice"])(cmd_dice)
bot.message_handler(commands=["slot"])(cmd_slot)
bot.message_handler(commands=["redeem"])(cmd_redeem)

# ================= KEEP ALIVE (FOR REPLIT) =================
keep_alive()

# ================= START BOT =================
print("BOT STARTED!")
while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        print("BOT CRASH:", e)
        time.sleep(3)
