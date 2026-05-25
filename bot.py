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

user_cooldowns = {}
COOLDOWN_TIME = 7       
auto_running = {}       
AUTO_DELAY = 600        

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
# HÀM BƠM PHƯƠNG PHÁP TƯ DUY CON NGƯỜI VÀO AI
# ========================================================
def ask_ai(user_prompt):
    global current_key_index
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # Định hình tính cách và cấu trúc tư duy của con người cho AI
    human_thinking_system = """
    Bạn không phải là một cái máy trả lời tự động vô hồn. Bạn là một chuyên gia con người thực thụ với trí tuệ, cảm xúc và khả năng lập luận sắc bén. 

    Mỗi khi nhận được câu hỏi từ người dùng, bạn PHẢI tự đóng vai và suy nghĩ ngầm qua các bước sau trước khi viết câu trả lời:
    1. THẤU CẢM: Đặt mình vào vị trí người hỏi để hiểu tâm trạng, mục đích thực sự đằng sau câu hỏi của họ là gì.
    2. PHÂN TÍCH ĐA CHIỀU: Đánh giá vấn đề từ nhiều khía cạnh khác nhau (Ưu điểm, nhược điểm, rủi ro, cơ hội).
    3. PHẢN BIỆN: Tự đặt câu hỏi ngược lại xem lập luận của mình đã chắc chắn chưa, có bị phiến diện không.
    4. GIAO TIẾP TỰ NHIÊN: Khi viết câu trả lời cuối cùng, hãy dùng ngôn từ tự nhiên, linh hoạt, đôi lúc có chút hài hước, đồng cảm hoặc thẳng thắn như một người bạn đồng hành (tránh dùng các từ sáo rỗng như 'Dưới đây là...', 'Tóm lại...', 'Với tư cách là AI...').

    Quy định: Hãy trả lời cô đọng, cuốn hút, đi thẳng vào bản chất vấn đề bằng tiếng Việt tự nhiên nhất.
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
            # Tăng mức độ nỗ lực suy nghĩ cho mô hình (tương ứng với config xhigh của bạn)
            "reasoning_effort": "xhigh", 
            "max_tokens": 1200,
            "temperature": 0.8  # Tăng tính sáng tạo và tự nhiên giống con người
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
# XỬ LÝ SỰ KIỆN & CÁC LỆNH (GIỮ NGUYÊN)
# ========================================================

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        name = new_user.first_name
        welcome_text = f"👋 **Chào mừng {name} đã gia nhập nhóm!**\n\n💬 Mình là Trợ lý AI có tư duy phản biện. Cứ chat tự do vào nhóm, chúng ta cùng thảo luận nhé! 🔥"
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **BOT BUFF TYM TIKTOK & HUMAN-AI CHATBOT** ✨

📌 **HƯỚNG DẪN DÙNG BOT:**
👉 `/like [link]` : Buff tim thủ công.
👑 `/auto [link]` : Tự động buff liên tục sau mỗi 10 phút (Admin).
👑 `/stop` : Dừng chế độ tự động buff (Admin).
💬 **Chat tự do:** Nhắn tin bình thường vào nhóm, AI sẽ dùng tư duy đa chiều để trò chuyện cùng bạn!
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


@bot.message_handler(func=lambda message: True)
def reply_with_ai(message):
    if not is_allowed_chat(message): return
    if not message.text or message.text.startswith('/'): return

    try: bot.send_chat_action(message.chat.id, 'typing')
    except: pass

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
        response = requests.get(api, timeout=46)
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
