# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz, random, re, html
from threading import Thread, Lock
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAGtAejJsqZ8pYKEgcZn-lS198t4eTPej2I"
ALLOWED_GROUP_ID, ADMIN_ID = -1003925717296, 5736655322              

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

# Cấu hình chống spam nhóm
SPAM_LOGS = {}
MAX_MESSAGES = 5      # Tối đa 5 tin nhắn
SPAM_WINDOW = 4       # Trong vòng 4 giây

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

KHO_THINH = [
    "Trời đổ mưa rồi, sao anh chưa đổ em?",
    "Anh ơi, anh có ngửi thấy mùi gì cháy không? Mùi tim em đang cháy vì anh đấy!",
    "Người ta thích gọi anh là chồng, còn em thì thích gọi anh là của em.",
    "Anh có biết bơi không? Sao cứ chìm đắm trong tâm trí em hoài thế?",
    "Trăng dưới nước là trăng trên trời, người trước mặt là người trong tim em.",
    "Muốn bình yên thì lên chùa cầu phúc, muốn hạnh phúc thì đứng đó đợi em.",
    "Em không thích xem mười vạn câu hỏi vì sao xuiu nào, em chỉ thích câu trả lời vì sao yêu anh thôi.",
    "Mọi người cứ bảo em 18 tuổi ngây ngô, nhưng em thừa biết là em thích anh rồi.",
    "Số điện thoại của em chưa có ai gọi, anh có muốn làm người đầu tiên không?",
    "Hôm nay trời xanh mây trắng, anh có muốn cùng em viết nên câu chuyện tình?"
]

KHO_THO = [
    "Yêu nhau mấy núi cũng trèo\nMấy sông cũng lội, mấy đèo cũng qua.",
    "Nước non xoay xoay vần vần\nLòng em vẫn giữ vẹn phần yêu anh.",
    "Người đi một nửa hồn tôi mất\nMột nửa hồn tôi bỗng dại khờ.",
    "Sóng bắt đầu từ gió\nGió bắt đầu từ đâu?\nEm cũng không biết nữa\nKhi nào ta yêu nhau.",
    "Trăm năm trong cõi người ta\nChữ yêu chữ nghĩa mới là anh em.",
    "Nắng mưa là chuyện của trời\nTương tư là chuyện của tôi yêu nàng.",
    "Đôi ta như lửa mới nhen\nNhư trăng mới mọc, như đèn mới khơi.",
    "Yêu anh không biết để đâu\nĐể trong túi áo lâu lâu lại nhìn."
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
    return False

def is_admin(m):
    return m.from_user.id == ADMIN_ID

def clean_dynamic_text(text):
    clean_text = re.sub(r'\*.*?\*', '', text)
    clean_text = re.sub(r'[_*`\[\]()]', '', clean_text)
    return clean_text.strip()

# Kiểm tra chống spam tin nhắn liên tục
def check_antispam(m):
    if is_admin(m): return False
    uid = m.from_user.id
    now = time.time()
    
    if uid not in SPAM_LOGS:
        SPAM_LOGS[uid] = []
        
    # Lọc lại các mốc thời gian trong khoảng cửa sổ kiểm tra
    SPAM_LOGS[uid] = [t for t in SPAM_LOGS[uid] if now - t < SPAM_WINDOW]
    SPAM_LOGS[uid].append(now)
    
    if len(SPAM_LOGS[uid]) > MAX_MESSAGES:
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn = bot.send_message(m.chat.id, f"⚠️ Anh <b>{html.escape(m.from_user.first_name)}</b> ơi, nhắn chậm thôi kẻo trôi bài của em nha...", parse_mode="HTML")
            delay_delete(m.chat.id, warn.message_id, 10)
        except: pass
        return True
    return False

def check_and_delete_tele_link(m):
    if is_admin(m): return False
    text_to_check = (m.text or "") + (m.caption or "")
    if TELE_LINK_PATTERN.search(text_to_check):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn_msg = ask_ai("Phát hiện link rác quảng cáo bẩn. Hãy nhắc nhở nhẹ nhàng vì em sợ bẩn nhóm.")
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {html.escape(warn_msg)}", parse_mode="HTML").message_id, 30)
        except: pass
        return True
    return False

def ask_ai(prompt):
    global current_key_index, group_memory
    group_memory.append({"role": "user", "content": prompt})
    sys_content = (
        "Bạn là em gái 18 tuổi xinh xắn, ngọt ngào. Gọi đối phương là 'anh', xưng 'em'. "
        "Nói năng nũng nịu, lễ phép, dưới 15 từ, không emoji."
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
        try:
            res = http_session.post(act["url"], json={"model": act["model"], "messages": messages, "max_tokens": 100}, headers=headers, timeout=10)
            if res.status_code == 200:
                reply = clean_dynamic_text(res.json()['choices'][0]['message']['content'].strip())
                group_memory.append({"role": "assistant", "content": reply})
                save_memory(group_memory)
                return reply
        except: pass
        AI_KEYS[current_key_index]["status"] = False
        current_key_index = (current_key_index + 1) % len(AI_KEYS)
    return "Em hơi mệt, anh đợi xíu nha..."

@bot.message_handler(content_types=['document'])
def handle_incoming_file(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return 
    save_active_user(m.from_user.id, m.from_user.first_name)
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Anh gửi file nhanh quá em đọc không kịp nè", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File này nặng quá, em không tải nổi đâu", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Anh đợi em xem file xíu nha", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            res = ask_ai(f"Mã nguồn của anh {m.from_user.first_name}:\n{content}")
            bot.delete_message(m.chat.id, loading.message_id)
            delay_delete(m.chat.id, bot.reply_to(m, f"Anh yêu ơi:\n{html.escape(res)}", parse_mode="HTML").message_id)
        except: pass
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    text = "<b>Em gái nhỏ sẵn sàng phục vụ các anh!</b>\nAnh cứ dán link TikTok vào nhóm, em tự tải video không logo về cho.\n/tym [link] : Chạy ngầm buff tim.\n/stop : Dừng luồng ngầm nha anh."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['tym'])
def tym_handler(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
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
    if check_antispam(m): return
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
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    
    match = TIKTOK_LINK_PATTERN.search(m.text)
    if match:
        Thread(target=download_and_send_video, args=(match.group(0), m.chat.id, m.message_id), daemon=True).start()
        return  

    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 3: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Anh nhắn nhanh quá, đợi em rep xíu nha", parse_mode="HTML").message_id, 3)

    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time

    def run_reply():
        reply = ask_ai(m.text)
        is_tagged = BOT_USERNAME in m.text
        is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == BOT_INFO.id
        
        if is_tagged or is_reply_to_bot:
            bot.reply_to(m, html.escape(reply), parse_mode="HTML")
        else:
            delay_delete(m.chat.id, bot.reply_to(m, html.escape(reply), parse_mode="HTML").message_id)
    Thread(target=run_reply, daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: 
            if u.id == BOT_INFO.id: continue
            save_active_user(u.id, u.first_name)
            text = f"🌸 Em chào anh <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> đã vào nhóm chơi với tụi em nha!\n<i>(Tin nhắn tự hủy sau 30s)</i>"
            delay_delete(m.chat.id, bot.send_message(m.chat.id, text, parse_mode="HTML").message_id, 30)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_member(m):
    if is_allowed_chat(m):
        u = m.left_chat_member
        if u.id == BOT_INFO.id: return
        text = f"🍂 Anh <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa rời nhóm mất rồi... Em tạm biệt anh nhé, giữ gìn sức khỏe nha anh!\n<i>(Tin nhắn tự hủy sau 30s)</i>"
        delay_delete(m.chat.id, bot.send_message(m.chat.id, text, parse_mode="HTML").message_id, 30)

def download_and_send_video(url, chat_id, reply_id):
    try:
        api_url = f"https://api.tikwm.com/api/?url={urllib.parse.quote(url)}"
        res = http_session.get(api_url, timeout=10).json()
        if res.get("code") == 0:
            video_res = http_session.get(res["data"].get("play"), timeout=25)
            msg = bot.send_video(chat_id, io.BytesIO(video_res.content), reply_to_message_id=reply_id, caption="Của anh nè (Xóa sau 30s)", parse_mode="HTML")
            delay_delete(chat_id, msg.message_id, 30)
    except: pass

def tym_worker(uid, raw_tiktok_url, chat_id):
    while auto_running.get(f"{uid}_tym", False):
        try:
            api_url = f"https://api.tikwm.com/api/?url={urllib.parse.quote(raw_tiktok_url)}"
            res = http_session.get(api_url, timeout=10).json()
            if res.get("code") == 0 and "data" in res:
                clean_url = res["data"].get("play")
                encoded_param = urllib.parse.quote(clean_url)
                target_endpoint = f"http://abcdxyz310107.x10.mx/tim.php?url={encoded_param}"
                resp = http_session.get(target_endpoint, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
                t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
                if resp.status_code == 200:
                    msg = bot.send_message(chat_id, f"⚡ <b>[BUFF TYM THÀNH CÔNG RỒI ANH]</b>\nRequest thành công\nThời gian: {t}", parse_mode="HTML")
                else:
                    msg = bot.send_message(chat_id, f"❌ API tym báo lỗi rồi: {resp.status_code}")
                delay_delete(chat_id, msg.message_id, 30)
        except: pass
        for _ in range(AUTO_DELAY):
            if not auto_running.get(f"{uid}_tym", False): return
            time.sleep(1)

def scheduled_time_worker():
    last_sent_hour = -1
    while True:
        try:
            now = datetime.now(VN_TZ)
            if now.minute == 0 and now.hour != last_sent_hour:
                target_id, target_name = get_random_user()
                if target_id:
                    text = f"🔔 <b>{now.strftime('%H:%M')}</b>\nAnh <a href='tg://user?id={target_id}'>{html.escape(target_name)}</a> ơi... {random.choice(KHO_THINH)}\n<i>(Xóa sau 15s)</i>"
                    delay_delete(ALLOWED_GROUP_ID, bot.send_message(ALLOWED_GROUP_ID, text, parse_mode="HTML").message_id, 15)
                last_sent_hour = now.hour
            if now.minute != 0: last_sent_hour = -1
        except: pass
        time.sleep(25)

def auto_poem_worker():
    while True:
        time.sleep(3600)
        try:
            tho = random.choice(KHO_THO)
            text = f"🌸 <b>Gửi tặng các anh một câu thơ:</b>\n\n<i>{tho}</i>\n\n<i>(Em tự xóa sau 15s nha)</i>"
            msg = bot.send_message(ALLOWED_GROUP_ID, text, parse_mode="HTML")
            delay_delete(ALLOWED_GROUP_ID, msg.message_id, 15)
        except: pass

if __name__ == "__main__":
    print("Em gái nhỏ đã cài thêm lớp bảo vệ nhóm chống spam...")
    Thread(target=scheduled_time_worker, daemon=True).start()
    Thread(target=auto_poem_worker, daemon=True).start()
    bot.infinity_polling(timeout=60, none_stop=True)
