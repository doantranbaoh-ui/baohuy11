#!/usr/bin/env python3
# bot.py - Shop acc Telegram (Full, cải tiến)
import telebot
from telebot import types
import sqlite3, random, time, threading, traceback, string, secrets, os

# ================== CẤU HÌNH ==================
TOKEN = "YOUR_BOT_TOKEN"   # <-- Thay token ở đây
ADMINS = ["5736655322"]    # <-- ID admin (string list)
PRICE_RANDOM = 2000        # giá 1 acc random
DAILY_REPORT_HOUR = 24*60*60  # 24h

# ================== KEEP ALIVE ==================
# File keep_alive.py phải có hàm keep_alive() (Flask thread) hoặc comment phần này nếu không dùng.
try:
    from keep_alive import keep_alive
except Exception:
    def keep_alive():
        print("keep_alive not provided - continuing without it")

# ================== INIT BOT + DB ==================
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
DB_PATH = "data.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
db_lock = threading.Lock()

def init_db():
    with db_lock:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS stock_acc(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acc TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            user_id TEXT,
            acc TEXT,
            time TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS giftcode(
            code TEXT PRIMARY KEY,
            amount INTEGER,
            used_by TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            file_id TEXT,
            amount INTEGER,
            status TEXT,
            created_at TEXT
        )""")
        conn.commit()

init_db()

# ================== HỖ TRỢ DB/NGƯỜI DÙNG ==================
def ensure_user(uid: str):
    with db_lock:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)",(uid,))
        conn.commit()

def get_balance(uid: str) -> int:
    ensure_user(uid)
    with db_lock:
        c.execute("SELECT balance FROM users WHERE user_id=?",(uid,))
        r = c.fetchone()
    return int(r[0]) if r and r[0] is not None else 0

def add_money(uid: str, amount: int):
    ensure_user(uid)
    with db_lock:
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
        conn.commit()

def set_balance(uid: str, amount: int):
    ensure_user(uid)
    with db_lock:
        c.execute("UPDATE users SET balance = ? WHERE user_id=?", (amount, uid))
        conn.commit()

def deduct(uid: str, amount: int) -> bool:
    ensure_user(uid)
    with db_lock:
        c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        r = c.fetchone()
        bal = int(r[0]) if r and r[0] is not None else 0
        if bal < amount:
            return False
        c.execute("UPDATE users SET balance=? WHERE user_id=?", (bal-amount, uid))
        conn.commit()
        return True

def is_admin_uid(uid):
    return str(uid) in ADMINS

# ================== HỖ TRỢ LOG ==================
def log_exc(tag="ERR"):
    print(f"--- {tag} ---")
    traceback.print_exc()
    print("-----------")

# ================== GIAO DIỆN MENU ==================
def send_main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛍 Mua Random", "📦 Acc đã mua")
    kb.row("💰 Số dư", "🎲 Dice")
    kb.row("🎰 Slot", "🎁 Redeem")
    bot.send_message(chat_id, "Chọn chức năng:", reply_markup=kb)

# ================== COMMANDS CHÍNH ==================
@bot.message_handler(commands=["start", "help"])
def cmd_start(m):
    try:
        ensure_user(str(m.from_user.id))
        txt = ("🎮 *SHOP ACC RANDOM*\n\n"
               "Chào bạn! Dùng menu dưới hoặc /commands để xem lệnh.")
        bot.reply_to(m, txt)
        send_main_menu(m.chat.id)
    except Exception:
        log_exc("/start")

@bot.message_handler(commands=["commands"])
def cmd_list(m):
    try:
        txt = (
            "/start, /help - Menu\n"
            "/sodu - Kiểm tra số dư\n"
            "/nap <sotien> - Yêu cầu nạp (gửi bill)\n"
            "/random - Mua acc random (confirm)\n"
            "/myacc - Xem acc đã mua\n"
            "/redeem <code> - Nhập giftcode\n\n"
            "Admin: /addacc, /stock, /listacc, /delacc, /delall, /export, /addmoney, /makecode, /broadcast"
        )
        bot.reply_to(m, txt)
    except Exception:
        log_exc("/commands")

@bot.message_handler(commands=["sodu"])
def cmd_sodu(m):
    try:
        uid = str(m.from_user.id)
        bot.reply_to(m, f"💰 Số dư: *{get_balance(uid)}đ*")
    except Exception:
        log_exc("/sodu")

@bot.message_handler(commands=["myacc"])
def cmd_myacc(m):
    try:
        uid = str(m.from_user.id)
        with db_lock:
            c.execute("SELECT acc,time FROM purchases WHERE user_id=?", (uid,))
            rows = c.fetchall()
        if not rows:
            bot.reply_to(m, "📭 Bạn chưa mua acc nào.")
            return
        text = "\n".join([f"• `{r[0]}` | {r[1]}" for r in rows])
        bot.reply_to(m, f"📄 ACC đã mua:\n{text}")
    except Exception:
        log_exc("/myacc")

# ================== NẠP TIỀN (gửi bill chờ duyệt) ==================
@bot.message_handler(commands=["nap"])
def cmd_nap(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            return bot.reply_to(m, "📌 Sử dụng: /nap <sotien>")
        amount = int(parts[1])
        txt = (f"💳 Hướng dẫn nạp tiền:\n\n"
               f"• STK: *0971487462*\n• Ngân hàng: *MB BANK*\n• Nội dung: `{m.from_user.id}`\n• Số tiền: *{amount}đ*\n\n"
               "📸 Gửi ảnh bill vào chat để admin duyệt (không tự cộng tiền để tránh lừa đảo).")
        bot.reply_to(m, txt)
    except Exception:
        log_exc("/nap")

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    try:
        # Lưu bill (file_id) + tạo thông báo cho admin
        uid = str(msg.from_user.id)
        file_id = msg.photo[-1].file_id
        # amount unknown here; admin sẽ chèn số khi duyệt hoặc bạn có thể yêu cầu user ghi tiền trong caption
        caption = msg.caption or ""
        amount = None
        # nếu user ghi /nap <sotien> trước đó, ta không lưu amount tự động
        with db_lock:
            c.execute("INSERT INTO bills(user_id,file_id,amount,status,created_at) VALUES(?,?,?,?,?)",
                      (uid, file_id, 0, "pending", time.ctime()))
            conn.commit()
            bill_id = c.lastrowid
        bot.reply_to(msg, "⏳ Hoá đơn đã gửi, chờ admin duyệt. (Bill ID: {})".format(bill_id))
        # Gửi notification cho admins kèm inline buttons Approve/Reject + set amount quick
        for ad in ADMINS:
            try:
                kb = types.InlineKeyboardMarkup(row_width=2)
                kb.add(
                    types.InlineKeyboardButton("✔ Duyệt (10k)", callback_data=f"bill_accept:{bill_id}:10000"),
                    types.InlineKeyboardButton("✔ Duyệt (20k)", callback_data=f"bill_accept:{bill_id}:20000"),
                )
                kb.add(
                    types.InlineKeyboardButton("✏️ Duyệt Tùy", callback_data=f"bill_prompt:{bill_id}"),
                    types.InlineKeyboardButton("❌ Từ chối", callback_data=f"bill_reject:{bill_id}")
                )
                bot.send_photo(int(ad), file_id, caption=f"Bill #{bill_id} từ {uid}\nCaption: {caption}", reply_markup=kb)
            except Exception:
                print("Không gửi được bill cho admin:", ad)
    except Exception:
        log_exc("photo handler")

@bot.callback_query_handler(func=lambda call: call.data.startswith("bill_accept:") or call.data.startswith("bill_reject:") or call.data.startswith("bill_prompt:"))
def cb_handle_bill(call):
    try:
        parts = call.data.split(":")
        action = parts[0]
        bill_id = int(parts[1])
        caller = call.from_user.id
        if not is_admin_uid(caller):
            return bot.answer_callback_query(call.id, "Không có quyền", show_alert=True)
        if action == "bill_accept":
            amount = int(parts[2])
            # cập nhật bill
            with db_lock:
                c.execute("SELECT user_id, status FROM bills WHERE id=?", (bill_id,))
                r = c.fetchone()
                if not r: return bot.answer_callback_query(call.id, "Bill không tồn tại")
                if r[1] != "pending":
                    return bot.answer_callback_query(call.id, "Bill đã xử lý")
                user_id = r[0]
                c.execute("UPDATE bills SET amount=?, status=? WHERE id=?", (amount, "approved", bill_id))
                conn.commit()
            # cộng tiền và thông báo user
            add_money(user_id, amount)
            bot.send_message(user_id, f"✅ Bill #{bill_id} đã được duyệt bởi admin. Đã cộng {amount}đ vào ví bạn.")
            bot.answer_callback_query(call.id, f"Duyệt & cộng {amount}đ")
        elif action == "bill_reject":
            with db_lock:
                c.execute("SELECT user_id, status FROM bills WHERE id=?", (bill_id,))
                r = c.fetchone()
                if not r: return bot.answer_callback_query(call.id, "Bill không tồn tại")
                if r[1] != "pending":
                    return bot.answer_callback_query(call.id, "Bill đã xử lý")
                user_id = r[0]
                c.execute("UPDATE bills SET status=? WHERE id=?", ("rejected", bill_id))
                conn.commit()
            bot.send_message(user_id, f"❌ Bill #{bill_id} đã bị từ chối bởi admin.")
            bot.answer_callback_query(call.id, "Đã từ chối")
        elif action == "bill_prompt":
            # admin muốn nhập số tiền thủ công => yêu cầu trả lời
            bot.answer_callback_query(call.id, "Nhập số tiền bằng cách chat: /setbill <id> <amount>")
            bot.send_message(call.from_user.id, f"Ví dụ: /setbill {bill_id} 15000")
    except Exception:
        log_exc("cb_handle_bill")

@bot.message_handler(commands=["setbill"])
def cmd_setbill(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 3:
            return bot.reply_to(m, "📌 /setbill <bill_id> <amount>")
        bill_id = int(parts[1]); amount = int(parts[2])
        with db_lock:
            c.execute("SELECT user_id, status FROM bills WHERE id=?", (bill_id,))
            r = c.fetchone()
            if not r: return bot.reply_to(m, "Bill không tồn tại")
            if r[1] != "pending": return bot.reply_to(m, "Bill đã xử lý")
            user_id = r[0]
            c.execute("UPDATE bills SET amount=?, status=? WHERE id=?", (amount, "approved", bill_id))
            conn.commit()
        add_money(user_id, amount)
        bot.reply_to(m, f"Đã duyệt bill #{bill_id} và cộng {amount}đ cho {user_id}")
        try:
            bot.send_message(user_id, f"✅ Bill #{bill_id} đã được duyệt. Bạn nhận {amount}đ.")
        except:
            pass
    except Exception:
        log_exc("/setbill")

# ================== MUA ACC RANDOM (confirm bằng inline) ==================
@bot.message_handler(commands=["random"])
def cmd_random(m):
    try:
        uid = str(m.from_user.id)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(f"Mua ngay ({PRICE_RANDOM}đ)", callback_data="buy_confirm"))
        bot.send_message(m.chat.id, "Bạn muốn mua 1 ACC random?", reply_markup=kb)
    except Exception:
        log_exc("/random")

@bot.callback_query_handler(func=lambda c: c.data == "buy_confirm")
def cb_buy_confirm(call):
    try:
        uid = str(call.from_user.id)
        if not deduct(uid, PRICE_RANDOM):
            return bot.answer_callback_query(call.id, "❌ Không đủ tiền", show_alert=True)
        # lấy acc
        with db_lock:
            c.execute("SELECT id, acc FROM stock_acc ORDER BY RANDOM() LIMIT 1")
            row = c.fetchone()
            if not row:
                add_money(uid, PRICE_RANDOM)
                return bot.answer_callback_query(call.id, "⚠ Hết hàng, tiền đã hoàn lại", show_alert=True)
            acc_id, acc_val = row
            c.execute("DELETE FROM stock_acc WHERE id=?", (acc_id,))
            c.execute("INSERT INTO purchases(user_id, acc, time) VALUES(?,?,?)", (uid, acc_val, time.ctime()))
            conn.commit()
        bot.send_message(uid, f"🛍 Bạn nhận được ACC:\n`{acc_val}`")
        bot.answer_callback_query(call.id, "Giao dịch thành công")
    except Exception:
        log_exc("cb_buy_confirm")
        # refund on error
        try:
            add_money(str(call.from_user.id), PRICE_RANDOM)
        except:
            pass
        bot.answer_callback_query(call.id, "Có lỗi, tiền đã hoàn lại", show_alert=True)

# ================== GIFT CODE ==================
def make_code(n=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

@bot.message_handler(commands=["makecode"])
def cmd_makecode(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 3:
            return bot.reply_to(m, "📌 /makecode <amount> <count> (ví dụ /makecode 10000 3)")
        amount = int(parts[1]); count = int(parts[2])
        codes = []
        with db_lock:
            for _ in range(count):
                code = make_code(10)
                c.execute("INSERT INTO giftcode(code, amount, used_by) VALUES(?,?,?)", (code, amount, None))
                codes.append(code)
            conn.commit()
        bot.reply_to(m, "Tạo thành công:\n" + "\n".join(codes))
    except Exception:
        log_exc("/makecode")

@bot.message_handler(commands=["redeem"])
def cmd_redeem(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            return bot.reply_to(m, "📌 /redeem <code>")
        code = parts[1].strip().upper()
        with db_lock:
            c.execute("SELECT amount, used_by FROM giftcode WHERE code=?", (code,))
            r = c.fetchone()
        if not r:
            return bot.reply_to(m, "❌ Code không tồn tại")
        if r[1] is not None:
            return bot.reply_to(m, "⚠ Code đã được sử dụng")
        amount = int(r[0])
        uid = str(m.from_user.id)
        add_money(uid, amount)
        with db_lock:
            c.execute("UPDATE giftcode SET used_by=? WHERE code=?", (uid, code))
            conn.commit()
        bot.reply_to(m, f"🎉 Nhận {amount}đ từ giftcode `{code}`")
    except Exception:
        log_exc("/redeem")

# ================== ADMIN: quản lý kho ==================
@bot.message_handler(commands=["addacc"])
def cmd_addacc(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        data = m.text.replace("/addacc", "").strip()
        if not data:
            return bot.reply_to(m, "📌 /addacc email:pass")
        with db_lock:
            c.execute("INSERT INTO stock_acc(acc) VALUES(?)", (data,))
            conn.commit()
        bot.reply_to(m, "➕ Đã thêm acc vào kho")
    except Exception:
        log_exc("/addacc")

@bot.message_handler(commands=["stock"])
def cmd_stock(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        with db_lock:
            c.execute("SELECT COUNT(*) FROM stock_acc")
            cnt = c.fetchone()[0]
        bot.reply_to(m, f"📦 Còn {cnt} ACC trong kho")
    except Exception:
        log_exc("/stock")

@bot.message_handler(commands=["listacc"])
def cmd_listacc(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        limit = 100
        with db_lock:
            c.execute("SELECT id, acc FROM stock_acc LIMIT ?", (limit,))
            rows = c.fetchall()
        if not rows:
            return bot.reply_to(m, "Kho trống")
        text = "\n".join([f"{r[0]}. {r[1]}" for r in rows])
        bot.reply_to(m, f"📄 Danh sách (max {limit}):\n{text}\n\n/delacc <id>")
    except Exception:
        log_exc("/listacc")

@bot.message_handler(commands=["delacc"])
def cmd_delacc(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 2:
            return bot.reply_to(m, "📌 /delacc <id>")
        aid = int(parts[1])
        with db_lock:
            c.execute("DELETE FROM stock_acc WHERE id=?", (aid,))
            conn.commit()
        bot.reply_to(m, "🗑 Đã xoá acc")
    except Exception:
        log_exc("/delacc")

@bot.message_handler(commands=["delall"])
def cmd_delall(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        with db_lock:
            c.execute("DELETE FROM stock_acc")
            conn.commit()
        bot.reply_to(m, "🔥 Đã xoá toàn bộ kho")
    except Exception:
        log_exc("/delall")

@bot.message_handler(commands=["export"])
def cmd_export(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        with db_lock:
            c.execute("SELECT acc FROM stock_acc")
            rows = c.fetchall()
        path = "stock_export.txt"
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(r[0] + "\n")
        bot.send_document(m.chat.id, open(path, "rb"))
        try:
            os.remove(path)
        except:
            pass
    except Exception:
        log_exc("/export")

# ================== ADMIN: tiền & broadcast ==================
@bot.message_handler(commands=["addmoney"])
def cmd_addmoney(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        parts = m.text.split()
        if len(parts) < 3:
            return bot.reply_to(m, "📌 /addmoney <user_id> <amount>")
        uid = parts[1]; amount = int(parts[2])
        add_money(uid, amount)
        bot.reply_to(m, f"Đã cộng {amount}đ cho {uid}")
        try:
            bot.send_message(int(uid), f"✅ Admin đã cộng cho bạn {amount}đ")
        except:
            pass
    except Exception:
        log_exc("/addmoney")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(m):
    try:
        if not is_admin_uid(m.from_user.id): return
        text = m.text.replace("/broadcast", "").strip()
        if not text: return bot.reply_to(m, "📌 /broadcast <message>")
        with db_lock:
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
        sent = 0
        for u in users:
            try:
                bot.send_message(int(u[0]), text)
                sent += 1
                time.sleep(0.05)
            except:
                pass
        bot.reply_to(m, f"Đã gửi đến {sent} users")
    except Exception:
        log_exc("/broadcast")

# ================== MINI GAMES ==================
@bot.message_handler(commands=["dice"])
def cmd_dice(m):
    try:
        roll = random.randint(1,6)
        reward = roll * 200
        add_money(str(m.from_user.id), reward)
        bot.reply_to(m, f"🎲 Lắc ra *{roll}* → +{reward}đ")
    except Exception:
        log_exc("/dice")

@bot.message_handler(commands=["slot"])
def cmd_slot(m):
    try:
        icons = ['🍒','💎','⭐','7️⃣']
        s = [random.choice(icons) for _ in range(3)]
        if s.count(s[0])==3:
            add_money(str(m.from_user.id), 10000)
            bot.reply_to(m, f"🎰 {' '.join(s)}\n🔥 JACKPOT +10000đ")
        else:
            bot.reply_to(m, f"🎰 {' '.join(s)}\n😢 Thua rồi")
    except Exception:
        log_exc("/slot")

# ================== AUTO BÁO CÁO HÀNG NGÀY (thread) ==================
def daily_report_thread():
    while True:
        try:
            with db_lock:
                c.execute("SELECT COUNT(*) FROM stock_acc")
                count = c.fetchone()[0]
            for ad in ADMINS:
                try:
                    bot.send_message(int(ad), f"📅 Báo cáo tự động: Còn {count} ACC trong kho")
                except Exception:
                    pass
        except Exception:
            log_exc("daily_report")
        time.sleep(DAILY_REPORT_HOUR)

t = threading.Thread(target=daily_report_thread, daemon=True)
t.start()

# ================== START POLLING SAFE (auto restart) ==================
if __name__ == "__main__":
    keep_alive()
    print("BOT STARTED")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print("Polling crashed:", e)
            traceback.print_exc()
            time.sleep(5)
