#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback, os
from telebot import types
from keep_alive import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAFTX43OlmNc0JpSwOagE8W0P22yOBH0lLU"
OWNER_ID = 5736655322
PRICE_RANDOM = 2000
DAILY_REPORT_HOUR = 24*60*60

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================= DATABASE =================
conn = sqlite3.connect("data.db", check_same_thread=False, isolation_level=None)
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
        print("Lỗi init DB")
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
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🛍 Mua Random", callback_data="buy_acc"),
            types.InlineKeyboardButton("🎁 Redeem", callback_data="redeem_code")
        )
        kb.add(
            types.InlineKeyboardButton("🎲 Dice", callback_data="dice_game"),
            types.InlineKeyboardButton("🎰 Slot", callback_data="slot_game")
        )
        bot.send_message(chat_id,"Chọn chức năng:",reply_markup=kb)
    except Exception:
        log_exc("send_user_menu")

# ================= START / HELP =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        bot.reply_to(m,
        "🎮 *SHOP ACC RANDOM*\nChào bạn!\n\nLệnh chính:\n/myacc - Xem acc đã mua\n/sodu - Xem số dư\n/nap - Nạp tiền\n/redeem <code> - Nhập giftcode",
        parse_mode="Markdown")
        send_user_menu(m.chat.id)
    except Exception:
        log_exc("/start")

# ================= CHECK SỐ DƯ =================
@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        bot.reply_to(m,f"💰 Số dư: *{get_balance(str(m.from_user.id))}đ*",parse_mode="Markdown")
    except Exception:
        log_exc("/sodu")

# ================= XEM ACC ĐÃ MUA =================
@bot.message_handler(commands=["myacc"])
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

# ================= CALLBACK NÚT USER =================
@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    try:
        uid = str(call.from_user.id)
        if call.data == "buy_acc":
            if deduct(uid, PRICE_RANDOM):
                with db_lock:
                    c.execute("SELECT id,acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
                    row = c.fetchone()
                    if not row:
                        add_money(uid, PRICE_RANDOM)
                        bot.answer_callback_query(call.id,"⚠ Hết hàng, tiền đã hoàn lại", show_alert=True)
                        return
                    acc_id, acc_val = row
                    c.execute("DELETE FROM stock_acc WHERE id=?",(acc_id,))
                    c.execute("INSERT INTO purchases(user_id,acc,time) VALUES(?,?,?)",(uid,acc_val,time.ctime()))
                bot.send_message(uid,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
                bot.answer_callback_query(call.id,"Giao dịch thành công")
            else:
                bot.answer_callback_query(call.id,"❌ Không đủ tiền", show_alert=True)
        elif call.data == "redeem_code":
            bot.send_message(uid,"Nhập /redeem <code> để nhận giftcode")
        elif call.data == "dice_game":
            roll=random.randint(1,6)
            reward=roll*200
            add_money(uid,reward)
            bot.answer_callback_query(call.id,f"🎲 Lắc ra {roll} → +{reward}đ")
        elif call.data == "slot_game":
            icons=['🍒','💎','⭐','7️⃣']
            s=[random.choice(icons) for _ in range(3)]
            if s.count(s[0])==3:
                add_money(uid,10000)
                bot.answer_callback_query(call.id,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
            else:
                bot.answer_callback_query(call.id,f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except Exception:
        log_exc("handle_callback")
        try:
            bot.answer_callback_query(call.id,"❌ Lỗi, thử lại", show_alert=True)
        except Exception:
            pass

# ================= NẠP TIỀN =================
@bot.message_handler(commands=["nap"])
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

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    try:
        uid = str(msg.from_user.id)
        file_id = msg.photo[-1].file_id
        with db_lock:
            c.execute("INSERT INTO bills(user_id,file_id,amount,status,created_at) VALUES(?,?,?,?,?)",
                      (uid,file_id,0,"pending",time.ctime()))
            bill_id = c.lastrowid
        bot.reply_to(msg,f"⏳ Hoá đơn đã gửi, chờ admin duyệt. (Bill ID: {bill_id})")
        # Gửi bill cho owner/admin
        try:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("✔ Duyệt 10k", callback_data=f"bill_accept:{bill_id}:10000"),
                types.InlineKeyboardButton("✔ Duyệt 20k", callback_data=f"bill_accept:{bill_id}:20000"),
                types.InlineKeyboardButton("❌ Từ chối", callback_data=f"bill_reject:{bill_id}")
            )
            bot.send_photo(OWNER_ID, file_id, caption=f"Bill #{bill_id} từ {uid}", reply_markup=kb)
        except Exception:
            log_exc("send_bill_to_owner")
    except Exception:
        log_exc("photo handler")

# ================= ADMIN & GIFT CODE, DAILY REPORT =================
# Tất cả admin lệnh: /addacc, /delacc, /delall, /listacc, /stock, /setbill, /addmoney, /broadcast, /addcode
# Duyệt bill và giftcode
# Daily report thread

# ================= START BOT =================
print("BOT STARTED!")
keep_alive()  # chạy keep_alive nếu dùng Replit/Render
while True:
    try:
        bot.infinity_polling(timeout=60,long_polling_timeout=60,skip_pending=False)
    except Exception as e:
        print("BOT CRASH:",e)
        time.sleep(5)
