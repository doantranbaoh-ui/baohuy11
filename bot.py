import telebot as tele  # Sử dụng alias 'tele' ngắn gọn
import sqlite3
import logging
from keep_alive import keep_alive

# --- TỰ ĐỘNG CHẠY WEB SERVER KEEP_ALIVE ---
keep_alive()

# --- CẤU HÌNH HỆ THỐNG ---
BOT_TOKEN = "6367532329:AAE4QlpU0abr7lfPTDxZWugKVOcB_usdSYg"  # Thay Token Bot Telegram của bạn vào đây
ADMIN_ID = 5736655322              # Thay ID Chát Telegram của bạn vào đây
PRICE_RD = 500                   # Thiết lập giá bán 1 acc ngẫu nhiên (1,000đ)

# Cấu hình đường dẫn hỗ trợ của Shop
TELEGRAM_GROUP_URL = "https://t.me/baohuydevs" 
ADMIN_USERNAME = "baohuyno1" # Username Telegram viết liền không dấu @

# Cấu hình LOGGING để theo dõi hệ thống trên Render Logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo instance Bot
bot = tele.TeleBot(BOT_TOKEN)

# --- HÀM KẾT NỐI DATABASE (ĐÃ TỐI ƯU CHO RENDER) ---
def get_db_connection():
    # Sử dụng thư mục /tmp/ để bảo đảm Render cho phép quyền ĐỌC/GHI dữ liệu liên tục
    conn = sqlite3.connect('/tmp/shop_lienquan.db', timeout=15)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

# --- KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_rd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_info TEXT,
            status TEXT DEFAULT 'con_hang'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_qr (
            id INTEGER PRIMARY KEY DEFAULT 1,
            bank_bin TEXT DEFAULT '970422',
            bank_acc TEXT DEFAULT '0123456789',
            bank_name TEXT DEFAULT 'NGUYEN VAN A'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO config_qr (id, bank_bin, bank_acc, bank_name) VALUES (1, '970422', '0123456789', 'NGUYEN VAN A')")
    conn.commit()
    conn.close()

init_db()

def check_user(user_id, username):
    username_clean = username if username else f"User_{user_id}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username_clean))
        conn.commit()
    conn.close()

# --- GIAO DIỆN MENU CHÍNH ---
def get_main_menu_keyboard():
    markup = tele.types.InlineKeyboardMarkup(row_width=2)
    btn_buy = tele.types.InlineKeyboardButton("🛒 Mua Acc Ngẫu Nhiên", callback_data="user_buy_rd")
    btn_stock = tele.types.InlineKeyboardButton("📦 Kiểm Tra Kho", callback_data="user_check_stock")
    btn_balance = tele.types.InlineKeyboardButton("💳 Kiểm Tra Số Dư", callback_data="user_check_balance")
    btn_deposit = tele.types.InlineKeyboardButton("💰 Nạp Tiền Vào Ví", callback_data="user_deposit_menu")
    btn_support = tele.types.InlineKeyboardButton("📞 Liên Hệ Admin / Hỗ Trợ", callback_data="user_support")
    
    markup.add(btn_buy, btn_stock, btn_balance, btn_deposit)
    markup.add(btn_support)
    return markup

# --- LỆNH /START KHỞI ĐỘNG HỆ THỐNG ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    check_user(message.from_user.id, message.from_user.username)
    welcome_text = (
        f"🤖 **CHÀO MỪNG BẠN ĐẾN VỚI SHOP LIÊN QUÂN TỰ ĐỘNG**\n"
        f"──────────────────────────\n"
        f"👋 Xin chào, *{message.from_user.first_name}*!\n"
        f"🎯 Hệ thống cung cấp acc Random uy tín, trả acc tự động 24/7.\n\n"
        f"👇 Vui lòng chọn một chức năng dưới menu để bắt đầu:"
    )
    bot.reply_to(message, welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

# Lệnh /qr hiển thị nhanh mã QR nạp tiền tài khoản ngân hàng
@bot.message_handler(commands=['qr'])
def qr_cmd(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT bank_bin, bank_acc, bank_name FROM config_qr WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    bank_bin, bank_acc, bank_name = row['bank_bin'], row['bank_acc'], row['bank_name']
    qr_url = f"https://api.vietqr.io/image/{bank_bin}-{bank_acc}-compact.jpg?accountName={bank_name}&add=1"
    
    markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="user_back_to_main_from_photo"))
    bot.send_photo(message.chat.id, qr_url, reply_markup=markup)

# Lệnh nạp số dư thủ công dạng văn bản văn minh /nap 50000
@bot.message_handler(commands=['nap'])
def nap_cmd(message):
    check_user(message.from_user.id, message.from_user.username)
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Vui lòng nhập đúng cú pháp: `/nap <số tiền>`\nVí dụ: `/nap 50000`", parse_mode="Markdown")
            return
        
        amount = float(args[1])
        if amount <= 0:
            bot.reply_to(message, "❌ Số tiền nạp phải lớn hơn 0đ.")
            return

        username = message.from_user.username if message.from_user.username else f"User_{message.from_user.id}"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO deposit_requests (user_id, username, amount) VALUES (?, ?, ?)", (message.from_user.id, username, amount))
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        markup = tele.types.InlineKeyboardMarkup()
        btn_approve = tele.types.InlineKeyboardButton("✅ Duyệt Ngay", callback_data=f"adm_pub_approve_{request_id}")
        btn_reject = tele.types.InlineKeyboardButton("❌ Hủy Đơn", callback_data=f"adm_pub_reject_{request_id}")
        markup.add(btn_approve, btn_reject)

        bot.send_message(
            ADMIN_ID, 
            f"🔔 **CÓ YÊU CẦU NẠP TIỀN MỚI (Mã đơn: #{request_id})**\n\n"
            f"👤 Khách hàng: @{username} (ID: `{message.from_user.id}`)\n"
            f"💵 Số tiền: **{int(amount):,}đ**\n\n"
            f"Hãy check tài khoản ngân hàng trước khi duyệt!",
            reply_markup=markup, parse_mode="Markdown"
        )
        bot.reply_to(message, f"⏳ Đã gửi đơn nạp tiền **#{request_id}**. Vui lòng chờ Admin check ngân hàng và duyệt số dư!")
    except ValueError:
        bot.reply_to(message, "❌ Số tiền không hợp lệ. Vui lòng chỉ nhập số liền nhau (Ví dụ: 50000).")

# --- XỬ LÝ SỰ KIỆN TẤT CẢ NÚT BẤM (CALLBACK QUERY) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username if call.from_user.username else f"User_{user_id}"
    data = call.data

    # ────────────────────────────────────────────────────────
    # 👤 PHÂN HỆ KHÁCH HÀNG (USER CALLBACKS)
    # ────────────────────────────────────────────────────────
    
    if data == "user_back_to_main":
        welcome_text = (
            f"🤖 **CHÀO MỪNG BẠN ĐẾN VỚI SHOP LIÊN QUÂN TỰ ĐỘNG**\n"
            f"──────────────────────────\n"
            f"👇 Vui lòng chọn một chức năng dưới menu để bắt đầu:"
        )
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

    elif data == "user_check_balance":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()['balance']
        conn.close()
        
        text = (
            f"💳 **THÔNG TIN TÀI KHOẢN CỦA BẠN**\n"
            f"──────────────────────────\n"
            f"👤 Tên tài khoản: @{username}\n"
            f"🆔 ID Telegram: `{user_id}`\n"
            f"💵 Số dư hiện tại: **{int(balance):,} VNĐ**\n\n"
            f"💡 _Bạn có thể nạp thêm tiền bằng nút dưới đây nếu muốn mua thêm acc._"
        )
        markup = tele.types.InlineKeyboardMarkup()
        markup.add(tele.types.InlineKeyboardButton("💰 Nạp Tiền Ngay", callback_data="user_deposit_menu"))
        markup.add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_check_stock":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM stock_rd WHERE status = 'con_hang'")
        count = cursor.fetchone()['total']
        conn.close()
        
        text = (
            f"📦 **THÔNG TIN KHO HÀNG HIỆN TẠI**\n"
            f"──────────────────────────\n"
            f"🏷 Sản phẩm: **Acc Liên Quân Random**\n"
            f"💵 Giá bán lẻ: **{PRICE_RD:,}đ / acc**\n"
            f"⚡ Tình trạng kho: Còn **{count}** tài khoản\n\n"
            f"👇 Bấm nút dưới đây để tiến hành mua ngay:"
        )
        markup = tele.types.InlineKeyboardMarkup()
        markup.add(tele.types.InlineKeyboardButton("🛒 Mua Liền Tay", callback_data="user_buy_rd"))
        markup.add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_support":
        text = (
            f"📞 **TRUNG TÂM HỖ TRỢ KHÁCH HÀNG**\n"
            f"──────────────────────────\n"
            f"Nếu gặp lỗi trong quá trình nạp tiền, lỗi tài khoản hoặc cần tư vấn thêm, sếp vui lòng liên hệ trực tiếp với hệ thống.\n\n"
            f"👤 **Admin Chăm Sóc:** @{ADMIN_USERNAME}\n"
            f"⏰ Thời gian hỗ trợ: 08:00 - 23:00 hàng ngày."
        )
        markup = tele.types.InlineKeyboardMarkup(row_width=1)
        btn_tg = tele.types.InlineKeyboardButton("💬 Tham Gia Nhóm Telegram Shop", url=TELEGRAM_GROUP_URL)
        btn_back = tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main")
        markup.add(btn_tg, btn_back)
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_deposit_menu":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bank_bin, bank_acc, bank_name FROM config_qr WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        bank_bin, bank_acc, bank_name = row['bank_bin'], row['bank_acc'], row['bank_name']
        qr_url = f"https://api.vietqr.io/image/{bank_bin}-{bank_acc}-compact.jpg?accountName={bank_name}&add=1"
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="user_back_to_main_from_photo"))
        bot.send_photo(call.message.chat.id, qr_url, reply_markup=markup)

    elif data == "user_back_to_main_from_photo":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        welcome_text = (
            f"🤖 **CHÀO MỪNG BẠN ĐẾN VỚI SHOP LIÊN QUÂN TỰ ĐỘNG**\n"
            f"──────────────────────────\n"
            f"👇 Vui lòng chọn một chức năng dưới menu để bắt đầu:"
        )
        bot.send_message(call.message.chat.id, welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

    elif data == "user_buy_rd":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()['balance']
        
        if balance < PRICE_RD:
            conn.close()
            text = (
                f"❌ **GIAO DỊCH THẤT BẠI**\n"
                f"──────────────────────────\n"
                f"Số dư tài khoản không đủ để thực hiện giao dịch.\n"
                f"💵 Giá 1 acc: **{PRICE_RD:,}đ**\n"
                f"💳 Ví của bạn: **{int(balance):,}đ**\n\n"
                f"Vui lòng nạp thêm tiền vào ví để tiếp tục mua sắm."
            )
            markup = tele.types.InlineKeyboardMarkup()
            markup.add(tele.types.InlineKeyboardButton("💰 Nạp Tiền Ngay", callback_data="user_deposit_menu"))
            markup.add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        cursor.execute("SELECT id, account_info FROM stock_rd WHERE status = 'con_hang' LIMIT 1")
        acc = cursor.fetchone()
        
        if not acc:
            conn.close()
            text = "😭 **HẾT HÀNG MẤT RỒI**\n──────────────────────────\nHiện tại kho acc ngẫu nhiên vừa hết sạch hàng. Admin đang tích cực bổ sung kho acc, sếp vui lòng quay lại sau ít phút nhé!"
            markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại", callback_data="user_back_to_main"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        acc_id, acc_info = acc['id'], acc['account_info']
        new_balance = balance - PRICE_RD
        
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("UPDATE stock_rd SET status = 'da_ban' WHERE id = ?", (acc_id,))
        conn.commit()
        conn.close()
        
        success_msg = (
            f"🎉 **MUA TÀI KHOẢN THÀNH CÔNG** 🎉\n"
            f"──────────────────────────\n"
            f"🔑 **Thông tin tài khoản:**\n`{acc_info}`\n"
            f"──────────────────────────\n"
            f"💵 Số tiền đã trừ: -{PRICE_RD:,}đ\n"
            f"💳 Số dư còn lại: **{int(new_balance):,}đ**\n\n"
            f"⚠️ *Lưu ý:* Hãy đổi mật khẩu và liên kết thông tin bảo mật ngay sau khi nhận tài khoản."
        )
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="user_back_to_main"))
        bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # ────────────────────────────────────────────────────────
    # ⚙️ PHÂN HỆ QUẢN TRỊ (ADMIN ONLY CALLBACKS)
    # ────────────────────────────────────────────────────────
    if data.startswith("adm_") or data.startswith("panel_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Lỗi bảo mật: Bạn không có quyền hạn Admin!", show_alert=True)
            return

    if data.startswith("adm_pub_"):
        parts = data.split('_')
        action = parts[2] 
        request_id = int(parts[3])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount, status FROM deposit_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req or req['status'] != 'pending':
            conn.close()
            bot.edit_message_text(f"⚠️ Đơn hàng #{request_id} này đã được xử lý từ trước.", call.message.chat.id, call.message.message_id)
            return
            
        target_user_id = req['user_id']
        amount = req['amount']
        
        if action == "approve":
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id))
            cursor.execute("UPDATE deposit_requests SET status = 'approved' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            
            bot.edit_message_text(f"✅ **ĐÃ DUYỆT THÀNH CÔNG**\n──────────────────\nĐã cộng **+{int(amount):,}đ** cho khách đơn số #`{request_id}`.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            try:
                bot.send_message(target_user_id, f"🎉 **Đơn nạp tiền #{request_id} đã thành công!** Tài khoản của bạn vừa được cộng vào **+{int(amount):,}đ**.")
            except Exception:
                pass
                
        elif action == "reject":
            cursor.execute("UPDATE deposit_requests SET status = 'rejected' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            
            bot.edit_message_text(f"❌ **ĐÃ HỦY ĐƠN NẠP**\n──────────────────\nĐã huỷ và từ chối đơn hàng số #`{request_id}`.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            try:
                bot.send_message(target_user_id, f"❌ Yêu cầu nạp tiền đơn số **#{request_id}** của bạn đã bị Admin từ chối phê duyệt.")
            except Exception:
                pass

    elif data == "panel_view_pending":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, amount FROM deposit_requests WHERE status = 'pending' ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            bot.answer_callback_query(call.id, "🎉 Hiện tại không có đơn nạp nào đang chờ!", show_alert=True)
            return
            
        text = "📥 **DANH SÁCH ĐƠN NẠP CHỜ DUYỆT (MỚI NHẤT):**\n\n"
        markup = tele.types.InlineKeyboardMarkup(row_width=2)
        
        for row in rows:
            text += f"🔹 Đơn `#{row['id']}` - Khách: @{row['username']} - Số tiền: **{int(row['amount']):,}đ**\n"
            btn_ok = tele.types.InlineKeyboardButton(f"✅ Duyệt #{row['id']}", callback_data=f"adm_pub_approve_{row['id']}")
            btn_no = tele.types.InlineKeyboardButton(f"❌ Huỷ #{row['id']}", callback_data=f"adm_pub_reject_{row['id']}")
            markup.add(btn_ok, btn_no)
            
        markup.add(tele.types.InlineKeyboardButton("⬅️ Quay lại Menu Admin", callback_data="panel_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "panel_guide_acc":
        guide_text = (
            "➕ **CÁCH THÊM ACC HÀNG LOẠT**\n\n"
            "Hãy gửi tin nhắn định dạng dấu gạch đứng `|` như sau:\n"
            "`/addacc`\n"
            "`thuthu7tung|minhthu032`\n"
            "`taikhoan2|matkhau2`\n\n"
            "_Lưu ý: Lệnh `/addacc` ở dòng đầu tiên, danh sách tài khoản nằm ở các dòng tiếp theo._"
        )
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay lại", callback_data="panel_main"))
        bot.edit_message_text(guide_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "panel_guide_qr":
        guide_text = (
            "⚙️ **CÁCH THAY ĐỔI CONFIG QR BANK**\n\n"
            "Hãy gửi tin nhắn văn bản theo cú pháp:\n"
            "`/addqr <Mã_BIN> <STK> <Tên_Không_Dấu>`\n\n"
            "Ví dụ mẫu:\n"
            "`/addqr 970422 0123456789 NGUYEN VAN A`"
        )
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay lại", callback_data="panel_main"))
        bot.edit_message_text(guide_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "panel_main":
        markup = tele.types.InlineKeyboardMarkup(row_width=1)
        btn_view_pending = tele.types.InlineKeyboardButton("📥 Xem các đơn nạp chờ duyệt", callback_data="panel_view_pending")
        btn_guide_acc = tele.types.InlineKeyboardButton("➕ Cách thêm Acc hàng loạt", callback_data="panel_guide_acc")
        btn_guide_qr = tele.types.InlineKeyboardButton("⚙️ Cách đổi cấu hình QR Bank", callback_data="panel_guide_qr")
        markup.add(btn_view_pending, btn_guide_acc, btn_guide_qr)
        bot.edit_message_text("⚙️ **TRUNG TÂM ĐIỀU HÀNH ADMIN SHOP**\n\nChào sếp, vui lòng chọn tính năng cần xử lý nhanh:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


# ────────────────────────────────────────────────────────
# 🔒 LỆNH VĂN BẢN QUẢN TRỊ ADMIN
# ────────────────────────────────────────────────────────

@bot.message_handler(commands=['admin_panel'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = tele.types.InlineKeyboardMarkup(row_width=1)
    btn_view_pending = tele.types.InlineKeyboardButton("📥 Xem các đơn nạp chờ duyệt", callback_data="panel_view_pending")
    btn_guide_acc = tele.types.InlineKeyboardButton("➕ Cách thêm Acc hàng loạt", callback_data="panel_guide_acc")
    btn_guide_qr = tele.types.InlineKeyboardButton("⚙️ Cách đổi cấu hình QR Bank", callback_data="panel_guide_qr")
    markup.add(btn_view_pending, btn_guide_acc, btn_guide_qr)
    bot.reply_to(message, "⚙️ **TRUNG TÂM ĐIỀU HÀNH ADMIN SHOP**\n\nChào sếp, vui lòng chọn tính năng cần xử lý nhanh:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['addacc'])
def addacc_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Gõ thiếu dữ liệu! Định dạng mẫu:\n`/addacc`\n`thuthu7tung|minhthu032`", parse_mode="Markdown")
        return
    
    lines = args[1].strip().split('\n')
    added_count = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    for line in lines:
        acc_info = line.strip()
        if acc_info:
            cursor.execute("INSERT INTO stock_rd (account_info) VALUES (?)", (acc_info,))
            added_count += 1
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ Đã nạp thành công **{added_count}** tài khoản định dạng gạch đứng `|` vào kho hàng.")

@bot.message_handler(commands=['addqr'])
def addqr_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(message, "❌ Định dạng đúng: `/addqr <Mã_BIN> <STK> <TÊN_BANK_VIẾT_HOA_KHÔNG_DẤU>`", parse_mode="Markdown")
        return
    bank_bin, bank_acc = args[1].strip(), args[2].strip()
    bank_name = " ".join(args[3:]).upper().strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE config_qr SET bank_bin = ?, bank_acc = ?, bank_name = ? WHERE id = 1", (bank_bin, bank_acc, bank_name))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ Đã cập nhật thông tin tài khoản QR ngân hàng thành công!")

# --- KHỞI CHẠY ĐỘNG CƠ BOT TỐI ƯU HOÀN TOÀN CHO RENDER ---
if __name__ == '__main__':
    logger.info("Bot đang kết nối với máy chủ Render...")
    
    # ⚡ ÉP BUỘC XÓA SẠCH WEBHOOK NGHẼN TRÊN MẠNG
    try:
        bot.delete_webhook(drop_pending_updates=True)
        logger.info("Đã xóa Webhook nghẽn và làm sạch bộ nhớ đệm thành công.")
    except Exception as e:
        logger.error(f"Không thể dọn dẹp Webhook cũ: {e}")
        
    # Chạy vòng lặp polling liên tục, tự động bỏ qua các lỗi rớt mạng cục bộ trên Cloud
    bot.infinity_polling(timeout=20, skip_pending_updates=True, long_polling_timeout=10)
