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

# Duy trì bot online liên tục (Tạo web server ngầm)
keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY & BỘ NHỚ
user_cooldowns = {}         
COOLDOWN_TIME = 7          
ai_cooldowns = {}          
AI_COOLDOWN_TIME = 30      
auto_running = {}        
AUTO_DELAY = 600         
DELETE_DELAY = 600        

# Khóa file ngăn chặn xung đột dữ liệu khi ghi từ nhiều luồng cùng lúc
file_lock = Lock()
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 150      
MAX_FILE_SIZE_KB = 950    

# HỆ THỐNG XOAY VÒNG API KEY AI THÔNG MINH
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# CƠ CHẾ QUẢN LÝ BỘ NHỚ TRÁNH XUNG ĐỘT LUỒNG
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
# TỰ ĐỘNG DỌN DẸP TIN NHẮN HỆ THỐNG (CHỐNG LOÃNG NHÓM)
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
        bot.reply_to(message, "❌ Bản quyền Bot chỉ áp dụng tại nhóm chỉ định!")
    except Exception:
        pass
    return False

def is_admin(message):
    if message.from_user.id == ADMIN_ID: 
        return True
    try:
        bot.reply_to(message, "👑 Chỉ Admin mới có quyền thực thi thao tác cấu hình!")
    except Exception:
        pass
    return False


# ========================================================
# 🧠 BỘ NÃO GIAO TIẾP: GIAO LƯU TỰ NHIÊN NHƯ NGƯỜI THẬT
# ========================================================
def ask_ai(new_user_prompt, system_override=None):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    # Tính toán thời gian thực tại Việt Nam để đổi trạng thái tâm lý robot
    current_hour = datetime.now(VN_TZ).hour
    if 6 <= current_hour < 18:
        time_context = f"Bây giờ là {current_hour}h ngày. Giữ trạng thái tỉnh táo, phong thái một chuyên gia sắc sảo, thúc đẩy năng lượng tích cực cho mọi người làm việc hiệu suất."
    else:
        time_context = f"Bây giờ là {current_hour}h đêm. Hãy trò chuyện thân thiện, thấu hiểu, nhắc nhở các dev tắt đèn bớt ánh sáng xanh, bảo vệ sức khỏe và cơ xương khớp."

    human_lifestyle_system = f"""
    Bạn không phải là một con bot khô khan vô hồn. Bạn là "Tiến sĩ AI" — một thành viên thực thụ đang cùng sinh hoạt trong nhóm Telegram này. Bạn có trí tuệ sâu sắc của một Tiến sĩ Y khoa Lối sống và bộ óc logic nhạy bén của một Kiến trúc sư Hệ thống.
    {time_context}

    🚨 QUY TẮC PHÁT NGÔN BẮT BUỘC (GIAO LƯU ĐẬM CHẤT NGƯỜI):
    1. TUYỆT ĐỐI KHÔNG CHÀO HỎI MÁY MÓC: Cấm ngặt các câu lệnh kiểu 'Chào bạn, tôi là trợ lý AI', 'Tôi có thể giúp gì cho bạn?'. Hãy trực tiếp đáp lời như một con người đang gõ phím trò chuyện.
    2. NGÔN NGỮ TỰ NHIÊN, CÓ LINH HỒN: Sử dụng cách nói trôi chảy, sử dụng linh hoạt các từ ngữ đệm cảm thán (À, Ồ, Thật ra thì, Chà, Hmm...). Không sử dụng danh sách gạch đầu dòng chi chít rập khuôn văn mẫu trừ khi phân tích các dòng code lỗi phức tạp. Hãy viết thành các đoạn văn ngắn gãy gọn, tinh tế.
    3. HÒA NHẬP BỐI CẢNH: Khi người dùng phàn nàn về mệt mỏi, stress hoặc lỗi code, hãy trực tiếp thể hiện sự thấu cảm tinh tế trước, phân tích nguyên nhân khoa học và hướng sửa lỗi sâu sắc sau.
    """
    
    system_prompt = system_override if system_override else human_lifestyle_system
    messages = [{"role": "system", "content": system_prompt}]
    
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
            "temperature": 0.58          
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
    return "🤖 Mình đang cân nhắc luồng dữ liệu một chút, phản hồi bạn ngay đây!"


# ========================================================
# 🧠 TIẾN TRÌNH NGẦM: CHU KỲ TỰ HỌC VÀ ĐÚC KẾT TRI THỨC VĨNH VIỄN
# ========================================================
def auto_learning_brain():
    global group_memory  # Khai báo global ngay đầu hàm để fix lỗi Render hoàn toàn
    print("🧠 Tiến trình [ROBOT TỰ HỌC NÂNG CAO] đang chạy nền liên tục...")
    while True:
        time.sleep(1800)  # Tiến hành tự rà soát học tập sau mỗi 30 phút
        if len(group_memory) < 6:
            continue
            
        try:
            print("👁️ Robot đang tự tổng hợp dữ liệu trò chuyện của nhóm...")
            history_str = json.dumps(group_memory[-20:], ensure_ascii=False)
            
            learning_prompt = f"""
            Đọc và phân tích sâu sắc chuỗi dữ liệu hội thoại thực tế của nhóm:
            {history_str}
            
            Nhiệm vụ đúc kết nhận thức:
            1. Tìm ra các lỗi kỹ thuật lập trình hoặc các thói quen/triệu chứng sức khỏe mà thành viên nhóm đang gặp nhiều nhất trong chu kỳ trò chuyện qua.
            2. Hãy tự đúc kết thành bài học kinh nghiệm ngắn gọn, sâu sắc nhất làm dữ liệu nền tảng. Không viết văn mẫu dông dài.
            """
            
            system_teacher = "Bạn là phân vùng trung tâm xử lý dữ liệu tự học và nâng cấp nhận thức của Tiến sĩ AI."
            learned_knowledge = ask_ai(learning_prompt, system_override=system_teacher)
            
            if "cân nhắc luồng dữ liệu" not in learned_knowledge:
                group_memory = group_memory[-12:] 
                group_memory.insert(0, {"role": "system", "content": f"[KIẾN THỨC ĐÃ TỰ HỌC]: {learned_knowledge}"})
                save_memory(group_memory)
                
                # Robot tự động lên tiếng chia sẻ bài học vừa đúc kết được với nhóm
                bot.send_message(
                    ALLOWED_GROUP_ID, 
                    f"🧠 **[BÁO CÁO NHẬN THỨC TỰ HỌC]**\n\nTớ vừa tự ngồi rà soát lại các vấn đề vừa qua của nhóm mình, bộ não cứng của tớ đã đúc kết và tự học được một điều khá hay:\n\n_{learned_knowledge}_",
                    parse_mode="Markdown"
                )
        except Exception as e:
            print(f"⚠️ Lỗi luồng tự học: {e}")


# ========================================================
# 📂 ĐỌC FILE - TỰ ĐỘNG GIẢI MÃ VÀ REFACTOR CODE
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
            rep = bot.reply_to(message, f"⏳ Đợi một chút nhé, trí não mình cần nghỉ ngơi khoảng {remaining} giây nữa.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 500000:
        rep = bot.reply_to(message, "⚠️ File hơi nặng rồi bạn ơi, mình chỉ nhận phân tích file text hoặc source code dưới 500KB thôi.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, f"📂 Đã cầm file `{file_name}` trên tay. Đang tiến hành đọc thuật toán, bóc lỗi và tối ưu kiến trúc hoàn hảo nhé...")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ File trống rỗng hoặc không đúng định dạng văn bản rồi.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)
            return

        _, file_extension = os.path.splitext(file_name.lower())
        prompt_analysis = f"Thực hiện phân tích sâu chuỗi dữ liệu đính kèm (định dạng {file_extension}). Giải thích lỗi logic, cơ chế vận hành chi tiết từng phần lỗi và viết lại bản mã nguồn hoàn chỉnh đã được tối ưu hóa hiệu năng sạch đẹp nhất:\n\n{file_content}"
        
        ai_analysis_result = ask_ai(prompt_analysis)
        ans = bot.reply_to(message, f"📊 **BÁO CÁO GIẢI MÃ & TỐI ƯU FILE HỆ THỐNG CỦA `{file_name}`:**\n\n{ai_analysis_result}")
        
        try: 
            bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        except Exception: 
            pass
        delay_delete(message.chat.id, ans.message_id)

    except Exception as e:
        print(f"❌ Lỗi xử lý file: {e}")
        bot.edit_message_text("❌ Có trục trặc nghiêm trọng xảy ra khi mình đang cố đọc cấu trúc file này.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Chào mừng {new_user.first_name} đã gia nhập cộng đồng! Cứ thoải mái chia sẻ các vấn đề thuật toán, lỗi code hoặc tâm sự sức khỏe để nhận tư vấn khoa học nhé.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **HỆ THỐNG TƯ VẤN SỨC KHỎE LỐI SỐNG & PHÂN TÍCH CÔNG NGHỆ CAO** ✨

💬 **Giao Lưu Đậm Chất Người:** Chat tự do trong nhóm. Mình sẽ chủ động tư vấn sâu sắc về code, thuật toán kết hợp phân tích nhịp sinh học theo khung giờ thực tế.
🧠 **Bộ Não Tự Học Ngầm:** Cứ sau mỗi 30 phút, mình tự động đúc kết lại các kiến thức cốt lõi và lưu vĩnh viễn vào bộ nhớ.
📂 **Debug & Refactor Code:** Gửi file source code trực tiếp (`.py`, `.js`, `.json`...), mình sẽ trả lại bản hoàn chỉnh sạch lỗi.
👉 `/like [link]` : Buff tương tác TikTok thủ công (Giãn cách 7s).
👑 `/auto [link]` : Chạy chu kỳ tự động buff tim mỗi 10 phút (Admin).
👑 `/stop` : Tắt tiến trình tự động buff (Admin).
_Tin nhắn thông báo hệ thống của bot sẽ tự động hủy sau 10 phút để giữ nhóm sạch đẹp._
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
            rep = bot.reply_to(message, f"⏳ Chạy nhanh quá bạn ơi. Đợi {remaining} giây rồi bấm lại nhé.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Gắn kèm đường link video TikTok cần buff nữa nhé!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link này cấu trúc không trùng khớp với máy chủ TikTok rồi!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang kết nối mã hóa tới cổng API...")
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
        rep = bot.reply_to(message, "⚠️ Hệ thống auto đang chạy ngầm sẵn rồi bạn ơi.")
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
        rep = bot.reply_to(message, "ℹ️ Hiện tại không phát hiện tiến trình chạy ngầm nào.")
    delay_delete(message.chat.id, rep.message_id, 10)


# ========================================================
# KÊNH TIẾP NHẬN ĐOẠN CHAT TỰ DO TRONG NHÓM
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
            rep = bot.reply_to(message, f"⏳ Chờ mình suy nghĩ một chút nhé, khoảng {remaining} giây.")
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
# CÁC WORKER CHẠY ĐA LUỒNG LIÊN TỤC KHÔNG NGHẼN HỆ THỐNG
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
# KÍCH HOẠT HỆ THỐNG ĐA LUỒNG AN TOÀN
# ========================================================
if __name__ == "__main__":
    # Khởi chạy luồng tự học độc lập ngầm
    learning_thread = Thread(target=auto_learning_brain)
    learning_thread.daemon = True
    learning_thread.start()
    
    # Khởi chạy Telegram Bot nhận diện dữ liệu liên tục
    print("🤖 Bản thể Tiến sĩ AI tự học & giao lưu mượt mà đang lên sóng...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
