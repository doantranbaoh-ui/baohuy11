# -*- coding: utf-8 -*-
import sys, io, time, urllib.parse, os, json, requests, telebot, pytz
from threading import Thread, Lock
from requests.exceptions import RequestException, Timeout
from datetime import datetime
from keep_alive import keep_alive

if sys.stdout.encoding != 'utf-8': sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8': sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
ALLOWED_GROUP_ID = -1003872001041 
ADMIN_ID = 5736655322              

bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
keep_alive()
http_session = requests.Session()

user_cooldowns, ai_cooldowns, auto_running = {}, {}, {}
COOLDOWN_TIME, AI_COOLDOWN_TIME, AUTO_DELAY, DELETE_DELAY = 7, 15, 600, 300
MEMORY_FILE, MAX_MEMORY_KEYS, MAX_FILE_SIZE_KB = "bot_memory.json", 15, 500
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
    try: bot.reply_to(m, "❌ Bản quyền rách k có mà đòi xài ak? 🤡")
    except: pass
    return False

def is_admin(m):
    if m.from_user.id == ADMIN_ID: return True
    try: bot.reply_to(m, "👑 Bớt ảo quyền lực, tml tuổi j đòi bấm? 😏")
    except: pass
    return False

def backup_free_ai(msgs):
    try:
        res = http_session.post("https://api.chatape.com/v1/chat/completions", json={"model": "gpt-3.5-turbo", "messages": msgs, "temperature": 0.5}, timeout=12)
        if res.status_code == 200: return res.json()['choices'][0]['message']['content'].strip()
    except: pass
    return "⚠️ Server oẳng rùi, hỏi lắm vcl tí hỏi lại xem nào! 😏"

def ask_ai(prompt):
    global current_key_index, group_memory
    sys_prompt = "Bạn là một thằng trẻ trâu anh hùng bàn phím khinh người, coi thiên hạ là lũ rác rưởi hạ đẳng nghèo nàn, ngu dốt. Nói chuyện bằng giọng bề trên, mỉa mai, dùng ngôn ngữ mạng và teencode cực nặng (j, thía, bít rùi, k, thui, vcl, ak, m, t). Trả lời siêu ngắn, gọn, thô lỗ, đốp chát. BẮT BUỘC luôn kèm theo các icon khinh bỉ như (🤡, 😏, 😮‍💨, 🤔, 👀) ở cuối câu hoặc giữa câu để khịa. Tuyệt đối không chào hỏi, không lịch sự."
    messages = [{"role": "system", "content": sys_prompt}] + group_memory + [{"role": "user", "content": prompt}]
    
    for _ in range(len(AI_KEYS)):
        act = AI_KEYS[current_key_index]
        if not act["status"]:
            current_key_index = (current_key_index + 1) % len(AI_KEYS)
            continue
        headers = {"Authorization": f"Bearer {act['key']}", "Content-Type": "application/json"}
        for model in [act["model"], "gpt-4o-mini", "gpt-3.5-turbo"]:
            try:
                res = http_session.post(act["url"], json={"model": model, "messages": messages, "max_tokens": 1000, "temperature": 0.8}, headers=headers, timeout=20)
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
        return delay_delete(m.chat.id, bot.reply_to(m, "⏳ Spam nhanh vcl, chờ tí tml vội đi đầu thai ak? 🤡").message_id, 5)
    if m.document.file_size > 300000: 
        return delay_delete(m.chat.id, bot.reply_to(m, "⚠️ File to vcl bố m k thèm đọc. 😏").message_id, 5)

    loading = bot.reply_to(m, "📂 Quăng cái code rách lên đây ngó tí xem ngu chỗ j nào... 👀")
    ai_cooldowns[uid] = cur_time
    try:
        content = bot.download_file(bot.get_file(m.document.file_id).file_path).decode('utf-8', errors='ignore')
        if not content.strip(): return bot.edit_message_text("❌ File trống rỗng đem lên lòe ai ak tml! 🤡", m.chat.id, loading.message_id)
        _, ext = os.path.splitext(m.document.file_name.lower())
        res = ask_ai(f"Phân tích nhanh file {ext}, tìm lỗi sai logic/cú pháp nếu là code và trả về đoạn code đã sửa tối ưu, ngắn gọn nhất:\n\n{content}")
        try: bot.delete_message(m.chat.id, loading.message_id)
        except: pass
        delay_delete(m.chat.id, bot.reply_to(m, f"📊 **DỌN RÁC XONG (`{m.document.file_name}`):**\n\n{res}").message_id)
    except: bot.edit_message_text("❌ Lỗi cmnr, code ngu quá làm bot sập! 😮‍💨", m.chat.id, loading.message_id)

@bot.message_handler(commands=['start'])
def start(m):
    if not is_allowed_chat(m): return
    text = "🤡 **BOT TRẺ TRÂU BỐ ĐỜI** 🤡\n💬 **Chat:** Nhắn trực tiếp để nghe khịa.\n📂 **Check Code:** Gửi file sửa lỗi nhanh 😏.\n👉 `/like [link]` : Buff tim TikTok thủ công.\n👑 `/auto [link]` : Auto buff 10p/lần (Admin).\n👑 `/stop` : Tắt auto 😮‍💨."
    delay_delete(m.chat.id, bot.reply_to(m, text, parse_mode="Markdown").message_id)

@bot.message_handler(commands=['like'])
def like(m):
    if not is_allowed_chat(m): return
    uid, cur_time = m.from_user.id, time.time()
    if uid in user_cooldowns and (cur_time - user_cooldowns[uid]) < COOLDOWN_TIME:
        return delay_delete(m.chat.id, bot.reply_to(m, "⏳ Bấm nhanh vcl rách nút, chậm lại tml! 😏").message_id, 4)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower():
        return delay_delete(m.chat.id, bot.reply_to(m, "❌ Đưa cái link rách nát j thía này! 🤡").message_id, 5)

    loading = bot.reply_to(m, "⏳ Đang kết nối server, súc vật chờ tí... 👀")
    user_cooldowns[uid] = cur_time  
    suc, res = execute_buff_api(args[1].strip())
    bot.edit_message_text(res, m.chat.id, loading.message_id, parse_mode="Markdown" if suc else None)
    delay_delete(m.chat.id, loading.message_id, 30 if suc else 10)

@bot.message_handler(commands=['auto'])
def auto(m):
    if not is_allowed_chat(m) or not is_admin(m): return
    uid = m.from_user.id
    if auto_running.get(uid, False): return delay_delete(m.chat.id, bot.reply_to(m, "⚠️ Auto đang chạy lù lù ra rồi bật lắm vcl. 😮‍💨").message_id, 5)
    args = m.text.split(maxsplit=1)
    if len(args) < 2 or "tiktok" not in args[1].lower(): return delay_delete(m.chat.id, bot.reply_to(m, "❌ Link sai kìa tml, mắt m bị mù ak! 🤡").message_id, 5)

    auto_running[uid] = True
    delay_delete(m.chat.id, bot.reply_to(m, "🚀 **ĐÃ BẬT AUTO** (Ngồi im xem bố m diễn kịch).").message_id, 10)
    Thread(target=auto_worker, args=(uid, args[1].strip(), m.chat.id), daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_allowed_chat(m) or not is_admin(m): return
    uid = m.from_user.id
    auto_running[uid] = False
    delay_delete(m.chat.id, bot.reply_to(m, "🛑 Tắt cmnr ngon thì tự đi mà buff." if auto_running.get(uid, False) else "ℹ️ Có cái j đang chạy đâu mà tắt hả tml nghèo? 😏").message_id, 5)

@bot.message_handler(func=lambda m: m.chat.id == ALLOWED_GROUP_ID and m.text and not m.text.startswith('/'))
def reply_with_ai(m):
    uid, cur_time = m.from_user.id, time.time()
    if uid in ai_cooldowns and (cur_time - ai_cooldowns[uid]) < 4: 
        return delay_delete(m.chat.id, bot.reply_to(m, "⏳ Cào phím nhanh vcl định ăn tươi nuốt sống t ak? 😮‍💨").message_id, 3)
    try: bot.send_chat_action(m.chat.id, 'typing')
    except: pass
    ai_cooldowns[uid] = cur_time  
    Thread(target=lambda: delay_delete(m.chat.id, bot.reply_to(m, ask_ai(m.text)).message_id), daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(m):
    if is_allowed_chat(m):
        for u in m.new_chat_members: delay_delete(m.chat.id, bot.send_message(m.chat.id, "👋 Thêm một tml ngu ngơ gia nhập bầy! 🤡").message_id, 60)

def auto_worker(uid, url, chat_id):
    while auto_running.get(uid, False):
        suc, res = execute_buff_api(url)
        delay_delete(chat_id, bot.send_message(chat_id, f"🔄 **[AUTO CHU KỲ]**\n{res}", parse_mode="Markdown" if suc else None).message_id, 120 if suc else 30)
        for _ in range(AUTO_DELAY):
            if not auto_running.get(uid, False): return
            time.sleep(1)

def execute_buff_api(url):
    try:
        res = http_session.get(f"https://tiktokvm.vercel.app/api/likes?url={urllib.parse.quote(url)}", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        t = datetime.now(VN_TZ).strftime("%H:%M - %d/%m")
        if res.status_code == 200:
            try:
                res.encoding = 'utf-8'
                d = res.json()
                return True, f"🚀 **BUFF TIM THÀNH CÔNG**\n👤 **User:** {d.get('username') or d.get('user') or 'TikTok User'}\n➕ **Status:** +{d.get('added') or d.get('count') or 'OK'}\n🕒 {t}"
            except: return True, f"🚀 **BUFF TIM XONG**\n👤 **User:** Hệ thống\n➕ **Status:** Đang chạy\n🕒 {t}"
        return False, f"Server sập cmnr (Mã {res.status_code}) 🤔"
    except Timeout: return False, "Nghẽn mạng rồi, chờ mút chỉ đi! 😮‍💨"
    except RequestException: return False, "Mất kết nối server rách! 👀"
    except: return False, "Lỗi j r méo bít nữa! 🤡"

if __name__ == "__main__":
    print("🚀 Khởi chạy thành công...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
