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
ALLOWED_GROUP_ID = -1003872001041  
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY
user_cooldowns = {}       
COOLDOWN_TIME = 7         

ai_cooldowns = {}         
AI_COOLDOWN_TIME = 15     

auto_running = {}       
AUTO_DELAY = 600        
DELETE_DELAY = 600       # Thời gian tự động xóa tin nhắn (600 giây = 10 phút)

# DANH SÁCH 2 API KEY AI CỦA BẠN
AI_KEYS = [
    "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",  
    "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3"   
]
current_key_index = 0  


# ========================================================
# HÀM TỰ ĐỘNG XÓA TIN NHẮN CHẠY NGẦM (NEW)
# ========================================================
def delay_delete(chat_id, message_id, delay_seconds=DELETE_DELAY):
    def delete_worker():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id, message_id)
            print(f"🗑️ Đã tự động xóa tin nhắn ID {message_id} tại nhóm {chat_id} sau 10 phút.")
        except Exception as e:
            # Lỗi xảy ra nếu tin nhắn đã bị admin xóa trước đó hoặc bot bị tước quyền Admin trong nhóm
            print(f"⚠️ Không thể xóa tin nhắn {message_id}: {e}")

    # Chạy ngầm độc lập để không làm nghẽn luồng xử lý chính của Bot
    thread = Thread(target=delete_worker)
    thread.daemon = True
    thread.start()


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
            "max_tokens": 1500,  
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


@bot.message_handler(content_types=['document'])
def handle_incoming_file(message):
    if not is_allowed_chat(message): return

    user_id = message.from_user.id
    current_time = time.time()

    if user_id in ai_cooldowns:
        elapsed_time = current_time - ai_cooldowns[user_id]
        if elapsed_time < AI_COOLDOWN_TIME:
            remaining = round(AI_COOLDOWN_TIME - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ [AI FILE] Bạn thao tác nhanh quá. Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 10) # Xóa nhắc nhở sau 10s cho sạch nhóm
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 500000:
        rep = bot.reply_to(message, "⚠️ File của bạn quá lớn (Vượt quá 500KB).")
        delay_delete(message.chat.id, rep.message_id, 15)
        return

    loading = bot.reply_to(message, f"📂 Đã nhận file `{file_name}`.\n⏳ Đang đọc nội dung và tiến hành phân tích bằng tư duy AI, vui lòng đợi...")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ Lỗi: File này trống rỗng, không có dữ liệu văn bản để phân tích.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 15)
            return

        prompt_analysis = f"""
        Người dùng vừa gửi lên một file có tên là: {file_name}
        Nội dung chi tiết bên trong file như sau:
        ---
        {file_content}
        ---
        Dựa trên tư duy con người, hãy tự động nhận diện loại file này. Sau đó, phân tích chi tiết nội dung bên trong, tóm tắt các điểm cốt lõi, tìm ra lỗi (nếu có) và đưa ra lời khuyên tối ưu chuyên nghiệp nhất cho người dùng.
        """

        ai_analysis_result = ask_ai(prompt_analysis)
        ans = bot.reply_to(message, f"📊 **KẾT QUẢ PHÂN TÍCH FILE: `{file_name}`**\n━━━━━━━━━━━━━━━━━━\n{ai_analysis_result}")
        bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        
        # ⏱️ Tự động xóa kết quả phân tích file sau 10 phút
        delay_delete(message.chat.id, ans.message_id)

    except Exception as e:
        bot.edit_message_text("❌ Có lỗi xảy ra trong quá trình đọc cấu trúc file của bạn.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 15)


@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        name = new_user.first_name
        welcome_text = f"👋 **Chào mừng {name} đã gia nhập nhóm!**\n\n💬 Mình là Trợ lý AI nâng cao. Bạn có thể chat tự do hoặc gửi trực tiếp file tài liệu vào đây nhé! 🔥"
        msg = bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")
        # ⏱️ Xóa tin nhắn chào mừng sau 10 phút cho đỡ loãng nhóm
        delay_delete(message.chat.id, msg.message_id)


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
📂 **Phân tích dữ liệu:** Gửi trực tiếp file văn bản/code để nhận báo cáo.
⚠️ *Lưu ý: Tất cả tin nhắn thông báo của bot sẽ tự động hủy sau 10 phút để dọn dẹp nhóm.*
"""
    msg = bot.reply_to(message, text, parse_mode="Markdown")
    delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return
    user_id = message.from_user.id
    current_time = time.time()

    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ [BUFF TIM] Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, "⏳ Đang kết nối máy chủ API...")
    user_cooldowns[user_id] = current_time  

    success, res_text = execute_buff_api(url)
    if success:
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
        # ⏱️ Tự động xóa kết quả buff thành công sau 10 phút
        delay_delete(message.chat.id, loading.message_id)
    else:
        if user_id in user_cooldowns:
            del user_cooldowns[user_id]
        bot.edit_message_text(f"❌ {res_text}", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 20)


@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        rep = bot.reply_to(message, "⚠️ Tiến trình đang chạy rồi.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🚀 **KÍCH HOẠT AUTO CHUYÊN NGHIỆP**\n🤖 Tự động chạy sau mỗi 10 phút.")
    delay_delete(message.chat.id, msg.message_id, 30)

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
        rep = bot.reply_to(message, "🛑 Đã dừng chế độ Auto.")
    else:
        rep = bot.reply_to(message, "ℹ️ Không có tiến trình nào đang chạy.")
    delay_delete(message.chat.id, rep.message_id, 15)


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
            rep = bot.reply_to(message, f"⏳ [AI CHAT] Hãy cho tôi {remaining} giây để 'suy ngẫm' đã.")
            delay_delete(message.chat.id, rep.message_id, 8)
            return

    try: bot.send_chat_action(message.chat.id, 'typing')
    except: pass

    ai_cooldowns[user_id] = current_time  
    ai_response = ask_ai(message.text)
    ans = bot.reply_to(message, ai_response)
    
    # ⏱️ Tự động xóa câu trả lời chat tự do của AI sau 10 phút
    delay_delete(message.chat.id, ans.message_id)


def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): break
        success, res_text = execute_buff_api(url)
        if success:
            msg = bot.send_message(chat_id, f"🔄 **[REPORT]**\n{res_text}", parse_mode="Markdown")
            # ⏱️ Xóa báo cáo Auto sau 10 phút
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[LỖI CHU KỲ]:** {res_text}")
            delay_delete(chat_id, msg.message_id, 60)
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): return
            time.sleep(1)


def execute_buff_api(url):
    try:
        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        response = requests.get(api, headers=headers, timeout=25)
        current_vn_time = datetime.now(VN_TZ).strftime("%H:%M | %d/%m/%Y")

        print(f"🤖 [API DEBUG] Code: {response.status_code} | Phản hồi: {response.text}")

        if response.status_code == 200:
            try:
                data = response.json()
                username = data.get("username") or data.get("user") or "TikTok User"
                added = data.get("added") or data.get("count") or "Đang chạy ngầm..."
            except Exception:
                username = "Hệ thống tiếp nhận"
                added = "Đang tăng"

            formatted_result = f"""
🚀 **BUFF TYM THÀNH CÔNG**
━━━━━━━━━━━━━━━━━━
👤 **Tài khoản:** {username}
➕ **Trạng thái:** +{added}
🕒 **Thời gian:** {current_vn_time}
"""
            return True, formatted_result
        elif response.status_code == 429:
            return False, "API bị quá tải (Rate limit). Vui lòng thử lại sau."
        else:
            return False, f"Server API đang bận hoặc chặn yêu cầu (Mã lỗi: {response.status_code})"
            
    except Timeout: return False, "Kết nối đến server API bị quá hạn."
    except RequestException: return False, "Lỗi mạng hoặc server API sập nguồn."
    except: return False, "Hệ thống gặp sự cố không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
