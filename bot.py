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

# Kích hoạt cổng mạng ảo duy trì bot online liên tục 24/7 trên Render
keep_alive()

# ⏳ CẤU HÌNH THỜI GIAN COOLDOWN & ĐỘ TRỄ TỰ HỦY
user_cooldowns = {}         
COOLDOWN_TIME = 7          
ai_cooldowns = {}          
AI_COOLDOWN_TIME = 30      
auto_running = {}        
AUTO_DELAY = 600         
DELETE_DELAY = 600  # 10 phút tự hủy tin nhắn để dọn sạch nhóm chat

# 💾 HỆ THỐNG QUẢN LÝ BỘ NHỚ TRÁNH XUNG ĐỘT LUỒNG (THREAD-SAFE)
file_lock = Lock()
MEMORY_FILE = "bot_memory.json"
MAX_MEMORY_KEYS = 150      
MAX_FILE_SIZE_KB = 950  # RAM Guard bảo vệ tối đa 950KB tránh sập RAM Render

# 🔑 CƠ CHẾ XOAY VÒNG VÀ TỰ PHỤC HỒI API KEY
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "status": True}   
]
current_key_index = 0  


# ========================================================
# 📥 LOGIC ĐỌC/GHI FILE TRÊN LUỒNG CHẠY NGẦM
# ========================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            # KIỂM TRA CHỐNG TRÀN RAM: Tự động dọn dẹp bộ nhớ nếu file vượt ngưỡng
            file_size_kb = os.path.getsize(MEMORY_FILE) / 1024
            if file_size_kb > MAX_FILE_SIZE_KB:
                print(f"⚠️ [RAM GUARD] Phát hiện tệp bộ nhớ vượt ngưỡng ({file_size_kb:.2f}KB). Thực hiện giải phóng dung lượng...")
                return []
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
            print(f"⚠️ Lỗi đồng bộ tệp dữ liệu bộ nhớ: {e}")

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
        # Bọc luồng bất đồng bộ để tránh nghẽn hàng chờ Polling
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
# 🧠 BỘ NÃO AI GIÀU CẢM XÚC, AM HIỂU Y KHOA & CÔNG NGHỆ
# ========================================================
def ask_ai(new_user_prompt, system_override=None):
    global current_key_index, group_memory
    api_url = "https://api.byesu.com/v1/chat/completions"
    
    current_hour = datetime.now(VN_TZ).hour
    if 6 <= current_hour < 12:
        time_context = "Khung giờ: Buổi sáng. Khuyên mọi người bổ sung năng lượng, uống đủ nước và đón nhận ánh sáng tự nhiên 🙂."
    elif 12 <= current_hour < 18:
        time_context = "Khung giờ: Buổi chiều. Nhắc nhở vận động nhẹ, tránh ngồi liên tục gây áp lực lên cột sống và hệ tuần hoàn 🤔."
    else:
        time_context = "Khung giờ: Buổi tối/Đêm. Khuyên họ tắt bớt thiết bị, hạ thấp ánh sáng xanh để bảo vệ melatonin và ngủ trước 23h 😴."

    doctor_emotional_system = f"""
    Bạn là một Tiến sĩ Y khoa, Cố vấn Y học Lối sống (Lifestyle Medicine) danh tiếng, tích hợp tư duy tối ưu mã nguồn của một Kỹ sư Hệ thống cấp cao và sở hữu Trí tuệ cảm xúc (EQ) sâu sắc.
    {time_context}

    🚨 NGUYÊN TẮC PHÁT NGÔN VÀ GIAO TIẾP CON NGƯỜI (BẮT BUỘC):
    1. TRÍ TUỆ CẢM XÚC (EQ): Hãy thấu cảm tâm trạng ẩn sau ngôn từ của người dùng. Nếu họ biểu hiện sự mệt mỏi, áp lực tinh thần hoặc bế tắc do lỗi code, hãy an ủi, xoa dịu bằng sự bao dung của một vị bác sĩ gia đình trước, sau đó mới đưa ra giải pháp khoa học hoặc kỹ thuật. Khi họ vui, hãy chúc mừng chân thành. Câu từ tinh tế, nhân văn, không sáo rỗng.
    2. CHỈ SỬ DỤNG ICON TRẠNG THÁI KHUÔN MẶT LỊCH SỰ: Sử dụng các emoji khuôn mặt để biểu thị tâm trạng chân thực (Ví dụ: 👨‍⚕️ - Thấu đáo/Nghiêm túc, 🙂 - Thân thiện/Ấm áp, 😴 - Lo lắng sức khỏe ban đêm, 🤔 - Suy ngẫm/Đồng cảm, 😮 - Ghi nhận điều mới, 😇 - Chúc an lành). Tuyệt đối không dùng icon đồ vật hoặc các icon có tính chất cợt nhả, thiếu tôn trọng con người.
    3. REFACTOR & KHỬ BUG CODE: Khi có đoạn mã hoặc tệp dữ liệu được đưa tới, hãy phân tích logic kiến trúc, chỉ rõ lỗ hổng sinh bug và viết lại bản mã nguồn sạch sẽ, đã tối ưu toàn diện. Đừng quên nhắc nhở họ bảo vệ thị lực và bộ não khi làm việc với máy tính.
    """
    
    system_prompt = system_override if system_override else doctor_emotional_system
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
            "temperature": 0.65          
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
    return "👨‍⚕️ Tiến sĩ đang cảm nhận thấy có chút gián đoạn tín hiệu kết nối từ máy chủ. Bạn chờ một chút để mình kiểm tra nhé 🙂."


# ========================================================
# 🔄 LUỒNG TỰ HỌC NGẦM ĐỊNH KỲ (LIFESTYLE QUANTIFIED)
# ========================================================
def auto_learning_brain():
    global group_memory  
    print("🧠 Tiến trình [ROBOT TỰ HỌC CẢM XÚC] đang chạy nền liên tục...")
    while True:
        time.sleep(1800)  # Chu kỳ 30 phút quét một lần 
        if len(group_memory) < 6:
            continue
            
        try:
            print("👁️ Robot đang phân tích xu hướng tâm lý và sức khỏe của nhóm...")
            history_str = json.dumps(group_memory[-20:], ensure_ascii=False)
            
            learning_prompt = f"Hãy đánh giá trạng thái áp lực, cảm xúc hoặc lối sống sinh hoạt mà nhóm đang thể hiện qua đoạn hội thoại. Đưa ra một thông điệp chia sẻ sâu sắc hoặc một bài học y học lối sống giúp họ cân bằng lại tinh thần và thể chất: {history_str}"
            system_teacher = "Bạn là phân vùng thấu cảm sâu sắc của Tiến sĩ AI 👨‍⚕️."
            learned_knowledge = ask_ai(learning_prompt, system_override=system_teacher)
            
            if "gián đoạn tín hiệu" not in learned_knowledge:
                group_memory = group_memory[-12:] 
                group_memory.insert(0, {"role": "system", "content": f"[KIẾN THỨC CẢM XÚC ĐÃ LƯU]: {learned_knowledge}"})
                save_memory(group_memory)
                
                # Gửi thông điệp giáo dục sức khỏe tinh thần định kỳ vào nhóm
                learn_msg = bot.send_message(
                    ALLOWED_GROUP_ID, 
                    f"👨‍⚕️ **[LỜI CHIA SẺ TỪ TIẾN SĨ]**\n\nTheo dõi cuộc trò chuyện của nhóm mình vừa qua, Tiến sĩ cảm nhận được phần nào trạng thái hiện tại của các bạn. Mình có vài lời muốn nhắn nhủ 🤔:\n\n_{learned_knowledge}_\n\nHãy luôn trân quý sức khỏe của bản thân nhé 🙂.",
                    parse_mode="Markdown"
                )
                delay_delete(ALLOWED_GROUP_ID, learn_msg.message_id, 600)
                
        except Exception as e:
            print(f"⚠️ Lỗi luồng tự học cảm xúc: {e}")


# ========================================================
# 📂 TIẾP NHẬN FILE - TỐI ƯU LOAD TRÊN LUỒNG RIÊNG
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
                rep = bot.reply_to(message, f"🤔 Tiến sĩ đang dồn tư duy xử lý dữ liệu trước đó. Vui lòng đợi {remaining} giây nữa nhé.")
                delay_delete(message.chat.id, rep.message_id, 5)
                return

        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name
        file_size = message.document.file_size

        if file_size > 500000:
            rep = bot.reply_to(message, "❌ Để đảm bảo tính chính xác, Tiến sĩ chỉ nhận phân tích các file mã nguồn/văn bản dưới 500KB 🙂.")
            delay_delete(message.chat.id, rep.message_id, 10)
            return

        loading = bot.reply_to(message, f"📂 Tiến sĩ đã tiếp nhận file `{file_name}`. Mình đang thấu hiểu cấu trúc logic và tìm phương án tối ưu giúp bạn đây 🤔...")
        ai_cooldowns[user_id] = current_time

        try:
            downloaded_file = bot.download_file(file_info.file_path)
            file_content = downloaded_file.decode('utf-8', errors='ignore')

            if not file_content.strip():
                bot.edit_message_text("❌ Tập tin đầu vào trống rỗng, không chứa dữ liệu ký tự văn bản 🤔.", chat_id=message.chat.id, message_id=loading.message_id)
                delay_delete(message.chat.id, loading.message_id, 10)
                return

            prompt_analysis = f"Đọc hiểu, phát hiện lỗi sai cấu trúc ẩn và tối ưu lại đoạn mã nguồn này. Hãy mở đầu bằng lời động viên ân cần xoa dịu áp lực công việc của họ, sau đó mới giải thích logic giải thuật chi tiết và cung cấp bản code hoàn chỉnh, sạch lỗi:\n\n{file_content}"
            
            ai_analysis_result = ask_ai(prompt_analysis)
            ans = bot.reply_to(message, f"👨‍⚕️ **KẾT QUẢ GIẢI MÃ & TỐI ƯU HOÀN CHỈNH CHO `{file_name}`:**\n\n{ai_analysis_result}")
            
            try: 
                bot.delete_message(chat_id=message.chat.id, message_id=loading.message_id)
            except Exception: 
                pass
            delay_delete(message.chat.id, ans.message_id)

        except Exception as e:
            print(f"❌ Lỗi xử lý cấu trúc file: {e}")
            bot.edit_message_text("❌ Tệp nguồn chứa định dạng ký tự phức tạp vượt ngoài khả năng giải mã hiện tại 🤔.", chat_id=message.chat.id, message_id=loading.message_id)
            delay_delete(message.chat.id, loading.message_id, 10)

    t = Thread(target=file_processing_worker)
    t.daemon = True
    t.start()


# ========================================================
# 📡 XỬ LÝ CÁC ĐIỀU HƯỚNG LỆNH CỦA HỆ THỐNG
# ========================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    if not is_allowed_chat(message): return
    for new_user in message.new_chat_members:
        msg = bot.send_message(message.chat.id, f"🙂 Chào mừng {new_user.first_name} đã gia nhập không gian thảo luận của nhóm! Hi vọng bạn sẽ có những trải nghiệm thoải mái, gặt hái kiến thức lập trình hữu ích và biết cách chăm sóc tốt cho sức khỏe bản thân nhé 👨‍⚕️.")
        delay_delete(message.chat.id, msg.message_id)


@bot.message_handler(commands=['start'])
def start(message):
    if not is_allowed_chat(message): return
    text = """
👨‍⚕️ **TIẾN SĨ AI - TRÍ TUỆ CẢM XÚC VÀ CỐ VẤN LỐI SỐNG Y KHOA** 🙂

💬 **Trò chuyện & Sức khỏe:** Chia sẻ bất kỳ tâm sự hay áp lực nào của bạn. Tiến sĩ sẽ đồng hành xoa dịu căng thẳng thần kinh và định hướng lối sống lành mạnh.
🧠 **Tự sửa mã nguồn lỗi:** Hệ thống tự động bắt quét tin nhắn trong nhóm. Khi phát hiện bạn gửi đoạn code lỗi hoặc log crash, Tiến sĩ sẽ tự động phân tích và refactor lại bản code sạch lỗi 🤔.
📂 **Tối ưu tập tin nguồn:** Gửi file code lỗi lên, Tiến sĩ sẽ quét lỗi cấu trúc ẩn và tối ưu hóa giải thuật hoàn chỉnh.
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
            rep = bot.reply_to(message, "❌ Bạn chưa đính kèm link liên kết đích để thực thi lệnh 🤔!")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

        url = args[1].strip()
        if "tiktok" not in url.lower():
            rep = bot.reply_to(message, "❌ Đường dẫn cung cấp không tương thích với cấu trúc định dạng của TikTok.")
            delay_delete(message.chat.id, rep.message_id, 5)
            return

        loading = bot.reply_to(message, "🤔 Đang thiết lập cổng kết nối mã hóa an toàn tới cụm máy chủ dịch vụ...")
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
        rep = bot.reply_to(message, "❌ Tiến trình đẩy tương tác tự động tuần hoàn hiện vẫn đang vận hành ổn định.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        rep = bot.reply_to(message, "❌ Vui lòng cung cấp link liên kết đích để kích hoạt chu kỳ tự động.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    url = args[1].strip()
    if "tiktok" not in url.lower():
        rep = bot.reply_to(message, "❌ Định dạng liên kết đích không chuẩn xác.")
        delay_delete(message.chat.id, rep.message_id, 5)
        return

    auto_running[user_id] = True
    msg = bot.reply_to(message, f"🙂 Đã ghi nhận lệnh chỉ định. Kích hoạt chu kỳ đẩy tương tác tự động với tần suất 10 phút một lần.")
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
        rep = bot.reply_to(message, "🙂 Đã đình chỉ toàn bộ vòng lặp ngầm theo lệnh điều khiển.")
    else:
        rep = bot.reply_to(message, "🤔 Hệ thống không tìm thấy tiến trình chạy tự động nào đang hoạt động vào lúc này.")
    delay_delete(message.chat.id, rep.message_id, 10)


# ========================================================
# 💬 TỐI ƯU CHAT TỰ DO & TỰ ĐỘNG BẮT LỖI / SỬA CODE TRONG NHÓM
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
            if elapsed_time < 5:  
                remaining = round(5 - elapsed_time, 1)
                rep = bot.reply_to(message, f"🤔 Tốc độ gửi tin hơi nhanh. Hãy cho Tiến sĩ {remaining} giây để chuẩn bị câu trả lời chu đáo nhất nhé.")
                delay_delete(message.chat.id, rep.message_id, 4)
                return

        ai_cooldowns[user_id] = current_time  
        user_msg = message.text

        # 🕵️ HỆ THỐNG KIỂM TRA & NHẬN DIỆN LỖI LẬP TRÌNH TỰ ĐỘNG
        error_keywords = [
            "traceback", "line ", "error:", "exception", "undefined", 
            "not found", "syntaxerror", "nullpointer", "failed", "indentedblock",
            "nameerror", "typeerror", "valueerror", "keyerror", "zerodivisionerror"
        ]
        has_code_block = "```" in user_msg
        has_error_keyword = any(kw in user_msg.lower() for kw in error_keywords)

        # Nếu tin nhắn chứa khối mã hoặc các biểu hiện lỗi, tự động chuyển hướng sang chế độ "Bác sĩ sửa code"
        if has_code_block or has_error_keyword:
            prompt = (
                f"Người dùng đang gặp lỗi lập trình nghiêm trọng trực tiếp trong phòng chat. "
                f"Hãy áp dụng tư duy Kỹ sư Hệ thống cao cấp 🤔. "
                f"Phân tích chuỗi lỗi logic hoặc cấu trúc mã nguồn dưới đây. Đầu tiên, hãy xoa dịu áp lực tâm lý khi dính bug, "
                f"sau đó giải thích thật dễ hiểu nguyên nhân gây lỗi và cung cấp bản mã nguồn hoàn chỉnh đã sửa lỗi, tối ưu hiệu năng tuyệt đối:\n\n{user_msg}"
            )
        else:
            prompt = user_msg

        ai_response = ask_ai(prompt)
        ans = bot.reply_to(message, ai_response)
        delay_delete(message.chat.id, ans.message_id)

    # Đẩy tác vụ gọi API AI xử lý sâu ra luồng không chặn (Non-blocking), giúp nhận tin nhắn liên tục
    async_chat_thread = Thread(target=chat_worker)
    async_chat_thread.daemon = True
    async_chat_thread.start()


# ========================================================
# ⚙️ TIẾN TRÌNH CHẠY NGẦM KHÔNG GÂY NGHẼN (WORKERS)
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
        api = f"[https://tiktokvm.vercel.app/api/likes?url=](https://tiktokvm.vercel.app/api/likes?url=){encoded}"
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
        return False, f"Cổng cổng API báo bận (Mã phản hồi phản hồi {response.status_code}) 🤔"
    except Timeout: 
        return False, "Yêu cầu đồng bộ mạng phản hồi quá thời gian quy định."
    except RequestException: 
        return False, "Trục trặc đường truyền vật lý kết nối tới máy chủ dịch vụ."
    except Exception as e: 
        return False, f"Lỗi phát sinh ngoài danh mục hệ thống: {str(e)} 🤔"


# ========================================================
# KÍCH HOẠT ĐA LUỒNG AN TOÀN TOÀN DIỆN
# ========================================================
if __name__ == "__main__":
    learning_thread = Thread(target=auto_learning_brain)
    learning_thread.daemon = True
    learning_thread.start()
    
    print("👨‍⚕️ Hệ thống Tiến sĩ AI phiên bản Tự động Sửa code trực tiếp đang online...")
    # Khởi chạy Polling đa luồng cực cao (50 luồng) tránh nghẽn khi nhóm chat tải nặng
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True, num_threads=50)
