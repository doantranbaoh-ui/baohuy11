import time
import urllib.parse
from threading import Thread
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
# Gọi hệ thống keep_alive từ file keep_alive.py kế bên sang
from keep_alive import keep_alive

# ========================================================
# CẤU HÌNH BẢO MẬT & HỆ THỐNG
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  # ID Nhóm độc quyền của bạn
ADMIN_ID = 5736655322              # ID Admin tối cao được quyền dùng Auto

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Kích hoạt tính năng giữ sống Web Server ngầm trước
keep_alive()
print(f"✅ Bot AI đang chạy độc quyền cho nhóm: {ALLOWED_GROUP_ID}")
print(f"👑 Admin tối cao: {ADMIN_ID}")

user_cooldowns = {}
COOLDOWN_TIME = 7       # Thời gian giãn cách giữa các lần /like (giây)
auto_running = {}       # Lưu trạng thái auto: {user_id: True/False}
AUTO_DELAY = 736        # Khoảng cách giữa các lần auto (10 phút)

# ========================================================
# DANH SÁCH 2 API KEY AI CỦA BẠN (DỰ PHÒNG LUÂN PHIÊN)
# ========================================================
AI_KEYS = [
    "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",  # Key 1
    "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3"   # Key 2
]
current_key_index = 0  # Vị trí key đang dùng hiện tại


# ========================================================
# HÀM KIỂM TRA QUYỀN TRUY CẬP (MIDDLEWARE)
# ========================================================
def is_allowed_chat(message):
    if message.chat.id == ALLOWED_GROUP_ID:
        return True
    try:
        bot.reply_to(message, "❌ Bot này đã được khóa bản quyền và chỉ hoạt động trong nhóm riêng biệt!")
    except Exception as e:
        print(f"Lỗi gửi từ chối truy cập chat: {e}")
    return False


def is_admin(message):
    if message.from_user.id == ADMIN_ID:
        return True
    try:
        bot.reply_to(message, "👑 Lệnh này chỉ dành riêng cho Admin của hệ thống!")
    except Exception as e:
        print(f"Lỗi gửi từ chối quyền admin: {e}")
    return False


# HÀM GỌI AI THÔNG MINH (SỬ DỤNG API KEY CỦA BẠN)
def ask_ai(user_prompt):
    global current_key_index
    
    # Cấu hình endpoint kết nối theo file config.toml bạn cung cấp
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # Thử gọi API (Có cơ chế tự đổi Key nếu gặp lỗi)
    for _ in range(len(AI_KEYS)):
        active_key = AI_KEYS[current_key_index]
        
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }
        
        # Payload cấu hình mẫu model gpt-5.4 phản hồi nhanh
        payload = {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": "Bạn là trợ lý AI thông minh, thân thiện của nhóm Telegram. Hãy trả lời ngắn gọn, tập trung và chính xác bằng tiếng Việt."},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                ai_data = response.json()
                return ai_data['choices'][0]['message']['content']
            else:
                # Nếu Key này lỗi hoặc hết tiền (mã 429, 401...), chuyển sang Key tiếp theo
                print(f"⚠️ Key vị trí {current_key_index} báo lỗi HTTP {response.status_code}. Đang đổi Key...")
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception as e:
            print(f"⚠️ Lỗi kết nối API AI ở Key vị trí {current_key_index}: {e}")
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    return "🤖 Server AI hiện tại đang quá tải hoặc cả 2 API Key đã hết lượt sử dụng. Vui lòng thử lại sau!"


# ========================================================
# CƠ CHẾ 1: TỰ ĐỘNG CHÀO MỪNG THÀNH VIÊN MỚI VÀO NHÓM
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        name = new_user.first_name
        welcome_text = f"👋 **Chào mừng {name} đã tham gia vào nhóm!**\n\n💬 Mình là Bot tích hợp AI. Bạn cứ chat bình thường vào nhóm, mình sẽ tự động trả lời câu hỏi của bạn nhé! 🔥"
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")


# ========================================================
# LỆNH HỆ THỐNG /START (CÓ SHARE CONFIG)
# ========================================================
@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **BOT BUFF TYM TIKTOK & AI CHATBOT** ✨

📌 **HƯỚNG DẪN DÙNG BOT TELEGRAM:**
👉 `/like [link]` : Buff tim thủ công (Thành viên).
👑 `/auto [link]` : Tự động buff liên tục sau mỗi 10 phút (Admin).
👑 `/stop` : Dừng chế độ tự động buff (Admin).
💬 **Chat tự do:** Cứ nhắn tin bình thường, Bot AI sẽ tự động trả lời giải đáp mọi thắc mắc của bạn!

━━━━━━━━━━━━━━━━━━━━━━━━━━━


😮 **Bước 1:** Nhấn giữ `Windows + R`, nhập: `%userprofile%\\.codex`
😮 *`config.toml`  cấu hình OpenAI (Xem tin nhắn cũ).
"""
    bot.reply_to(message, text, parse_mode="Markdown")


# LỆNH BUFF THỦ CÔNG
@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return
    user_id = message.from_user.id
    current_time = time.time()

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


# LỆNH TỰ ĐỘNG BUFF (ADMIN)
@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        bot.reply_to(message, "⚠️ Bạn đang có một tiến trình Auto chạy rồi.")
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
    bot.reply_to(message, f"🚀 **ĐÃ KÍCH HOẠT CHẾ ĐỘ AUTO (ADMIN)**\n🤖 Tự động buff sau mỗi **10 phút**.")

    thread = Thread(target=auto_worker, args=(user_id, url, message.chat.id))
    thread.daemon = True
    thread.start()


# LỆNH DỪNG AUTO (ADMIN)
@bot.message_handler(commands=['stop'])
def stop(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        auto_running[user_id] = False
        bot.reply_to(message, "🛑 Đã gửi lệnh dừng chế độ Auto.")
    else:
        bot.reply_to(message, "ℹ️ Bạn hiện không cài đặt tiến trình Auto nào.")


# ========================================================
# CƠ CHẾ CHÍNH: TỰ ĐỘNG TRẢ LỜI BẰNG AI KHI CHAT TỰ DO
# ========================================================
@bot.message_handler(func=lambda message: True)
def reply_with_ai(message):
    # Kiểm tra nhóm hợp lệ
    if not is_allowed_chat(message): return

    # Bỏ qua nếu tin nhắn trống hoặc là các lệnh hệ thống
    if not message.text or message.text.startswith('/'):
        return

    # Hiển thị hành động "Đang gõ tin nhắn..." cho chuyên nghiệp
    try:
        bot.send_chat_action(message.chat.id, 'typing')
    except:
        pass

    # Gửi câu hỏi đến hệ thống AI thông minh
    ai_response = ask_ai(message.text)
    
    # Trả lời trực tiếp tin nhắn của thành viên
    bot.reply_to(message, ai_response)


# ========================================================
# CÁC HÀM XỬ LÝ CHẠY NGẦM KHÁC
# ========================================================
def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False):
            break
        success, res_text = execute_buff_api(url)
        if success:
            bot.send_message(chat_id, f"🔄 **[AUTO REPORT] NEXT TURN PREPARED**\n{res_text}", parse_mode="Markdown")
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
        response = requests.get(api, timeout=36)
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
✅ Hệ thống đã tiếp nhận video của bạn!
"""
            return True, formatted_result
        else:
            return False, f"Máy chủ bận (Mã lỗi: {response.status_code})"
    except Timeout:
        return False, "Kết nối quá hạn (Timeout)."
    except RequestException:
        return False, "Lỗi kết nối mạng."
    except Exception:
        return False, "Lỗi không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
