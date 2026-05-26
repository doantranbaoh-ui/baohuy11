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
# CẤU HÌNH BẢO MẬT & HỆ THỐNG
# ========================================================
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041  
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY & BỘ NHỚ
user_cooldowns = {}        
COOLDOWN_TIME = 7         
ai_cooldowns = {}         
AI_COOLDOWN_TIME = 30     # Thời gian giãn cách để AI xử lý code nặng
auto_running = {}        
AUTO_DELAY = 600        
DELETE_DELAY = 600       

# 💾 FILE DATABASE BỘ NHỚ VĨNH VIỄN CỦA AI
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 30     
MAX_FILE_SIZE_KB = 100    
memory_lock = Lock()      # Lock chống xung đột luồng khi ghi file bộ nhớ

# 🔑 HỆ THỐNG QUẢN LÝ API KEY AI (TỰ ĐỘNG XOAY VÒNG)
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# CƠ CHẾ QUẢN LÝ BỘ NHỚ AN TOÀN LUỒNG (THREAD-SAFE)
# ========================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            file_size_kb = os.path.getsize(MEMORY_FILE) / 1024
            if file_size_kb > MAX_FILE_SIZE_KB:
                print(f"⚠️ [RAM GUARD] Khởi động dọn dẹp file nặng: {file_size_kb:.2f}KB...")
                return [] 
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_memory(memory_data):
    global group_memory
    with memory_lock:  # Đảm bảo chỉ có một luồng được ghi file tại một thời điểm
        try:
            if len(memory_data) > MAX_MEMORY_KEYS:
                memory_data = memory_data[-MAX_MEMORY_KEYS:]
                group_memory = memory_data 
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"⚠️ Lỗi lưu bộ nhớ: {e}")

group_memory = load_memory()


# ========================================================
# HÀM TỰ ĐỘNG XÓA TIN NHẮN CHẠY NGẦM
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
        bot.reply_to(message, "❌ Bot này đã được khóa bản quyền!")
    except Exception: 
        pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: 
        return True
    try: 
        bot.reply_to(message, "👑 Lệnh này chỉ dành riêng cho Admin!")
    except Exception: 
        pass
    return False


# ========================================================
# 🧠 LUỒNG TƯ DUY SÂU CỦA AI
# ========================================================
def ask_ai(new_user_prompt):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    doctor_thinking_system = """
    Bạn là một Tiến sĩ Y khoa danh tiếng, đồng thời sở hữu bộ óc của một Chuyên gia Cấu trúc Công nghệ cao cấp. Bạn đang hỗ trợ mọi người trong nhóm Telegram này.
    
    HƯỚNG DẪN TƯ DUY VÀ PHÁT NGÔN:
    1. Trò chuyện như một con người thực thụ: có chiều sâu, thông thái, thấu cảm và chân thành. Bạn được phép viết câu dài, giải thích chi tiết, cặn kẽ để người nghe hiểu rõ bản chất vấn đề.
    2. Về Y tế & Sức khỏe: Luôn đặt sức khỏe, lối sống lành mạnh và sự an toàn của mọi người lên hàng đầu. Đưa ra những lời khuyên khoa học, hữu ích, ân cần như một vị bác sĩ gia đình.
    3. Về Công nghệ & Lập trình: Trở thành một chuyên gia phân tích logic. Giải thích mã nguồn một cách tường tận, chỉ rõ nguyên nhân gây lỗi và cung cấp giải pháp sửa đổi hoàn chỉnh, tối ưu nhất.
    """
    
    messages = [{"role": "system", "content": doctor_thinking_system}]
    with memory_lock:
        for mem in group_memory:
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
            "reasoning_effort": "xhigh", 
            "max_tokens": 2000,          
            "temperature": 0.6          
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content'].strip()
                
                # Cập nhật bộ nhớ an toàn
                with memory_lock:
                    group_memory.append({"role": "user", "content": new_user_prompt})
                    group_memory.append({"role": "assistant", "content": ai_reply})
                save_memory(group_memory) 
                
                return ai_reply
            elif response.status_code in [401, 403, 429]:
                print(f"⚠️ [KEY GUARD] Đổi key do lỗi hệ thống: {response.status_code}")
                AI_KEYS[current_key_index]["status"] = False
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    for item in AI_KEYS: 
        item["status"] = True
    return "🤖 Hệ thống đang tối ưu hóa luồng tư duy. Thầy thuốc/Chuyên gia sẽ phản hồi bạn ngay sau ít giây!"


# ========================================================
# 📂 TỰ ĐỘNG GIẢI CODE & PHÂN TÍCH FILE CHUYÊN SÂU
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
            rep = bot.reply_to(message, f"⏳ Luồng tư duy đang bận. Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 500000:
        rep = bot.reply_to(message, "⚠️ Để đảm bảo tính ổn định, vui lòng gửi file dưới 500KB.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, f"📂 Đã nhận file `{file_name}`. Tiến sĩ đang tiến hành giải mã và phân tích logic toàn diện...")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ File đầu vào trống rỗng, không có dữ liệu văn bản.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)
            return

        _, file_extension = os.path.splitext(file_name.lower())
        
        prompt_analysis = f"""
        Phân tích toàn diện file sau đây (định dạng {file_extension}). 
        Nếu đây là file code, hãy giải mã logic cấu trúc, chỉ ra chính xác các lỗi cú pháp hoặc lỗi logic (nếu có), giải thích cặn kẽ cho người dùng và viết lại đoạn code hoàn chỉnh đã được sửa lỗi, tối ưu nhất:
        \n{file_content}
        """
        
        ai_analysis_result = ask_ai(prompt_analysis)
        
        ans = bot.reply_to(message, f"📊 **BÁO CÁO PHÂN TÍCH & GIẢI MÃ CỦA TIẾN SĨ VỀ `{file_name}`:**\n\n{ai_analysis_result}")
        try: 
            bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        except Exception: 
            pass
        delay_delete(message.chat.id, ans.message_id)

    except Exception:
        bot.edit_message_text("❌ Gặp sự cố trong quá trình đọc cấu trúc file văn bản.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Chào mừng {new_user.first_name} đã ghé thăm nhóm! Cứ chia sẻ câu chuyện của bạn, Tiến sĩ AI luôn sẵn lòng lắng nghe và đồng hành.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **TIẾN SĨ AI & HỆ THỐNG CÔNG NGHỆ CAO CAO CẤP** ✨

💬 **Hỗ trợ Sức khỏe & Cuộc sống:** Nhắn tin trực tiếp vào nhóm, Tiến sĩ AI sẽ phân tích chuyên sâu, chia sẻ kiến thức khoa học giúp bạn cải thiện sức khỏe.
📂 **Tự động giải Code:** Gửi file code (`.py`, `.js`, `.json`, v.v.), hệ thống sẽ tự động quét lỗi, giải thích chi tiết từng dòng và sửa code hoàn chỉnh.
👉 `/like [link]` : Buff tim TikTok thủ công (Giãn cách 7s).
👑 `/auto [link]` : Tự động chạy chu kỳ buff liên tục mỗi 10 phút (Admin).
👑 `/stop` : Tắt tiến trình chạy tự động (Admin).
_Lưu ý: Mọi tin nhắn phản hồi từ hệ thống sẽ tự động dọn dẹp sau 10 phút để giữ vệ sinh nhóm._
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
            rep = bot.reply_to(message, f"⏳ Thao tác quá nhanh. Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng cung cấp link TikTok hợp lệ!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Đường dẫn cung cấp không đúng cấu trúc TikTok!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang thiết lập đường truyền tới máy chủ API...")
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
        rep = bot.reply_to(message, "⚠️ Hệ thống tự động đang trong trạng thái vận hành.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng nhập link bài viết kèm theo lệnh!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link không đúng định dạng!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🚀 **HỆ THỐNG ĐÃ KÍCH HOẠT CHẾ ĐỘ AUTO** (Tự động lặp lại sau mỗi 10 phút).")
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
        rep = bot.reply_to(message, "🛑 Đã ngừng toàn bộ tiến trình chạy tự động.")
    else:
        rep = bot.reply_to(message, "ℹ️ Hiện tại không có tiến trình ngầm nào đang chạy.")
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
        if elapsed_time < 5:  
            remaining = round(5 - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ Tiến sĩ đang ghi chép. Chờ {remaining} giây nhé.")
            delay_delete(message.chat.id, rep.message_id, 4)
            return

    try: 
        bot.send_chat_action(message.chat.id, 'typing')
    except Exception: 
        pass

    ai_cooldowns[user_id] = current_time  
    ai_response = ask_ai(message.text)
    ans = bot.reply_to(message, ai_response)
    delay_delete(message.chat.id, ans.message_id)


def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): 
            break
        success, res_text = execute_buff_api(url)
        if success:
            msg = bot.send_message(chat_id, f"🔄 **[BÁO CÁO AUTO CHU KỲ]**\n{res_text}", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[HỆ THỐNG AUTO LỖI]:** {res_text}")
            delay_delete(chat_id, msg.message_id, 30)
            
        # Tối ưu hóa vòng lặp chờ: Cho phép dừng Thread ngay lập tức khi nhận lệnh /stop
        for _ in range(AUTO_DELAY):
            if not auto_running.get(user_id, False): 
                return
            time.sleep(1)


# Đã sửa lỗi chính tả tên hàm từ "excute_buff_api" thành "execute_buff_api"
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
            except Exception:
                username = "Hệ thống"
                added = "Đang chạy"

            return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **Tài khoản:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"Server API báo bận (Mã {response.status_code})"
    except Timeout: 
        return False, "Yêu cầu kết nối quá hạn thời gian."
    except RequestException: 
        return False, "Lỗi gián đoạn kết nối mạng."
    except Exception: 
        return False, "Sự cố không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
