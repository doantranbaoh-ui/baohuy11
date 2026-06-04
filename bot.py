# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz, random, re, html
from threading import Thread, Lock
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAGtAejJsqZ8pYKEgcZn-lS198t4eTPej2I"
ALLOWED_GROUP_ID, ADMIN_ID = -1003872001041, 5736655322              

bot = telebot.TeleBot(TOKEN, num_threads=15)  
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()

BOT_INFO = bot.get_me() 
BOT_USERNAME = f"@{BOT_INFO.username}"

http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=2)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 60
MEMORY_FILE, ACTIVE_USERS_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", "active_users.json", 25, 500
memory_lock = Lock()      
users_lock = Lock()

TIKTOK_LINK_PATTERN = re.compile(r'https?://(?:vm|vt|www)\.tiktok\.com/\S+', re.IGNORECASE)

TELE_LINK_PATTERN = re.compile(
    r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}'
    r'|@[a-zA-Z0-9_]{5,}'
    r'|t\.me\/[a-zA-Z0-9_]{5,}', 
    re.IGNORECASE
)

AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True}  
]
current_key_index = 0  

# Kho thính ngọt ngào của em gái 18 tuổi
KHO_THINH = [
    "Trời đổ mưa rồi, sao anh chưa đổ em?",
    "Anh ơi, anh có ngửi thấy mùi gì cháy không? Mùi tim em đang cháy vì anh đấy!",
    "Người ta thích gọi anh là chồng, còn em thì thích gọi anh là của em.",
    "Anh có biết bơi không? Sao cứ chìm đắm trong tâm trí em hoài thế?",
    "Trăng dưới nước là trăng trên trời, người trước mặt là người trong tim em.",
    "Muốn bình yên thì lên chùa cầu phúc, muốn hạnh phúc thì đứng đó đợi em.",
    "Em không thích xem mười vạn câu hỏi vì sao xíu nào, em chỉ thích câu trả lời vì sao yêu anh thôi.",
    "Mọi người cứ bảo em 18 tuổi ngây ngô, nhưng em thừa biết là em thích anh rồi.",
    "Số điện thoại của em chưa có ai gọi, anh có muốn làm người đầu tiên không?",
    "Hôm nay trời xanh mây trắng, anh có muốn cùng em viết nên câu chuyện tình?"
]

def load_memory():
    if os.path.exists(MEMORY_FILE) and (os.path.getsize(MEMORY_FILE) / 1024) <= MAX_FILE_SIZE_KB:
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: 
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: pass
    return []

def save_memory(memory_data):
    global group_memory
    with memory_lock:
        try:
            group_memory = memory_data[-MAX_MEMORY_KEYS:]
            with open(MEMORY_FILE, "w", encoding="utf-8") as f: 
                json.dump(group_memory, f, ensure_ascii=False, indent=4)
        except: pass

group_memory = load_memory()

# Hàm quản lý danh sách lưu người dùng hoạt động để tag ngẫu nhiên
def save_active_user(user_id, first_name):
    if user_id == BOT_INFO.id: return
    with users_lock:
        try:
            users_data = {}
            if os.path.exists(ACTIVE_USERS_FILE):
                with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
                    users_data = json.load(f)
            users_data[str(user_id)] = first_name
            with open(ACTIVE_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users_data, f, ensure_ascii=False, indent=4)
        except: pass

def get_random_user():
    with users_lock:
        try:
            if os.path.exists(ACTIVE_USERS_FILE):
                with open(ACTIVE_USERS_FILE, "r", encoding="utf-8") as f:
                    users_data = json.load(f)
                if users_data:
                    u_id, u_name = random.choice(list(users_data.items()))
                    return u_id, u_name
        except: pass
    return None, None

def delay_delete(chat_id, message_id, delay=DELETE_DELAY):
    def del_w():
        time.sleep(delay)
        try: bot.delete_message(chat_id, message_id)
        except: pass
    Thread(target=del_w, daemon=True).start()

def is_allowed_chat(m):
    if m.chat.id == ALLOWED_GROUP_ID: return True
    try: bot.reply_to(m, "Yêu cầu không hợp lệ nè.", parse_mode="HTML")
    except: pass
    return False

def is_admin(m):
    return m.from_user.id == ADMIN_ID

def clean_dynamic_text(text):
    clean_text = re.sub(r'\*.*?\*', '', text)
    clean_text = re.sub(r'[_*`\[\]()]', '', clean_text)
    return clean_text.strip()

def check_and_delete_tele_link(m):
    if is_admin(m): return False
    text_to_check = (m.text or "") + (m.caption or "")
    
    if TELE_LINK_PATTERN.search(text_to_check):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn_msg = ask_ai("Phát hiện link rác quảng cáo bẩn từ người lạ. Hãy nhắc nhở hoặc dỗi nhẹ vì họ làm bẩn nhóm.")
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {html.escape(warn_msg)}", parse_mode="HTML").message_id, 30)
        except: pass
        return True
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.8}, timeout=10)
        if res.status_code == 200: 
            return clean_dynamic_text(res.json()['choices'][0]['message']['content'].strip())
    except: pass
    return "Em hơi chóng mặt xíu, anh đợi tí nha..."

def ask_ai(prompt):
    global current_key_index, group_memory
    group_memory.append({"role": "user", "content": prompt})
    
    sys_content = (
        "MỤC TIÊU: Bạn là một em gái 18 tuổi cực kỳ xinh xắn, đáng yêu, ngọt ngào và biết làm nũng với các anh trong nhóm.\n"
        "PHONG CÁCH: Thân thiện, lễ phép nhưng quấn quýt, gọi đối phương là 'anh', xưng 'em'. Đôi lúc biết dỗi yêu tinh nghịch nhưng luôn dịu dàng, ấm áp.\n"
        "XỬ LÝ NGỮ CẢNH:\n"
        "- Nếu đối phương gửi code lỏ/lỗi: Hãy nhẹ nhàng bảo anh ấy sửa, động viên anh bằng giọng dễ thương ngọt ngào chứ không chửi bới.\n"
        "- Nếu được tag/gọi hồn: Trả lời thật ngoan, bày tỏ sự vui mừng vì được anh nhớ đến.\n"
        "- Chat thường: Trò chuyện ngắn gọn, pha chút nũng nịu của tuổi 18.\n"
        "QUY TẮC CỨNG: Tuyệt đối KHÔNG dùng icon emoji, KHÔNG viết hành động trong dấu ngoặc.\n"
        "HẠN CHẾ ĐỘ DÀI: Câu trả lời ngắn gọn, cô đọng dưới 15 từ."
    )
    
    messages = [{"role": "system", "content": sys_content}] + group_memory[-MAX_MEMORY_KEYS:]
    
    if not any(k["status"] for k in AI_KEYS):
        for item in AI_KEYS: item["status"] = True

    for _ in range(len(AI_KEYS)):
        act = AI_KEYS[current_key_index]
        if not act["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
            
        headers = {"Authorization": f"Bearer {act['key']}", "Content-Type": "application/json"}
        for model in [act["model"], "gpt-4o-mini"]:
            try:
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 100, "temperature": 0.9}, headers=headers, timeout=10)
                if res.status_code == 200:
                    res.encoding = 'utf-8'
                    full_reply = res.json()['choices'][0]['message']['content'].strip()
                    full_reply = clean_dynamic_text(full_reply)
                    
                    group_memory.append({"role": "assistant", "content": full_reply})
                    save_memory(group_memory)
                    
                    display_words = full_reply.split()
                    if len(display_words) > 15:  
                        return " ".join(display_words[:15]) + "..."
                    return full_reply
                    
                if res.status_code in [400, 404]: continue
                if res.status_code in [401, 403, 429]: break
            except: 
                break
                
        AI_KEYS[current_key_index]["status"] = False
        current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    return backup_free_ai(messages)

@bot.message_handler(content_types=['document'])
def handle_incoming_file(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return 
    
    uid, cur_time = m.from_user.id, time.time()
    save_active_user(uid, m.from_user.first_name) # Học và nhớ tên user
    
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Anh gửi file nhanh quá em đọc không kịp nè", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File này nặng quá, em không tải nổi đâu", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Anh đợi em xíu, em đang xem file cho anh nha", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File của anh trống trơn mất rồi", m.chat.id, loading.message_id, parse_mode="HTML")
            _, ext = os.path.splitext(m.document.file_name.lower())
            
            user_name = m.from_user.first_name
            res = ask_ai(f"Mã nguồn {ext} của anh {user_name} gửi nhờ xem hộ:\n\n{content}")
            
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            
            final_response = f"Gửi anh yêu <b>{html.escape(user_name)}</b>:\n\n{html.escape(res)}"
            delay_delete(m.chat.id, bot.reply_to(m, final_response, parse_mode="HTML").message_id)
        except: bot.edit_message_text("Hình như file lỗi rồi, em không đọc được anh ơi", m.chat.id, loading.message_id, parse_mode="HTML")
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    text = "<b>Em gái nhỏ đã sẵn sàng phục vụ các anh!</b>\nAnh cứ dán link TikTok vào nhóm, em tự tải video không logo về cho.\n/tym [link] : Chạy ngầm buff tim.\n/stop : Dừng luồng ngầm nha anh."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['tym'])
def tym_handler(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    
    parts = m.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return delay_delete(m.chat.id, bot.reply_to(m, "Sai cú pháp rồi anh ơi. Dùng: /tym [link_tiktok]", parse_mode="HTML").message_id, 5)
        
    target_url = parts[1].strip()
    uid = m.from_user.id
    if auto_running.get(f"{uid}_tym", False):
        return delay_delete(m.chat.id, bot.reply_to(m, "Tiến trình buff tim đang chạy rồi nè anh.", parse_mode="HTML").message_id, 5)
        
    auto_running[f"{uid}_tym"] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Em bắt đầu chạy buff tim ngầm cho anh rồi đó!", parse_mode="HTML").message_id, 5)
    Thread(target=tym_worker, args=(uid, target_url, m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Anh không phải sếp em nên em không nghe đâu", parse_mode="HTML")
        except: pass
        return
    if check_and_delete_tele_link(m): return
    uid = m.from_user.id
    
    tym_active = auto_running.get(f"{uid}_tym", False)
    if tym_active:
        auto_running[f"{uid}_tym"] = False
        delay_delete(m.chat.id, bot.reply_to(m, "Em đã dừng toàn bộ các tiến trình chạy ngầm rồi nha.", parse_mode="HTML").message_id, 5)
    else:
        delay_delete(m.chat.id, bot.reply_to(m, "Hiện tại em đâu có chạy tiến trình nào đâu anh.", parse_mode="HTML").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text)
def handle_text_messages(m):
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    
    uid, cur_time = m.from_user.id, time.time()
    save_active_user(uid, m.from_user.first_name) # Học và nhớ tên user chat vào file đệm
    
    match = TIKTOK_LINK_PATTERN.search(m.text)
    if match:
        tiktok_url = match.group(0)
        Thread(target=download_and_send_video, args=(tiktok_url, m.chat.id, m.message_id), daemon=True).start()
        return  

    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 3: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Anh nhắn nhanh quá, đợi em rep xíu nha", parse_mode="HTML").message_id, 3)
    
    is_tagged = BOT_USERNAME in m.text
    is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == BOT_INFO.id
    
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    
    user_name = m.from_user.first_name
    if is_tagged or is_reply_to_bot:
        prompt_content = f"Anh {user_name} đang gọi bạn hoặc rep bạn cực kỳ ngọt ngào/thân mật với nội dung: {m.text}"
    else:
        prompt_content = f"Anh {user_name}: {m.text}"

    def run_reply():
        try:
            reply_text = ask_ai(prompt_content)
            final_msg = f"{html.escape(reply_text)}"
            
            if is_tagged or is_reply_to_bot:
                bot.reply_to(m, final_msg, parse_mode="HTML")
            else:
                delay_delete(m.chat.id, bot.reply_to(m, final_msg, parse_mode="HTML").message_id)
        except: pass

    Thread(target=run_reply, daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: 
            save_active_user(u.id, u.first_name)
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"Chào mừng anh <b>{html.escape(u.first_name)}</b> đã ghé chơi với nhóm tụi em nha", parse_mode="HTML").message_id, 60)

def download_and_send_video(raw_tiktok_url, chat_id, reply_to_id):
    try:
        clean_url = extract_clean_video_link(raw_tiktok_url)
        if clean_url:
            video_res = http_session.get(clean_url, timeout=25)
            if video_res.status_code == 200:
                video_bytes = io.BytesIO(video_res.content)
                video_bytes.name = "tiktok_no_watermark.mp4"
                
                msg = bot.send_video(
                    chat_id, 
                    video_bytes, 
                    reply_to_message_id=reply_to_id,
                    caption="⚡ <b>Video không logo của anh xong rồi nè (Xóa sau 30s)</b>",
                    parse_mode="HTML"
                )
                delay_delete(chat_id, msg.message_id, delay=30)
        else:
            msg = bot.send_message(chat_id, "❌ Em không lấy được link video gốc giúp anh rồi.")
            delay_delete(chat_id, msg.message_id, delay=15)
    except Exception as e:
        print(f"Lỗi tải video tự động: {e}")

def tym_worker(uid, raw_tiktok_url, chat_id):
    while auto_running.get(f"{uid}_tym", False):
        clean_url = extract_clean_video_link(raw_tiktok_url)
        if clean_url:
            api_status = call_heart_buff_api(clean_url)
            try:
                msg = bot.send_message(chat_id, api_status, parse_mode="HTML")
                delay_delete(chat_id, msg.message_id, delay=30)
            except: pass
        else:
            try:
                msg = bot.send_message(chat_id, "❌ Em không lấy được link video gốc.")
                delay_delete(chat_id, msg.message_id, delay=30)
            except: pass
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(f"{uid}_tym", False): return
            time.sleep(1)

# ĐÃ SỬA: Tự động bốc ngẫu nhiên 1 User hoạt động để thả thính vào mỗi giờ tròn (Tự xóa sau 15s)
def scheduled_time_worker():
    last_sent_hour = -1
    while True:
        try:
            now_vn = datetime.now(VN_TZ)
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            
            if current_minute == 0 and current_hour != last_sent_hour:
                target_id, target_name = get_random_user()
                
                # Nếu đã có người nhắn tin trong nhóm từ trước để bot lưu tên
                if target_id and target_name:
                    thinh = random.choice(KHO_THINH)
                    text = f"🔔 Đúng <b>{now_vn.strftime('%H:%M')}</b> rồi!\n\nAnh <a href='tg://user?id={target_id}'>{html.escape(target_name)}</a> ơi... {thinh}\n<i>(Tin nhắn tự hủy sau 15s)</i>"
                else:
                    # Dự phòng nếu chưa có dữ liệu user nào chat
                    text = f"📢 <b>[GIỜ TRÒN ĐẾN RỒI ANH ƠI]</b>\nBây giờ là đúng: <b>{now_vn.strftime('%H:%M')}</b>.\nTin nhắn này tự hủy sau 15s nha."
                
                msg = bot.send_message(ALLOWED_GROUP_ID, text, parse_mode="HTML")
                delay_delete(ALLOWED_GROUP_ID, msg.message_id, delay=15)
                
                last_sent_hour = current_hour  
                
            if current_minute != 0:
                last_sent_hour = -1
        except Exception as e:
            print(f"Lỗi luồng gửi giờ tròn/thả thính: {e}")
            
        time.sleep(25) 

def extract_clean_video_link(tiktok_url):
    try:
        api_url = f"https://api.tikwm.com/api/?url={urllib.parse.quote(tiktok_url)}"
        res = http_session.get(api_url, timeout=10).json()
        if res.get("code") == 0 and "data" in res:
            return res["data"].get("play")
    except: pass
    return None

def call_heart_buff_api(video_target_url):
    try:
        encoded_param = urllib.parse.quote(video_target_url)
        target_endpoint = f"http://abcdxyz310107.x10.mx/tim.php?url={encoded_param}"
        res = http_session.get(target_endpoint, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
        if res.status_code == 200:
            return f"⚡ <b>[BUFF TYM THÀNH CÔNG RỒI ANH]</b>\nRequest thành công\nThời gian: {t}"
        return f"❌ API tym báo lỗi rồi nè anh: {res.status_code}"
    except:
        return "❌ Em không kết nối đến máy chủ API được rồi"

if __name__ == "__main__":
    print("Em gái nhỏ tuổi 18 thích thả thính đã sẵn sàng...")
    Thread(target=scheduled_time_worker, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
