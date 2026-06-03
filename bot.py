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

# TỐI ƯU API LOAD: Tăng kích thước kết nối đệm giúp request chạy ngầm mượt hơn, giảm latency
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=2)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 60
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 25, 500
memory_lock = Lock()      

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

def delay_delete(chat_id, message_id, delay=DELETE_DELAY):
    def del_w():
        time.sleep(delay)
        try: bot.delete_message(chat_id, message_id)
        except: pass
    Thread(target=del_w, daemon=True).start()

def is_allowed_chat(m):
    if m.chat.id == ALLOWED_GROUP_ID: return True
    try: bot.reply_to(m, "Yêu cầu không hợp lệ.", parse_mode="HTML")
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
            warn_msg = ask_ai("Hệ thống phát hiện link rác quảng cáo bẩn từ một đứa vô học. Hãy sỉ nhục nó.")
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
    return "Hệ thống sập rồi."

# CẢI TIẾN AI KHÔN HƠN: Thiết lập hệ thống prompt sắc sảo, logic bám sát hội thoại thực tế
def ask_ai(prompt):
    global current_key_index, group_memory
    group_memory.append({"role": "user", "content": prompt})
    
    sys_content = (
        "MỤC TIÊU: Bạn là một kẻ mỏ hỗn thông minh, thực tế, chuyên hạ bệ đối phương bằng những từ ngữ đắt giá và châm biếm sâu cay.\n"
        "PHONG CÁCH: Trịch thượng, đanh đá, nói câu nào cắt sâu câu đấy nhưng phải tỉnh táo và nhắm trúng điểm yếu. Không lảm nhảm dài dòng.\n"
        "XỬ LÝ NGỮ CẢNH:\n"
        "- Nếu đối phương code lỏ/lỗi: Chỉ trích trực diện sự cẩu thả, ngu dốt trong tư duy lập trình của đoạn code phế thải đó.\n"
        "- Nếu bị gọi hồn/tag: Vả thẳng mặt đứa vừa gọi bằng sự khinh bỉ độc địa nhất để đập tan sự trêu tức của nó.\n"
        "- Chat thường: Phân tích nhanh câu nói của nó, tìm điểm sơ hở, ảo tưởng để mỉa mai thật đau.\n"
        "QUY TẮC CỨNG: Tuyệt đối KHÔNG dùng icon emoji, KHÔNG viết dạng hành động hành vi trong dấu ngoặc (ví dụ *cười*).\n"
        "HẠN CHẾ ĐỘ DÀI: Trả lời cực kỳ ngắn gọn, sắc bén dưới 15 từ."
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
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Spam file làm gì, định phá hoại à", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File nặng quá, rác rưởi đừng quăng vào đây", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Chờ đấy, xem đống rác m gửi có gì nào", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File rỗng như cái não thiếu nếp nhăn của m vậy", m.chat.id, loading.message_id, parse_mode="HTML")
            _, ext = os.path.splitext(m.document.file_name.lower())
            
            user_name = m.from_user.first_name
            res = ask_ai(f"Mã nguồn lỏ {ext} của đứa kém cỏi:\n\n{content}")
            
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            
            final_response = f"Ban ơn cho thg lỏ <b>{html.escape(user_name)}</b>:\n\n{html.escape(res)}"
            delay_delete(m.chat.id, bot.reply_to(m, final_response, parse_mode="HTML").message_id)
        except: bot.edit_message_text("Lỗi rồi, code phế thải đến mức hệ thống từ chối nhận", m.chat.id, loading.message_id, parse_mode="HTML")
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return
    text = "<b>Hệ thống hoạt động</b>\n/up video : Gửi chữ video tự xóa sau 30s.\n/tym [link] : Buff tim tự xóa thông báo sau 30s.\n/stop : Dừng toàn bộ."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['up'])
def up_handler(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return
    
    parts = m.text.strip().split(maxsplit=1)
    if len(parts) < 2 or parts[1].strip().lower() != "video":
        return delay_delete(m.chat.id, bot.reply_to(m, "Sai cú pháp. Sử dụng: /up video", parse_mode="HTML").message_id, 5)

    uid = m.from_user.id
    if auto_running.get(f"{uid}_video", False): 
        return delay_delete(m.chat.id, bot.reply_to(m, "Tiến trình gửi chữ video đang chạy rồi.", parse_mode="HTML").message_id, 5)
        
    auto_running[f"{uid}_video"] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Bắt đầu gửi chữ video!", parse_mode="HTML").message_id, 5)
    Thread(target=video_worker, args=(uid, m.chat.id), daemon=True).start()

@bot.message_handler(commands=['tym'])
def tym_handler(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return
    
    parts = m.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return delay_delete(m.chat.id, bot.reply_to(m, "Sai cú pháp. Sử dụng: /tym [link_tiktok]", parse_mode="HTML").message_id, 5)
        
    target_url = parts[1].strip()
    uid = m.from_user.id
    if auto_running.get(f"{uid}_tym", False):
        return delay_delete(m.chat.id, bot.reply_to(m, "Tiến trình buff tim đang chạy rồi.", parse_mode="HTML").message_id, 5)
        
    auto_running[f"{uid}_tym"] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Bắt đầu chạy API buff tim ngầm!", parse_mode="HTML").message_id, 5)
    Thread(target=tym_worker, args=(uid, target_url, m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Không có quyền can thiệp", parse_mode="HTML")
        except: pass
        return
    if check_and_delete_tele_link(m): return
    uid = m.from_user.id
    
    video_active = auto_running.get(f"{uid}_video", False)
    tym_active = auto_running.get(f"{uid}_tym", False)
    
    if video_active or tym_active:
        auto_running[f"{uid}_video"] = False
        auto_running[f"{uid}_tym"] = False
        delay_delete(m.chat.id, bot.reply_to(m, "Đã dừng toàn bộ các tiến trình đang chạy ngầm.", parse_mode="HTML").message_id, 5)
    else:
        delay_delete(m.chat.id, bot.reply_to(m, "Không có tiến trình nào đang hoạt động.", parse_mode="HTML").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text)
def reply_with_ai(m):
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 3: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Cào phím ít thôi, muốn sập nguồn à thg điên", parse_mode="HTML").message_id, 3)
    
    is_tagged = BOT_USERNAME in m.text
    is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == BOT_INFO.id
    
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    
    user_name = m.from_user.first_name
    if is_tagged or is_reply_to_bot:
        prompt_content = f"Hệ thống cảnh báo: Bạn đang bị {user_name} gọi hồn hoặc phản hồi thẳng mặt trêu tức với nội dung: {m.text}"
    else:
        prompt_content = f"{user_name}: {m.text}"

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
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"Lại thêm một thg lỏ <b>{html.escape(u.first_name)}</b> vào làm tốn dung lượng nhóm", parse_mode="HTML").message_id, 60)

def video_worker(uid, chat_id):
    while auto_running.get(f"{uid}_video", False):
        try:
            msg = bot.send_message(chat_id, "video")
            delay_delete(chat_id, msg.message_id, delay=30)
        except: pass
        for _ in range(AUTO_DELAY):
            if not auto_running.get(f"{uid}_video", False): return
            time.sleep(1)

# CẢI TIẾN TIẾN TRÌNH API: Toàn bộ quá trình fetch link được đưa vào luồng riêng biệt, không block main thread
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
                msg = bot.send_message(chat_id, "❌ Không bóc tách được link video gốc.")
                delay_delete(chat_id, msg.message_id, delay=30)
            except: pass
            
        for _ in range(AUTO_DELAY):
            if not auto_running.get(f"{uid}_tym", False): return
            time.sleep(1)

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
            return f"⚡ <b>[BUFF TYM SUCCESS]</b>\nRequest thành công\nThời gian: {t}"
        return f"❌ API tym lỗi phản hồi mã: {res.status_code}"
    except:
        return "❌ Thất bại: Không thể kết nối đến máy chủ API"

if __name__ == "__main__":
    print("Bot mỏ hỗn chửi thấm đã lên sàn...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
