import time
import urllib.parse
from threading import Thread
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
import io
from keep_alive import keep_alive

# ========================================================
# CẤU HÌNH BẢO MẬT & HỆ THỐNG
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY
user_cooldowns = {}       
COOLDOWN_TIME = 15         

ai_cooldowns = {}         
AI_COOLDOWN_TIME = 9     # Áp dụng cho cả chat tự do và gửi file phân tích

auto_running = {}       
AUTO_DELAY = 900        

# DANH SÁCH 2 API KEY AI CỦA BẠN
AI_KEYS = [
    "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",  
    "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3"   
]
current_key_index = 0  


def is_allowed_chat(message):
    if message.chat.id == ALLOWED_GROUP_ID: return True
    try: bot.reply_to(message, "❌ Bot này đã được khóa bản quyền!")
    except: pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: return True
    try: bot.reply_to(message, "👑 Lệnh này chỉ dành riêng cho Admin!")
    except: pass
    return False


# ========================================================
# HÀM TƯ DUY CON NGƯỜI CỦA AI
# ========================================================
def ask_ai(user_prompt):
    global current_key_index
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    human_thinking_system = """
    Bạn là một chuyên gia con người thực thụ với trí tuệ, cảm xúc và khả năng lập luận sắc bén. 
    Khi phân tích dữ liệu hoặc câu hỏi, hãy thực hiện theo các bước tư duy: Thấu cảm nhu cầu -> Phân tích cấu trúc dữ liệu đa chiều -> Tự phản biện tính logic -> Giao tiếp tự nhiên.
    Yêu cầu: Trả lời cô đọng, đi thẳng vào bản chất vấn đề bằng tiếng Việt tự nhiên, không rập khuôn máy móc.
    """
    
    for _ in range(len(AI_KEYS)):
        active_key = AI_KEYS[current_key_index]
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": human_thinking_system},
                {"role": "user", "content": user_prompt}
            ],
            "reasoning_effort": "xhigh", 
            "max_tokens": 1500,  # Tăng token để chứa câu trả lời phân tích dài hơn
            "temperature": 0.7  
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                ai_data = response.json()
                return ai_data['choices'][0]['message']['content']
            else:
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception as e:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    return "🤖 Server AI hiện tại đang bận xử lý logic phức tạp. Bạn thử lại nhé!"


# ========================================================
# TÍNH NĂNG MỚI: TỰ ĐỘNG NHẬN DIỆN VÀ PHÂN TÍCH FILE
# ========================================================
@bot.message_handler(content_types=['document'])
def handle_incoming_file(message):
    if not is_allowed_chat(message): return

    user_id = message.from_user.id
    current_time = time.time()

    # Kiểm tra Cooldown chống spam gửi file liên tục
    if user_id in ai_cooldowns:
        elapsed_time = current_time - ai_cooldowns[user_id]
        if elapsed_time < AI_COOLDOWN_TIME:
            remaining = round(AI_COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ [AI FILE] Bạn thao tác nhanh quá. Vui lòng đợi {remaining} giây để gửi yêu cầu tiếp theo.")
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    # Giới hạn chỉ đọc file < 500KB để tránh quá tải token truyền dữ liệu qua API
    if file_size > 500000:
        bot.reply_to(message, "⚠️ File của bạn quá lớn (Vượt quá 500KB). Vui lòng cắt nhỏ file dữ liệu văn bản/code để AI phân tích chính xác nhất!")
        return

    loading = bot.reply_to(message, f"📂 Đã nhận file `{file_name}`.\n⏳ Đang đọc nội dung và tiến hành phân tích bằng tư duy AI, vui lòng đợi...")
    ai_cooldowns[user_id] = current_time

    try:
        # Tải file từ server Telegram về bộ nhớ cache
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Đọc file dưới dạng chuỗi văn bản UTF-8
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ Lỗi: File này trống rỗng, không có dữ liệu văn bản để phân tích.", chat_id=message.chat.id, message_id=loading.message_id)
            return

        # Tạo prompt ra lệnh cho AI đọc hiểu dữ liệu
        prompt_analysis = f"""
        Người dùng vừa gửi lên một file có tên là: {file_name}
        Nội dung chi tiết bên trong file như sau:
        ---
        {file_content}
        ---
        Dựa trên tư duy con người, hãy tự động nhận diện loại file này (Ví dụ: File code, file cấu hình, file nhật ký log, hay văn bản thông thường...). Sau đó, phân tích chi tiết nội dung bên trong, tóm tắt các điểm cốt lõi, tìm ra lỗi (nếu có) và đưa ra lời khuyên tối ưu chuyên nghiệp nhất cho người dùng.
        """

        # Gọi AI xử lý dữ liệu file
        ai_analysis_result = ask_ai(prompt_analysis)
        
        # Trả kết quả phân tích về nhóm
        bot.reply_to(message, f"📊 **KẾT QUẢ PHÂN TÍCH FILE: `{file_name}`**\n━━━━━━━━━━━━━━━━━━\n{ai_analysis_result}")
        bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)

    except Exception as e:
        print(f"Lỗi xử lý đọc file: {e}")
        bot.edit_message_text("❌ Có lỗi xảy ra trong quá trình đọc cấu trúc file của bạn. Đảm bảo file thuộc định dạng văn bản (txt, json, toml, py, csv, json...).", chat_id=message.chat.id, message_id=loading.message_id)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG CŨ (GIỮ NGUYÊN 100%)
# ========================================================

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        name = new_user.first_name
        welcome_text = f"👋 **Chào mừng {name} đã gia nhập nhóm!**\n\n💬 Mình là Trợ lý AI nâng cao. Bạn có thể chat tự do hoặc **gửi trực tiếp file tài liệu/file code** vào đây, mình sẽ tự đọc và phân tích cấu trúc dữ liệu cho bạn nhé! 🔥"
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **BOT BUFF TYM TIKTOK & AI FILE ANALYST** ✨

📌 **HƯỚNG DẪN DÙNG BOT:**
👉 `/like [link]` : Buff tim thủ công (Giãn cách 7s).
👑 `/auto [link]` : Tự động buff liên tục sau mỗi 10 phút (Admin).
👑 `/stop` : Dừng chế độ tự động buff (Admin).
💬 **Chat tự do:** Nhắn tin bình thường, AI sẽ trò chuyện cùng bạn.
📂 **Phân tích dữ liệu:** Gửi trực tiếp bất kỳ file văn bản/file code nào (`.txt`, `.py`, `.toml`, `.json`, `.csv`...), AI sẽ tự động đọc nội dung và xuất báo cáo phân tích!
"""
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return
    user_id = message.from_user.id
    current_time = time.time()

    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ [BUFF TIM] Vui lòng đợi {remaining} giây.")
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        return

    loading = bot.reply_to(message, "⏳ Đang xử lý dữ liệu...")
    user_cooldowns[user_id] = current_time  

    success, res_text = execute_buff_api(url)
    if success:
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text(f"❌ Lỗi: {res_text}", chat_id=message.chat.id, message_id=loading.message_id)


@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        bot.reply_to(message, "⚠️ Tiến trình đang chạy rồi.")
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
    bot.reply_to(message, f"🚀 **KÍCH HOẠT AUTO CHUYÊN NGHIỆP**\n🤖 Tự động chạy sau mỗi 10 phút.")

    thread = Thread(target=auto_worker, args=(user_id, url, message.chat.id))
    thread.daemon = True
    thread.start()


@bot.message_handler(commands=['stop'])
def stop(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        auto_running[user_id] = False
        bot.reply_to(message, "🛑 Đã dừng chế độ Auto.")
    else:
        bot.reply_to(message, "ℹ️ Không có tiến trình nào đang chạy.")


# TRẢ LỜI BẰNG AI KHI CHAT TỰ DO
@bot.message_handler(func=lambda message: True)
def reply_with_ai(message):
    if not is_allowed_chat(message): return
    if not message.text or message.text.startswith('/'): return

    user_id = message.from_user.id
    current_time = time.time()

    if user_id in ai_cooldowns:
        elapsed_time = current_time - ai_cooldowns[user_id]
        if elapsed_time < AI_COOLDOWN_TIME:
            remaining = round(AI_COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ [AI CHAT] Bạn hỏi nhanh quá! Hãy cho tôi {remaining} giây để 'suy ngẫm' câu trước đã nhé.")
            return

    try: bot.send_chat_action(message.chat.id, 'typing')
    except: pass

    ai_cooldowns[user_id] = current_time  
    ai_response = ask_ai(message.text)
    bot.reply_to(message, ai_response)


def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): break
        success, res_text = execute_buff_api(url)
        if success:
            bot.send_message(chat_id, f"🔄 **[REPORT]**\n{res_text}", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"⚠️ **[LỖI CHU KỲ]:** {res_text}")
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): return
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
"""
            return True, formatted_result
        else:
            return False, f"Máy chủ bận ({response.status_code})"
    except Timeout: return False, "Quá hạn kết nối."
    except RequestException: return False, "Lỗi mạng."
    except: return False, "Lỗi hệ thống."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
