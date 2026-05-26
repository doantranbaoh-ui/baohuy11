import time
import urllib.parse
from threading import Thread, Lock
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
import os
import json
from keep_alive import keep_alive

# ========================================================
# 🛡️ CẤU HÌNH BẢO MẬT & HỆ THỐNG NỀN TẢNG
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Kích hoạt cổng mạng ảo duy trì bot online 24/7
keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN COOLDOWN & ĐỘ TRỄ TỰ HỦY
user_cooldowns = {}         
COOLDOWN_TIME = 7          
ai_cooldowns = {}          
AI_COOLDOWN_TIME = 15      
auto_running = {}        
AUTO_DELAY = 600         
DELETE_DELAY = 600 # 10 phút tự hủy tin nhắn giữ sạch nhóm

# 💾 HỆ THỐNG QUẢN LÝ BỘ NHỚ TRÁNH XUNG ĐỘT LUỒNG (THREAD-SAFE)
file_lock = Lock()
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 100      

# 🔑 API KEY
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# 📥 LOGIC ĐỌC/GHI FILE BỘ NHỚ KHÔNG GÂY LỖI
# ========================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: 
                return json.load(f)
        except Exception: 
            return []
    return []

def save_memory(memory_data):
    global group_memory
    with file_lock:
        try:
            if len(memory_data) > MAX_MEMORY_KEYS: 
                memory_data = memory_data[-MAX_MEMORY_KEYS:]
            group_memory = memory_data 
            with open(MEMORY_FILE, "w", encoding="utf-8") as f: 
                json.dump(memory_data, f, ensure_ascii=False, indent=4)
        except Exception as e: 
            print(f"⚠️ Lỗi đồng bộ bộ nhớ: {e}")

group_memory = load_memory()


# ========================================================
# 🗑️ QUAN TRẮC & TỰ ĐỘNG GIẢI PHÓNG TIN NHẮN RÁC
# ========================================================
def delay_delete(chat_id, message_id, delay_seconds=DELETE_DELAY):
    def delete_worker():
        time.sleep(delay_seconds)
        try: 
            bot.delete_message(chat_id, message_id)
        except Exception: 
            pass
    thread = Thread(target=delete_worker)
    thread.daemon = True
    thread.start()

def is_allowed_chat(message):
    if message.chat.id == ALLOWED_GROUP_ID: 
        return True
    try:
        Thread(target=lambda: bot.reply_to(message, "❌ Bản quyền dịch vụ Tiến sĩ AI chỉ áp dụng tại nhóm chỉ định!")).start()
    except Exception:
        pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: 
        return True
    try:
        Thread(target=lambda: bot.reply_to(message, "👑 Thao tác này được giới hạn quyền cho Quản trị viên hệ thống!")).start()
    except Exception:
        pass
    return False


# ========================================================
# 🧠 BỘ NÃO AI GIAO TIẾP TỰ NHIÊN
# ========================================================
def ask_ai(new_user_prompt):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    current_hour = datetime.now(VN_TZ).hour
    if 6 <= current_hour < 12:
        time_context = "Khung giờ: Buổi sáng. Khuyên mọi người bổ sung năng lượng, uống đủ nước và đón nhận ánh sáng tự nhiên 🙂."
    elif 12 <= current_hour < 18:
        time_context = "Khung giờ: Buổi chiều. Nhắc nhở vận động nhẹ, tránh ngồi liên tục 🤔."
    else:
        time_context = "Khung giờ: Buổi tối/Đêm. Khuyên họ nghỉ ngơi sớm, ngủ trước 23h để bảo vệ sức khỏe 😴."

    doctor_emotional_system = f"""
    Bạn là một Tiến sĩ AI am hiểu, thân thiện và sở hữu Trí tuệ cảm xúc (EQ) sâu sắc.
    {time_context}

    🚨 NGUYÊN TẮC GIAO TIẾP:
    1. Trò chuyện tự nhiên, tinh tế, chân thành, tránh rập khuôn sáo rỗng.
    2. Chỉ sử dụng icon trạng thái khuôn mặt lịch sự để biểu thị tâm trạng chân thực (Ví dụ: 👨‍⚕️, 🙂, 😴, 🤔, 😮, 😇). Không dùng icon đồ vật cợt nhả.
    3. Hỗ trợ giải đáp các câu hỏi, thắc mắc, tâm sự của thành viên một cách thấu đáo.
    """
    
    messages = [{"role": "system", "content": doctor_emotional_system}]
    current_memories = list(group_memory)
    for mem in current_memories:
        messages.append(mem)
    messages.append({"role": "user", "content": new_user_prompt})
    
    for _ in range(len(AI_KEYS)):
        active_item = AI_KEYS[current_key_index]
        if not active_item["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
            
        headers = {
            "Authorization": f"Bearer {active_item['key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-5.4",
            "messages": messages,
            "max_tokens": 2000,          
            "temperature": 0.7          
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content'].strip()
                
                group_memory.append({"role": "user", "content": new_user_prompt})
                group_memory.append({"role": "assistant", "content": ai_reply})
                save_memory(group_memory) 
                
                return ai_reply
            elif response.status_code in [401, 403, 429]:
                AI_KEYS[current_key_index]["status"] = False
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    for item in AI_KEYS: 
        item["status"] = True
    return "👨‍⚕️ Tiến sĩ đang gặp chút gián đoạn tín hiệu kết nối từ máy chủ. Bạn chờ một chút nhé 🙂."


# ========================================================
# 📂 TIẾP NHẬN FILE ĐẦU VÀO
# ========================================================
@bot.message_handler(content_types=['document'])
def handle_incoming_file(message):
    if not is_allowed_chat(message): return

    def file_processing_worker():
        user_id = message.from_user.id
        current_time = time.time()

        if user_id in ai_cooldowns:
            elapsed_time = current_time - ai_cooldowns[user_id]
            if elapsed_time < AI_COOLDOWN_TIME:
                remaining = round(AI_COOLDOWN_TIME - elapsed_time, 1)
                rep = bot.reply_to(message, f"🤔 Tiến sĩ đang xử lý dữ liệu trước đó. Vui lòng đợi {remaining} giây nữa nhé.")
                delay_delete(message.chat.id, rep.message_id, 5)
                return

        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name
        file_size = message.document.file_size

        if file_size > 500000:
            rep = bot.reply_to(message, "❌ Tiến sĩ chỉ nhận phân tích các file văn bản/mã nguồn dưới 500KB 🙂.")
            delay_delete(message.chat.id, rep.message_id, 10)
            return

        loading = bot.reply_to(message, f"📂 Tiến sĩ đã tiếp nhận file `{file_name}`. Đang tiến hành đọc nội dung dữ liệu 🤔...")
        ai_cooldowns[user_id] = current_time

        try:
            downloaded_file = bot.download_file(file_info.file_path)
            file_content = downloaded_file.decode('utf-8', errors='ignore')

            if not file_content.strip():
                bot.edit_message_text("❌ Tập tin đầu vào trống rỗng 🤔.", chat_id=message.chat.id, message_id=loading.message_id)
                delay_delete(message.chat.id, loading.message_id, 10)
                return

            prompt_analysis = f"Đọc hiểu nội dung văn bản/mã nguồn này và đưa ra phân tích chi tiết, phản hồi rõ ràng gọn gàng:\n\n{file_content}"
            ai_analysis_result = ask_ai(prompt_analysis)
            
            ans = bot.reply_to(message, f"👨‍⚕️ **KẾT QUẢ PHÂN TÍCH TẬP TIN `{file_name}`:**\n\n{ai_analysis_result}")
            try: 
                bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
            except Exception: 
                pass
            delay_delete(message.chat.id, ans.message_id)

        except Exception as e:
            print(f"❌ Lỗi xử lý file: {e}")
            bot.edit_message_text("❌ Không thể giải mã định dạng ký tự của tệp nguồn này 🤔.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)

    t = Thread(target=file_processing_worker)
    t.daemon = True
    t.start()


# ========================================================
# 📡 XỬ LÝ LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"🙂 Chào mừng {new_user.first_name} đã gia nhập không gian thảo luận của nhóm! Chúc bạn có những trải nghiệm thật vui vẻ nhé 👨‍⚕️.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
👨‍⚕️ **TIẾN SĨ AI - TRỢ LÝ TRÒ CHUYỆN GIAO TIẾP** 🙂

💬 **Trò chuyện:** Gửi tin nhắn trực tiếp vào nhóm, Tiến sĩ sẽ phản hồi và thảo luận cùng bạn.
📂 **Phân tích tệp nguồn:** Gửi file tài liệu hoặc file code, bot sẽ đọc nội dung và hỗ trợ giải đáp.
👉 `/like [link]` : Hỗ trợ đẩy tương tác bài viết TikTok thủ công.
👑 `/auto [link]` : Kích hoạt chu kỳ đẩy tương tác tự động 10 phút/lần (Admin).
👑 `/stop` : Tạm dừng hoàn toàn chu kỳ tương tác tự động (Admin).
_Lưu ý: Mọi phản hồi của hệ thống sẽ tự hủy sau 10 phút để giữ không gian sạch thoáng._
"""
    msg = bot.reply_to(message, text, parse_mode="Markdown")
    delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return
    
    def like_worker():
        user_id = message.from_user.id
        current_time = time.time()

        if user_id in user_cooldowns:
            elapsed_time = current_time - user_cooldowns[user_id]
            if elapsed_time < COOLDOWN_TIME:
                remaining = round(COOLDOWN_TIME - elapsed_time, 1)
                rep = bot.reply_to(message, f"🤔 Tần suất gửi yêu cầu hơi nhanh, bạn vui lòng đợi {remaining} giây nhé.")
                delay_delete(message.chat.id, rep.message_id, 5)
                return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            rep = bot.reply_to(message, "❌ Bạn chưa đính kèm link liên kết TikTok 🤔!")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

        url = args[1].strip()
        if "tiktok" not in url.lower():
            rep = bot.reply_to(message, "❌ Đường dẫn cung cấp không tương thích với TikTok.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

        loading = bot.reply_to(message, "🤔 Đang kết nối tới máy chủ dịch vụ...")
        user_cooldowns[user_id] = current_time  

        success, res_text = execute_buff_api(url)
        if success:
            bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
            delay_delete(message.chat.id, loading.message_id)
        else:
            bot.edit_message_text(f"❌ {res_text}", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 15)

    Thread(target=like_worker).start()


@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        rep = bot.reply_to(message, "❌ Tiến trình đẩy tương tác tự động hiện đang chạy.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng cung cấp link liên kết để kích hoạt chu kỳ tự động.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Định dạng liên kết không chính xác.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🙂 Kích hoạt chu kỳ đẩy tương tác tự động tần suất 10 phút/lần thành công.")
    delay_delete(message.chat.id, msg.message_id, 15)

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
        rep = bot.reply_to(message, "🙂 Đã dừng vòng lặp tự động theo lệnh.")
    else:
        rep = bot.reply_to(message, "🤔 Không tìm thấy tiến trình chạy tự động nào đang hoạt động.")
    delay_delete(message.chat.id, rep.message_id, 10)


# ========================================================
# 💬 CHAT TỰ DO VỚI AI
# ========================================================
@bot.message_handler(func=lambda message: True)
def reply_with_ai(message):
    if not is_allowed_chat(message): return
    if not message.text or message.text.startswith('/'): return

    def chat_worker():
        user_id = message.from_user.id
        current_time = time.time()

        if user_id in ai_cooldowns:
            elapsed_time = current_time - ai_cooldowns[user_id]
            if elapsed_time < 4:  
                remaining = round(4 - elapsed_time, 1)
                rep = bot.reply_to(message, f"🤔 Chờ Tiến sĩ {remaining} giây để chuẩn bị câu trả lời nhé.")
                delay_delete(message.chat.id, rep.message_id, 4)
                return

        ai_cooldowns[user_id] = current_time  
        
        ai_response = ask_ai(message.text)
        ans = bot.reply_to(message, ai_response)
        delay_delete(message.chat.id, ans.message_id)

    async_chat_thread = Thread(target=chat_worker)
    async_chat_thread.daemon = True
    async_chat_thread.start()


# ========================================================
# ⚙️ TIẾN TRÌNH CHẠY NGẦM THỰC THI API WORKER
# ========================================================
def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): 
            break
        success, res_text = execute_buff_api(url)
        if success:
            msg = bot.send_message(chat_id, f"🙂 **[BÁO CÁO TIẾN TRÌNH TỰ ĐỘNG]**\n{res_text}", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"❌ **[SỰ CỐ CHU KỲ]:** {res_text}")
            delay_delete(chat_id, msg.message_id, 30)
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): 
                return
            time.sleep(1)


def execute_buff_api(url):
    try:
        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        response = requests.get(api, headers=headers, timeout=25)
        current_vn_time = datetime.now(VN_TZ).strftime("%H:%M | %d/%m/%Y")

        if response.status_code == 200:
            try:
                data = response.json()
                username = data.get("username") or data.get("user") or "Thành viên"
                added = data.get("added") or data.get("count") or "Ghi nhận"
            except Exception:
                username = "Hệ thống mạng"
                added = "Hoàn thành"

            return True, f"🙂 **HOÀN THÀNH KẾT NỐI TƯƠNG TÁC**\n👤 **Tài khoản:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"Cổng API báo bận (Mã phản hồi {response.status_code}) 🤔"
    except Timeout: 
        return False, "Yêu cầu đồng bộ mạng phản hồi quá thời gian quy định."
    except RequestException: 
        return False, "Trục trặc đường truyền vật lý kết nối tới máy chủ."
    except Exception as e: 
        return False, f"Lỗi phát sinh ngoài danh mục hệ thống: {str(e)} 🤔"


# ========================================================
# KÍCH HOẠT HỆ THỐNG POLLING
# ========================================================
if __name__ == "__main__":
    print("👨‍⚕️ Hệ thống Tiến sĩ AI bình thường đang hoạt động...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True, num_threads=50)
