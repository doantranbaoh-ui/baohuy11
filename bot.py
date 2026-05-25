import time
import urllib.parse
from threading import Thread
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
import os
import json
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
DELETE_DELAY = 600       

# 💾 FILE DATABASE BỘ NHỚ VĨNH VIỄN CỦA AI
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 100     # Giới hạn tối đa 20 tin nhắn trong RAM đệm
MAX_FILE_SIZE_KB = 1000    # Giới hạn file tối đa 50KB để bảo vệ RAM tuyệt đối

# DANH SÁCH 2 API KEY AI CỦA BẠN
AI_KEYS = [
    "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",  
    "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3"   
]
current_key_index = 0  


# ========================================================
# CƠ CHẾ QUẢN LÝ BỘ NHỚ CHỐNG TRÀN RAM (GIỚI HẠN PHẦN TỬ & DUNG LƯỢNG)
# ========================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            # KIỂM TRA CHỐNG TRÀN: Nếu file bỗng dưng quá nặng (>50KB), tự động cắt tỉa
            file_size_kb = os.path.getsize(MEMORY_FILE) / 1024
            if file_size_kb > MAX_FILE_SIZE_KB:
                print(f"⚠️ [RAM GUARD] Phát hiện file bộ nhớ nặng {file_size_kb:.2f}KB. Tiến hành dọn dẹp dữ liệu cũ...")
                return [] # Reset bộ nhớ đệm tạm thời để giải phóng dung lượng RAM
                
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Lỗi đọc bộ nhớ: {e}")
            return []
    return []

def save_memory(memory_data):
    global group_memory
    try:
        # KIỂM TRA TRÊN RAM: Giới hạn số lượng câu thoại lưu trên bộ đệm RAM sinh tồn
        if len(memory_data) > MAX_MEMORY_KEYS:
            memory_data = memory_data[-MAX_MEMORY_KEYS:]
            group_memory = memory_data # Cập nhật lại RAM toàn cục
            
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Không thể tối ưu lưu bộ nhớ: {e}")

# Tải dữ liệu ban đầu an toàn
group_memory = load_memory()


# ========================================================
# HÀM TỰ ĐỘNG XÓA TIN NHẮN CHẠY NGẦM
# ========================================================
def delay_delete(chat_id, message_id, delay_seconds=DELETE_DELAY):
    def delete_worker():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
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


# ========================================================
# LUỒNG XỬ LÝ AI: TỰ HỌC & GIỚI HẠN TỪ NGỮ SIÊU NGẮN
# ========================================================
def ask_ai(new_user_prompt):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    human_thinking_system = """
    Bạn là một thực thể AI thông minh chat nhóm. Bạn biết tự học dựa vào lịch sử chat ngắn được cung cấp.
    QUY TẮC PHÁT NGÔN:
    1. Chỉ trả lời từ 1 đến 3 câu ngắn. Tuyệt đối không viết dài dòng.
    2. Đi thẳng vào đáp án cốt lõi, không chào hỏi rườm rà khách sáo.
    3. Ngôn từ tự nhiên như bạn bè chat nhanh.
    """
    
    messages = [{"role": "system", "content": human_thinking_system}]
    for mem in group_memory:
        messages.append(mem)
    messages.append({"role": "user", "content": new_user_prompt})
    
    for _ in range(len(AI_KEYS)):
        active_key = AI_KEYS[current_key_index]
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-5.4",
            "messages": messages,
            "reasoning_effort": "xhigh", 
            "max_tokens": 250, # Khóa chặt độ dài để tránh phình bộ nhớ RAM khi nhận text phản hồi
            "temperature": 0.6  
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content'].strip()
                
                # Cập nhật thông minh và kích hoạt bộ lọc RAM Guard lập tức
                group_memory.append({"role": "user", "content": new_user_prompt})
                group_memory.append({"role": "assistant", "content": ai_reply})
                save_memory(group_memory) 
                
                return ai_reply
            else:
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    return "🤖 Hệ thống đang bận tối ưu tài nguyên phần cứng. Vui lòng thử lại sau ít giây!"


# ========================================================
# TỰ ĐỘNG ĐỌC VÀ PHÂN TÍCH FILE (CÓ HẸN GIỜ XÓA)
# ========================================================
@bot.message_handler(content_types=['document'])
def handle_incoming_file(message):
    if not is_allowed_chat(message): return

    user_id = message.from_user.id
    current_time = time.time()

    if user_id in ai_cooldowns:
        elapsed_time = current_time - ai_cooldowns[user_id]
        if elapsed_time < AI_COOLDOWN_TIME:
            remaining = round(AI_COOLDOWN_TIME - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 500000:
        rep = bot.reply_to(message, "⚠️ Dung lượng file không được vượt quá 500KB.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, f"📂 Đã nhận file `{file_name}`. Đang quét dữ liệu...")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ File trống.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)
            return

        prompt_analysis = f"Đọc hiểu file {file_name} này và tóm tắt siêu ngắn lỗi hoặc điểm cốt lõi nhất:\n{file_content}"
        ai_analysis_result = ask_ai(prompt_analysis)
        
        ans = bot.reply_to(message, f"📊 **BÁO CÁO PHÂN TÍCH `{file_name}`:**\n\n{ai_analysis_result}")
        bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, ans.message_id)

    except Exception:
        bot.edit_message_text("❌ Lỗi đọc cấu trúc file văn bản.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Chào {new_user.first_name}! Chat tự do đi, tôi sẽ nghe và tự ghi nhớ bài học.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **BOT SMART AI & TIKTOK BUFF** ✨

👉 `/like [link]` : Buff tim thủ công (Giãn cách 7s).
👑 `/auto [link]` : Tự động buff liên tục mỗi 10 phút (Admin).
👑 `/stop` : Dừng chế độ tự động buff (Admin).
💬 **Chat tự do:** AI ngắn gọn, tự nhớ kiến thức và tự dọn RAM chống tràn.
📂 **Gửi file văn bản/code:** Nhận phân tích và tóm tắt siêu tốc.
*Tin nhắn hệ thống sẽ tự biến mất sau 10 phút.*
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
            rep = bot.reply_to(message, f"⏳ Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng cung cấp link TikTok!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Đường dẫn TikTok không hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang gửi yêu cầu đến server API...")
    user_cooldowns[user_id] = current_time  

    success, res_text = execute_buff_api(url)
    if success:
        bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
        delay_delete(message.chat.id, loading.message_id)
    else:
        if user_id in user_cooldowns: del user_cooldowns[user_id]
        bot.edit_message_text(f"❌ {res_text}", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 15)


@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message): return
    if not is_admin(message): return  

    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        rep = bot.reply_to(message, "⚠️ Chế độ tự động đang chạy.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🚀 **BẮT ĐẦU CHẠY AUTO** (Vòng lặp 10 phút/lần).")
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
        rep = bot.reply_to(message, "🛑 Đã tắt chế độ Auto.")
    else:
        rep = bot.reply_to(message, "ℹ️ Hiện không có tiến trình nào đang chạy.")
    delay_delete(message.chat.id, rep.message_id, 10)


# ========================================================
# KÊNH TIẾP NHẬN CHAT TỰ DO TRONG NHÓM
# ========================================================
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
            rep = bot.reply_to(message, f"⏳ Chờ {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 4)
            return

    try: bot.send_chat_action(message.chat.id, 'typing')
    except: pass

    ai_cooldowns[user_id] = current_time  
    ai_response = ask_ai(message.text)
    ans = bot.reply_to(message, ai_response)
    delay_delete(message.chat.id, ans.message_id)


def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): break
        success, res_text = execute_buff_api(url)
        if success:
            msg = bot.send_message(chat_id, f"🔄 **[AUTO REPORT]**\n{res_text}", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[AUTO LỖI]:** {res_text}")
            delay_delete(chat_id, msg.message_id, 30)
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): return
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
                username = data.get("username") or data.get("user") or "TikTok User"
                added = data.get("added") or data.get("count") or "Đang tăng..."
            except:
                username = "Hệ thống"
                added = "Đang chạy"

            return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **User:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"Server bận (Mã phản hồi {response.status_code})"
    except Timeout: return False, "API quá hạn thời gian kết nối."
    except RequestException: return False, "Lỗi kết nối mạng đến cổng API."
    except: return False, "Lỗi hệ thống không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
