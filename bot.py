# -*- coding: utf-8 -*-
import sys, io, os, json, time, random, re, html, hashlib, subprocess, socket
from threading import Thread, Lock
from datetime import datetime, timedelta
from collections import deque, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from keep_alive import keep_alive
    keep_alive()
except ImportError:
    print("[!] No keep_alive.py")

import telebot, requests, pytz

# ==================== NÃO ROBOT (BRAIN) ====================
class Brain:
    """Não điều khiển bot - tự học, tự sửa, tự quyết định"""
    def __init__(self):
        self.state = "normal"  # normal | aggressive | sleep | repair
        self.mood = 0  # -10 đến 10
        self.learned = defaultdict(int)  # học từ user
        self.banned_words = set()
        self.trusted_users = set()
        self.stats = {"msg": 0, "spam_blocked": 0, "ai_called": 0, "errors": 0, "uptime": time.time()}
        self.decision_log = deque(maxlen=100)
        self.last_health_check = time.time()
        self.repair_mode = False
        self.load_brain()
        
    def load_brain(self):
        if os.path.exists("brain.json"):
            try:
                with open("brain.json", "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.learned = defaultdict(int, d.get("learned", {}))
                    self.banned_words = set(d.get("banned", []))
                    self.trusted_users = set(d.get("trusted", []))
                    self.stats = d.get("stats", self.stats)
            except: pass
    
    def save_brain(self):
        with open("brain.json", "w", encoding="utf-8") as f:
            json.dump({
                "learned": dict(self.learned),
                "banned": list(self.banned_words),
                "trusted": list(self.trusted_users),
                "stats": self.stats,
                "state": self.state,
                "mood": self.mood
            }, f, ensure_ascii=False, indent=2)
    
    def think(self, context):
        """Quyết định hành động dựa trên context"""
        uid, txt, cmd = context.get("uid"), context.get("txt", ""), context.get("cmd", False)
        self.stats["msg"] += 1
        
        # Học từ user
        words = re.findall(r'\w+', txt.lower())
        for w in words:
            self.learned[w] += 1
        
        # Điều chỉnh mood
        if any(x in txt.lower() for x in ["bot ngu", "bot dở", "bot lỗi"]):
            self.mood -= 2
        elif any(x in txt.lower() for x in ["bot hay", "bot pro", "cảm ơn bot"]):
            self.mood += 1
        
        # Quyết định
        if self.mood < -5:
            self.state = "aggressive"
        elif self.mood > 5:
            self.state = "normal"
        
        self.decision_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "uid": uid,
            "decision": self.state,
            "mood": self.mood
        })
        self.save_brain()
        return self.state
    
    def should_reply(self, uid, txt):
        """Quyết định có trả lời không"""
        if uid in self.trusted_users:
            return True
        if self.learned.get(txt.lower(), 0) > 5:  # đã hỏi nhiều lần
            return random.random() > 0.3  # 70% trả lời
        return random.random() > 0.1  # 90% trả lời
    
    def get_insult_level(self):
        """Mức độ chửi dựa trên mood"""
        if self.state == "aggressive":
            return "extreme"
        elif self.mood < 0:
            return "high"
        return "normal"
    
    def health_check(self):
        """Kiểm tra sức khỏe não"""
        now = time.time()
        if now - self.last_health_check > 300:  # 5 phút
            self.last_health_check = now
            # Tự sửa nếu error nhiều
            if self.stats["errors"] > 20:
                self.repair_mode = True
                self.state = "repair"
                self.stats["errors"] = 0
                return "repair"
            self.save_brain()
        return "ok"

brain = Brain()

# ==================== CẤU HÌNH ====================
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAFt2FiCfDdmVB01ybOsdum7iQd3400OCfo")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=25)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
ses = requests.Session()
ses.mount('https://', requests.adapters.HTTPAdapter(pool_connections=150, pool_maxsize=300, max_retries=3))
ses.mount('http://', requests.adapters.HTTPAdapter(pool_connections=150, pool_maxsize=300, max_retries=3))

# ==================== AI KEYS (TỰ SỬA - NÃO QUẢN LÝ) ====================
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0}
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ==================== KHO CHỬI (NÃO CHỌN THEO MOOD) ====================
KHO_NORMAL = [
    "Mồm thối, câm đi.",
    "Não bã đậu, im lặng.",
    "Thùng rỗng kêu to.",
    "Cào phím nhanh, não chậm.",
    "Ảo tưởng sức mạnh.",
    "Về nhà rửa bát.",
    "IQ âm, đừng nói.",
    "Không ai cần mày.",
    "Mày là gì? Không là gì.",
    "Câm mồm, đỡ nhục."
]

KHO_HIGH = [
    "Nứt mắt đòi làm anh hùng.",
    "Đầu rỗng, mồm thối.",
    "Mạng xã hội nuôi mày à?",
    "Ra đời người ta vả cho.",
    "Mẹ gọi, về nhà đi.",
    "Tưởng mình ngầu? Hề vãi.",
    "Học không lo, cào phím giỏi.",
    "Tương lai mù mịt như chị Dậu.",
    "Đời vả mặt, mày cười ngây.",
    "Không có gì để nói với mày."
]

KHO_EXTREME = [
    "Mày đáng giá bằng cái nút block thôi.",
    "Tồn tại để làm gì? Để tao chửi à?",
    "Não mày như ổ đĩa format nhầm - trống trơn.",
    "Mày là lỗi của tự nhiên, bug của xã hội.",
    "Tao chửi mày còn thấy phí thời gian.",
    "Mày không đáng để tao nhớ tên.",
    "Cút về lỗ mà mày chui ra.",
    "Mày là minh chứng cho thất bại của tiến hóa.",
    "Tao nhìn mày mà tưởng đang xem phim hài.",
    "Mày sống làm gì? Để tổn thương người khác à?"
]

def get_kho():
    lvl = brain.get_insult_level()
    if lvl == "extreme": return KHO_EXTREME
    elif lvl == "high": return KHO_HIGH
    return KHO_NORMAL

# ==================== BIẾN ====================
lock = Lock()
mem = deque(maxlen=50)
users = {}
spam = {}
cd = {}
ai_cd = {}
auto = {}
warn = {}
MEM_FILE, USR_FILE = "mem.json", "usr.json"

TIKTOK = re.compile(r'https?://(?:vm|vt|www|m)\.tiktok\.com/\S+', re.I)
TELE = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}', re.I)

# ==================== TIỆN ÍCH ====================
def load(f): return json.load(open(f,encoding='utf-8')) if os.path.exists(f) and os.path.getsize(f)<512000 else {}
def save(f,d): 
    with lock: json.dump(d,open(f,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
def del_msg(c,m,t=60): Thread(target=lambda:(time.sleep(t),bot.delete_message(c,m)),daemon=True).start()
def is_ad(m): return m.from_user.id == ADMIN_ID
def is_grp(m): return m.chat.id == GROUP_ID

# ==================== AI TỰ SỬA (NÃO GIÁM SÁT) ====================
def ask_ai(prompt, uid=None):
    global ck_idx
    # Não quyết định có dùng AI không
    if brain.state == "sleep":
        return random.choice(get_kho())
    
    sys_msg = "Bạn là kẻ cọc cằn, chửi khịa trẻ trâu. Xưng 'tao' gọi 'mày'. Trả lời dưới 12 từ, không emoji."
    msgs = [{"role":"system","content":sys_msg}] + [{"role":"user","content":x} for x in list(mem)[-10:]] + [{"role":"user","content":prompt}]
    
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                r = ses.post(k["url"], json={"model":k["model"],"messages":msgs,"max_tokens":50,"temperature":0.95},
                           headers={"Authorization":f"Bearer {k['key']}","Content-Type":"application/json"}, timeout=12)
                if r.status_code == 200:
                    txt = r.json()['choices'][0]['message']['content'].strip()
                    txt = re.sub(r'[_*`\[\]()]','',txt)
                    k["fail"], k["last_used"] = 0, time.time()
                    mem.append(prompt)
                    mem.append(txt)
                    brain.stats["ai_called"] += 1
                    return txt
                else:
                    k["fail"] += 1
                    if k["fail"] >= MAX_FAIL: k["status"] = False
            except Exception as e:
                k["fail"] += 1
                if k["fail"] >= MAX_FAIL: k["status"] = False
                brain.stats["errors"] += 1
                print(f"[AI FAIL {ck_idx}]: {e}")
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
    
    # NÃO TỰ SỬA: Reset nếu tất cả die
    if not any(x["status"] for x in AI_KEYS):
        for x in AI_KEYS: 
            x["status"], x["fail"] = True, 0
        brain.stats["errors"] = 0
        brain.state = "repair"
        print("[NÃO] Tất cả AI key được tự sửa")
        return "[Não tự sửa] AI đã reset. Thử lại sau 5s."
    return random.choice(get_kho())

# ==================== ANTI-SPAM (NÃO QUẢN LÝ) ====================
def antispam(m):
    if is_ad(m): return False
    u, n = m.from_user.id, time.time()
    spam[u] = [t for t in spam.get(u,[]) if n-t<4] + [n]
    if len(spam[u]) > 5:
        warn[u] = warn.get(u,0) + 1
        brain.stats["spam_blocked"] += 1
        try:
            bot.delete_message(m.chat.id, m.message_id)
            t = f"🚫 Bị ban!" if warn[u]>=3 else f"⚠️ Spam {warn[u]}/3"
            w = bot.send_message(m.chat.id, f"{t} <b>{html.escape(m.from_user.first_name)}</b>", parse_mode="HTML")
            del_msg(m.chat.id, w.message_id, 15)
        except: pass
        return True
    return False

def antilink(m):
    if is_ad(m): return False
    t = (m.text or "") + (m.caption or "")
    if TELE.search(t):
        try: bot.delete_message(m.chat.id,m.message_id); w=bot.send_message(m.chat.id,f"⚠️ Link bẩn. {random.choice(get_kho())}",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,30)
        except: pass
        return True
    return False

# ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m) or antispam(m) or antilink(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save(USR_FILE,users)
    brain.trusted_users.add(m.from_user.id)
    msg = bot.reply_to(m,"<b>🧠 Não Robot khởi động.</b>\n/tym [link] = buff\nTikTok = tải\nTag = chat\n/brain = xem não\n<i>(Xóa 60s)</i>",parse_mode="HTML")
    del_msg(m.chat.id,msg.message_id,60)

@bot.message_handler(commands=['brain'])
def brain_cmd(m):
    if not is_grp(m): return
    if not is_ad(m):
        return del_msg(m.chat.id,bot.reply_to(m,"⛔ Mày không đủ quyền xem não tao.",parse_mode="HTML").message_id,10)
    uptime = int(time.time() - brain.stats["uptime"])
    txt = (f"🧠 <b>TRẠNG THÁI NÃO</b>\n"
           f"State: <code>{brain.state}</code>\n"
           f"Mood: <code>{brain.mood}</code>\n"
           f"Msgs: <code>{brain.stats['msg']}</code>\n"
           f"Spam blocked: <code>{brain.stats['spam_blocked']}</code>\n"
           f"AI called: <code>{brain.stats['ai_called']}</code>\n"
           f"Errors: <code>{brain.stats['errors']}</code>\n"
           f"Uptime: <code>{uptime//3600}h{(uptime%3600)//60}m</code>\n"
           f"Trusted: <code>{len(brain.trusted_users)}</code>\n"
           f"Learned words: <code>{len(brain.learned)}</code>")
    msg = bot.reply_to(m, txt, parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(commands=['tym'])
def tym(m):
    if not is_grp(m) or antispam(m) or antilink(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save(USR_FILE,users)
    p = m.text.strip().split(maxsplit=1)
    if len(p)<2: return del_msg(m.chat.id,bot.reply_to(m,"Cú pháp: /tym [link]",parse_mode="HTML").message_id,5)
    u = m.from_user.id
    if auto.get(f"{u}_tym"): return del_msg(m.chat.id,bot.reply_to(m,"Đang chạy!",parse_mode="HTML").message_id,5)
    auto[f"{u}_tym"] = True
    del_msg(m.chat.id,bot.reply_to(m,"Buff tim...",parse_mode="HTML").message_id,5)
    Thread(target=tym_wk,args=(u,p[1],m.chat.id),daemon=True).start()

@bot.message_handler(commands=['stop'])
def stop(m):
    if not is_grp(m) or not is_ad(m): return
    u = m.from_user.id
    if auto.get(f"{u}_tym"):
        auto[f"{u}_tym"] = False
        del_msg(m.chat.id,bot.reply_to(m,"Đã dừng.",parse_mode="HTML").message_id,5)
    else:
        del_msg(m.chat.id,bot.reply_to(m,"Không có gì chạy.",parse_mode="HTML").message_id,5)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def txt(m):
    if antispam(m) or antilink(m) or m.text.startswith('/'): return
    users[str(m.from_user.id)] = m.from_user.first_name; save(USR_FILE,users)
    
    # Não suy nghĩ
    brain.think({"uid": m.from_user.id, "txt": m.text, "cmd": False})
    
    match = TIKTOK.search(m.text)
    if match: Thread(target=dl_vid,args=(match.group(0),m.chat.id,m.message_id),daemon=True).start(); return
    
    u = m.from_user.id
    if not brain.should_reply(u, m.text):
        return  # Não quyết định không trả lời
    
    if u in ai_cd and time.time()-ai_cd[u] < 3: return del_msg(m.chat.id,bot.reply_to(m,"Đợi 3s.",parse_mode="HTML").message_id,3)
    ai_cd[u] = time.time()
    try: bot.send_chat_action(m.chat.id,'typing')
    except: pass
    def run():
        r = ask_ai(m.text, u)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id):
            bot.reply_to(m,html.escape(r),parse_mode="HTML")
        else:
            del_msg(m.chat.id,bot.reply_to(m,html.escape(r),parse_mode="HTML").message_id)
    Thread(target=run,daemon=True).start()

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    for u in m.new_chat_members:
        if u.id == bot.get_me().id: continue
        users[str(u.id)] = u.first_name; save(USR_FILE,users)
        msg = bot.send_message(m.chat.id,f"🔥 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào. {random.choice(get_kho())} <i>(Xóa 30s)</i>",parse_mode="HTML")
        del_msg(m.chat.id,msg.message_id,30)

@bot.message_handler(content_types=['left_chat_member'])
def bye(m):
    if not is_grp(m): return
    u = m.left_chat_member
    if u.id == bot.get_me().id: return
    msg = bot.send_message(m.chat.id,f"🍂 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> cút. {random.choice(get_kho())} <i>(Xóa 30s)</i>",parse_mode="HTML")
    del_msg(m.chat.id,msg.message_id,30)

# ==================== WORKERS ====================
def dl_vid(url,cid,rid):
    try:
        r = ses.get(f"https://api.tikwm.com/api/?url={requests.utils.quote(url)}",timeout=15).json()
        if r.get("code")==0:
            v = ses.get(r["data"]["play"],timeout=30).content
            msg = bot.send_video(cid,io.BytesIO(v),reply_to_message_id=rid,caption=f"🎬 Của mày. <i>(Xóa 60s)</i>",parse_mode="HTML")
            del_msg(cid,msg.message_id,60)
    except Exception as e: 
        brain.stats["errors"] += 1
        print(f"[DL ERR]: {e}")

def tym_wk(uid,url,cid):
    cyc = 0
    while auto.get(f"{uid}_tym"):
        cyc += 1
        try:
            r = ses.get(f"https://api.tikwm.com/api/?url={requests.utils.quote(url)}",timeout=15).json()
            if r.get("code")==0:
                u = requests.utils.quote(r["data"]["play"])
                resp = ses.get(f"http://abcdxyz310107.x10.mx/tim.php?url={u}",headers={"User-Agent":"Mozilla/5.0"},timeout=15)
                t = datetime.now(tz).strftime("%H:%M %d/%m")
                msg = bot.send_message(cid,f"⚡ [#{cyc}] {'✅' if resp.status_code==200 else '❌'+str(resp.status_code)} | {t}",parse_mode="HTML")
                del_msg(cid,msg.message_id,30)
        except Exception as e: 
            brain.stats["errors"] += 1
            print(f"[TYM ERR]: {e}")
        for _ in range(600):
            if not auto.get(f"{uid}_tym"): return
            time.sleep(1)

def sched():
    last = -1
    while True:
        try:
            n = datetime.now(tz)
            # Não health check
            brain.health_check()
            if brain.state == "repair":
                brain.state = "normal"
                brain.repair_mode = False
            
            if n.minute==0 and n.hour!=last and users:
                uid,uname = random.choice(list(users.items()))
                msg = bot.send_message(GROUP_ID,f"🔔 <b>{n.strftime('%H:%M')}</b> | <a href='tg://user?id={uid}'>{html.escape(uname)}</a>... {random.choice(get_kho())} <i>(Xóa 15s)</i>",parse_mode="HTML")
                del_msg(GROUP_ID,msg.message_id,15); last=n.hour
            if n.minute!=0: last=-1
        except: pass
        time.sleep(20)

def poem():
    while True:
        time.sleep(3600)
        try:
            msg = bot.send_message(GROUP_ID,f"🌸 <b>Thơ:</b>\n<i>{random.choice(get_kho())}</i>\n<i>(Xóa 20s)</i>",parse_mode="HTML")
            del_msg(GROUP_ID,msg.message_id,20)
        except: pass

# ==================== MAIN ====================
if __name__ == "__main__":
    loaded = load(USR_FILE)
    if isinstance(loaded,dict): users = loaded
    print(f"[{datetime.now(tz).strftime('%H:%M:%S')}] 🧠 Não Robot khởi động | Users: {len(users)} | Mood: {brain.mood}")
    Thread(target=sched,daemon=True).start()
    Thread(target=poem,daemon=True).start()
    bot.infinity_polling(timeout=60,none_stop=True)
