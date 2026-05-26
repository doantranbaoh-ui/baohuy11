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
# CẤU HÌNH HỆ THỐNG & BẢO MẬT
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()

# ⏳ COOLDOWN & ĐỘ TRỄ (TỐI ƯU GỌN)
user_cooldowns = {}        
COOLDOWN_TIME = 7         
ai_cooldowns = {}         
AI_COOLDOWN_TIME = 15     # Giảm xuống 15s để phản hồi nhanh
auto_running = {}        
AUTO_DELAY = 600        
DELETE_DELAY = 300        # 5 phút tự động xóa tin rác

# 💾 QUẢN LÝ BỘ NHỚ RAM CHỐNG TRÀN
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 15      # Giữ hội thoại ngắn gọn (15 câu gần nhất)
MAX_FILE_SIZE_KB = 50    
memory_lock = Lock()      

# 🔑 XOAY VÒNG 2 API KEY AI
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  

# ========================================================
# QUẢN LÝ DATABASE FILE JSON AN TOÀN
# ========================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            if (os.path.getsize(MEMORY_FILE) / 1024) > MAX_FILE_SIZE_KB: return []
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return []
    return []

def save_memory(memory_data):
    global group_memory
    with memory_lock:
        try:
            if len(memory_data) > MAX_MEMORY_KEYS:
                memory_data = memory_data[-MAX_MEMORY_KEYS:]
                group_memory = memory_data 
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=4)
        except Exception: pass

group_memory = load_memory()

# ========================================================
# HÀM BỔ TRỢ & PHÂN QUYỀN
# ========================================================
def delay_delete(chat_id, message_id, delay_seconds=DELETE_DELAY):
    def delete_worker():
        time.sleep(delay_seconds)
        try: bot.delete_message(chat_id, message_id)
        except Exception: pass
    Thread(target=delete_worker, daemon=True).start()

def is_allowed_chat(message):
    if message.chat.id == ALLOWED_GROUP_ID: return True
    try: bot.reply_to(message, "❌ Bản quyền không hợp lệ!")
    except Exception: pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: return True
    try: bot.reply_to(message, "👑 Chỉ dành cho Admin!")
    except Exception: pass
    return False

# ========================================================
# 🧠 CƠ CHẾ GỌI AI TRẢ LỜI NGẮN GỌN, TRỌNG TÂM
# ========================================================
def ask_ai(new_user_prompt):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # Ép AI bắt buộc phải chat ngắn, súc tích, đi thẳng vào vấn đề
    short_system = "Bạn là Tiến sĩ Y khoa kiêm Chuyên gia Lập trình cấp cao. Hãy trả lời cực kỳ ngắn gọn, cô đọng, bỏ qua các câu chào hỏi rườm rà, tập trung 100% vào giải pháp chính xác và câu trả lời súc tích."
    
    messages = [{"role": "system", "content": short_system}]
    with memory_lock:
        for mem in group_memory: messages.append(mem)
    messages.append({"role": "user", "content": new_user_prompt})
    
    for _ in range(len(AI_KEYS)):
        active_item = AI_KEYS[current_key_index]
        if not active_item["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
            
        headers = {"Authorization": f"Bearer {active_item['key']}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-5.4",
            "messages": messages,
            "max_tokens": 1000, # Đủ cho code ngắn và câu trả lời súc tích
            "temperature": 0.4
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=45)
            if response.status_code == 200:
                ai_reply = response.json()['choices'][0]['message']['content'].strip()
                with memory_lock:
                    group_memory.append({"role": "user", "content": new_user_prompt})
                    group_memory.append({"role": "assistant", "content": ai_reply})
                save_memory(group_memory) 
                return ai_reply
            elif response.status_code in [401, 403, 429]:
                AI_KEYS[current_key_index]["status"] = False
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    for item in AI_KEYS: item["status"] = True
    return "🤖 Hệ thống bận, vui lòng thử lại sau vài giây!"

# ========================================================
# 📂 PHÂN TÍCH FILE & ĐOÁN LỖI CODE TỰ ĐỘNG
# ========================================================
@bot.message_handler(content_types=['document'])
def handle_incoming_file(message):
    if not is_allowed_chat(message): return
    user_id = message.from_user.id
    current_time = time.time()

    if user_id in ai_cooldowns and (current_time - ai_cooldowns[user_id]) < AI_COOLDOWN_TIME:
        rep = bot.reply_to(message, f"⏳ Vui lòng chờ {round(AI_COOLDOWN_TIME - (current_time - ai_cooldowns[user_id]), 1)} giây.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    if message.document.file_size > 300000: # Giới hạn 300KB cho nhẹ nhóm
        rep = bot.reply_to(message, "⚠️ Chỉ chấp nhận file văn bản/code dưới 300KB.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "📂 Đang đọc và phân tích cấu trúc file...")
    ai_cooldowns[user_id] = current_time

    try:
        file_info = bot.get_file(message.document.file_id)
        file_content = bot.download_file(file_info.file_path).decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ File trống!", chat_id=message.chat.id, message_id=loading.message_id)
            return

        _, ext = os.path.splitext(message.document.file_name.lower())
        prompt = f"Phân tích nhanh file {ext}, tìm lỗi sai logic/cú pháp nếu là code và trả về đoạn code đã sửa tối ưu, ngắn gọn nhất:\n\n{file_content}"
        
        result = ask_ai(prompt)
        ans = bot.reply_to(message, f"📊 **KẾT QUẢ PHÂN TÍCH (`{message.document.file_name}`):**\n\n{result}")
        try: bot.delete_message(message.chat.id, loading.message_id)
        except Exception: pass
        delay_delete(message.chat.id, ans.message_id)
    except Exception:
        bot.edit_message_text("❌ Lỗi đọc cấu trúc file!", chat_id=message.chat.id, message_id=loading.message_id)

# ========================================================
# XỬ LÝ LỆNH HỆ THỐNG & BUFF TƯƠNG TÁC TIKTOK
# ========================================================
@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """✨ **HỆ THỐNG AI TRỢ LÝ RÚT GỌN** ✨
💬 **Chat tự do:** Nhắn trực tiếp vào nhóm để hỏi đáp Y tế & Công nghệ (Ngắn gọn).
📂 **Check Code:** Gửi file code trực tiếp lên nhóm để sửa lỗi nhanh.
👉 `/like [link]` : Tăng tim TikTok thủ công (Cooldown 7s).
👑 `/auto [link]` : Tự động buff mỗi 10 phút (Admin).
👑 `/stop` : Dừng chế độ chạy tự động (Admin)."""
    msg = bot.reply_to(message, text, parse_mode="Markdown")
    delay_delete(message.chat.id, msg.message_id)

@bot.message_handler(commands=['like'])
def like(message):
    if not is_allowed_chat(message): return
    user_id = message.from_user.id
    current_time = time.time()

    if user_id in user_cooldowns and (current_time - user_cooldowns[user_id]) < COOLDOWN_TIME:
        rep = bot.reply_to(message, "⏳ Thao tác quá nhanh, vui lòng chậm lại!")
        delay_delete(message.chat.id, rep.message_id, 4)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        rep = bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang kết nối server...")
    user_cooldowns[user_id] = current_time  

    success, res_text = execute_buff_api(args[1].strip())
    bot.edit_message_text(res_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown" if success else None)
    delay_delete(message.chat.id, loading.message_id, 30 if success else 10)

@bot.message_handler(commands=['auto'])
def auto(message):
    if not is_allowed_chat(message) or not is_admin(message): return
    user_id = message.from_user.id

    if auto_running.get(user_id, False):
        rep = bot.reply_to(message, "⚠️ Hệ thống Auto đang chạy sẵn rồi.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        rep = bot.reply_to(message, "❌ Cung cấp thiếu hoặc sai link TikTok!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, "🚀 **ĐÃ KÍCH HOẠT CHẾ ĐỘ AUTO** (Mỗi 10 phút tự chạy lại).")
    delay_delete(message.chat.id, msg.message_id, 10)

    Thread(target=auto_worker, args=(user_id, args[1].strip(), message.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(message):
    if not is_allowed_chat(message) or not is_admin(message): return
    user_id = message.from_user.id
    if auto_running.get(user_id, False):
        auto_running[user_id] = False
        rep = bot.reply_to(message, "🛑 Đã tắt toàn bộ tiến trình Auto ngầm.")
    else:
        rep = bot.reply_to(message, "ℹ️ Không có tiến trình ngầm nào đang chạy.")
    delay_delete(message.chat.id, rep.message_id, 5)

# ========================================================
# KÊNH CHAT TỰ DO TRONG BOX NHÓM
# ========================================================
@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text and not m.text.startswith('/'))
def reply_with_ai(message):
    user_id = message.from_user.id
    current_time = time.time()

    if user_id in ai_cooldowns and (current_time - ai_cooldowns[user_id]) < 4: # Giãn cách chat thường 4s
        rep = bot.reply_to(message, "⏳ Bạn chat nhanh quá, chờ xíu nhé!")
        delay_delete(message.chat.id, rep.message_id, 3)
        return

    try: bot.send_chat_action(message.chat.id, 'typing')
    except Exception: pass

    ai_cooldowns[user_id] = current_time  
    ai_response = ask_ai(message.text)
    ans = bot.reply_to(message, ai_response)
    delay_delete(message.chat.id, ans.message_id)

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for u in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Chào mừng {u.first_name} gia nhập nhóm! Mình là AI hỗ trợ ngắn gọn, hãy đặt câu hỏi nhé.")
        delay_delete(message.chat.id, msg.message_id, 60)

def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): break
        success, res_text = execute_buff_api(url)
        msg = bot.send_message(chat_id, f"🔄 **[AUTO CHU KỲ]**\n{res_text}", parse_mode="Markdown" if success else None)
        delay_delete(chat_id, msg.message_id, 120 if success else 30)
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): return
            time.sleep(1)

def execute_buff_api(url):
    try:
        api = f"https://tiktokvm.vercel.app/api/likes?url={urllib.parse.quote(url)}"
        response = requests.get(api, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        vn_time = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")

        if response.status_code == 200:
            try:
                data = response.json()
                user = data.get("username") or data.get("user") or "TikTok User"
                count = data.get("added") or data.get("count") or "OK"
            except Exception:
                user, count = "Hệ thống", "Đang chạy"
            return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **User:** {user}\n➕ **Status:** +{count}\n🕒 {vn_time}"
        return False, f"Server bận (Mã {response.status_code})"
    except Timeout: return False, "Lỗi kết nối quá hạn!"
    except RequestException: return False, "Mất kết nối mạng!"
    except Exception: return False, "Sự cố không xác định!"

# Khởi động hệ thống polling vô hạn
bot.infinity_polling(none_stop=True)
