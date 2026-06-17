# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz, random, re, html
from threading import Thread, Lock
from datetime import datetime

# Phòng chống crash nếu thiếu file keep_alive.py khi chạy trên Replit
try:
    from keep_alive import keep_alive
    keep_alive()
except ImportError:
    print("[CẢNH BÁO] Không tìm thấy keep_alive.py, bỏ qua luồng treo 24/7...")

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# KHUYẾN KHÍCH: Thay các chuỗi dưới đây bằng os.getenv("TÊN_BIẾN") để bảo mật tuyệt đối
TOKEN = "8080338995:AAFt2FiCfDdmVB01ybOsdum7iQd3400OCfo"
ALLOWED_GROUP_ID, ADMIN_ID = -1003925717296, 5736655322      

bot = telebot.TeleBot(TOKEN, num_threads=15)  
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

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

# KHO THOẠI KHỊA TRẺ TRÂU TỰ ĐỘNG THEO GIỜ
KHO_KHIA = [
    "Lo mà học hành đi con ạ, bớt cào bàn phím với ảo tưởng giang hồ mạng lại.",
    "Mở mồm ra là tưởng mình ngầu, nhìn lại xem chả khác gì thằng hề tấu hài.",
    "Đầu toàn bã đậu mà thích thể hiện, ra đời người ta vả cho không trượt phát nào.",
    "Suốt ngày cắm mặt vào ba cái video vô tri, tương lai mù mịt như tiền đồ chị Dậu nha con.",
    "Bớt bớt cái thói ăn nói xà lơ lại, nứt mắt ra đã thích làm đại ca mạng xã hội.",
    "Người ta khinh không thèm nói chứ tưởng mình là trung tâm vũ trụ chắc?",
    "Gớm, oai hùm trên mạng làm gì, về nhà mẹ bảo rửa bát còn phụng phịu.",
    "Đã dốt còn hay nói chữ, bớt tỏ ra nguy hiểm giùm cái đi con ranh."
]

# KHO THƠ KHỊA ĐỘC QUYỀN
KHO_THO_KHIA = [
    "Trẻ trâu lướt mạng suốt ngày\nMẹ gọi nấu cơm thì giả vờ say.",
    "Học hành thì chẳng ra chi\nLên mạng cào phím làm gì hả con?",
    "Thùng rỗng thì kêu rất to\nĐầu không có chữ chỉ lo thể hiện.",
    "Đời còn dài lắm ai ơi\nBớt bớt khua môi kẻo đời vả cho.",
    "Cào phím thì rõ là nhanh\nĐến khi học toán mắt lanh chanh sầu.",
    "Ra đường tinh tướng anh hào\nVề nhà sợ mẹ cầm cào rượt quanh."
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
    with memory_lock:  # Đảm bảo Thread-safe tuyệt đối khi ghi file
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
    return m.chat.id == ALLOWED_GROUP_ID

def is_admin(m):
    return m.from_user.id == ADMIN_ID

def clean_dynamic_text(text):
    clean_text = re.sub(r'\*.*?\*', '', text)
    clean_text = re.sub(r'[_*`\[\]()]', '', clean_text)
    return clean_text.strip()

def check_antispam(m):
    if is_admin(m): return False
    uid = m.from_user.id
    now = time.time()
    
    if uid not in SPAM_LOGS:
        SPAM_LOGS[uid] = []
        
    SPAM_LOGS[uid] = [t for t in SPAM_LOGS[uid] if now - t < SPAM_WINDOW]
    SPAM_LOGS[uid].append(now)
    
    if len(SPAM_LOGS[uid]) > MAX_MESSAGES:
        try:
            bot.delete_message(m.chat.id, m.message_id)
            warn = bot.send_message(m.chat.id, f"⚠️ Thằng lỏ <b>{html.escape(m.from_user.first_name)}</b> kia! Cào bàn phím chậm thôi không tao vả gãy răng bây giờ, spam trôi hết bài!", parse_mode="HTML")
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
            warn_msg = ask_ai("Phát hiện một thằng rác rưởi quăng link quảng cáo bẩn vô nhóm. Hãy chửi thẳng mặt nó thật gắt.")
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {html.escape(warn_msg)}", parse_mode="HTML").message_id, 30)
        except: pass
        return True
    return False

def ask_ai(prompt):
    global current_key_index, group_memory
    group_memory.append({"role": "user", "content": prompt})
    
    # SYSTEM PROMPT: CHẾ ĐỘ CHỬI KHỊA TRẺ TRÂU AUTO THẤM
    sys_content = (
        "Bạn là một kẻ cọc cằn, đanh đá, chuyên đi khịa và chửi xéo lũ trẻ trâu ảo tưởng sức mạnh trên mạng. "
        "Ăn nói gắt gỏng, thô lỗ nhưng cực kỳ thấm, dùng từ ngữ góc cạnh, xưng 'tao' gọi 'mày' hoặc 'thằng lỏ'. "
        "Trả lời cực kỳ ngắn gọn dưới 15 từ, tuyệt đối không dùng emoji."
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
    return "Tao đang bận chửi đứa khác, tí quay lại nói chuyện với mày sau!"

@bot.message_handler(content_types=['document'])
def handle_incoming_file(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return 
    save_active_user(m.from_user.id, m.from_user.first_name)
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Gửi file dồn dập thế định khủng bố bố mày à? Tí rảnh tao xem!", parse_mode="HTML").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File nặng vcl, giữ lấy mà xài chứ bộ nhớ tao không chứa rác.", parse_mode="HTML").message_id, 5)

    loading = bot.reply_to(m, "Đợi tí xem cái đống mã nguồn rác rưởi của mày có gì nào...", parse_mode="HTML")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            res = ask_ai(f"Mã nguồn của thằng {m.from_user.first_name}:\n{content}")
            bot.delete_message(m.chat.id, loading.message_id)
            delay_delete(m.chat.id, bot.reply_to(m, f"Nghe tao phán nè thằng lỏ:\n{html.escape(res)}", parse_mode="HTML").message_id)
        except: pass
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    text = "<b>Bố đời thiên hạ đã kích hoạt! Chế độ chửi trẻ trâu mở 24/7!</b>\nQuăng link TikTok vào đây tao tải video không logo cho bớt ngứa mắt.\n/tym [link] : Chạy ngầm buff tim.\n/stop : Bật chế độ câm lặng cho tiến trình ngầm."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="HTML").message_id)

@bot.message_handler(commands=['tym'])
def tym_handler(m):
    if not is_allowed_chat(m): return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return
    save_active_user(m.from_user.id, m.from_user.first_name)
    
    parts = m.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return delay_delete(m.chat.id, bot.reply_to(m, "Mắt mù à? Dùng đúng cú pháp giùm: /tym [link_tiktok]", parse_mode="HTML").message_id, 5)
        
    target_url = parts[1].strip()
    uid = m.from_user.id
    if auto_running.get(f"{uid}_tym", False):
        return delay_delete(m.chat.id, bot.reply_to(m, "Nôn nóng cái gì, tiến trình đang chạy sấp mặt rồi!", parse_mode="HTML").message_id, 5)
        
    auto_running[f"{uid}_tym"] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Rồi rồi, tao đang đi buff tim ngầm cho mày rồi đó thằng lỏ mạng!", parse_mode="HTML").message_id, 5)
    Thread(target=tym_worker, args=(uid, target_url, m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Mày không phải sếp tao, sủa tiếp đi tao éo nghe đâu!", parse_mode="HTML")
        except: pass
        return
    if check_antispam(m): return
    if check_and_delete_tele_link(m): return
    uid = m.from_user.id
    
    tym_active = auto_running.get(f"{uid}_tym", False)
    if tym_active:
        auto_running[f"{uid}_tym"] = False
        delay_delete(m.chat.id, bot.reply_to(m, "Tao đã dập tắt toàn bộ các luồng chạy ngầm rồi nhé.", parse_mode="HTML").message_id, 5)
    else:
        delay_delete(m.chat.id, bot.reply_to(m, "Có luồng nào đang chạy đâu mà bắt tao dừng? Tháo não ra à?", parse_mode="HTML").message_id, 5)

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
        return delay_delete(m.chat.id, bot.reply_to(m, "Nhắn lắm thế, câm mồm vài giây đợi tao load dữ liệu!", parse_mode="HTML").message_id, 3)

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
            text = f"🔥 Thêm một thành viên mới tên là <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào xới bạc. Vào đây xem tao khịa tụi trẻ trâu nè con!\n<i>(Xóa sau 30s)</i>"
            delay_delete(m.chat.id, bot.send_message(m.chat.id, text, parse_mode="HTML").message_id, 30)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_member(m):
    if is_allowed_chat(m):
        u = m.left_chat_member
        if u.id == BOT_INFO.id: return
        text = f"🍂 Thằng lỏ <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> chịu nhiệt không nổi đã cút khỏi nhóm rồi... Tiễn vong nha con!\n<i>(Xóa sau 30s)</i>"
        delay_delete(m.chat.id, bot.send_message(m.chat.id, text, parse_mode="HTML").message_id, 30)

def download_and_send_video(url, chat_id, reply_id):
    try:
        api_url = f"https://api.tikwm.com/api/?url={urllib.parse.quote(url)}"
        res = http_session.get(api_url, timeout=10).json()
        if res.get("code") == 0:
            video_res = http_session.get(res["data"].get("play"), timeout=25)
            msg = bot.send_video(chat_id, io.BytesIO(video_res.content), reply_to_message_id=reply_id, caption="Của mày nè, xem xong thì câm mồm giùm (Xóa sau 30s)", parse_mode="HTML")
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
                    msg = bot.send_message(chat_id, f"⚡ <b>[BUFF TIM XONG RỒI THẰNG LỎ]</b>\nRequest thành công, sướng nhé!\nThời gian: {t}", parse_mode="HTML")
                else:
                    msg = bot.send_message(chat_id, f"❌ API buff tim báo lỗi rồi: {resp.status_code}")
                delay_delete(chat_id, msg.message_id, 30)
        except Exception as e:
            print(f"[LỖI WORKER]: {e}")
        
        # ĐÃ VÁ LỖI: Đưa luồng ngủ ra ngoài khối try-except để chắc chắn bot dừng 10 phút, tránh lặp vô hạn gây cháy CPU
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
                    text = f"🔔 <b>Đúng {now.strftime('%H:%M')} rồi!</b>\nThằng lỏ <a href='tg://user?id={target_id}'>{html.escape(target_name)}</a> ơi... Nghe tao bảo này: {random.choice(KHO_KHIA)}\n<i>(Tự hủy sau 15s)</i>"
                    delay_delete(ALLOWED_GROUP_ID, bot.send_message(ALLOWED_GROUP_ID, text, parse_mode="HTML").message_id, 15)
                last_sent_hour = now.hour
            if now.minute != 0: last_sent_hour = -1
        except: pass
        time.sleep(25)

def auto_poem_worker():
    while True:
        time.sleep(3600)  # Cứ mỗi tiếng khịa một bài thơ
        try:
            tho = random.choice(KHO_THO_KHIA)
            text = f"🌸 <b>Gửi tặng lũ trẻ trâu trong nhóm một bài thơ tỉnh ngộ:</b>\n\n<i>{tho}</i>\n\n<i>(Tao tự xóa sau 15s cho đỡ rác nhóm)</i>"
            msg = bot.send_message(ALLOWED_GROUP_ID, text, parse_mode="HTML")
            delay_delete(ALLOWED_GROUP_ID, msg.message_id, 15)
        except: pass

if __name__ == "__main__":
    print("Bot chửi trẻ trâu đã khởi động thành công và đang quét mục tiêu...")
    Thread(target=scheduled_time_worker, daemon=True).start()
    Thread(target=auto_poem_worker, daemon=True).start()
    bot.infinity_polling(timeout=60, none_stop=True)
