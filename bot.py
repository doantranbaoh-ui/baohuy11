# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz, random, re, html
from threading import Thread, Lock
from requests.exceptions import RequestException, Timeout
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAFFePhaV2MRGUzY3U6CF55Te4SpnSN72IE"
ALLOWED_GROUP_ID, ADMIN_ID = -1003872001041, 5736655322              

bot = telebot.TeleBot(TOKEN, num_threads=10)  
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()

BOT_INFO = bot.get_me() 

http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=30)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 300
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 20, 500
memory_lock = Lock()      

user_memories = {}
MAX_USER_MEMORY = 4  

TELE_LINK_PATTERN = re.compile(r'(t\.me|telegram\.me|telegram\.org)\/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{5,}')

PRE_ICONS_LIST = [
    '<tg-emoji emoji-id="5431447214631033120">⭐️</tg-emoji>', 
    '<tg-emoji emoji-id="5431609312157771741">✨</tg-emoji>', 
    '<tg-emoji emoji-id="5217730999052504851">🔥</tg-emoji>', 
    '<tg-emoji emoji-id="5445279603056581413">👑</tg-emoji>', 
    '<tg-emoji emoji-id="5431940989396593421">⚡️</tg-emoji>', 
    '<tg-emoji emoji-id="5467652701881744154">💎</tg-emoji>'  
]

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
    try: bot.reply_to(m, "Yêu cầu không hợp lệ.", parse_mode="HTML")
    except: pass
    return False

def is_admin(m):
    return m.from_user.id == ADMIN_ID

def check_and_delete_tele_link(m):
    if is_admin(m): return False
    text_to_check = (m.text or "") + (m.caption or "")
    
    if TELE_LINK_PATTERN.search(text_to_check):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn_msg = ask_ai("Cấm quảng cáo link.", u_id=m.from_user.id)
            icon = random.choice(PRE_ICONS_LIST)
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {html.escape(warn_msg)} {icon}", parse_mode="HTML").message_id, 30)
        except: pass
        return True
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.5}, timeout=10)
        if res.status_code == 200: 
            return res.json()['choices'][0]['message']['content'].strip()
    except: pass
    return "Lỗi AI."

def ask_ai(prompt, custom_sys=None, u_id=None):
    global current_key_index, group_memory, user_memories
    
    u_mem = user_memories.get(u_id, []) if u_id else group_memory
    messages = [{"role": "system", "content": custom_sys}] + u_mem + [{"role": "user", "content": prompt}]
    
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
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 20, "temperature": 0.5}, headers=headers, timeout=12)
                if res.status_code == 200:
                    res.encoding = 'utf-8'
                    reply = res.json()['choices'][0]['message']['content'].strip()
                    
                    # Giới hạn tin nhắn siêu ngắn (Tối đa 5 từ)
                    words = reply.split()
                    if len(words) > 5:
                        reply = " ".join(words[:5]) + "..."
                    
                    if u_id:
                        u_mem.append({"role": "user", "content": prompt})
                        u_mem.append({"role": "assistant", "content": reply})
                        user_memories[u_id] = u_mem[-MAX_USER_MEMORY:]
                    else:
                        save_memory(messages[1:] + [{"role": "assistant", "content": reply}])
                    
                    return reply
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
        return delay_delete(m.chat.id, bot.reply_to(m, "Thao tác chậm lại.", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File quá lớn.", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Đang xử lý...", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File trống.", m.chat.id, loading.message_id, parse_mode="HTML")
            _, ext = os.path.splitext(m.document.file_name.lower())
            
            user_name = m.from_user.first_name
            sys_p = "Bạn là trợ lý code. Nhận xét ngắn gọn dưới 5 từ."
            res = ask_ai(f"File {ext}:\n\n{content}", custom_sys=sys_p, u_id=uid)
            
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            icon_pre = "".join(random.sample(PRE_ICONS_LIST, 2))
            
            final_response = f"Kết quả cho <b>{html.escape(user_name)}</b>:\n\n<pre><code>{html.escape(res)}</code></pre> {icon_pre}"
            delay_delete(m.chat.id, bot.reply_to(m, final_response, parse_mode="HTML").message_id)
        except: bot.edit_message_text("Lỗi phân tích file.", m.chat.id, loading.message_id, parse_mode="HTML")
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    text = "<b>Hệ thống sẵn sàng.</b>\n<pre>/like [link] : Buff tim.\n/auto [link] : Auto.\n/stop : Tắt.</pre>"
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['like'])
def like(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in user_cooldowns and (cur_time - user_cooldowns[uid]) < COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Thử lại sau.", parse_mode="HTML").message_id, 4)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        return delay_delete(m.chat.id, bot.reply_to(m, "Liên kết lỗi.", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Đang chạy...", parse_mode="HTML")
    user_cooldowns[uid] = cur_time  
    def run_like():
        suc, res = execute_buff_api(args[1].strip())
        bot.edit_message_text(res, m.chat.id, loading.message_id, parse_mode="HTML")
        delay_delete(m.chat.id, loading.message_id, 30 if suc else 10)
    Thread(target=run_like, daemon=True).start()

@bot.message_handler(commands=['auto'])
def auto(m):
    if not is_allowed_chat(m) or not is_admin(m): 
        try: bot.reply_to(m, "Từ chối truy cập.", parse_mode="HTML")
        except: pass
        return
    uid = m.from_user.id
    if auto_running.get(uid, False): return delay_delete(m.chat.id, bot.reply_to(m, "Đang chạy rồi.", parse_mode="HTML").message_id, 5)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower(): return delay_delete(m.chat.id, bot.reply_to(m, "Sai liên kết.", parse_mode="HTML").message_id, 5)

    auto_running[uid] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Kích hoạt auto.", parse_mode="HTML").message_id, 10)
    Thread(target=auto_worker, args=(uid, args[1].strip(), m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Từ chối truy cập.", parse_mode="HTML")
        except: pass
        return
    uid = m.from_user.id
    auto_running[uid] = False
    delay_delete(m.chat.id, bot.reply_to(m, "Đã dừng auto." if auto_running.get(uid, False) else "Không có tác vụ chạy.", parse_mode="HTML").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text)
def reply_with_ai(m):
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 4: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Đừng gửi liên tục.", parse_mode="HTML").message_id, 3)
    
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    
    user_name = m.from_user.first_name
    sys_prompt = "Bạn là trợ lý nhóm. Trả lời hữu ích và BẮT BUỘC dưới 5 từ."
    prompt_content = f"Người dùng '{user_name}': {m.text}."

    def run_reply():
        try:
            reply_text = ask_ai(prompt_content, custom_sys=sys_prompt, u_id=uid)
            icon_pre = "".join(random.sample(PRE_ICONS_LIST, 2))
            final_msg = f"{html.escape(reply_text)} {icon_pre}"
            delay_delete(m.chat.id, bot.reply_to(m, final_msg, parse_mode="HTML").message_id)
        except: pass

    Thread(target=run_reply, daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        icon = random.choice(PRE_ICONS_LIST)
        for u in m.new_chat_members: 
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"Chào mừng <b>{html.escape(u.first_name)}</b>. {icon}", parse_mode="HTML").message_id, 60)

def auto_worker(uid, url, chat_id):
    while auto_running.get(uid, False):
        suc, res = execute_buff_api(url)
        bot.send_message(chat_id, f"[AUTO]\n{res}", parse_mode="HTML")
        for _ in range(AUTO_DELAY):
            if not auto_running.get(uid, False): return
            time.sleep(1)

def execute_buff_api(url):
    try:
        api_endpoint = f"http://180.93.32.186:1817/api/buff/start?link={urllib.parse.quote(url)}"
        res = http_session.get(api_endpoint, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
        icon = random.choice(PRE_ICONS_LIST)
        
        if res.status_code == 200:
            try:
                res.encoding = 'utf-8'
                d = res.json()
                user_info = html.escape(d.get('username') or d.get('user') or 'TikTok User')
                status_info = html.escape(d.get('added') or d.get('count') or d.get('msg') or 'Đang xử lý')
                output = f"Buff xong {icon}\n<pre>User: {user_info}\nStatus: {status_info}\nTime: {t}</pre>"
                return output
            except: 
                return f"Buff xong {icon}\n<pre>User: Hệ thống\nStatus: Chạy\nTime: {t}</pre>"
        return f"Mã lỗi {res.status_code} {icon}"
    except Timeout: return f"Hệ thống chậm. {icon}"
    except RequestException: return f"Lỗi kết nối API. {icon}"
    except: return f"Lỗi ẩn. {icon}"

if __name__ == "__main__":
    print("Bot khởi chạy thành công...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
