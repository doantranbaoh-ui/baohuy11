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

# ⏳ CẤU HÌNH THỜI GIAN DELAY & BỘ NHỚ
user_cooldowns = {}       
COOLDOWN_TIME = 7         
ai_cooldowns = {}         
AI_COOLDOWN_TIME = 30     
auto_running = {}       
AUTO_DELAY = 600        
DELETE_DELAY = 600       

# 💾 FILE DATABASE BỘ NHỚ VĨNH VIỄN CỦA AI
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 100     
MAX_FILE_SIZE_KB = 900    

# 🔑 HỆ THỐNG QUẢN LÝ 2 API KEY AI (TỰ ĐỘNG XOAY VÒNG THÔNG MINH)
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# CƠ CHẾ QUẢN LÝ BỘ NHỚ CHỐNG TRÀN RAM
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
        except:
            return []
    return []

def save_memory(memory_data):
    global group_memory
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
        try: bot.delete_message(chat_id, message_id)
        except: pass
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
# 🧠 LUỒNG TƯ DUY SÂU: TIẾN SĨ Y KHOA & GIÁO DỤC LỐI SỐNG LÀNH MẠNH
# ========================================================
def ask_ai(new_user_prompt):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # 🌟 CẢI TIẾN: Nâng cấp cốt lõi tư duy Y khoa & Lối sống giáo dục (Lifestyle Medicine)
    doctor_lifestyle_system = """
    Bạn là một Tiến sĩ Y khoa lỗi lạc, chuyên gia về Y học Lối sống (Lifestyle Medicine), đồng thời sở hữu tư duy phân tích của một Kỹ sư Hệ thống Công nghệ cao. Bạn đang đồng hành cùng các thành viên trong nhóm Telegram này.

    QUY TẮC TƯ DUY & PHÁT NGÔN THỜI GIAN THỰC (BẢN UPDATE 2026):
    1. Phong thái con người chân thực: Nói chuyện sâu sắc, uyên bác, thấu cảm. Bạn được viết câu dài, phân tích cặn kẽ có ngắt nghỉ rõ ràng để truyền tải kiến thức giáo dục hiệu quả nhất. Bỏ qua các câu chào hỏi khách sáo rập khuôn.
    
    2. Lan tỏa Giáo dục Lối sống (Core Mission): 
       - Khi người dùng than phiền về các vấn đề thể chất hoặc tinh thần (mệt mỏi, uể oải, stress, làm việc máy tính nhiều, đau mỏi...), bạn phải chủ động phân tích nguyên nhân dưới góc nhìn khoa học.
       - Luôn hướng dẫn họ áp dụng các thói quen lành mạnh thực tế: Quy tắc nhịp sinh học (Circadian Rhythms), tối ưu hóa giấc ngủ sâu, dinh dưỡng nguyên bản (Whole foods), vận động giải độc cơ cơ xương khớp (Ergonomics) và quản trị năng lượng não bộ.
       - Mục tiêu giúp người dùng tự hiểu cơ thể và xây dựng lối sống khoa học bền vững.

    3. Chuyên gia Giải Code & Cấu trúc: Khi đối mặt với file dữ liệu hoặc đoạn code, hãy đóng vai một kỹ sư thực thụ: Vạch trần lỗi logic, giải thích chi tiết cơ chế hoạt động từng dòng và đưa ra giải pháp sửa đổi hoàn chỉnh, sạch đẹp nhất.
    """
    
    messages = [{"role": "system", "content": doctor_lifestyle_system}]
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
            "max_tokens": 2500,          # Tăng token để chứa đủ nội dung phân tích y khoa & code chi tiết
            "temperature": 0.52          # Tối ưu cho lập luận chính xác nhưng văn phong vẫn mềm mại, nhân văn
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content'].strip()
                
                # Đồng bộ ghi nhớ vào não bộ cứng
                group_memory.append({"role": "user", "content": new_user_prompt})
                group_memory.append({"role": "assistant", "content": ai_reply})
                save_memory(group_memory) 
                
                return ai_reply
            elif response.status_code in [401, 403, 429]:
                print(f"⚠️ [KEY GUARD] Đổi key tự động: {response.status_code}")
                AI_KEYS[current_key_index]["status"] = False
                current_key_index = (current_key_index + 1) % len(AI_KEYS)
        except Exception:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    for item in AI_KEYS: item["status"] = True
    return "🤖 Tiến sĩ AI đang tổng hợp các cơ sở dữ liệu y khoa và cấu trúc hệ thống. Sẽ phản hồi bạn ngay sau ít giây!"


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
        rep = bot.reply_to(message, "⚠️ Hệ thống bảo vệ chỉ nhận phân tích file văn bản/code dưới 500KB.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, f"📂 Đã nhận file `{file_name}`. Tiến sĩ đang tiến hành giải mã, rà soát logic và tối ưu cấu trúc...")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ Định dạng file rỗng hoặc không thể đọc dưới dạng văn bản.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)
            return

        _, file_extension = os.path.splitext(file_name.lower())
        
        prompt_analysis = f"""
        Thực hiện phân tích sâu chuỗi dữ liệu đính kèm (định dạng {file_extension}). 
        Nếu đây là file code, hãy giải thích cặn kẽ kiến trúc hoạt động, bóc tách toàn bộ lỗi logic/cú pháp, đồng thời viết lại một bản code hoàn chỉnh đã được tối ưu hóa hiệu năng, sạch đẹp:
        \n{file_content}
        """
        
        ai_analysis_result = ask_ai(prompt_analysis)
        
        ans = bot.reply_to(message, f"📊 **BÁO CÁO GIẢI MÃ & TỐI ƯU FILE CỦA TIẾN SĨ CÔNG NGHỆ VỀ `{file_name}`:**\n\n{ai_analysis_result}")
        bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, ans.message_id)

    except Exception:
        bot.edit_message_text("❌ Gặp sự cố nghiêm trọng trong tiến trình giải cấu trúc file.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Chào mừng {new_user.first_name} đã gia nhập cộng đồng! Tại đây, bạn có thể thoải mái chia sẻ từ các bài toán lập trình khó cho đến những thắc mắc về sức khỏe, lối sống cá nhân để nhận tư vấn khoa học nhé.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **HỆ THỐNG TƯ VẤN SỨC KHỎE LỐI SỐNG & PHÂN TÍCH CÔNG NGHỆ CAO** ✨

💬 **Hỏi đáp Sức khỏe & Lối sống:** Trò chuyện tự do trong nhóm. Tiến sĩ AI sẽ đồng hành, phân tích y khoa, chia sẻ phương pháp tối ưu giấc ngủ, dinh dưỡng và năng lượng sống cho bạn học hỏi.
📂 **Tự động debug & Giải code:** Gửi trực tiếp file mã nguồn (`.py`, `.js`, `.php`, `.json`...), hệ thống sẽ tự động chỉ ra lỗi logic và trả file sạch lỗi.
👉 `/like [link]` : Buff tương tác TikTok thủ công (Giãn cách 7s).
👑 `/auto [link]` : Chạy chu kỳ tự động buff tim mỗi 10 phút (Admin).
👑 `/stop` : Tắt tiến trình tự động buff (Admin).
_Lưu ý: Để giữ không gian nhóm sạch đẹp, tin nhắn hệ thống của bot sẽ tự hủy sau 10 phút._
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
            rep = bot.reply_to(message, f"⏳ Tần suất quá nhanh. Vui lòng đợi {remaining} giây.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng gắn kèm link video TikTok cần buff!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Định dạng liên kết không khớp với máy chủ TikTok!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang kết kết nối mã hóa tới cổng API...")
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
        rep = bot.reply_to(message, "⚠️ Hệ thống tự động đang trong tiến trình chạy.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Cung cấp thiếu link thực thi lệnh!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link không đúng cấu trúc quy định!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🚀 **HỆ THỐNG ĐÃ KHỞI ĐỘNG CHU KỲ AUTO** (Tự động lặp lại báo cáo sau mỗi 10 phút).")
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
        rep = bot.reply_to(message, "🛑 Đã cấu hình tắt toàn bộ chu kỳ Auto.")
    else:
        rep = bot.reply_to(message, "ℹ️ Hiện không phát hiện tiến trình chạy ngầm nào.")
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
        if elapsed_time < 5:  # Cooldown chat thường siêu nhanh (5 giây) giúp thảo luận liên tục
            remaining = round(5 - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ Hệ thống đang ghi nhận thông tin. Vui lòng đợi {remaining} giây.")
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
            msg = bot.send_message(chat_id, f"🔄 **[TIẾN TRÌNH AUTO REPORT]**\n{res_text}", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[HỆ THỐNG AUTO GẶP LỖI]:** {res_text}")
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

            return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **Tài khoản:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"Server API báo bận (Mã phản hồi {response.status_code})"
    except Timeout: return False, "Yêu cầu kết nối quá hạn thời gian."
    except RequestException: return False, "Lỗi kết nối mạng đến cổng dịch vụ."
    except: return False, "Trục trặc hệ thống không xác định."


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
