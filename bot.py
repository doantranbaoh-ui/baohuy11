import time
import urllib.parse
from threading import Thread
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
from keep_alive import keep_alive

# ========================================================
# CẤU HÌNH BẢO MẬT & HỆ THỐNG
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  # ID Nhóm độc quyền
ADMIN_ID = 5736655322              # ID Admin độc quyền sử dụng lệnh Auto

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

keep_alive()
print(f"✅ Bot đang chạy độc quyền cho nhóm: {ALLOWED_GROUP_ID}")
print(f"👑 Admin tối cao: {ADMIN_ID}")

user_cooldowns = {}
COOLDOWN_TIME = 7       # Thời gian giãn cách giữa các lần /like (giây)
auto_running = {}       # Lưu trạng thái auto: {user_id: True/False}
AUTO_DELAY = 800        # Khoảng cách giữa các lần auto (10 phút)


# ========================================================
# HÀM KIỂM TRA QUYỀN TRUY CẬP (MIDDLEWARE)
# ========================================================
def is_allowed_chat(message):
    """Kiểm tra xem tin nhắn có đến từ nhóm được phép không"""
    if message.chat.id == ALLOWED_GROUP_ID:
        return True
    try:
        bot.reply_to(message, "❌ Bot này đã được khóa bản quyền và chỉ hoạt động trong nhóm riêng biệt!")
    except Exception as e:
        print(f"Lỗi gửi từ chối truy cập chat: {e}")
    return False


def is_admin(message):
    """Kiểm tra người dùng có phải là Admin tối cao không"""
    if message.from_user.id == ADMIN_ID:
        return True
    try:
        bot.reply_to(message, "👑 Lệnh này chỉ dành riêng cho Admin của hệ thống!")
    except Exception as e:
        print(f"Lỗi gửi từ chối quyền admin: {e}")
    return False


# ========================================================
# CÁC LỆNH ĐƯỢC ỦY QUYỀN
# ========================================================

@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return

    text = """
✨ **BOT BUFF TYM TIKTOK** ✨

📌 **Các lệnh dành cho Thành Viên:**
👉 `/like [link]` : Buff tim thủ công (1 lần).

👑 **Các lệnh dành riêng cho Admin:**
👉 `/auto [link]` : Tự động buff liên tục sau mỗi 10 phút.
👉 `/stop` : Dừng chế độ tự động buff.
"""
    bot.reply_to(message, text, parse_mode="Markdown")


# LỆNH BUFF THỦ CÔNG (Tất cả thành viên trong nhóm đều dùng được)
@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return

    user_id = message.from_user.id
    current_time = time.time()

    # Kiểm tra Cooldown chống spam
    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ Vui lòng đợi {remaining} giây.")
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        return

    loading = bot.reply_to(message, "⏳ Đang gửi yêu cầu...")
    user_cooldowns[user_id] = current_time

    success, res_text = execute_buff_api(url)
    
    if success:
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text(f"❌ Lỗi: {res_text}", chat_id=message.chat.id, message_id=loading.message_id)


# LỆNH TỰ ĐỘNG BUFF (Chỉ ADMIN được dùng)
@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  # Chặn nếu không phải Admin 5736655322

    user_id = message.from_user.id
    
    if auto_running.get(user_id, False):
        bot.reply_to(message, "⚠️ Bạn đang có một tiến trình Auto chạy rồi. Gõ `/stop` để dừng trước!")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        return

    auto_running[user_id] = True
    bot.reply_to(message, f"🚀 **ĐÃ KÍCH HOẠT CHẾ ĐỘ AUTO (ADMIN)**\n━━━━━━━━━━━━━━━━━━\n🤖 Hệ thống tự động buff sau mỗi **10 phút**.\n🛑 Gõ `/stop` để hủy.")

    thread = Thread(target=auto_worker, args=(user_id, url, message.chat.id))
    thread.daemon = True
    thread.start()


# LỆNH DỪNG AUTO (Chỉ ADMIN được dùng)
@bot.message_handler(commands=['stop'])
def stop(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  # Chặn nếu không phải Admin 5736655322

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        auto_running[user_id] = False
        bot.reply_to(message, "🛑 Đã gửi lệnh dừng chế độ Auto.")
    else:
        bot.reply_to(message, "ℹ️ Bạn hiện không cài đặt tiến trình Auto nào.")


# ========================================================
# HÀM XỬ LÝ CHẠY NGẦM
# ========================================================
def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False):
            break
        
        success, res_text = execute_buff_api(url)
        
        if success:
            alert_text = f"🔄 **[AUTO REPORT] NEXT TURN PREPARED**\n{res_text}"
            bot.send_message(chat_id, alert_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"⚠️ **[AUTO REPORT] LỖI CHU KỲ:**\n{res_text}")
        
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False):
                return
            time.sleep(1)


def execute_buff_api(url):
    try:
        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"
        response = requests.get(api, timeout=25)
        current_vn_time = datetime.now(VN_TZ).strftime("%H:%M | %d/%m/%Y")

        if response.status_code == 200:
            try:
                data = response.json()
                username = data.get("username") or data.get("user") or "TikTok User"
                added = data.get("added") or data.get("count") or "Đang chạy..."
            except:
                username = "Liên kết gửi lên"
                added = "Hệ thống đang tăng"

            formatted_result = f"""
🚀 **BUFF TYM THÀNH CÔNG**
━━━━━━━━━━━━━━━━━━
👤 **Tài khoản:** {username}
➕ **Trạng thái:** +{added}
🕒 **Thời gian:** {current_vn_time}
━━━━━━━━━━━━━━━━━━
✅ Hệ thống đã xử lý video thành công!
"""
            return True, formatted_result
        else:
            return False, f"Máy chủ bận (Mã lỗi HTTP: {response.status_code})"

    except Timeout:
        return False, "Kết nối quá hạn (Timeout)."
    except RequestException:
        return False, "Lỗi kết nối mạng đến máy chủ API."
    except Exception:
        return False, "Lỗi phân tích dữ liệu không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
