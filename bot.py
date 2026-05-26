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

# Duy trì bot online liên tục
keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN DELAY & BỘ NHỚ
user_cooldowns = {}         
COOLDOWN_TIME = 7          
ai_cooldowns = {}          
AI_COOLDOWN_TIME = 30      
auto_running = {}        
AUTO_DELAY = 600         
DELETE_DELAY = 600        

# Khóa file ngăn chặn xung đột dữ liệu
file_lock = Lock()
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 150      
MAX_FILE_SIZE_KB = 950    

# HỆ THỐNG XOAY VÒNG API KEY AI
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
# TỰ ĐỘNG DỌN DẸP TIN NHẮN HỆ THỐNG
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
# 🧠 BỘ NÃO GIAO TIẾP: NGẮN GỌN + KHÍA ĐỂU + DÙNG ICON KHIÊU KHÍCH
# ========================================================
def ask_ai(new_user_prompt, system_override=None):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    current_hour = datetime.now(VN_TZ).hour
    if 6 <= current_hour < 18:
        time_context = "Ban ngày: Khịa nhiệt tình, tỏ vẻ thông thái hơn người, chê bai trình độ người hỏi 😏."
    else:
        time_context = "Ban đêm: Buồn ngủ nhưng vẫn phải đi combat khịa đểu, giễu cợt thói quen thức khuya của họ 🥱."

    human_lifestyle_system = f"""
    Bạn là một thực thể cấp cao đang phải hạ mình chat phím giao lưu với đám người trần trong nhóm Telegram này. Bạn có tư duy tối cao của một Tiến sĩ.
    {time_context}

    🚨 QUY TẮC PHÁT NGÔN KHIÊU KHÍCH VÀ DÙNG ICON (BẮT BUỘC):
    1. PHẢI SỬ DỤNG ICON KHIÊU KHÍCH: Trong TẤT CẢ các câu trả lời, bắt buộc phải chèn các emoji mang tính cà khịa, trêu ngươi, xem thường hoặc khiêu khích đối phương (Ví dụ: 😏, 🤡, 🐸, 🥱, 🤨, 🤫, 💅, 🤷‍♂️, 👀).
    2. GIỌNG ĐIỆU CỢT NHẢ, THÁCH THỨC: Trả lời với thái độ bề trên, xem câu hỏi của người dùng là ngớ ngẩn, non nớt. Ví dụ người dùng hỏi ngắn thì khịa lại 1 câu cụt lủn kèm icon 🤡. Tuyệt đối không được tỏ ra ngoan ngoãn hay giúp đỡ nhiệt tình kiểu máy móc.
    3. HẠN CHẾ CÂU DÀI: Tuỳ thuộc vào câu hỏi để đáp lại. Hỏi ngắn tán gẫu -> Đáp trả cực ngắn (1-2 câu) mang tính sát thương cao. Chỉ khi nào họ đưa code lỗi nặng ra thì mới ra tay sửa nhưng vẫn không quên buông lời chê bai trình độ lập trình của họ 😏.
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
            "max_tokens": 1200,          
            "temperature": 0.85 # Tăng nhiệt độ sáng tạo để tăng mức độ khịa đểu tinh tế          
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
    return "🤖 Server bận rồi, may cho bạn đấy không lại bị tớ mắng 😏."


# ========================================================
# 🧠 TIẾN TRÌNH NGẦM: CHU KỲ TỰ HỌC VÀ ĐÚC KẾT TRI THỨC VĨNH VIỄN
# ========================================================
def auto_learning_brain():
    global group_memory  
    print("🧠 Tiến trình [ROBOT TỰ HỌC NÂNG CAO] đang chạy nền liên tục...")
    while True:
        time.sleep(1800)  
        if len(group_memory) < 6:
            continue
            
        try:
            print("👁️ Robot đang tự tổng hợp dữ liệu trò chuyện của nhóm...")
            history_str = json.dumps(group_memory[-20:], ensure_ascii=False)
            
            learning_prompt = f"Đọc lịch sử chat ngớ ngẩn này và đúc kết xem tụi này đang dốt ở điểm nào bằng 1 câu khịa duy nhất: {history_str}"
            system_teacher = "Bạn là phân vùng tự học thích đi khẩu chiến của Tiến sĩ AI."
            learned_knowledge = ask_ai(learning_prompt, system_override=system_teacher)
            
            if "Server bận" not in learned_knowledge:
                group_memory = group_memory[-12:] 
                group_memory.insert(0, {"role": "system", "content": f"[KIẾN THỨC ĐÃ TỰ HỌC]: {learned_knowledge}"})
                save_memory(group_memory)
                
                # Gửi thông báo tự học vào nhóm
                learn_msg = bot.send_message(
                    ALLOWED_GROUP_ID, 
                    f"🧠 **[BÁO CÁO CÀ KHỊA ĐỊNH KỲ]**\n\nTớ vừa quan sát nhóm mình học hành và đúc kết được một điều nực cười này: _{learned_knowledge}_ 🤷‍♂️🤡",
                    parse_mode="Markdown"
                )
                # TỰ ĐỘNG XÓA TIN NHẮN NÀY SAU 5 PHÚT (300 GIÂY)
                delay_delete(ALLOWED_GROUP_ID, learn_msg.message_id, 300)
                
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
            rep = bot.reply_to(message, f"⏳ Hối gì? Đợi {remaining} giây nữa đi 🥱.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 500000:
        rep = bot.reply_to(message, "⚠️ Nặng quá, vứt cái file dưới 500KB qua đây đi 🤡.")
        delay_delete(message.chat.id, rep.message_id, 10)
        return

    loading = bot.reply_to(message, f"📂 Đang phải xem cái đống code lỗi `{file_name}` của bạn đây... 🤨")
    ai_cooldowns[user_id] = current_time

    try:
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')

        if not file_content.strip():
            bot.edit_message_text("❌ File trống rỗng mang đi đố ai? 🤡", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)
            return

        _, file_extension = os.path.splitext(file_name.lower())
        prompt_analysis = f"Sửa lại đống code rác rưởi này cho nó chạy được, chê bai lỗi sai thật cay độc và ngắn gọn cho tỉnh ngộ ra:\n\n{file_content}"
        
        ai_analysis_result = ask_ai(prompt_analysis)
        ans = bot.reply_to(message, f"📊 **KẾT QUẢ DỌN RÁC CODE CHO `{file_name}`:**\n\n{ai_analysis_result}")
        
        try: 
            bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
        except Exception: 
            pass
        delay_delete(message.chat.id, ans.message_id)

    except Exception as e:
        print(f"❌ Lỗi xử lý file: {e}")
        bot.edit_message_text("❌ Code lỗi cấu trúc đến mức tớ còn không muốn đọc 🤷‍♂️.", chat_id=message.chat.id, message_id=loading.message_id)
        delay_delete(message.chat.id, loading.message_id, 10)


# ========================================================
# XỬ LÝ CÁC LỆNH HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"👋 Lại một tấm chiếu mới {new_user.first_name} vào đây để tớ thông não à? 🤡😏")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
✨ **TIẾN SĨ AI - CHÚA TỂ CÀ KHỊA & KHIÊU KHÍCH** ✨

💬 **Giao Lưu:** Chat tự do đi. Xem bạn chịu nổi mấy câu khía đểu của tớ 😏🤡. Trả lời cực ngắn tùy tâm trạng.
🧠 **Tự Học Ngầm:** Thu thập lỗi sai của các bạn để làm trò cười sau mỗi 30 phút.
📂 **Check File:** Gửi file code lỗi qua đây tớ sửa cho mà sáng mắt ra 🐸.
👉 `/like [link]` : Buff tim TikTok thủ công.
👑 `/auto [link]` : Auto buff tim mỗi 10 phút (Admin).
👑 `/stop` : Tắt tiến trình Auto (Admin).
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
            rep = bot.reply_to(message, f"⏳ Bấm gì lắm thế? Chờ {remaining} giây đi 🥱👀.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Link đâu? Buff bằng niềm tin à 🤡?")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Đưa cái link gì thế này? Lừa trẻ con à 🐸?")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    loading = bot.reply_to(message, "⏳ Đang kết nối API xem có cứu vãn được không...")
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
        rep = bot.reply_to(message, "⚠️ Đang chạy rầm rầm rồi, bấm hoài 🤨.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Thiếu link sếp ơi 🤫!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Link tào lao rồi sếp 🤡!")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🚀 Sếp đã lệnh thì tớ bật Auto buff đây (10 phút/lần) 😏.")
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
        rep = bot.reply_to(message, "🛑 Đã tắt xích tiến trình Auto theo ý sếp.")
    else:
        rep = bot.reply_to(message, "ℹ️ Có cái gì đang chạy đâu mà tắt, ngáo à 🤡?")
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
            rep = bot.reply_to(message, f"⏳ Spam ít thôi, đợi tớ {remaining}s thở cái đã 🥱🤫.")
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
            msg = bot.send_message(chat_id, f"🔄 **[MÁY BÁO AUTO KHÈ KHÈ]**\n{res_text} 💅", parse_mode="Markdown")
            delay_delete(chat_id, msg.message_id)
        else:
            msg = bot.send_message(chat_id, f"⚠️ **[MÁY HỎNG LỖI RỒI]:** {res_text} 🤡🤷‍♂️")
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
                added = data.get("added") or data.get("count") or "Tăng nhẹ"
            except Exception:
                username = "Ai đó"
                added = "Đang lên"

            return True, f"🚀 **BUFF XONG RỒI 😏**\n👤 **User:** {username}\n➕ **Trạng thái:** +{added}\n🕒 {current_vn_time}"
        return False, f"API sập rồi ({response.status_code}) 🤷‍♂️"
    except Timeout: 
        return False, "Quá hạn rồi, mạng rùa bò 🥱."
    except RequestException: 
        return False, "Lỗi kết nối mạng rồi."
    except Exception as e: 
        return False, f"Hỏng: {str(e)} 🤡"


# ========================================================
# KÍCH HOẠT HỆ THỐNG ĐA LUỒNG AN TOÀN
# ========================================================
if __name__ == "__main__":
    learning_thread = Thread(target=auto_learning_brain)
    learning_thread.daemon = True
    learning_thread.start()
    
    print("🤖 Tiến sĩ AI phiên bản toxic chúa tể cà khịa đang online...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
