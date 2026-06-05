import sqlite3
import logging
import requests
import telebot as tele
# Gọi hàm keep_alive từ file keep_alive.py vừa tạo
from keep_alive import keep_alive

# --- TỰ ĐỘNG KHỞI CHẠY WEB SERVER ĐỂ GIỮ CHẠY 24/7 ---
keep_alive()

# =====================================================================
# CẤU HÌNH HỆ THỐNG BOT
# =====================================================================
BOT_TOKEN = "6367532329:AAE4QlpU0abr7lfPTDxZWugKVOcB_usdSYg"  # 🔴 Thay Token Bot Telegram của bạn vào đây
ADMIN_ID = 5736655322              # 🔴 Thay ID Chat Telegram của bạn vào đây (Kiểu số)
PRICE_RD = 500                   # Thiết lập giá bán 1 acc ngẫu nhiên (1,000đ)

# Cấu hình thông tin hỗ trợ
TELEGRAM_GROUP_URL = "https://t.me/baohuydevs"
ADMIN_USERNAME = "baohuyno1" # Username Telegram viết liền không dấu @

# Cấu hình log hệ thống để theo dõi lỗi trên Render Logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Khởi tạo instance Bot
bot = tele.TeleBot(BOT_TOKEN)


# =====================================================================
# QUẢN LÝ CƠ SỞ DỮ LIỆU (SQLITE TRÊN RENDER)
# =====================================================================
def get_db_connection():
    conn = sqlite3.connect('/tmp/shop_lienquan.db', timeout=15)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

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


# =====================================================================
# BỘ PHÂN TÍCH CHUỒI VIETQR CHUẨN NGÂN HÀNG (EMVCo)
# =====================================================================
def parse_vietqr_string(qr_text):
    try:
        if "000201" not in qr_text or "3854" not in qr_text:
            return None
        
        tag_38_start = qr_text.find("38")
        if tag_38_start == -1: return None
        
        tag_38_len = int(qr_text[tag_38_start+2 : tag_38_start+4])
        sub_data = qr_text[tag_38_start+4 : tag_38_start+4+tag_38_len]
        
        tag_01_start = sub_data.find("01")
        if tag_01_start == -1: return None
        
        tag_01_len = int(sub_data[tag_01_start+2 : sub_data[tag_01_start+4]])
        bank_data = sub_data[tag_01_start+4 : tag_01_start+4+tag_01_len]
        
        bin_len = int(bank_data[2:4])
        bank_bin = bank_data[4 : 4+bin_len]
        
        acc_start = 4 + bin_len
        acc_len = int(bank_data[acc_start+2 : acc_start+4])
        bank_acc = bank_data[acc_start+4 : acc_start+4+acc_len]
        
        return bank_bin, bank_acc
    except Exception:
        return None


# =====================================================================
# GIAO DIỆN VÀ TÍNH NĂNG KHÁCH HÀNG
# =====================================================================
def get_main_menu_keyboard():
    markup = tele.types.InlineKeyboardMarkup(row_width=2)
    btn_buy = tele.types.InlineKeyboardButton("🛒 Mua Acc Ngẫu Nhiên", callback_data="user_buy_rd")
    btn_stock = tele.types.InlineKeyboardButton("📦 Kiểm Tra Kho", callback_data="user_check_stock")
    btn_balance = tele.types.InlineKeyboardButton("💳 Kiểm Tra Số Dư", callback_data="user_check_balance")
    btn_deposit = tele.types.InlineKeyboardButton("💰 Nạp Tiền Vào Ví", callback_data="user_deposit_select")
    btn_support = tele.types.InlineKeyboardButton("📞 Liên Hệ Admin / Hỗ Trợ", callback_data="user_support")
    
    markup.add(btn_buy, btn_stock, btn_balance, btn_deposit)
    markup.add(btn_support)
    return markup

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


# =====================================================================
# PHÂN HỆ QUÉT QR ĐỔI CẤU HÌNH BANK (DÙNG API ONLINE KHÔNG LỖI)
# =====================================================================
@bot.message_handler(content_types=['photo'])
def handle_admin_qr_photo(message):
    if message.from_user.id != ADMIN_ID:
        return

    status_msg = bot.reply_to(message, "⏳ Đang gửi ảnh lên máy chủ quét dữ liệu QR Bank...")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        
        api_scan_url = f"https://api.qrserver.com/v1/read-qr-code/?file={file_url}"
        response = requests.get(api_scan_url, timeout=15).json()
        
        qr_text = None
        if response and isinstance(response, list) and "symbol" in response[0]:
            symbol_data = response[0]["symbol"][0]
            if symbol_data.get("data"):
                qr_text = symbol_data["data"]
                
        if not qr_text:
            bot.edit_message_text("❌ Không thể tìm thấy hoặc đọc được mã QR nào trong hình ảnh sếp vừa gửi. Vui lòng gửi ảnh chụp trực diện, rõ nét hơn!", message.chat.id, status_msg.message_id)
            return
            
        parsed = parse_vietqr_string(qr_text)
        
        if not parsed:
            bot.edit_message_text("❌ Định dạng mã QR này không phải là mã QR tài khoản ngân hàng chuẩn (VietQR) tại Việt Nam!", message.chat.id, status_msg.message_id)
            return
            
        bank_bin, bank_acc = parsed
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE config_qr SET bank_bin = ?, bank_acc = ? WHERE id = 1", (bank_bin, bank_acc))
        conn.commit()
        conn.close()
        
        success_text = (
            f"✅ **CẬP NHẬT QR NHẬN TIỀN THÀNH CÔNG**\n"
            f"──────────────────────────\n"
            f"🏦 Mã định danh Ngân hàng (BIN): `{bank_bin}`\n"
            f"💳 Số tài khoản mới: `{bank_acc}`\n\n"
            f"ℹ️ _Kể từ bây giờ, khi khách hàng lên đơn nạp, hệ thống sẽ tự động xuất mã QR động chuyển tiền thẳng về tài khoản này của sếp._"
        )
        bot.edit_message_text(success_text, message.chat.id, status_msg.message_id, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Lỗi phân tích QR: {e}")
        bot.edit_message_text(f"❌ Có lỗi phát sinh khi xử lý tệp ảnh: `{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")


# =====================================================================
# LOGIC TẠO MÃ QR ĐỘNG GẮN ĐƠN NẠP VÀ MỆNH GIÁ
# =====================================================================
def send_dynamic_qr(chat_id, user_id, username, amount):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT bank_bin, bank_acc, bank_name FROM config_qr WHERE id = 1")
    row = cursor.fetchone()
    
    cursor.execute("INSERT INTO deposit_requests (user_id, username, amount) VALUES (?, ?, ?)", (user_id, username, amount))
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()

    bank_bin, bank_acc, bank_name = row['bank_bin'], row['bank_acc'], row['bank_name']
    memo = f"NAP {request_id}"
    
    qr_url = f"https://api.vietqr.io/image/{bank_bin}-{bank_acc}-qr_only.jpg?amount={int(amount)}&addInfo={memo}&accountName={bank_name}"

    admin_markup = tele.types.InlineKeyboardMarkup()
    btn_approve = tele.types.InlineKeyboardButton("✅ Duyệt Ngay", callback_data=f"adm_pub_approve_{request_id}")
    btn_reject = tele.types.InlineKeyboardButton("❌ Hủy Đơn", callback_data=f"adm_pub_reject_{request_id}")
    admin_markup.add(btn_approve, btn_reject)

    bot.send_message(
        ADMIN_ID, 
        f"🔔 **CÓ ĐƠN NẠP TIỀN ĐANG QUÉT QR (Mã: #{request_id})**\n\n"
        f"👤 Khách hàng: @{username} (ID: `{user_id}`)\n"
        f"💵 Số tiền: **{int(amount):,}đ**\n"
        f"📝 Nội dung cần khớp: `{memo}`\n\n"
        f"Vui lòng check biến động số dư trên app ngân hàng trước khi bấm Duyệt!",
        reply_markup=admin_markup, parse_mode="Markdown"
    )

    user_text = (
        f"✨ **MÃ QR NẠP TIỀN TỰ ĐỘNG (ĐƠN #{request_id})** ✨\n"
        f"──────────────────────────\n"
        f"💵 Số tiền: **{int(amount):,} VNĐ**\n"
        f"📝 Nội dung chuyển khoản: `{memo}`\n\n"
        f"📌 **HƯỚNG DẪN CHUYỂN KHOẢN:**\n"
        f"1. Lưu ảnh QR Code này về máy.\n"
        f"2. Mở app ngân hàng quét mã QR, hệ thống sẽ tự động điền số tiền và nội dung.\n"
        f"3. Xác nhận chuyển khoản. Số dư tài khoản Telegram sẽ tự cộng sau khi Admin phê duyệt đơn!"
    )
    user_markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="user_back_to_main_from_photo"))
    bot.send_photo(chat_id, qr_url, caption=user_text, reply_markup=user_markup, parse_mode="Markdown")

def process_custom_amount(message):
    try:
        amount = float(message.text.strip())
        if amount < 1000:
            bot.reply_to(message, "❌ Số tiền nạp tối thiểu phải từ **1,000đ** trở lên. Vui lòng vào lại Menu để thử lại.")
            return
        username = message.from_user.username if message.from_user.username else f"User_{message.from_user.id}"
        send_dynamic_qr(message.chat.id, message.from_user.id, username, amount)
    except ValueError:
        bot.reply_to(message, "❌ Lỗi định dạng chữ số. Vui lòng nhập số tiền bằng ký tự số (Ví dụ: 50000).")


# =====================================================================
# XỬ LÝ SỰ KIỆN NÚT BẤM (CALLBACK QUERY)
# =====================================================================
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username if call.from_user.username else f"User_{user_id}"
    data = call.data

    if data == "user_back_to_main":
        welcome_text = "🤖 **CHÀO MỪNG BẠN ĐẾN VỚI SHOP LIÊN QUÂN TỰ ĐỘNG**\n──────────────────────────\n👇 Vui lòng chọn một chức năng dưới menu để bắt đầu:"
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

    elif data == "user_check_balance":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()['balance']
        conn.close()
        text = f"💳 **THÔNG TIN TÀI KHOẢN CỦA BẠN**\n──────────────────────────\n👤 Tên tài khoản: @{username}\n🆔 ID Telegram: `{user_id}`\n💵 Số dư hiện tại: **{int(balance):,} VNĐ**"
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("💰 Nạp Tiền Ngay", callback_data="user_deposit_select")).add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_check_stock":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM stock_rd WHERE status = 'con_hang'")
        count = cursor.fetchone()['total']
        conn.close()
        text = f"📦 **THÔNG TIN KHO HÀNG HIỆN TẠI**\n──────────────────────────\n🏷 Sản phẩm: **Acc Liên Quân Random**\n💵 Giá bán lẻ: **{PRICE_RD:,}đ / acc**\n⚡ Tình trạng kho: Còn **{count}** tài khoản"
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("🛒 Mua Liền Tay", callback_data="user_buy_rd")).add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_support":
        text = f"📞 **TRUNG TÂM HỖ TRỢ KHÁCH HÀNG**\n──────────────────────────\n👤 **Admin Chăm Sóc:** @{ADMIN_USERNAME}\n⏰ Thời gian hỗ trợ: 08:00 - 23:00 hàng ngày."
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("💬 Tham Gia Nhóm Telegram Shop", url=TELEGRAM_GROUP_URL)).add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "user_deposit_select":
        text = "💰 **CHỌN MỆNH GIÁ CẦN NẠP VÀO VÍ**\n──────────────────────────\nVui lòng chọn một trong các mệnh giá nhanh bên dưới hoặc bấm **Tự nhập số tiền** để hệ thống tự động xuất mã QR Code chính xác:"
        markup = tele.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            tele.types.InlineKeyboardButton("💵 10,000đ", callback_data="user_dep_fix_10000"),
            tele.types.InlineKeyboardButton("💵 20,000đ", callback_data="user_dep_fix_20000"),
            tele.types.InlineKeyboardButton("💵 50,000đ", callback_data="user_dep_fix_50000"),
            tele.types.InlineKeyboardButton("💵 100,000đ", callback_data="user_dep_fix_100000")
        )
        markup.add(tele.types.InlineKeyboardButton("✍️ Tự nhập số tiền mong muốn", callback_data="user_dep_custom"))
        markup.add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data.startswith("user_dep_fix_"):
        amount = float(data.split('_')[3])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_dynamic_qr(call.message.chat.id, user_id, username, amount)

    elif data == "user_dep_custom":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        msg = bot.send_message(call.message.chat.id, "✍️ Sếp vui lòng **nhập số tiền bằng số** cần nạp vào ô chát (Ví dụ: `35000`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_custom_amount)

    elif data == "user_back_to_main_from_photo":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        welcome_text = "🤖 **CHÀO MỪNG BẠN ĐẾN VỚI SHOP LIÊN QUÂN TỰ ĐỘNG**\n──────────────────────────\n👇 Vui lòng chọn một chức năng dưới menu để bắt đầu:"
        bot.send_message(call.message.chat.id, welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

    elif data == "user_buy_rd":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()['balance']
        
        if balance < PRICE_RD:
            conn.close()
            text = f"❌ **GIAO DỊCH THẤT BẠI**\n──────────────────────────\nSố dư tài khoản không đủ.\n💵 Giá 1 acc: **{PRICE_RD:,}đ**\n💳 Ví của bạn: **{int(balance):,}đ**"
            markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("💰 Nạp Tiền Ngay", callback_data="user_deposit_select")).add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu", callback_data="user_back_to_main"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        cursor.execute("SELECT id, account_info FROM stock_rd WHERE status = 'con_hang' LIMIT 1")
        acc = cursor.fetchone()
        
        if not acc:
            conn.close()
            text = "😭 **HẾT HÀNG MẤT RỒI**\n──────────────────────────\nHiện tại kho hàng ngẫu nhiên vừa hết sạch hàng. Hãy liên hệ Admin để bổ sung!"
            markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại", callback_data="user_back_to_main"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        acc_id, acc_info = acc['id'], acc['account_info']
        new_balance = balance - PRICE_RD
        
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("UPDATE stock_rd SET status = 'da_ban' WHERE id = ?", (acc_id,))
        conn.commit()
        conn.close()
        
        success_msg = f"🎉 **MUA TÀI KHOẢN THÀNH CÔNG** 🎉\n──────────────────────────\n🔑 **Thông tin tài khoản:**\n`{acc_info}`\n──────────────────────────\n💵 Số tiền đã trừ: -{PRICE_RD:,}đ\n💳 Số dư còn lại: **{int(new_balance):,}đ**"
        markup = tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay Lại Menu Chính", callback_data="user_back_to_main"))
        bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # --- ADMIN CONTROL PANEL ---
    if data.startswith("adm_") or data.startswith("panel_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Lỗi: Bạn không có quyền Admin!", show_alert=True)
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
            bot.edit_message_text(f"⚠️ Đơn hàng #{request_id} đã được xử lý từ trước.", call.message.chat.id, call.message.message_id)
            return
            
        target_user_id = req['user_id']
        amount = req['amount']
        
        if action == "approve":
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id))
            cursor.execute("UPDATE deposit_requests SET status = 'approved' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"✅ Đã duyệt thành công và cộng **+{int(amount):,}đ** cho đơn số #`{request_id}`.", call.message.chat.id, call.message.message_id)
            try: bot.send_message(target_user_id, f"🎉 Đơn nạp tiền #{request_id} thành công! Tài khoản của bạn được cộng **+{int(amount):,}đ**.")
            except Exception: pass
        elif action == "reject":
            cursor.execute("UPDATE deposit_requests SET status = 'rejected' WHERE id = ?", (request_id,))
            conn.commit()
            conn.close()
            bot.edit_message_text(f"❌ Đã huỷ và từ chối duyệt đơn số #`{request_id}`.", call.message.chat.id, call.message.message_id)
            try: bot.send_message(target_user_id, f"❌ Yêu cầu nạp đơn số **#{request_id}** đã bị Admin từ chối phê duyệt.")
            except Exception: pass

    elif data == "panel_view_pending":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, amount FROM deposit_requests WHERE status = 'pending' ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.answer_callback_query(call.id, "🎉 Không có đơn nạp nào đang chờ duyệt!", show_alert=True)
            return
        text = "📥 **DANH SÁCH ĐƠN CHỜ DUYỆT CẬP NHẬT:**\n\n"
        markup = tele.types.InlineKeyboardMarkup(row_width=2)
        for row in rows:
            text += f"🔹 Đơn `#{row['id']}` - Khách: @{row['username']} - **{int(row['amount']):,}đ**\n"
            markup.add(tele.types.InlineKeyboardButton(f"✅ Duyệt #{row['id']}", callback_data=f"adm_pub_approve_{row['id']}"), tele.types.InlineKeyboardButton(f"❌ Huỷ #{row['id']}", callback_data=f"adm_pub_reject_{row['id']}"))
        markup.add(tele.types.InlineKeyboardButton("⬅️ Quay lại", callback_data="panel_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "panel_guide_acc":
        guide_text = "➕ **CÁCH THÊM ACC HÀNG LOẠT**\n\nSếp gửi tin nhắn định dạng văn bản thường như sau:\n`/addacc`\n`taikhoan1|matkhau1`\n`taikhoan2|matkhau2`"
        bot.edit_message_text(guide_text, call.message.chat.id, call.message.message_id, reply_markup=tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay lại", callback_data="panel_main")), parse_mode="Markdown")

    elif data == "panel_guide_qr":
        guide_text = "⚙️ **CÁCH ĐỔI CẤU HÌNH QR BANK**\n\nCực kỳ đơn giản! Sếp dùng tài khoản Admin **gửi trực tiếp hình ảnh mã QR ngân hàng** mới của sếp vào khung chát này. Bot sẽ tự động xử lý qua hệ thống Cloud API để cập nhật thông tin!"
        bot.edit_message_text(guide_text, call.message.chat.id, call.message.message_id, reply_markup=tele.types.InlineKeyboardMarkup().add(tele.types.InlineKeyboardButton("⬅️ Quay lại", callback_data="panel_main")), parse_mode="Markdown")

    elif data == "panel_main":
        markup = tele.types.InlineKeyboardMarkup(row_width=1)
        markup.add(tele.types.InlineKeyboardButton("📥 Xem đơn nạp chờ duyệt", callback_data="panel_view_pending"), tele.types.InlineKeyboardButton("➕ Cách thêm Acc hàng loạt", callback_data="panel_guide_acc"), tele.types.InlineKeyboardButton("⚙️ Cách đổi cấu hình QR Bank", callback_data="panel_guide_qr"))
        bot.edit_message_text("⚙️ **TRUNG TÂM ĐIỀU HÀNH ADMIN SHOP**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


# =====================================================================
# LỆNH VĂN BẢN (COMMANDS) DÀNH CHO ADMIN
# =====================================================================
@bot.message_handler(commands=['admin_panel'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    markup = tele.types.InlineKeyboardMarkup(row_width=1)
    markup.add(tele.types.InlineKeyboardButton("📥 Xem đơn nạp chờ duyệt", callback_data="panel_view_pending"), tele.types.InlineKeyboardButton("➕ Cách thêm Acc hàng loạt", callback_data="panel_guide_acc"), tele.types.InlineKeyboardButton("⚙️ Cách đổi cấu hình QR Bank", callback_data="panel_guide_qr"))
    bot.reply_to(message, "⚙️ **TRUNG TÂM ĐIỀU HÀNH ADMIN SHOP**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['addacc'])
def addacc_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return
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
    bot.reply_to(message, f"✅ Đã nạp thành công **{added_count}** tài khoản mới vào kho hàng.")


# =====================================================================
# KHỞI CHẠY ĐỘNG CƠ POLLING
# =====================================================================
if __name__ == '__main__':
    logger.info("Bot đang kết nối với máy chủ Render...")
    try: bot.delete_webhook(drop_pending_updates=True)
    except Exception: pass
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
