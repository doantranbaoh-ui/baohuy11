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
@bot.message_handler(commands=["start","help"])
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
@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        uid = str(m.from_user.id)
        bal = get_balance(uid)
        bot.reply_to(m,f"💰 Số dư: *{bal}đ*", parse_mode="Markdown")
    except Exception:
        log_exc("/sodu")

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

@bot.message_handler(commands=["random"])
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

@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    try:
        uid = str(m.from_user.id)
        roll = random.randint(1,6)
        reward = roll*200
        add_money(uid, reward)
        bot.reply_to(m,f"🎲 Bạn lắc ra *{roll}* → +{reward}đ", parse_mode="Markdown")
    except Exception:
        log_exc("/dice")

@bot.message_handler(commands=["slot"])
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

@bot.message_handler(commands=["redeem"])
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

# ================= ADMIN BILL CALLBACK =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("bill_"))
def cb_handle_bill(call):
    try:
        parts = call.data.split(":")
        action = parts[0]
        bill_id = int(parts[1])
        caller = call.from_user.id
        if not is_admin(caller):
            bot.answer_callback_query(call.id,"Không có quyền",show_alert=True)
            return
        if action=="bill_accept":
            amount = int(parts[2])
            with db_lock:
                c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
                r = c.fetchone()
                if not r or r[1]!="pending":
                    bot.answer_callback_query(call.id,"Bill đã xử lý hoặc không tồn tại")
                    return
                user_id = r[0]
                c.execute("UPDATE bills SET amount=?,status=? WHERE id=?",(amount,"approved",bill_id))
            add_money(user_id,amount)
            bot.send_message(user_id,f"✅ Bill #{bill_id} đã được duyệt. Nhận {amount}đ")
            bot.answer_callback_query(call.id,f"Duyệt & cộng {amount}đ")
        elif action=="bill_reject":
            with db_lock:
                c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
                r = c.fetchone()
                if not r or r[1]!="pending":
                    bot.answer_callback_query(call.id,"Bill đã xử lý hoặc không tồn tại")
                    return
                user_id = r[0]
                c.execute("UPDATE bills SET status=? WHERE id=?","rejected",bill_id)
            bot.send_message(user_id,f"❌ Bill #{bill_id} bị từ chối")
            bot.answer_callback_query(call.id,"Đã từ chối")
    except Exception:
        log_exc("cb_handle_bill")

# ================= ADMIN GIFT CODE =================
@bot.message_handler(commands=["addcode"])
def cmd_addcode(m):
    if not is_admin(m.from_user.id): return
    try:
        parts = m.text.split()
        if len(parts)<3:
            bot.reply_to(m,"📌 /addcode <code> <amount>")
            return
        code = parts[1].upper()
        amount = int(parts[2])
        with db_lock:
            c.execute("INSERT OR REPLACE INTO giftcode(code,amount,used_by) VALUES(?,?,?)",(code,amount,""))
        bot.reply_to(m,f"✅ Đã tạo giftcode {code} giá trị {amount}đ")
    except Exception:
        log_exc("/addcode")

# ================= ADMIN BROADCAST =================
@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(m):
    if not is_admin(m.from_user.id): return
    try:
        text = m.text.replace("/broadcast","").strip()
        if not text:
            bot.reply_to(m,"📌 /broadcast <message>")
            return
        with db_lock:
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
        sent = 0
        for u in users:
            try:
                bot.send_message(int(u[0]), text)
                sent += 1
            except Exception:
                pass
        bot.reply_to(m,f"Đã gửi đến {sent} users")
    except Exception:
        log_exc("/broadcast")

# ================= ADMIN ADD MONEY =================
@bot.message_handler(commands=["addmoney"])
def cmd_addmoney(m):
    if not is_admin(m.from_user.id): return
    try:
        _,uid,amount = m.text.split()
        amount=int(amount)
        add_money(uid,amount)
        bot.reply_to(m,f"Đã cộng {amount}đ cho {uid}")
        try:
            bot.send_message(int(uid),f"✅ Admin đã cộng {amount}đ")
        except Exception:
            pass
    except Exception:
        log_exc("/addmoney")

# ================= ADMIN STOCK =================
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    if not is_admin(m.from_user.id): return
    data = m.text.replace("/addacc","").strip()
    if not data: return bot.reply_to(m,"📌 /addacc email:pass")
    with db_lock:
        c.execute("INSERT INTO stock_acc(acc) VALUES(?)",(data,))
    bot.reply_to(m,"➕ Đã thêm acc vào kho")

@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    if not is_admin(m.from_user.id): return
    with db_lock:
        c.execute("SELECT COUNT(*) FROM stock_acc")
        cnt = c.fetchone()[0]
    bot.reply_to(m,f"📦 Còn {cnt} ACC trong kho")

@bot.message_handler(commands=["listacc"])
def cmd_listacc(m):
    if not is_admin(m.from_user.id): return
    limit=100
    with db_lock:
        c.execute("SELECT id,acc FROM stock_acc LIMIT ?",(limit,))
        rows=c.fetchall()
    if not rows: return bot.reply_to(m,"Kho trống")
    text="\n".join([f"{r[0]}. {r[1]}" for r in rows])
    bot.reply_to(m,f"📄 Danh sách (max {limit}):\n{text}\n/delacc <id>")

@bot.message_handler(commands=["delacc"])
def cmd_delacc(m):
    if not is_admin(m.from_user.id): return
    try: aid=int(m.text.split()[1])
    except: return bot.reply_to(m,"📌 /delacc <id>")
    with db_lock:
        c.execute("DELETE FROM stock_acc WHERE id=?",(aid,))
    bot.reply_to(m,"🗑 Đã xoá acc")

@bot.message_handler(commands=["delall"])
def cmd_delall(m):
    if not is_admin(m.from_user.id): return
    with db_lock:
        c.execute("DELETE FROM stock_acc")
    bot.reply_to(m,"🔥 Đã xoá toàn bộ kho")

@bot.message_handler(commands=["export"])
def cmd_export(m):
    if not is_admin(m.from_user.id): return
    with db_lock:
        c.execute("SELECT acc FROM stock_acc")
        rows = c.fetchall()
    path = "stock_export.txt"
    with open(path,"w",encoding="utf-8") as f:
        for r in rows: f.write(r[0]+"\n")
    bot.send_document(m.chat.id, open(path,"rb"))
    try: os.remove(path)
    except: pass

# ================= DAILY REPORT =================
def daily_report_thread():
    while True:
        try:
            with db_lock:
                c.execute("SELECT COUNT(*) FROM stock_acc")
                count = c.fetchone()[0]
            bot.send_message(OWNER_ID,f"📅 Báo cáo tự động: Còn {count} ACC trong kho")
        except Exception:
            log_exc("daily_report")
        time.sleep(DAILY_REPORT_HOUR)
threading.Thread(target=daily_report_thread,daemon=True).start()

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
