#!/usr/bin/env python3
import telebot, sqlite3, threading, time, random, string, secrets, traceback, os
from telebot import types
from keep_alive import keep_alive

# ================= KEEP ALIVE =================
keep_alive()

# ================= CONFIG =================
TOKEN = "6367532329:AAE7uL4iMtoRBkM-Y8GIHOYDD-04XBzaAWM"  # <-- Thay token ở đây
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

# ================= INLINE MENUS (user + admin) =================
def user_main_inline(admin=False):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔥 Mua Random", callback_data="menu_buy"),
        types.InlineKeyboardButton("💰 Số dư", callback_data="menu_balance"),
        types.InlineKeyboardButton("💳 Nạp tiền", callback_data="menu_nap"),
        types.InlineKeyboardButton("🎲 Dice", callback_data="menu_dice"),
        types.InlineKeyboardButton("🎰 Slot", callback_data="menu_slot"),
        types.InlineKeyboardButton("🎁 Redeem", callback_data="menu_redeem"),
        types.InlineKeyboardButton("📦 Acc đã mua", callback_data="menu_myacc")
    )
    if admin:
        kb.add(
            types.InlineKeyboardButton("➕ Thêm acc", callback_data="admin_addacc"),
            types.InlineKeyboardButton("📦 Kho", callback_data="admin_stock"),
            types.InlineKeyboardButton("💰 Cộng tiền", callback_data="admin_addmoney"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("🗑 Xoá acc", callback_data="admin_delacc")
        )
    return kb

# ================= HANDLERS =================
@bot.message_handler(commands=["start","help"])
def cmd_start(m):
    try:
        uid_str = str(m.from_user.id)
        ensure_user(uid_str)
        adm = is_admin(m.from_user.id)
        bot.reply_to(m,"🎮 *SHOP ACC RANDOM*\nChào bạn!",parse_mode="Markdown")
        bot.send_message(m.chat.id,"Chọn chức năng bên dưới:", reply_markup=user_main_inline(admin=adm))
    except:
        log_exc("/start")

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

# ================= RANDOM (command & inline) =================
@bot.message_handler(commands=["random"])
def cmd_random(m):
    try:
        kb=types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"Mua ngay ({PRICE_RANDOM}đ)",callback_data="buy_confirm"))
        bot.send_message(m.chat.id,"Bạn muốn mua 1 ACC random?",reply_markup=kb)
    except: log_exc("/random")

@bot.callback_query_handler(func=lambda c: c.data in [
    "menu_buy","menu_balance","menu_nap","menu_dice","menu_slot","menu_redeem","menu_myacc","buy_confirm"
])
def cb_menu_actions(call):
    try:
        data = call.data
        uid = str(call.from_user.id)
        # ---------- buy flow ----------
        if data == "menu_buy":
            kb=types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"Mua ngay ({PRICE_RANDOM}đ)",callback_data="buy_confirm"))
            bot.edit_message_text("Bạn muốn mua 1 ACC random?", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)
            bot.answer_callback_query(call.id)
            return

        if data == "buy_confirm":
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
            try: bot.send_message(uid,f"🛍 Bạn nhận được ACC:\n`{acc_val}`",parse_mode="Markdown")
            except: pass
            bot.answer_callback_query(call.id,"Giao dịch thành công")
            return

        # ---------- other menu actions ----------
        if data == "menu_balance":
            bot.answer_callback_query(call.id)
            bot.send_message(call.from_user.id,f"💰 Số dư: *{get_balance(uid)}đ*",parse_mode="Markdown")
        elif data == "menu_nap":
            bot.answer_callback_query(call.id)
            bot.send_message(call.from_user.id,"📌 Hướng dẫn nạp tiền:\nGửi /nap <số tiền> rồi upload ảnh bill vào chat để admin duyệt.")
        elif data == "menu_dice":
            bot.answer_callback_query(call.id)
            roll=random.randint(1,6); reward=roll*200
            add_money(uid,reward)
            bot.send_message(call.from_user.id,f"🎲 Lắc ra *{roll}* → +{reward}đ",parse_mode="Markdown")
        elif data == "menu_slot":
            bot.answer_callback_query(call.id)
            icons=['🍒','💎','⭐','7️⃣']; s=[random.choice(icons) for _ in range(3)]
            if s.count(s[0])==3:
                add_money(uid,10000)
                bot.send_message(call.from_user.id,f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
            else:
                bot.send_message(call.from_user.id,f"🎰 {' '.join(s)}\n😢 Thua rồi")
        elif data == "menu_redeem":
            bot.answer_callback_query(call.id)
            bot.send_message(call.from_user.id,"📌 Dùng lệnh: /redeem <giftcode>")
        elif data == "menu_myacc":
            bot.answer_callback_query(call.id)
            with db_lock:
                c.execute("SELECT acc,time FROM purchases WHERE user_id=?",(uid,))
                rows=c.fetchall()
            if not rows:
                bot.send_message(call.from_user.id,"📭 Bạn chưa mua acc nào.")
            else:
                text="\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
                bot.send_message(call.from_user.id,f"📄 ACC đã mua:\n{text}",parse_mode="Markdown")
    except:
        log_exc("cb_menu_actions")

# ================= BILL / NẠP TIỀN =================
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
                kb=types.InlineKeyboardMarkup(row_width=2)
                kb.add(types.InlineKeyboardButton("✔ Duyệt (10k)",callback_data=f"bill_accept:{bill_id}:10000"),
                       types.InlineKeyboardButton("✔ Duyệt (20k)",callback_data=f"bill_accept:{bill_id}:20000"))
                kb.add(types.InlineKeyboardButton("✏️ Duyệt Tùy",callback_data=f"bill_prompt:{bill_id}"),
                       types.InlineKeyboardButton("❌ Từ chối",callback_data=f"bill_reject:{bill_id}"))
                bot.send_photo(int(ad),file_id,caption=f"Bill #{bill_id} từ {uid}",reply_markup=kb)
            except: pass
    except: log_exc("photo handler")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bill_"))
def cb_handle_bill(call):
    try:
        parts=call.data.split(":")
        action=parts[0]; bill_id=int(parts[1])
        caller=call.from_user.id
        if not is_admin(caller): return bot.answer_callback_query(call.id,"Không có quyền",show_alert=True)
        if action=="bill_accept":
            amount=int(parts[2])
            with db_lock:
                c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
                r=c.fetchone()
                if not r: return bot.answer_callback_query(call.id,"Bill không tồn tại")
                if r[1]!="pending": return bot.answer_callback_query(call.id,"Bill đã xử lý")
                user_id=r[0]
                c.execute("UPDATE bills SET amount=?,status=? WHERE id=?",(amount,"approved",bill_id))
            add_money(user_id,amount)
            bot.send_message(user_id,f"✅ Bill #{bill_id} đã được duyệt. Nhận {amount}đ")
            bot.answer_callback_query(call.id,f"Duyệt & cộng {amount}đ")
        elif action=="bill_reject":
            with db_lock:
                c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
                r=c.fetchone()
                if not r: return bot.answer_callback_query(call.id,"Bill không tồn tại")
                if r[1]!="pending": return bot.answer_callback_query(call.id,"Bill đã xử lý")
                user_id=r[0]
                c.execute("UPDATE bills SET status=? WHERE id=?",( "rejected", bill_id ))
            bot.send_message(user_id,f"❌ Bill #{bill_id} bị từ chối")
            bot.answer_callback_query(call.id,"Đã từ chối")
        elif action=="bill_prompt":
            bot.answer_callback_query(call.id,"Nhập /setbill <id> <amount>")
            bot.send_message(call.from_user.id,f"/setbill {bill_id} 15000")
    except: log_exc("cb_handle_bill")

@bot.message_handler(commands=["setbill"])
def cmd_setbill(m):
    try:
        if not is_admin(m.from_user.id): return
        parts=m.text.split()
        if len(parts)<3: return bot.reply_to(m,"📌 /setbill <bill_id> <amount>")
        bill_id=int(parts[1]); amount=int(parts[2])
        with db_lock:
            c.execute("SELECT user_id,status FROM bills WHERE id=?",(bill_id,))
            r=c.fetchone()
            if not r: return bot.reply_to(m,"Bill không tồn tại")
            if r[1]!="pending": return bot.reply_to(m,"Bill đã xử lý")
            user_id=r[0]
            c.execute("UPDATE bills SET amount=?,status=? WHERE id=?",(amount,"approved",bill_id))
        add_money(user_id,amount)
        bot.reply_to(m,f"Đã duyệt bill #{bill_id}, cộng {amount}đ cho {user_id}")
        try: bot.send_message(user_id,f"✅ Bill #{bill_id} đã được duyệt. Nhận {amount}đ")
        except: pass
    except: log_exc("/setbill")

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

# ================= ADMIN: QUẢN LÝ KHO (inline prompts) =================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def cb_admin_actions(call):
    try:
        data = call.data
        caller = call.from_user.id
        if not is_admin(caller):
            return bot.answer_callback_query(call.id,"Không có quyền",show_alert=True)
        if data == "admin_addacc":
            bot.answer_callback_query(call.id)
            bot.send_message(caller,"📌 Gửi lệnh:\n/addacc email:pass")
        elif data == "admin_stock":
            with db_lock:
                c.execute("SELECT COUNT(*) FROM stock_acc")
                cnt=c.fetchone()[0]
            bot.answer_callback_query(call.id)
            bot.send_message(caller,f"📦 Có {cnt} ACC trong kho")
        elif data == "admin_addmoney":
            bot.answer_callback_query(call.id)
            bot.send_message(caller,"📌 Gửi lệnh:\n/addmoney <user_id> <amount>")
        elif data == "admin_broadcast":
            bot.answer_callback_query(call.id)
            bot.send_message(caller,"📌 Gửi lệnh:\n/broadcast <message>")
        elif data == "admin_delacc":
            bot.answer_callback_query(call.id)
            bot.send_message(caller,"📌 Gửi lệnh:\n/delacc <id> hoặc /delall")
    except: log_exc("cb_admin_actions")

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
        rows=c.fetchall()
    path="stock_export.txt"
    with open(path,"w",encoding="utf-8") as f:
        for r in rows: f.write(r[0]+"\n")
    bot.send_document(m.chat.id,open(path,"rb"))
    try: os.remove(path)
    except: pass

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

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(m):
    if not is_admin(m.from_user.id): return
    text=m.text.replace("/broadcast","").strip()
    if not text: return bot.reply_to(m,"📌 /broadcast <message>")
    with db_lock:
        c.execute("SELECT user_id FROM users")
        users=c.fetchall()
    sent=0
    for u in users:
        try: bot.send_message(int(u[0]),text); sent+=1
        except: pass
    bot.reply_to(m,f"Đã gửi đến {sent} users")

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
