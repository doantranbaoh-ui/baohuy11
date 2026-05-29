# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz, random, re
from threading import Thread, Lock
from requests.exceptions import RequestException, Timeout
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID, ADMIN_ID = -1003872001041, 5736655322              

bot = telebot.TeleBot(TOKEN, num_threads=10)  
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()

BOT_INFO = bot.get_me() # Lấy thông tin username của bot để bắt bài khi bị tag

http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=30)
http_session.mount('https://', adapter)
http_session.mount('http://', adapter)

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 300
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 20, 500
memory_lock = Lock()      

AUTO_KHIA_INTERVAL = 1800  

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
    try: bot.reply_to(m, "Xài lậu ak tml rách?")
    except: pass
    return False

def is_admin(m):
    if m.from_user.id == ADMIN_ID: return True
    return False

def check_and_delete_tele_link(m):
    if is_admin(m): return False
    text_to_check = ""
    if m.text: text_to_check += m.text
    if m.caption: text_to_check += m.caption
    if TELE_LINK_PATTERN.search(text_to_check):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            cay_msg = ask_ai("Chửi một câu cực gắt và khinh bỉ tml vừa định gửi link quảng cáo group tele khác vào nhóm này, đuổi thẳng cổ nó đi.")
            delay_delete(m.chat.id, bot.send_message(m.chat.id, f"⚠️ {cay_msg}").message_id, 30)
        except: pass
        return True
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.5}, timeout=10)
        if res.status_code == 200: return res.json()['choices'][0]['message']['content'].strip()
    except: pass
    return "Sập rồi tml, đừng hỏi nữa."

def ask_ai(prompt, custom_sys=None):
    global current_key_index, group_memory
    sys_prompt = custom_sys if custom_sys else "Bạn là một thằng anh hùng bàn phím vô học, cộc cằn, khinh người tột độ. Nhiệm vụ duy nhất là trả lời thật ngắn gọn nhưng câu nào cũng phải đốp chát, mỉa mai, móc mỉa sâu cay, cố tình gán mác đối phương là nghèo, ngu dốt, hoặc ảo tưởng để chọc cho họ điên tiết và cay cú. Sử dụng ngôn ngữ mạng, teencode nặng (j, thía, bít, k, thui, vcl, ak, m, t). ÉP BUỘC tự chèn các icon cực hãm (🤡, 😏, 😮‍💨, 🤔, 👀) thích hợp vào câu. Không chào hỏi, không giúp đỡ tử tế."
    messages = [{"role": "system", "content": sys_prompt}] + group_memory + [{"role": "user", "content": prompt}]
    
    for _ in range(len(AI_KEYS)):
        act = AI_KEYS[current_key_index]
        if not act["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
        headers = {"Authorization": f"Bearer {act['key']}", "Content-Type": "application/json"}
        for model in [act["model"], "gpt-4o-mini", "gpt-3.5-turbo"]:
            try:
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 1000, "temperature": 0.9}, headers=headers, timeout=15)
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

def auto_khia_worker():
    khia_topics = [
        "Chửi cái nhóm này toàn một lũ tàu ngầm vô dụng, không biết tương tác.",
        "Mỉa mai trình độ code rác rưởi của mấy thằng trong này suốt ngày lỗi.",
        "Sủa một câu vu vơ chê bai đám lười làm đòi có ăn, suốt ngày rình tool free.",
        "Cà khịa việc tụi nó thức đêm cày mấy cái game rách nát để trốn tránh thực tại nghèo khó."
    ]
    while True:
        time.sleep(AUTO_KHIA_INTERVAL)
        try:
            topic = random.choice(khia_topics)
            msg_khia = ask_ai(topic)
            if "Sập rồi" not in msg_khia:
                delay_delete(ALLOWED_GROUP_ID, bot.send_message(ALLOWED_GROUP_ID, msg_khia).message_id)
        except: pass

@bot.message_handler(content_types=['document'])
def handle_incoming_file(m):
    if not is_allowed_chat(m): return
    if check_and_delete_tele_link(m): return 
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < AI_COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Spam nhanh vcl, định ăn tươi nuốt sống t ak?").message_id, 5)
    if m.document.file_size > 500000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "File rác to vcl ai thèm đọc?").message_id, 5)

    loading = bot.reply_to(m, "Ngó xem cái đống rác m gửi là cái j...")
    ai_cooldowns[uid] = cur_time
    def process_file():
        try:
            content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
            if not content.strip(): return bot.edit_message_text("File trống rỗng đem đi lòe trẻ con ak?", m.chat.id, loading.message_id)
            _, ext = os.path.splitext(m.document.file_name.lower())
            
            # CẢI TIẾN 3: Đưa thông tin cá nhân thằng gửi file vào để AI chửi đích danh
            user_name = m.from_user.first_name
            res = ask_ai(f"Thằng rách tên '{user_name}' gửi file {ext} này. Phân tích tìm cái ngu logic của nó và trả về code đã sửa ngắn nhất để khịa nó:\n\n{content}")
            
            try: bot.delete_message(m.chat.id, loading.message_id)
            except: pass
            delay_delete(m.chat.id, bot.reply_to(m, f"Sửa xong cái đống nát của tml `{user_name}` rồi đấy:\n\n{res}").message_id)
        except: bot.edit_message_text("Code ngu quá làm bot lỗi luôn rồi.", m.chat.id, loading.message_id)
    Thread(target=process_file, daemon=True).start()

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    text = "Bố đời AI khởi chạy.\nChat trực tiếp để nghe chửi.\n/like [link] : Buff tim TikTok thủ công.\n/auto [link] : Tự động buff.\n/stop : Tắt auto."
    delay_delete(m.chat.id, bot.reply_to(m, text).message_id)

@bot.message_handler(commands=['like'])
def like(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in user_cooldowns and (cur_time - user_cooldowns[uid]) < COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "Bấm từ từ thôi rách nút tml.").message_id, 4)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        return delay_delete(m.chat.id, bot.reply_to(m, "Ném cái link rác j thía?").message_id, 5)

    loading = bot.reply_to(m, "Chờ tí đi súc vật...")
    user_cooldowns[uid] = cur_time  
    def run_like():
        suc, res = execute_buff_api(args[1].strip())
        bot.edit_message_text(res, m.chat.id, loading.message_id, parse_mode="Markdown" if suc else None)
        delay_delete(m.chat.id, loading.message_id, 30 if suc else 10)
    Thread(target=run_like, daemon=True).start()

@bot.message_handler(commands=['auto'])
def auto(m):
    if not is_allowed_chat(m) or not is_admin(m): 
        try: bot.reply_to(m, "Tuổi j đòi ra lệnh cho bố m?")
        except: pass
        return
    uid = m.from_user.id
    if auto_running.get(uid, False): return delay_delete(m.chat.id, bot.reply_to(m, "Chạy lù lù rồi bật lắm vcl.").message_id, 5)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower(): return delay_delete(m.chat.id, bot.reply_to(m, "Link sai kìa tml mù ak?").message_id, 5)

    auto_running[uid] = True
    delay_delete(m.chat.id, bot.reply_to(m, "Đã bật Auto ngầm.").message_id, 10)
    Thread(target=auto_worker, args=(uid, args[1].strip(), m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m):
        try: bot.reply_to(m, "Tuổi j đòi ra lệnh cho bố m?")
        except: pass
        return
    uid = m.from_user.id
    auto_running[uid] = False
    delay_delete(m.chat.id, bot.reply_to(m, "Tắt rồi ngon tự đi mà làm." if auto_running.get(uid, False) else "Có cái mẹ j đang chạy đâu mà bấm?").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text)
def reply_with_ai(m):
    if check_and_delete_tele_link(m): return 
    if m.text.startswith('/'): return
    
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 4: 
        return delay_delete(m.chat.id, bot.reply_to(m, "Gõ phím nhanh vcl ăn cắp thời gian ak?").message_id, 3)
    
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    
    # CẢI TIẾN 3 & 4: Phát hiện bị tag, bị reply và lấy tên sỉ nhục đích danh
    user_name = m.from_user.first_name
    is_reply_to_bot = m.reply_to_message and m.reply_to_message.from_user.id == BOT_INFO.id
    is_tagged_bot = f"@{BOT_INFO.username}" in m.text
    
    # Ép prompt hệ thống hung hãn hơn nếu tml đó dám động chạm trực tiếp đến bot
    sys_prompt = "Bạn là một thằng anh hùng bàn phím vô học, cộc cằn, khinh người tột độ. Nhiệm vụ duy nhất là trả lời thật ngắn gọn nhưng câu nào cũng phải đốp chát, mỉa mai, móc mỉa sâu cay, cố tình gán mác đối phương là nghèo, ngu dốt, hoặc ảo tưởng để chọc cho họ điên tiết và cay cú. Sử dụng ngôn ngữ mạng, teencode nặng (j, thía, bít, k, thui, vcl, ak, m, t). ÉP BUỘC tự chèn các icon cực hãm (🤡, 😏, 😮‍💨, 🤔, 👀) thích hợp vào câu. Không chào hỏi, không giúp đỡ tử tế."
    if is_reply_to_bot or is_tagged_bot:
        sys_prompt = "Bạn đang bị một tml rách rưới tag tên hoặc reply tin nhắn để đôi co thách thức. Hãy nổi điên lên, chửi bới thật đốp chát, vô học, bố đời, mỉa mai tột cùng vào thẳng mặt nó để nó câm mõm. Trả lời cực ngắn, gọn, hãm tài. Tự động thêm teencode nặng và icon khinh bỉ (🤡, 😏, 😮‍💨)."

    prompt_content = f"Thằng rách tên '{user_name}' vừa sủa câu này trong nhóm: {m.text}. Hãy phản hồi đốp chát trực diện vào nó."

    Thread(target=lambda: delay_delete(m.chat.id, bot.reply_to(m, ask_ai(prompt_content, custom_sys=sys_prompt)).message_id), daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: delay_delete(m.chat.id, bot.send_message(m.chat.id, f"Lại thêm một tml ngu ngơ tên `{u.first_name}` vào bầy.").message_id, 60)

def auto_worker(uid, url, chat_id):
    while auto_running.get(uid, False):
        suc, res = execute_buff_api(url)
        delay_delete(chat_id, bot.send_message(chat_id, f"[AUTO]\n{res}", parse_mode="Markdown" if suc else None).message_id, 120 if suc else 30)
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
                user_info = d.get('username') or d.get('user') or 'TikTok User'
                status_info = d.get('added') or d.get('count') or d.get('msg') or 'Đang xử lý'
                return True, f"Buff xong\nUser: {user_info}\nStatus: {status_info}\nTime: {t}"
            except: 
                return True, f"Buff xong\nUser: Hệ thống\nStatus: Đang chạy dữ liệu\nTime: {t}"
        return False, f"Server oẳng rùi (Mã {res.status_code})"
    except Timeout: return False, "Nghẽn mạng rồi chờ mút chỉ đi."
    except RequestException: return False, "Mất kết nối server rách."
    except: return False, "Lỗi méo bít nữa."

if __name__ == "__main__":
    print("Bot khởi chạy...")
    Thread(target=auto_khia_worker, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
