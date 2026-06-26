import sqlite3
import logging
import time
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest, Forbidden

TOKEN = '6367532329:AAHtfx-U0Jl0fByEtXEisrm6zh7lRC4kIew'
ADMIN_ID = 5736655322
SUPPORT_URL = 'https://t.me/baohuyno1'
PRICE_PER_ACC = 500
MIN_DEPOSIT = 1000
REQUEST_TIMEOUT = 1200

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

WAITING_FOR_AMOUNT = {}
WAITING_FOR_QR = {}
WAITING_FOR_ADD_BALANCE = {}
WAITING_FOR_BROADCAST = {}
WAITING_FOR_ACC_DATA = {}
USER_COOLDOWN = {}

class Database:
    def __init__(self, db_path='shop.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._init()

    def _init(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                balance INTEGER DEFAULT 0,
                total_deposited INTEGER DEFAULT 0,
                total_purchased INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_sold INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount INTEGER,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        ''')
        self.conn.commit()

    def execute(self, sql, params=()):
        return self.cursor.execute(sql, params)

    def fetchone(self, sql, params=()):
        return self.cursor.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        return self.cursor.execute(sql, params).fetchall()

    def commit(self):
        self.conn.commit()

db = Database()

def format_vnd(amount):
    return f"{amount:,}đ"

def get_user(user_id):
    db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    db.commit()
    return db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))

def add_transaction(user_id, txn_type, amount, details=""):
    db.execute("INSERT INTO transactions (user_id, type, amount, details) VALUES (?, ?, ?, ?)",
               (user_id, txn_type, amount, details))
    db.commit()

def check_cooldown(user_id, seconds=0.5):
    now = time.time()
    if user_id in USER_COOLDOWN and (now - USER_COOLDOWN[user_id]) < seconds:
        return False
    USER_COOLDOWN[user_id] = now
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    WAITING_FOR_AMOUNT.pop(user_id, None)
    user = get_user(user_id)
    total_accs = db.fetchone("SELECT COUNT(*) as c FROM accounts WHERE is_sold = 0", ())['c']

    keyboard = [
        [InlineKeyboardButton("💳 Nạp tiền", callback_data='menu_nap')],
        [InlineKeyboardButton("💰 Số dư", callback_data='balance')],
        [InlineKeyboardButton(f"🛒 Mua Acc ({format_vnd(PRICE_PER_ACC)})", callback_data='buy')],
        [InlineKeyboardButton("📦 Kho hàng", callback_data='stock')],
        [InlineKeyboardButton("📊 Lịch sử", callback_data='history')],
        [InlineKeyboardButton("🎧 Hỗ trợ", url=SUPPORT_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"🖥 **SHOP TỰ ĐỘNG**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID: `{user_id}`\n"
        f"💰 Số dư: **{format_vnd(user['balance'])}**\n"
        f"🛒 Đã mua: **{user['total_purchased']}** acc\n"
        f"📦 Tồn kho: **{total_accs}** acc\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if not check_cooldown(user_id):
        return

    user = get_user(user_id)
    if user['is_banned']:
        await query.message.reply_text("⛔ Bạn đã bị khóa.")
        return

    if data == 'menu_nap':
        qr = db.fetchone("SELECT value FROM settings WHERE key='qr_file_id'", ())
        keyboard = [
            [InlineKeyboardButton("10k", callback_data='nap_10000'), InlineKeyboardButton("50k", callback_data='nap_50000')],
            [InlineKeyboardButton("100k", callback_data='nap_100000'), InlineKeyboardButton("200k", callback_data='nap_200000')],
            [InlineKeyboardButton("500k", callback_data='nap_500000')],
            [InlineKeyboardButton("✍️ Nhập số khác", callback_data='nap_custom')],
            [InlineKeyboardButton("« Quay lại", callback_data='back_start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        caption = (
            f"💳 **NẠP TIỀN**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Quét mã QR hoặc chuyển khoản\n"
            f"📌 Chọn mệnh giá tương ứng\n"
            f"⚠️ Tối thiểu: **{format_vnd(MIN_DEPOSIT)}**\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        try:
            if qr and qr['value']:
                await query.message.delete()
                await context.bot.send_photo(chat_id=user_id, photo=qr['value'], caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await query.message.edit_text(caption + "\n⚠️ Admin chưa cấu hình QR.", reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest:
            await query.message.reply_text(caption, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'nap_custom':
        WAITING_FOR_AMOUNT[user_id] = True
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text=f"✍️ Nhập số tiền cần nạp (tối thiểu {format_vnd(MIN_DEPOSIT)}):", parse_mode='Markdown')

    elif data.startswith('nap_') and data != 'nap_custom':
        amount = int(data.split('_')[1])
        current_time = int(time.time())
        keyboard = [[InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_{user_id}_{amount}_{current_time}"), InlineKeyboardButton("❌ Hủy", callback_data=f"deny_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **YÊU CẦU NẠP**\n👤 `{user_id}`\n💵 **{format_vnd(amount)}**", reply_markup=reply_markup, parse_mode='Markdown')
            await query.message.delete()
            await context.bot.send_message(chat_id=user_id, text=f"✅ Đã gửi yêu cầu nạp **{format_vnd(amount)}**\n⏰ Chờ Admin duyệt.", parse_mode='Markdown')
        except Forbidden:
            await context.bot.send_message(chat_id=user_id, text="❌ Admin chưa khởi động bot.")

    elif data == 'balance':
        keyboard = [[InlineKeyboardButton("« Quay lại", callback_data='back_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"💰 Số dư: **{format_vnd(user['balance'])}**\n💵 Đã nạp: **{format_vnd(user['total_deposited'])}**", reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'buy':
        acc = db.fetchone("SELECT * FROM accounts WHERE is_sold = 0 ORDER BY id ASC LIMIT 1", ())
        keyboard = [[InlineKeyboardButton("« Quay lại", callback_data='back_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if user['balance'] < PRICE_PER_ACC:
            await query.message.edit_text("❌ Không đủ tiền.", reply_markup=reply_markup)
        elif not acc:
            await query.message.edit_text("❌ Hết hàng.", reply_markup=reply_markup)
        else:
            new_balance = user['balance'] - PRICE_PER_ACC
            db.execute("UPDATE users SET balance = ?, total_purchased = total_purchased + 1 WHERE user_id = ?", (new_balance, user_id))
            db.execute("UPDATE accounts SET is_sold = 1 WHERE id = ?", (acc['id'],))
            add_transaction(user_id, 'purchase', PRICE_PER_ACC, acc['data'])
            db.commit()
            await query.message.edit_text(f"🎉 **MUA THÀNH CÔNG!**\n\n📦 Tài khoản:\n`{acc['data']}`\n\n💰 Số dư còn: **{format_vnd(new_balance)}**", reply_markup=reply_markup, parse_mode='Markdown')
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🛒 Khách `{user_id}` đã mua acc\n📦 `{acc['data']}`", parse_mode='Markdown')
            except:
                pass

    elif data == 'stock':
        count = db.fetchone("SELECT COUNT(*) as c FROM accounts WHERE is_sold = 0", ())['c']
        keyboard = [[InlineKeyboardButton("« Quay lại", callback_data='back_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"📦 Tồn kho: **{count}** acc", reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'history':
        txns = db.fetchall("SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
        keyboard = [[InlineKeyboardButton("« Quay lại", callback_data='back_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if txns:
            text = "📊 **LỊCH SỬ GIAO DỊCH**\n━━━━━━━━━━━━━━━━━━\n"
            for t in txns:
                text += f"{'💵' if t['type']=='deposit' else '🛒'} {format_vnd(t['amount'])} - {t['timestamp']}\n"
        else:
            text = "📊 Chưa có giao dịch."
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'back_start':
        await start(update, context)

    elif data.startswith('approve_') and user_id == ADMIN_ID:
        parts = data.split('_')
        uid, amt, created_time = int(parts[1]), int(parts[2]), int(parts[3])
        if int(time.time()) - created_time > REQUEST_TIMEOUT:
            await query.message.edit_text("❌ Yêu cầu đã hết hạn.")
            try:
                await context.bot.send_message(chat_id=uid, text="⚠️ Yêu cầu nạp đã hết hạn.")
            except:
                pass
            return
        db.execute("UPDATE users SET balance = balance + ?, total_deposited = total_deposited + ? WHERE user_id = ?", (amt, amt, uid))
        add_transaction(uid, 'deposit', amt, f"Admin {user_id} duyệt")
        db.commit()
        await query.message.edit_text(f"✅ Đã duyệt {format_vnd(amt)} cho `{uid}`", parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 Đã cộng **{format_vnd(amt)}** vào tài khoản!", parse_mode='Markdown')
        except:
            pass

    elif data.startswith('deny_') and user_id == ADMIN_ID:
        uid = int(data.split('_')[1])
        await query.message.edit_text(f"❌ Đã từ chối đơn của `{uid}`", parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=uid, text="⚠️ Yêu cầu nạp bị từ chối.")
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if WAITING_FOR_AMOUNT.get(user_id):
        WAITING_FOR_AMOUNT.pop(user_id)
        if text.isdigit() and int(text) >= MIN_DEPOSIT:
            amount = int(text)
            current_time = int(time.time())
            keyboard = [[InlineKeyboardButton("✅ Duyệt", callback_data=f"approve_{user_id}_{amount}_{current_time}"), InlineKeyboardButton("❌ Hủy", callback_data=f"deny_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **YÊU CẦU NẠP**\n👤 `{user_id}`\n💵 **{format_vnd(amount)}**", reply_markup=reply_markup, parse_mode='Markdown')
                await update.message.reply_text(f"✅ Đã gửi yêu cầu nạp **{format_vnd(amount)}**", parse_mode='Markdown')
            except Forbidden:
                await update.message.reply_text("❌ Admin chưa khởi động bot.")
        else:
            await update.message.reply_text(f"❌ Số tiền không hợp lệ. Tối thiểu {format_vnd(MIN_DEPOSIT)}.")

    elif WAITING_FOR_ADD_BALANCE.get(user_id):
        WAITING_FOR_ADD_BALANCE.pop(user_id)
        try:
            parts = text.split()
            target_id = int(parts[0])
            amount = int(parts[1])
            db.execute("UPDATE users SET balance = balance + ?, total_deposited = total_deposited + ? WHERE user_id = ?", (amount, amount, target_id))
            add_transaction(target_id, 'deposit', amount, f"Admin {user_id} cộng thủ công")
            db.commit()
            await update.message.reply_text(f"✅ Đã cộng {format_vnd(amount)} cho `{target_id}`", parse_mode='Markdown')
            try:
                await context.bot.send_message(chat_id=target_id, text=f"🎉 Admin cộng **{format_vnd(amount)}** vào tài khoản!", parse_mode='Markdown')
            except:
                pass
        except:
            await update.message.reply_text("❌ Sai cú pháp. Dùng: ID SOTIEN")

    elif WAITING_FOR_ACC_DATA.get(user_id):
        WAITING_FOR_ACC_DATA.pop(user_id)
        lines = text.strip().split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if line:
                db.execute("INSERT INTO accounts (data) VALUES (?)", (line,))
                count += 1
        db.commit()
        total = db.fetchone("SELECT COUNT(*) as c FROM accounts WHERE is_sold = 0", ())['c']
        await update.message.reply_text(f"✅ Đã thêm **{count}** acc. Tổng kho: **{total}**", parse_mode='Markdown')

    elif WAITING_FOR_BROADCAST.get(user_id):
        WAITING_FOR_BROADCAST.pop(user_id)
        users = db.fetchall("SELECT user_id FROM users WHERE is_banned = 0", ())
        success = 0
        fail = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['user_id'], text=text, parse_mode='Markdown')
                success += 1
                await asyncio.sleep(0.05)
            except:
                fail += 1
        await update.message.reply_text(f"📢 Broadcast hoàn tất\n✅ Thành công: {success}\n❌ Thất bại: {fail}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and WAITING_FOR_QR.get(user_id):
        WAITING_FOR_QR.pop(user_id)
        file_id = update.message.photo[-1].file_id
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('qr_file_id', ?)", (file_id,))
        db.commit()
        await update.message.reply_text("✅ Đã lưu mã QR.")

async def admin_addqr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    WAITING_FOR_QR[update.effective_user.id] = True
    await update.message.reply_text("📸 Gửi ảnh QR:")

async def admin_addacc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    WAITING_FOR_ACC_DATA[update.effective_user.id] = True
    await update.message.reply_text("📦 Gửi dữ liệu acc (mỗi dòng 1 acc):")

async def admin_addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    WAITING_FOR_ADD_BALANCE[update.effective_user.id] = True
    await update.message.reply_text("💰 Nhập ID và số tiền cần cộng:\nVí dụ: 123456789 50000")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    WAITING_FOR_BROADCAST[update.effective_user.id] = True
    await update.message.reply_text("📢 Nhập nội dung broadcast:")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users = db.fetchone("SELECT COUNT(*) as c FROM users", ())['c']
    total_accs = db.fetchone("SELECT COUNT(*) as c FROM accounts WHERE is_sold = 0", ())['c']
    total_sold = db.fetchone("SELECT COUNT(*) as c FROM accounts WHERE is_sold = 1", ())['c']
    total_deposits = db.fetchone("SELECT COALESCE(SUM(amount),0) as c FROM transactions WHERE type='deposit'", ())['c']
    await update.message.reply_text(
        f"📊 **THỐNG KÊ**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Người dùng: **{total_users}**\n"
        f"📦 Tồn kho: **{total_accs}**\n"
        f"🛒 Đã bán: **{total_sold}**\n"
        f"💵 Tổng nạp: **{format_vnd(total_deposits)}**",
        parse_mode='Markdown'
    )

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Dùng: /ban USER_ID")
        return
    try:
        target = int(context.args[0])
        db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target,))
        db.commit()
        await update.message.reply_text(f"✅ Đã khóa `{target}`", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Sai cú pháp.")

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Dùng: /unban USER_ID")
        return
    try:
        target = int(context.args[0])
        db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target,))
        db.commit()
        await update.message.reply_text(f"✅ Đã mở khóa `{target}`", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Sai cú pháp.")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addqr", admin_addqr))
    app.add_handler(CommandHandler("addacc", admin_addacc))
    app.add_handler(CommandHandler("addbalance", admin_addbalance))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    await app.initialize()
    await app.updater.start_polling(allowed_updates=["message", "callback_query"])
    await app.start()
    print("🚀 BOT ĐÃ CHẠY")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        await app.stop()
        await app.updater.stop()

if __name__ == '__main__':
    try:
        from keep_alive import keep_alive
        keep_alive()
    except ImportError:
        pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot đã tắt.")
