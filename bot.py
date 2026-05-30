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
BOT_USERNAME = f"@{BOT_INFO.username}" # Tự động lấy username của bot để bắt tag

http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=30)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 300
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 20, 500
memory_lock = Lock()      

TELE_LINK_PATTERN = re.compile(r'(t\.me|telegram\.me|telegram\.org)\/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{5,}')

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

def check_and_delete_tele_link(m):
    if is_admin(m): return False
    text_to_check = (m.text or "") + (m.caption or "")
    
    if TELE_LINK_PATTERN.search(text_to_check):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn_msg = ask_ai("Sỉ nhục, chửi cay độc đứa vô học vừa gửi link rác quảng cáo bẩn.")
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {html.escape(warn_msg)}", parse_mode="HTML").message_id, 30)
        except: pass
        return True
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.8}, timeout=10)
        if res.status_code == 200: 
            return res.json()['choices'][0]['message']['content'].strip()
    except: pass
    return "Nghỉ đi, sập r, khóc lóc j 🤡"

def ask_ai(prompt, custom_sys=None):
    global current_key_index, group_memory
    
    group_memory.append({"role": "user", "content": prompt})
    
    sys_content = custom_sys if custom_sys else (
        "Bạn là một kẻ mỏ hỗn thiên tài, chuyên chửi bới châm biếm cực kỳ sâu cay và thấm thía. "
        "Hãy nói chuyện với giọng trịch thượng, khinh bỉ, dùng từ ngữ xéo xắt cắt sâu vào lòng tự ái của người khác. "
        "BẮT BUỘC lồng ghép các icon biểu cảm nhục mạ như 😏, 🤡, 🐸, 🧠, 🤏. "
        "Câu trả lời phải ngắn gọn, súc tích và giới hạn nghiêm ngặt dưới 15 từ."
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
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 120, "temperature": 0.95}, headers=headers, timeout=12)
                if res.status_code == 200:
                    res.encoding = 'utf-8'
                    full_reply = res.json()['choices'][0]['message']['content'].strip()
                    
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
        return delay_delete(m.chat.id, bot.reply_to(m, "Spam file làm j, định phá hoại à thg lỏ 🧠", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File nặng vcl, rác rưởi đừng quăng vào đây 🐸", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Chờ đấy, xem đống rác m gửi có j nào 😏", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File rỗng như cái não thiếu nếp nhăn của m v 🤡", m.chat.id, loading.message_id, parse_mode="HTML")
            _, ext = os.path.splitext(m.document.file_name.lower())
            
            user_name = m.from_user.first_name
            sys_p = "Bạn là chuyên gia soi code, hãy dùng những từ ngữ cay độc, thấm thía nhất để chê bai đoạn mã nguồn rác rưởi này dưới 15 từ."
            res = ask_ai(f"Mã nguồn lỏ {ext} của đứa kém cỏi:\n\n{content}", custom_sys=sys_p)
            
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            
            final_response = f"Ban ơn cho thg lỏ <b>{html.escape(user_name)}</b>:\n\n{html.escape(res)}"
            delay_delete(m.chat.id, bot.reply_to(m, final_response, parse_mode="HTML").message_id)
        except: bot.edit_message_text("Lỗi rồi, code phế thải đến mức hệ thống từ chối nhận 😏", m.chat.id, loading.message_id, parse_mode="HTML")
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    text = "<b>Bật rồi, định làm trò hề j đây 🧠</b>\n/like [link] : Buff lẹ đi.\n/auto [link] : Treo máy.\n/stop : Cút."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['like'])
def like(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in user_cooldowns and (cur_time - user_cooldowns[uid]) < COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Click lắm thế, rảnh rỗi quá không có việc j làm à 🤡", parse_mode="HTML").message_id, 4)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        return delay_delete(m.chat.id, bot.reply_to(m, "Đưa cái link lỗi mà cũng đòi chạy à, xem lại não đi 😏", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Đang chạy, hối cc chạy bằng cơm à 🐸", parse_mode="HTML")
    user_cooldowns[uid] = cur_time  
    def run_like():
        suc, res = execute_buff_api(args[1].strip())
        bot.edit_message_text(res, m.chat.id, loading.message_id, parse_mode="HTML")
        delay_delete(m.chat.id, loading.message_id, 30 if suc else 10)
    Thread(target=run_like, daemon=True).start()

@bot.message_handler(commands=['auto'])
def auto(m):
    if not is_allowed_chat(m) or not is_admin(m): 
        try: bot.reply_to(m, "Tuổi j đòi xài lệnh này, ảo tưởng à thg lỏ 🤏", parse_mode="HTML")
        except: pass
        return
    uid = m.from_user.id
    if auto_running.get(uid, False): return delay_delete(m.chat.id, bot.reply_to(m, "Đang chạy rồi, mắt mù không thấy hay sao bật lắm 🧠", parse_mode="HTML").message_id, 5)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower(): return delay_delete(m.chat.id, bot.reply_to(m, "Nhập cái link tử tế vào thg vô học 🐸", parse_mode="HTML").message_id, 5)

    auto_running[uid] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Bật auto rồi, đòi hỏi lắm vcl 😏", parse_mode="HTML").message_id, 10)
    Thread(target=auto_worker, args=(uid, args[1].strip(), m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Cút ra chỗ khác, không phải việc của m 🤡", parse_mode="HTML")
        except: pass
        return
    uid = m.from_user.id
    auto_running[uid] = False
    delay_delete(m.chat.id, bot.reply_to(m, "Tắt rồi, cút hộ cái cho sạch chỗ 🐒" if auto_running.get(uid, False) else "Có cái mẹ j chạy đâu mà tắt, ngáo à thg lỏ 👀", parse_mode="HTML").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text)
def reply_with_ai(m):
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 3: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Cào phím ít thôi, mún sập nguồn à thg điên 🤡", parse_mode="HTML").message_id, 3)
    
    # KIỂM TRA ĐIỀU KIỆN TAG @ HOẶC REPLY TIN NHẮN CỦA BOT ĐỂ KÍCH HOẠT LỆNH CHỬI
    is_tagged = BOT_USERNAME in m.text
    is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == BOT_INFO.id
    
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    
    user_name = m.from_user.first_name
    prompt_content = f"{user_name}: {m.text}"

    def run_reply():
        try:
            # Nếu bị tag hoặc reply trực tiếp, áp hệ thống lệnh ép AI chửi trực diện cực gắt
            if is_tagged or is_reply_to_bot:
                sys_p = (
                    "Bạn bị người này gọi hồn hoặc tag thẳng mặt. Hãy dùng những từ ngữ độc địa, "
                    "khinh bỉ và châm biếm nặng nề nhất để hạ bệ, sỉ nhục đứa vừa tag bạn. "
                    "BẮT BUỘC dùng icon nhục mạ như 😏, 🤡, 🐸, 🧠. Trả lời cực ngắn dưới 15 từ."
                )
                reply_text = ask_ai(prompt_content, custom_sys=sys_p)
            else:
                reply_text = ask_ai(prompt_content)
                
            final_msg = f"{html.escape(reply_text)}"
            bot.reply_to(m, final_msg, parse_mode="HTML") # Đổi sang reply trực tiếp đứa vừa tag
        except: pass

    Thread(target=run_reply, daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: 
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"Lại thêm một thg lỏ <b>{html.escape(u.first_name)}</b> vào làm tốn dung lượng nhóm 🤡", parse_mode="HTML").message_id, 60)

def auto_worker(uid, url, chat_id):
    while auto_running.get(uid, False):
        suc, res = execute_buff_api(url)
        bot.send_message(chat_id, f"[AUTO CHỬI THẤM]\n{res}", parse_mode="HTML")
        for _ in range(AUTO_DELAY):
            if not auto_running.get(uid, False): return
            time.sleep(1)

def execute_buff_api(url):
    try:
        api_endpoint = f"http://180.93.32.186:1817/api/buff/start?link={urllib.parse.quote(url)}"
        res = http_session.get(api_endpoint, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
        
        if res.status_code == 200:
            try:
                res.encoding = 'utf-8'
                d = res.json()
                user_info = html.escape(d.get('username') or d.get('user') or 'Kẻ vô danh')
                status_info = html.escape(d.get('added') or d.get('count') or d.get('msg') or 'Xong r')
                output = f"Xong rồi đấy thg lỏ 😏\nUser: {user_info}\nStatus: {status_info}\nTime: {t}"
                return output
            except: 
                return f"Xong rồi hỏi lắm vcl 🐸\nUser: Hệ thống\nStatus: Chạy\nTime: {t}"
        return f"Lỗi {res.status_code} rồi, khóc lóc cl 🤡"
    except Timeout: return "Mạng lag như rùa, do ăn ở cả thôi 🐢"
    except RequestException: return "API oẳng rồi, hết cứu 🐸"
    except: return "Lỗi hệ thống r, chịu 👀"

if __name__ == "__main__":
    print("Bot mỏ hỗn chửi thấm đã lên sàn...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
