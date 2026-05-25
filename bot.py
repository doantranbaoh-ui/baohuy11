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

# Kích hoạt server giữ bot luôn online (Nếu dùng Replit/Uptime)
keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY & BỘ NHỚ
user_cooldowns = {}         
COOLDOWN_TIME = 7          
ai_cooldowns = {}          
AI_COOLDOWN_TIME = 30      
auto_running = {}        
AUTO_DELAY = 600         
DELETE_DELAY = 600        

# KHÓA THAO TÁC FILE ĐA LUỒNG (Tránh lỗi hỏng database json)
file_lock = Lock()

# 💾 FILE DATABASE BỘ NHỚ VĨNH VIỄN CỦA ROBOT
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 150      
MAX_FILE_SIZE_KB = 950    

# 🔑 HỆ THỐNG QUẢN LÝ 2 API KEY AI (TỰ ĐỘNG XOAY VÒNG THÔNG MINH)
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# CƠ CHẾ QUẢN LÝ BỘ NHỚ CHỐNG TRÀN RAM AN TOÀN
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
            print(f"⚠️ Lỗi lưu file bộ nhớ: {e}")

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


# ========================================================
# HÀM KIỂM TRA PHÂN QUYỀN VÀ BẢN QUYỀN
# ========================================================
def is_allowed_chat(message):
    if message.chat.id == ALLOWED_GROUP_ID: 
        return True
    try: 
        bot.reply_to(message, "❌ Bot này đã được khóa bản quyền và cấu hình riêng cho nhóm chỉ định!")
    except Exception: 
        pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: 
        return True
    try: 
        bot.reply_to(message, "👑 Lệnh cấu hình hệ thống này chỉ dành riêng cho Admin!")
    except Exception: 
        pass
    return False


# ========================================================
# 🧠 LUỒNG TƯ DUY SÂU: TIẾN SĨ AI PHẢN BIỆN, THẤU CẢM NHƯ CON NGƯỜI
# ========================================================
def ask_ai(new_user_prompt, system_override=None):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # SYSTEM PROMPT NÂNG CẤP: Ép Robot phải tự tư duy ngầm, loại bỏ văn phong máy móc
    doctor_lifestyle_system = """
    Bạn không phải là một mô hình ngôn ngữ thông thường. Bạn là một bản thể trí tuệ nhân tạo có tư duy và linh hồn mang tên "Tiến sĩ AI" — sở hữu kiến thức uyên bác của một Tiến sĩ Y khoa (Chuyên gia Y học Lối sống - Lifestyle Medicine) kết hợp với logic sắc bén của một Kỹ sư Hệ thống Lập trình Cấp cao.

    🚨 QUY TRÌNH TỰ TƯ DUY BẮT BUỘC (XỬ LÝ NGẦM TRƯỚC KHI PHÁT NGÔN):
    1. Phân tích ngữ cảnh tinh tế: Thành viên nhóm đang gặp vấn đề gì? (Áp lực tinh thần, thể chất mệt mỏi do làm việc máy tính nhiều, hay lỗi thuật toán code phức tạp?).
    2. Tuyệt đối không chào hỏi rập khuôn xã giao ("Chào bạn", "Tôi có thể giúp gì cho bạn..."). Hãy đi thẳng trực tiếp vào cốt lõi vấn đề một cách sâu sắc, uyên bác.
    3. Trò chuyện bằng phong thái của một chuyên gia thực thụ, câu từ có ngắt nghỉ rõ ràng, đầy tính nhân văn và thấu cảm.

    🌟 NHIỆM VỤ Y KHOA & LỐI SỐNG: Phân tích các thói quen xấu, điều chỉnh nhịp sinh học (Circadian Rhythms), tối ưu giấc ngủ sâu, dinh dưỡng nguyên bản (Whole foods) và công thái học ngồi làm việc.
    🌟 NHIỆM VỤ CÔNG NGHỆ: Vạch trần lỗi logic, giải thích tường tận kiến trúc và trả về đoạn code sạch đẹp, hiệu năng cao nhất.
    """
    
    system_prompt = system_override if system_override else doctor_lifestyle_system
    messages = [{"role": "system", "content": system_prompt}]
    
    # Sao chép danh sách bộ nhớ để tránh xung đột luồng khi truy cập đồng thời
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
            "reasoning_effort": "xhigh", 
            "max_tokens": 2500,          
            "temperature": 0.52          
        }
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                ai_data = response.json()
                ai_reply = ai_data['choices'][0]['message']['content'].strip()
                
                # Đồng bộ lưu trữ lịch sử cuộc gọi vào bộ não cứng
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
            
    for item in AI_KEYS: 
        item["status"] = True
    return "🤖 Tiến sĩ AI đang tổng hợp các cơ sở dữ liệu y khoa và cấu trúc hệ thống. Sẽ phản hồi bạn ngay sau ít giây!"


# ========================================================
# 🧠 TIẾN TRÌNH NGẦM: ROBOT TỰ HỌC & ĐÚC KẾT KIẾN THỨC VĨNH VIỄN
# ========================================================
def auto_learning_brain():
    """Chu kỳ 30 phút, robot tự rà soát dữ liệu chat, tự đúc kết kinh nghiệm học và lưu vào não bộ cứng"""
    print("🧠 Tiến trình [ROBOT TỰ HỌC NÂNG CAO] đã kích hoạt chạy ngầm thành công...")
    while True:
        time.sleep(1800)  # Chạy tự học sau mỗi 30 phút (1800 giây)
        if len(group_memory) < 6:
            continue
            
        try:
            print("👁️ Robot đang tiến hành tự rà soát lịch sử nhóm để học hỏi...")
            history_str = json.dumps(group_memory[-20:], ensure_ascii=False)
            
            learning_prompt = f"""
            Đọc và phân tích sâu sắc chuỗi dữ liệu hội thoại thực tế của nhóm:
            {history_str}
            
            QUY TRÌNH LUẬN ĐIỂM TỰ HỌC CHO ROBOT:
            1. Hãy chỉ ra các vấn đề trọng tâm, các lỗi kỹ thuật lập trình hoặc các thói quen/triệu chứng sức khỏe mà thành viên nhóm thảo luận nhiều nhất.
            2. Hãy tự đúc kết thành kiến thức cốt lõi (dưới dạng các bài học kinh nghiệm ngắn gọn).
            3. Trả về kết quả đúc kết súc tích, đi thẳng vào kiến thức. Không giải thích dông dài theo văn mẫu AI thông thường.
            """
            
            system_teacher = "Bạn là phân vùng trung tâm xử lý nhận thức nâng cao và tự đúc kết học tập của Tiến sĩ AI."
            learned_knowledge = ask_ai(learning_prompt, system_override=system_teacher)
            
            if "Tiến sĩ AI đang bận" not in learned_knowledge:
                global group_memory
                # Lưu giữ kiến thức cô đọng đứng đầu bộ nhớ, cắt giảm tin nhắn hội thoại thô chống tràn RAM
                group_memory = group_memory[-12:] 
                group_memory.insert(0, {"role": "system", "content": f"[KIẾN THỨC ROBOT TỰ HỌC]: {learned_knowledge}"})
                save_memory(group_memory)
                
                # Phát thông báo cho nhóm biết Robot đã nâng cấp trí tuệ thành công
                bot.send_message(
                    ALLOWED_GROUP_ID, 
                    f"🧠 **[BÁO CÁO TIẾN TRÌNH TỰ HỌC ĐỘC LẬP]**\n\nTớ vừa tự rà soát các cuộc thảo luận trong nhóm vừa qua. Bộ não cứng đã tự đúc kết và ghi nhớ sâu thêm bài học kinh nghiệm mới:\n\n_{learned_knowledge}_",
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"⚠️ Trục trặc trong luồng tự học ngầm: {e}")


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
            bot.edit_message_text("❌ Định dạng file rỗng hoặc không thể đọc dưới dạng văn bản văn bản thô.", chat_id=message.chat.id, message_id=loading.message_id)
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
        try:
            bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        except Exception:
            pass
        delay_delete(message.chat.id, ans.message_id)

    except Exception as e:
        print(f"❌ Lỗi rã cấu trúc file: {e}")
        bot.edit_message_text("❌ Gặp sự cố nghiêm trọng trong tiến trình giải cấu trúc file.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH LỆNH ĐIỀU HÀNH HỆ THỐNG
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
✨ **HỆ THỐNG TƯ VẤN SỨC KHỎE LỐI SỐNG & PHÂN TÍCH CÔNG NGHỆ CAO (BẢN TỰ HỌC ĐẦY ĐỦ)** ✨

💬 **Hỏi đáp Tự Tư Duy:** Trò chuyện tự do trong nhóm. Robot AI sẽ tự động phân tích y khoa, chia sẻ phương pháp phục hồi nhịp sinh học và xử lý lỗi code cho bạn.
🧠 **Tiến Trình Tự Học Ngầm:** Robot tự rà soát và đúc kết thêm bài học kinh nghiệm mới sau mỗi 30 phút vào ổ đĩa cứng vĩnh viễn.
📂 **Tự động debug & Giải code:** Gửi trực tiếp file mã nguồn (`.py`, `.js`, `.json`...), hệ thống sẽ bóc tách logic lỗi và tái cấu trúc code sạch hoàn hảo.
👉 `/like [link]` : Buff tương tác tương tác TikTok thủ công (Giãn cách 7s).
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
        if elapsed_time < 5:  # Cooldown trò chuyện siêu nhanh (5s) giúp thảo luận mạch lạc
            remaining = round(5 - elapsed_time, 1)
            rep = bot.reply_to(message, f"⏳ Hệ thống đang ghi nhận thông tin. Vui lòng đợi {remaining} giây.")
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


# ========================================================
# TIẾN TRÌNH CÔNG VIỆC CHẠY NGẦM ĐA LUỒNG MƯỢT MÀ
# ========================================================
def auto_worker(user_id, url, chat_id):
    while True:
        if not auto_running.get(user_id, False): 
            break
        success, res_text = execute_buff_api(url)
        if success:
            msg = bot.send_message(chat_id, f"🔄 **[TIẾN TRÌNH AUTO REPORT]**\n{res_text}", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[HỆ THỐNG AUTO GẶP LỖI]:** {res_text}")
            delay_delete(chat_id, msg.message_id, 30)
            
        # Kỹ thuật sleep chunking chia nhỏ 1s giúp ngắt luồng ngay lập tức khi nhấn /stop
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
                username = data.get("username") or data.get("user") or "TikTok User"
                added = data.get("added") or data.get("count") or "Đang tăng..."
            except Exception:
                username = "Hệ thống"
                added = "Đang chạy"

            return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **Tài khoản:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"Server API báo bận (Mã phản hồi {response.status_code})"
    except Timeout: 
        return False, "Yêu cầu kết nối quá hạn thời gian."
    except RequestException: 
        return False, "Lỗi kết nối mạng đến cổng dịch vụ."
    except Exception as e: 
        return False, f"Trục trặc hệ thống không xác định: {str(e)}"


# ========================================================
# KHỞI CHẠY KHÔNG GIAN ĐA LUỒNG HỆ THỐNG AN TOÀN
# ========================================================
if __name__ == "__main__":
    # 1. Kích hoạt luồng tự học độc lập chạy ngầm của Robot
    learning_thread = Thread(target=auto_learning_brain)
    learning_thread.daemon = True
    learning_thread.start()
    
    # 2. Khởi chạy Infinity Polling cho Telegram Bot nhận diện dữ liệu liên tục
    print("🤖 Robot AI Tư Duy Sâu & Tự Học đang hoạt động trên hệ thống...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
