# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz
from threading import Thread, Lock
from requests.exceptions import RequestException, Timeout
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID, ADMIN_ID = -1003872001041, 5736655322              

bot = telebot.TeleBot(TOKEN, num_threads=10)  # Tăng số luồng xử lý đồng thời để bot mạnh hơn
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()

# Cấu hình Pool kết nối để tái sử dụng và tăng tốc độ request API
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=30)
http_session.mount('https://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 300
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 20, 500
memory_lock = Lock()      

AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True},  
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True}  
]
current_key_index = 0  

def load_memory():
    if os.path.exists(MEMORY_FILE) and (os.path.getsize(MEMORY_FILE) / 1024) <= MAX_FILE_SIZE_KB:
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return []

def save_memory(memory_data):
    global group_memory
    with memory_lock:
        try:
            group_memory = memory_data[-MAX_MEMORY_KEYS:]
            with open(MEMORY_FILE, "w", encoding="utf-8") as f: json.dump(group_memory, f, ensure_ascii=False, indent=4)
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
    try: bot.reply_to(m, "Bản quyền không hợp lệ")
    except: pass
    return False

def is_admin(m):
    if m.from_user.id == ADMIN_ID: return True
    try: bot.reply_to(m, "Chỉ dành cho Admin")
    except: pass
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.5}, timeout=10)
        if res.status_code == 200: return res.json()['choices'][0]['message']['content'].strip()
    except: pass
    return "Server bận rồi"

def ask_ai(prompt):
    global current_key_index, group_memory
    # Giao hoàn toàn quyền tự nghĩ icon, độ khinh người, teencode đốp chát cho API xử lý tự động
    sys_prompt = "Bạn là một thằng trẻ trâu anh hùng bàn phím khinh người, coi thiên hạ là lũ rác rưởi hạ đẳng ngu dốt. Nói chuyện bằng giọng bề trên, mỉa mai, dùng ngôn ngữ mạng và teencode nặng (j, thía, bít rùi, k, thui, vcl, ak, m, t). Trả lời cực ngắn, gọn, thô lỗ. BẮT BUỘC tự suy nghĩ và chèn các icon khinh bỉ, mỉa mai hãm tài (như 🤡, 😏, 😮‍💨, 🤔, 👀) một cách linh hoạt, phù hợp ngữ cảnh vào câu trả lời. Không chào hỏi."
    messages = [{"role": "system", "content": sys_prompt}] + group_memory + [{"role": "user", "content": prompt}]
    
    for _ in range(len(AI_KEYS)):
        act = AI_KEYS[current_key_index]
        if not act["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
        headers = {"Authorization": f"Bearer {act['key']}", "Content-Type": "application/json"}
        for model in [act["model"], "gpt-4o-mini", "gpt-3.5-turbo"]:
            try:
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 1000, "temperature": 0.85}, headers=headers, timeout=15)
                if res.status_code == 200:
                    res.encoding = 'utf-8'
                    reply = res.json()['choices'][0]['message']['content'].strip()
                    save_memory(messages[1:] + [{"role": "assistant", "content": reply}])
                    return reply
                if res.status_code in [400, 404]: continue
                if res.status_code in [401, 403, 429]: break
            except: break
        AI_KEYS[current_key_index]["status"] = False
        current_key_index = (current_key_index + 1) % len(AI_KEYS)
            
    for item in AI_KEYS: item["status"] = True
    return backup_free_ai(messages)

@bot.message_handler(content_types=['document'])
def handle_incoming_file(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Thao tác quá nhanh").message_id, 5)
    if m.document.file_size > 500000: # Nâng mức nhận dung lượng file lên tối đa 500KB
        return delay_delete(m.chat.id, bot.reply_to(m, "File quá lớn").message_id, 5)

    loading = bot.reply_to(m, "Đang đọc file...")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File trống", m.chat.id, loading.message_id)
            _, ext = os.path.splitext(m.document.file_name.lower())
            res = ask_ai(f"Phân tích nhanh file {ext}, tìm lỗi sai logic/cú pháp nếu là code và trả về đoạn code đã sửa tối ưu, ngắn gọn nhất:\n\n{content}")
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            delay_delete(m.chat.id, bot.reply_to(m, f"Kết quả phân tích file {m.document.file_name}:\n\n{res}").message_id)
        except: bot.edit_message_text("Lỗi hệ thống", m.chat.id, loading.message_id)
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    text = "Hệ thống trợ lý\nChat: Nhắn trực tiếp vào nhóm.\nCheck Code: Gửi file code.\n/like [link] : Buff tim TikTok.\n/auto [link] : Tự động buff.\n/stop : Dừng auto."
    delay_delete(m.chat.id, bot.reply_to(m, text).message_id)

@bot.message_handler(commands=['like'])
def like(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in user_cooldowns and (cur_time - user_cooldowns[uid]) < COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Thao tác quá nhanh").message_id, 4)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        return delay_delete(m.chat.id, bot.reply_to(m, "Link sai").message_id, 5)

    loading = bot.reply_to(m, "Đang xử lý...")
    user_cooldowns[uid] = cur_time  
    def run_like():
        suc, res = execute_buff_api(args[1].strip())
        bot.edit_message_text(res, m.chat.id, loading.message_id, parse_mode="Markdown" if suc else None)
        delay_delete(m.chat.id, loading.message_id, 30 if suc else 10)
    Thread(target=run_like, daemon=True).start()

@bot.message_handler(commands=['auto'])
def auto(m):
    if not is_allowed_chat(m) or not is_admin(m): return
    uid = m.from_user.id
    if auto_running.get(uid, False): return delay_delete(m.chat.id, bot.reply_to(m, "Đang chạy rồi").message_id, 5)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower(): return delay_delete(m.chat.id, bot.reply_to(m, "Link sai").message_id, 5)

    auto_running[uid] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Đã bật tiến trình Auto").message_id, 10)
    Thread(target=auto_worker, args=(uid, args[1].strip(), m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m): return
    uid = m.from_user.id
    auto_running[uid] = False
    delay_delete(m.chat.id, bot.reply_to(m, "Đã tắt tiến trình Auto ngầm" if auto_running.get(uid, False) else "Không có tiến trình nào đang chạy").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text and not m.text.startswith('/'))
def reply_with_ai(m):
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 4: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Chat quá nhanh").message_id, 3)
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    Thread(target=lambda: delay_delete(m.chat.id, bot.reply_to(m, ask_ai(m.text)).message_id), daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: delay_delete(m.chat.id, bot.send_message(m.chat.id, "Thành viên mới gia nhập nhóm").message_id, 60)

def auto_worker(uid, url, chat_id):
    while auto_running.get(uid, False):
        suc, res = execute_buff_api(url)
        delay_delete(chat_id, bot.send_message(chat_id, f"[AUTO CHU KỲ]\n{res}", parse_mode="Markdown" if suc else None).message_id, 120 if suc else 30)
        for _ in range(AUTO_DELAY):
            if not auto_running.get(uid, False): return
            time.sleep(1)

def execute_buff_api(url):
    try:
        res = http_session.get(f"https://tiktokvm.vercel.app/api/likes?url={urllib.parse.quote(url)}", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
        if res.status_code == 200:
            try:
                res.encoding = 'utf-8'
                d = res.json()
                return True, f"Buff thành công\nUser: {d.get('username') or d.get('user') or 'TikTok User'}\nStatus: +{d.get('added') or d.get('count') or 'OK'}\nTime: {t}"
            except: return True, f"Buff thành công\nUser: Hệ thống\nStatus: Đang xử lý\nTime: {t}"
        return False, f"Lỗi máy chủ (Mã {res.status_code})"
    except Timeout: return False, "Quá hạn kết nối"
    except RequestException: return False, "Lỗi mạng"
    except: return False, "Lỗi không xác định"

if __name__ == "__main__":
    print("Bot khởi chạy...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
