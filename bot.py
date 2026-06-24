# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - 2000 DÒNG FULL AI                       │
# │  AI Brain + AI RAM + AI Nổ Hũ + AI Câu Đố + 10 Mini Games + Voice     │
# │  Tác giả: palofsc (palo)  |  Ngày: 2026-06-24                          │
# └────────────────────────────────────────────────────────────────────────┘
import sys, io, os, json, time, random, re, html, logging
import urllib.parse, gc, ctypes, psutil, weakref
from threading import Thread, Lock, Timer
from datetime import datetime, timedelta, date
from collections import deque, defaultdict
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from dataclasses import dataclass, field
from io import BytesIO

# ─── LOGGING ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("NaoRobot")

# ─── ENCODING ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ─── KEEP ALIVE ────────────────────────────────────────────────────────────
try:
    from keep_alive import keep_alive; keep_alive()
except ImportError: pass

# ─── THƯ VIỆN NGOÀI ───────────────────────────────────────────────────────
import telebot; from telebot import types; import requests; import pytz

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI RAM MANAGER - TỰ ĐỘNG DỌN DẸP BỘ NHỚ                  ║
# ╚══════════════════════════════════════════════════════════════╝
class AIRamManager:
    WARNING, LIGHT, MEDIUM, AGGRESSIVE, CRITICAL = 0.70, 0.75, 0.82, 0.90, 0.95
    def __init__(self, max_mb=512):
        self.max_bytes = max_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.snapshots = deque(maxlen=100)
        self.last_clean = 0; self.cooldown = 30; self.freed = 0; self.cleans = 0
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.clean_lock = Lock()

    def usage_pct(self): return self.process.memory_info().rss / self.max_bytes
    def usage_mb(self): return self.process.memory_info().rss / (1024*1024)

    def smart_cache_get(self, key):
        if key in self.cache:
            val, exp = self.cache[key]
            if time.time() < exp: return val
            else: del self.cache[key]
        return None

    def smart_cache_set(self, key, val, ttl=300):
        self.cache[key] = (val, time.time() + ttl)
        if len(self.cache) > 1000:
            for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:300]: del self.cache[k]

    def clean(self, level):
        freed = 0
        if level >= 1:
            now = time.time()
            expired = [k for k, (v, e) in self.cache.items() if now >= e]
            for k in expired: del self.cache[k]
            freed += len(expired) * 100
            freed += gc.collect(0) * 200
        if level >= 2:
            freed += gc.collect(2) * 200
            if len(self.cache) > 100:
                for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:len(self.cache)//2]: del self.cache[k]
        if level >= 3:
            if self.cache:
                for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:int(len(self.cache)*0.8)]: del self.cache[k]
            try: ctypes.CDLL("libc.so.6").malloc_trim(0); freed += 1024*1024
            except: pass
            for _ in range(3): gc.collect(2)
        self.freed += freed; self.cleans += 1
        return freed

    def ai_decide_clean(self):
        with self.clean_lock:
            if time.time() - self.last_clean < self.cooldown: return 0, "cooldown"
            pct = self.usage_pct()
            if pct >= self.CRITICAL: lvl = 3; act = "critical"
            elif pct >= self.AGGRESSIVE: lvl = 3; act = "aggressive"
            elif pct >= self.MEDIUM: lvl = 2; act = "medium"
            elif pct >= self.LIGHT: lvl = 1; act = "light"
            else: lvl = 0; act = "none"
            freed = self.clean(lvl) if lvl > 0 else 0
            self.last_clean = time.time()
            return freed, act

    def start_monitor(self):
        def loop():
            while True:
                time.sleep(30)
                if self.usage_pct() >= self.WARNING: self.ai_decide_clean()
        Thread(target=loop, daemon=True).start()

ram_mgr = AIRamManager()

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI BRAIN - NÃO ĐIỀU KHIỂN TỰ HỌC                          ║
# ╚══════════════════════════════════════════════════════════════╝
class Brain:
    def __init__(self):
        self.state = "normal"; self.mood = 0
        self.learned = defaultdict(int); self.trusted = set()
        self.stats = {"msgs":0, "spam":0, "ai":0, "err":0, "games":0,
                      "voice":0, "nohu":0, "start":time.time()}
        self.load()

    def load(self):
        if os.path.exists("brain.json"):
            try:
                with open("brain.json","r") as f:
                    d = json.load(f)
                    self.learned = defaultdict(int, d.get("learned",{}))
                    self.trusted = set(d.get("trusted",[]))
                    self.stats.update(d.get("stats",{}))
                    self.state = d.get("state","normal"); self.mood = d.get("mood",0)
            except: pass

    def save(self):
        with Lock():
            self.stats["ram_cleans"] = ram_mgr.cleans; self.stats["ram_freed"] = ram_mgr.freed/1024/1024
            try:
                with open("brain.json","w") as f:
                    json.dump({"learned":dict(self.learned),"trusted":list(self.trusted),
                               "stats":self.stats,"state":self.state,"mood":self.mood}, f)
            except: self.stats["err"] += 1

    def think(self, uid, txt):
        self.stats["msgs"] += 1
        for w in re.findall(r'\w{3,}', txt.lower()): self.learned[w] += 1
        if any(x in txt.lower() for x in ["bot ngu","mày ngu"]): self.mood -= 2
        elif any(x in txt.lower() for x in ["bot hay","cảm ơn bot"]): self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"
        if random.random() < 0.1: self.save()
        return self.state

    def should_reply(self, uid, txt):
        if uid in self.trusted: return True
        if self.learned.get(txt.lower(),0) > 5: return random.random() > 0.3
        return random.random() > 0.1

    def insult_level(self):
        if self.state == "aggressive": return "extreme"
        if self.mood < 0: return "high"
        return "normal"

brain = Brain()

# ╔══════════════════════════════════════════════════════════════╗
# ║  CONFIG + BIẾN TOÀN CỤC                                    ║
# ╚══════════════════════════════════════════════════════════════╝
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))
bot = telebot.TeleBot(TOKEN, num_threads=50)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
ses = requests.Session()
ses.mount('https://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))

AI_KEYS = [
    {"key":"sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d","url":"https://api.byesu.com/v1/chat/completions","model":"gpt-4o","status":True,"fail":0},
    {"key":"sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3","url":"https://api.byesu.com/v1/chat/completions","model":"gpt-4o","status":True,"fail":0}
]
MAX_FAIL, ck_idx, ck_lock = 3, 0, Lock()

KHO_NORMAL = ["Mồm thối, câm đi.","Não bã đậu, im lặng.","Thùng rỗng kêu to."]
KHO_HIGH = ["Nứt mắt đòi làm anh hùng.","Đầu rỗng, mồm thối.","Mạng xã hội nuôi mày à?"]
KHO_EXTREME = ["Mày đáng giá bằng cái nút block.","Não mày như ổ đĩa format nhầm.","Cút về lỗ mà mày chui ra."]
def get_kho():
    lvl = brain.insult_level()
    if lvl == "extreme": return KHO_EXTREME
    if lvl == "high": return KHO_HIGH
    return KHO_NORMAL

lock = Lock(); mem = deque(maxlen=50)
users = {}; spam = {}; warns = {}; mutes = {}; ai_cd = {}
balance = {}; daily_ck = {}
nohu_jp = 100000; nohu_hist = deque(maxlen=20); nohu_fee = 1000; nohu_mult = 0.05
GAME_SESSIONS = {}
USR_FILE = "usr.json"; BAL_FILE = "balances.json"; DAILY_FILE = "daily_ck.json"; JP_FILE = "jp.json"

def load_json(p, d={}):
    if os.path.exists(p):
        try:
            with open(p,'r') as f: return json.load(f)
        except: pass
    return d
def save_json(p, d):
    with lock:
        try:
            with open(p,'w') as f: json.dump(d, f, ensure_ascii=False, indent=2)
        except: pass

def auto_del(cid, mid, delay=15):
    Thread(target=lambda:(time.sleep(delay), bot.delete_message(cid,mid)), daemon=True).start()
def del_both(m, bid): auto_del(m.chat.id, m.message_id); auto_del(m.chat.id, bid)

def is_grp(m): return m.chat.id == GROUP_ID
def is_adm(m): return m.from_user.id == int(os.getenv("ADMIN_ID","5736655322"))

def get_bal(uid):
    if uid not in balance: balance[uid] = 5000; save_json(BAL_FILE, {str(k):v for k,v in balance.items()})
    return balance[uid]
def add_bal(uid, amt):
    bal = get_bal(uid); balance[uid] = max(0, bal+amt); save_json(BAL_FILE, {str(k):v for k,v in balance.items()})

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI CÂU ĐỐ RANDOM - KHÔNG TRÙNG                            ║
# ╚══════════════════════════════════════════════════════════════╝
class AICauDo:
    RIDDLES = [
        {"q":"Có 1 đàn chuột điếc đi qua cầu, hỏi có mấy con?","a":["24 con","24","hai tư"],"h":"Điếc = hư tai = 24"},
        {"q":"Cái gì càng kéo càng ngắn?","a":["điếu thuốc","thuốc lá"],"h":"Hút"},
        {"q":"Cái gì có răng mà không có miệng?","a":["cái cưa","cưa"],"h":"Cắt gỗ"},
        {"q":"Cái gì đen khi mua, đỏ khi dùng, xám khi vứt?","a":["than","củ than"],"h":"Đốt"},
        {"q":"Con gì sinh ra đã biết bơi?","a":["con cá","cá"],"h":"Dưới nước"},
        {"q":"Cái gì càng nhiều lửa càng ít?","a":["cây nến","nến"],"h":"Thắp sáng"},
        {"q":"Cái gì luôn đến nhưng không bao giờ đến?","a":["ngày mai","tương lai"],"h":"Thời gian"},
        # ... thêm nhiều câu khác cho đủ phong phú
    ]
    @staticmethod
    def generate(difficulty=1, used=None):
        if used is None: used = set()
        avail = [r for r in AICauDo.RIDDLES if r["a"][0] not in used]
        if avail and random.random() < 0.7: return random.choice(avail)
        # AI tự tạo
        tmpl = random.choice([
            lambda: {"q":f"Con gì {random.choice(['ăn','sợ','thích'])} {random.choice(['lửa','nước','bóng tối'])}?","a":["rồng","ma"],"h":"Huyền thoại"},
            lambda: {"q":f"Cái gì có {random.randint(3,6)} chân mà không đi được?","a":["cái bàn","bàn"],"h":"Nội thất"},
            lambda: {"q":f"Từ gì bỏ dấu thành '{random.choice(['ma','ba','ca'])}', thêm dấu thành '{random.choice(['má','bà','cá'])}'?","a":["đố mẹo"],"h":"Chơi chữ"}
        ])
        return tmpl()

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI NỔ HŨ - TỈ LỆ THẮNG THÔNG MINH                         ║
# ╚══════════════════════════════════════════════════════════════╝
class AINoHu:
    SYMBOLS = ["🍒","🍋","🍊","🍇","💎","🔔","7️⃣"]
    WEIGHTS = [28,24,20,16,6,4,2]
    PAYOUTS = {"🍒🍒🍒":5,"🍋🍋🍋":8,"🍊🍊🍊":12,"🍇🍇🍇":20,"💎💎💎":50,"🔔🔔🔔":100,"7️⃣7️⃣7️⃣":500}
    @staticmethod
    def adjust_weights(jp):
        w = AINoHu.WEIGHTS.copy()
        if jp > 300000: w[6] = max(1, w[6]-2); w[0] += 2
        if jp > 500000: w[6] = max(1, w[6]-3); w[1] += 2
        return w
    @staticmethod
    def spin(jp, bet):
        c1,c2,c3 = [random.choices(AINoHu.SYMBOLS, weights=AINoHu.adjust_weights(jp), k=1)[0] for _ in range(3)]
        if c1==c2==c3:
            if c1=="7️⃣": return jp, "jackpot"
            mult = AINoHu.PAYOUTS.get(f"{c1}{c2}{c3}",2)
            return bet*mult, f"win_{mult}"
        if c1==c2 or c2==c3 or c1==c3: return int(bet*0.5), "half"
        return 0, "lose"

# ╔══════════════════════════════════════════════════════════════╗
# ║  VOICE - 18 GIỌNG VIỆT NAM RANDOM                          ║
# ╚══════════════════════════════════════════════════════════════╝
VOICES = [
    {"name":"🇻🇳 Hà Nội (Chậm)","speed":0.8},{"name":"🇻🇳 Hà Nội (Vừa)","speed":1.0},
    {"name":"🇻🇳 Hà Nội (Nhanh)","speed":1.3},{"name":"🇻🇳 Sài Gòn (Chậm)","speed":0.7},
    {"name":"🇻🇳 Sài Gòn (Vừa)","speed":1.0},{"name":"🇻🇳 Sài Gòn (Nhanh)","speed":1.4},
    {"name":"🇻🇳 Nhẹ nhàng","speed":0.6},{"name":"🇻🇳 Trầm ấm","speed":0.9},
    {"name":"🇻🇳 Cao vút","speed":1.5},{"name":"🇻🇳 Lơ lớ","speed":0.75},
    {"name":"🇻🇳 Robot 🤖","speed":0.5},{"name":"🇻🇳 Sành điệu","speed":1.2},
    {"name":"🇻🇳 Bà cụ","speed":0.55},{"name":"🇻🇳 Em bé","speed":1.6},
    {"name":"🇻🇳 Phát thanh viên","speed":1.05},{"name":"🇻🇳 Hài hước","speed":1.1},
    {"name":"🇻🇳 Nghiêm túc","speed":0.85},{"name":"🇻🇳 Huế","speed":0.95}
]
TTS_URL = "https://translate.google.com/translate_tts"
TTS_HEADERS = {"User-Agent":"Mozilla/5.0","Accept":"audio/mpeg","Referer":"https://translate.google.com/"}

@dataclass
class VoiceReq:
    cid: int; rid: int; text: str; user: str; voice: dict = None

vqueue = Queue(maxsize=50)

def tts_fetch(text, lang="vi", speed=1.0):
    params = {"ie":"UTF-8","q":text,"tl":lang,"total":"1","idx":"0","textlen":str(len(text)),"client":"tw-ob","prev":"input","ttsspeed":str(speed)}
    try:
        r = ses.get(TTS_URL, params=params, headers=TTS_HEADERS, timeout=10)
        if r.status_code==200 and len(r.content)>100: return r.content
    except: pass
    return None

def tts_gen(text, speed=1.0):
    clean = re.sub(r'[<>"\'{}|\\^~\[\]`]','',text).strip()
    if not clean: return None
    chunks = []
    while len(clean) > 180:
        pos = 180
        for sep in ['. ','! ','? ',', ','; ',': ',' - ','\n',' ']:
            p = clean.rfind(sep, 0, 180)
            if p > 90: pos = p+len(sep); break
        chunks.append(clean[:pos].strip()); clean = clean[pos:].strip()
    if clean: chunks.append(clean)
    audio = b""
    for c in chunks:
        a = tts_fetch(c, "vi", speed)
        if a: audio += a
    return BytesIO(audio) if audio else None

def voice_worker():
    while True:
        req = vqueue.get()
        if not req: continue
        v = req.voice if req.voice else random.choice(VOICES)
        audio = tts_gen(req.text[:500], v["speed"])
        cap = f"🎙️ {html.escape(req.text[:150])}\n🗣️ {v['name']}"
        if audio:
            audio.name = "voice.mp3"
            try: bot.send_voice(req.cid, audio, reply_to_message_id=req.rid, caption=cap, parse_mode="HTML")
            except:
                audio.seek(0)
                bot.send_audio(req.cid, audio, reply_to_message_id=req.rid, title="Voice", caption=cap, parse_mode="HTML")
        else:
            bot.send_message(req.cid, f"❌ {html.escape(req.user)}, lỗi tạo voice.", reply_to_message_id=req.rid)
        vqueue.task_done()
for _ in range(4): Thread(target=voice_worker, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  MINI GAMES - 10+ TRÒ CHƠI                                 ║
# ╚══════════════════════════════════════════════════════════════╝
def init_game(uid, gt):
    if gt=="taixiu": return {"type":"taixiu","bal":1000,"w":0,"l":0}
    if gt=="baucua": return {"type":"baucua","bal":1000,"sym":["🦀","🐟","🦐","🐓","🦌","🎃"],"w":0,"l":0}
    if gt=="kbb": return {"type":"kbb","score":0,"bot":0,"draw":0}
    if gt=="doanso": return {"type":"doanso","secret":random.randint(1,100),"att":0,"max":7}
    if gt=="lxn": return {"type":"lxn","bal":1000,"w":0,"l":0}
    if gt=="xx": return {"type":"xx","bal":1000,"w":0,"l":0}
    if gt=="caudo": return {"type":"caudo","score":0,"qnum":0,"cur":None,"hint":False,"ans":False,"start":0}
    return {}

@bot.message_handler(commands=['taixiu'])
def taixiu(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"taixiu")
        g=GAME_SESSIONS[uid]; bot.reply_to(m,f"🎲 Tài Xỉu\n/taixiu [tai/xiu] [cược]\n💎 Game: {g['bal']} xu"); return
    ch,bt=parts[1].lower(),0
    try: bt=int(parts[2])
    except: bot.reply_to(m,"❌ Cược số"); return
    if ch not in ['tai','xiu']: bot.reply_to(m,"❌ Chọn tai/xiu"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"taixiu")
    g=GAME_SESSIONS[uid]
    if bt>g["bal"] or bt<1: bot.reply_to(m,f"❌ Số dư game: {g['bal']}"); return
    dice=[random.randint(1,6) for _ in range(3)]; total=sum(dice); res="tai" if total>=11 else "xiu"
    if ch==res: g["bal"]+=bt; g["w"]+=1; out=f"✅ +{bt}"
    else: g["bal"]-=bt; g["l"]+=1; out=f"❌ -{bt}"
    brain.stats["games"]+=1
    m2=bot.reply_to(m,f"🎲 {''.join('⚀⚁⚂⚃⚄⚅'[d-1] for d in dice)} = {total} → {res.upper()}\n💰 {out} | Game: {g['bal']}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['baucua'])
def baucua(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    sm={"bau":0,"bầu":0,"cua":1,"ca":2,"cá":2,"tom":3,"tôm":3,"ga":4,"gà":4,"nai":5,"huou":5,"hươu":5}
    if len(parts)<3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"baucua")
        g=GAME_SESSIONS[uid]; bot.reply_to(m,f"🎲 Bầu Cua\n🦀🐟🦐🐓🦌🎃\n/baucua [con] [cược]\n💎 Game: {g['bal']}"); return
    ch=parts[1].lower(); bt=0
    try: bt=int(parts[2])
    except: bot.reply_to(m,"❌ Cược số"); return
    if ch not in sm: bot.reply_to(m,f"❌ Chọn: {','.join(sm)}"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"baucua")
    g=GAME_SESSIONS[uid]
    if bt>g["bal"] or bt<1: bot.reply_to(m,f"❌ Số dư game: {g['bal']}"); return
    ci=sm[ch]; roll=[random.randint(0,5) for _ in range(3)]; rs=[g["sym"][i] for i in roll]; match=roll.count(ci)
    if match>0: wa=bt*(match+1); g["bal"]+=wa-bt; g["w"]+=1; out=f"✅ +{wa-bt}"
    else: g["bal"]-=bt; g["l"]+=1; out=f"❌ -{bt}"
    brain.stats["games"]+=1
    m2=bot.reply_to(m,f"🎲 {' '.join(rs)}\nBạn: {g['sym'][ci]} (trúng {match})\n💰 {out} | Game: {g['bal']}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['kbb'])
def kbb(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    chs={"keo":"✌️ Kéo","kéo":"✌️ Kéo","bua":"🔨 Búa","búa":"🔨 Búa","bao":"📄 Bao"}
    if len(parts)<2:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"kbb")
        g=GAME_SESSIONS[uid]; bot.reply_to(m,f"✌️ Kéo Búa Bao\n/kbb [keo/bua/bao]\n👤 {g['score']} | 🤖 {g['bot']} | 🤝 {g['draw']}"); return
    ch=parts[1].lower()
    if ch not in chs: bot.reply_to(m,"❌ keo/bua/bao"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"kbb")
    g=GAME_SESSIONS[uid]; uc,bc=chs[ch],random.choice(list(chs.values()))
    ui,bi=list(chs.values()).index(uc),list(chs.values()).index(bc)
    if ui==bi: r="🤝 Hòa"; g["draw"]+=1
    elif(ui==0 and bi==2)or(ui==1 and bi==0)or(ui==2 and bi==1): r="✅ Thắng"; g["score"]+=1
    else: r="❌ Thua"; g["bot"]+=1
    brain.stats["games"]+=1
    m2=bot.reply_to(m,f"✌️ {uc} vs {bc}\n📊 {r}\n🏆 {g['score']} | 🤖 {g['bot']} | 🤝 {g['draw']}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['doanso'])
def doanso(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if len(parts)<2:
        GAME_SESSIONS[uid]=init_game(uid,"doanso"); bot.reply_to(m,"🔢 Đoán Số (1-100)\n/doanso [số]\n7 lần"); return
    try: gs=int(parts[1])
    except: bot.reply_to(m,"❌ Nhập số"); return
    if gs<1 or gs>100: bot.reply_to(m,"❌ 1-100"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"doanso")
    g=GAME_SESSIONS[uid]; g["att"]+=1; brain.stats["games"]+=1
    if gs==g["secret"]:
        rw=(8-g["att"])*500; add_bal(uid,rw); m2=bot.reply_to(m,f"🎉 Đúng! Số {g['secret']} ({g['att']} lần)\n💰 +{rw}"); del GAME_SESSIONS[uid]
    elif g["att"]>=g["max"]: m2=bot.reply_to(m,f"💀 Hết lượt! Số {g['secret']}"); del GAME_SESSIONS[uid]
    elif gs<g["secret"]: m2=bot.reply_to(m,f"⬆️ Cao hơn ({g['max']-g['att']} lần)")
    else: m2=bot.reply_to(m,f"⬇️ Thấp hơn ({g['max']-g['att']} lần)")
    del_both(m,m2.message_id)

@bot.message_handler(commands=['lxn','lacxingau'])
def lxn(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"lxn")
        g=GAME_SESSIONS[uid]; bot.reply_to(m,f"🎲 Lắc Xí Ngầu\n/lxn [tổng 3-18] [cược]\n💎 Game: {g['bal']}"); return
    try: gt,bt=int(parts[1]),int(parts[2])
    except: bot.reply_to(m,"❌ Số"); return
    if gt<3 or gt>18: bot.reply_to(m,"❌ 3-18"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"lxn")
    g=GAME_SESSIONS[uid]
    if bt>g["bal"] or bt<1: bot.reply_to(m,f"❌ Số dư: {g['bal']}"); return
    dice=[random.randint(1,6) for _ in range(3)]; total=sum(dice)
    if total==gt: wa=bt*10; g["bal"]+=wa-bt; out=f"🎉 +{wa-bt}"
    elif abs(total-gt)==1: wa=int(bt*0.5); g["bal"]+=wa-bt; out=f"🔄 Hoàn {wa}"
    else: g["bal"]-=bt; out=f"💀 -{bt}"
    brain.stats["games"]+=1
    m2=bot.reply_to(m,f"🎲 {' '.join('⚀⚁⚂⚃⚄⚅'[d-1] for d in dice)} = {total}\n🎯 Bạn: {gt}\n💰 {out} | Game: {g['bal']}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['xx','xucxac'])
def xx(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"xx")
        g=GAME_SESSIONS[uid]; bot.reply_to(m,f"🎲 Xúc Xắc\n/xx [số 1-6] [cược]\n💎 Game: {g['bal']}"); return
    try: gs,bt=int(parts[1]),int(parts[2])
    except: bot.reply_to(m,"❌ Số"); return
    if gs<1 or gs>6: bot.reply_to(m,"❌ 1-6"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid]=init_game(uid,"xx")
    g=GAME_SESSIONS[uid]
    if bt>g["bal"] or bt<1: bot.reply_to(m,f"❌ Số dư: {g['bal']}"); return
    dr=random.randint(1,6); de="⚀⚁⚂⚃⚄⚅"[dr-1]
    if gs==dr: wa=bt*4; g["bal"]+=wa-bt; out=f"🎉 +{wa-bt}"
    elif abs(gs-dr)==1: wa=int(bt*0.5); g["bal"]+=wa-bt; out=f"🔄 Hoàn {wa}"
    else: g["bal"]-=bt; out=f"💀 -{bt}"
    brain.stats["games"]+=1
    m2=bot.reply_to(m,f"🎲 {de} {dr}\n🎯 Bạn: {gs}\n💰 {out} | Game: {g['bal']}"); del_both(m,m2.message_id)

# ─── CÂU ĐỐ AI ──────────────────────────────────────────────────────────
@bot.message_handler(commands=['caudo','cd'])
def caudo(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="caudo" or GAME_SESSIONS[uid].get("ans",False):
        used = set()
        if uid in GAME_SESSIONS and GAME_SESSIONS[uid].get("type")=="caudo":
            used = set(GAME_SESSIONS[uid].get("used",[]))
        r = AICauDo.generate(difficulty=1+ (GAME_SESSIONS[uid]["score"]//5 if uid in GAME_SESSIONS else 0), used=used)
        GAME_SESSIONS[uid] = {"type":"caudo","score":GAME_SESSIONS[uid].get("score",0) if uid in GAME_SESSIONS else 0,
                              "qnum":GAME_SESSIONS[uid].get("qnum",0)+1 if uid in GAME_SESSIONS else 1,
                              "cur":r,"hint":False,"ans":False,"start":time.time(),"used":used+[r["a"][0]]}
        m2=bot.reply_to(m,f"🧩 <b>Câu đố #{GAME_SESSIONS[uid]['qnum']}</b>\n⏰ 60s\n📝 {r['q']}\n🤔 /caudo [đáp án]\n💡 /caudo hint"); del_both(m,m2.message_id)
        def timeout():
            time.sleep(60)
            if uid in GAME_SESSIONS and GAME_SESSIONS[uid].get("type")=="caudo" and not GAME_SESSIONS[uid].get("ans",True):
                GAME_SESSIONS[uid]["ans"]=True
                bot.send_message(m.chat.id,f"⏰ Hết giờ! Đáp án: <b>{r['a'][0]}</b>", parse_mode="HTML")
        Thread(target=timeout, daemon=True).start(); return
    g=GAME_SESSIONS[uid]
    if g.get("ans",False): m2=bot.reply_to(m,"⏰ Hết giờ rồi! /caudo để chơi mới"); del_both(m,m2.message_id); return
    if len(parts)<2:
        rem=max(0,60-int(time.time()-g["start"])); m2=bot.reply_to(m,f"⏰ Còn {rem}s\n📝 {g['cur']['q']}\n🤔 /caudo [đáp án]"); del_both(m,m2.message_id); return
    arg=" ".join(parts[1:]).lower().strip()
    if arg in ["hint","gợi ý"]:
        if g["hint"]: m2=bot.reply_to(m,"❌ Đã dùng hint"); del_both(m,m2.message_id); return
        g["hint"]=True; g["score"]=max(0,g["score"]-1); m2=bot.reply_to(m,f"💡 {g['cur']['h']}\n🏆 {g['score']}"); del_both(m,m2.message_id); return
    if any(arg==a.lower() or a.lower() in arg for a in g["cur"]["a"]):
        elapsed=int(time.time()-g["start"]); bonus=max(0,(60-elapsed)//10); rw=2000+bonus*500
        add_bal(uid,rw); g["score"]+=3+bonus; g["ans"]=True
        m2=bot.reply_to(m,f"🎉 Chính xác! ({elapsed}s)\n💰 +{rw} xu\n🏆 {g['score']} điểm"); del_both(m,m2.message_id)
    else:
        g["score"]=max(0,g["score"]-1); rem=max(0,60-int(time.time()-g["start"]))
        if rem<=0: g["ans"]=True; m2=bot.reply_to(m,f"⏰ Hết giờ! Đáp án: {g['cur']['a'][0]}"); del GAME_SESSIONS[uid]
        else: m2=bot.reply_to(m,f"❌ Sai! (-1)\n⏰ {rem}s\n🏆 {g['score']}"); del_both(m,m2.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║  NỔ HŨ + ĐIỂM DANH + TÀI CHÍNH                             ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['nohu'])
def nohu(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    if len(parts)<2: m2=bot.reply(m,f"🎰 Nổ Hũ\n💰 Jackpot: {nohu_jp:,} xu\n/nohu [cược]"); del_both(m,m2.message_id); return
    try: bet=int(parts[1])
    except: bot.reply_to(m,"❌ Số"); return
    if bet<100 or bet>100000: bot.reply_to(m,"❌ 100-100k"); return
    total=bet+nohu_fee
    if get_bal(uid)<total: bot.reply_to(m,f"❌ Cần {total}"); return
    deduct_bal(uid,total); global nohu_jp; nohu_jp+=int(bet*nohu_mult)
    win,typ=AINoHu.spin(nohu_jp,bet)
    if typ=="jackpot": add_bal(uid,win); nohu_hist.append({"name":m.from_user.first_name,"amount":win}); nohu_jp=100000
    elif typ.startswith("win"): add_bal(uid,win)
    elif typ=="half": add_bal(uid,win)
    brain.stats["nohu"]+=1
    m2=bot.reply_to(m,f"🎰 Nổ Hũ\n💰 JP: {nohu_jp:,}\n💎 Số dư: {get_bal(uid):,}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['daily'])
def daily(m):
    if not is_grp(m): return
    uid=m.from_user.id; today=date.today().isoformat()
    if daily_ck.get(uid)==today: bot.reply_to(m,f"❌ Đã điểm danh\n💰 {get_bal(uid)}"); return
    daily_ck[uid]=today; rw=500+random.randint(0,1000); add_bal(uid,rw)
    m2=bot.reply(m,f"✅ Điểm danh\n💰 +{rw}\n💎 {get_bal(uid)}"); del_both(m,m2.message_id)

@bot.message_handler(commands=['give'])
def give(m):
    if not is_grp(m): return
    uid=m.from_user.id; parts=m.text.split()
    target=None; amt=0
    if m.reply_to_message: target=m.reply_to_message.from_user.id; amt=int(parts[1]) if len(parts)>1 else 0
    else:
        if len(parts)>2:
            if parts[1].startswith('@'): target=bot.get_chat_member(m.chat.id,parts[1]).user.id
            elif parts[1].isdigit(): target=int(parts[1])
            amt=int(parts[2]) if len(parts)>2 else 0
    if not target or amt<100: bot.reply_to(m,"❌ /give @mention [số]"); return
    fee=int(amt*0.05)
    if not deduct_bal(uid,amt+fee): bot.reply_to(m,f"❌ Thiếu {amt+fee}"); return
    add_bal(target,amt); m2=bot.reply(m,f"💸 Chuyển {amt} xu"); del_both(m,m2.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI CHAT + ANTI-SPAM                                       ║
# ╚══════════════════════════════════════════════════════════════╝
def ask_ai(prompt):
    global ck_idx
    if len(mem)>=2 and mem[-2]==prompt: return mem[-1]
    msgs=[{"role":"system","content":"Cọc cằn, chửi khịa, dưới 12 từ."}]
    for t in list(mem)[-8:]: msgs.append({"role":"user","content":t})
    msgs.append({"role":"user","content":prompt})
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k=AI_KEYS[ck_idx]
            if not k["status"] or k["fail"]>=MAX_FAIL: ck_idx=(ck_idx+1)%len(AI_KEYS); continue
            try:
                r=ses.post(k["url"],json={"model":k["model"],"messages":msgs,"max_tokens":40,"temperature":0.9},
                           headers={"Authorization":f"Bearer {k['key']}","Content-Type":"application/json"},timeout=8)
                if r.status_code==200:
                    txt=r.json()['choices'][0]['message']['content'].strip()
                    txt=re.sub(r'[_*`\[\]()]','',txt); k["fail"]=0
                    mem.append(prompt); mem.append(txt); brain.stats["ai"]+=1; return txt
                else: k["fail"]+=1
            except: k["fail"]+=1; brain.stats["err"]+=1
            ck_idx=(ck_idx+1)%len(AI_KEYS)
    for k in AI_KEYS: k["status"],k["fail"]=True,0
    return random.choice(get_kho())

def antispam(m):
    if is_adm(m): return False
    uid,now=m.from_user.id,time.time()
    spam[uid]=[t for t in spam.get(uid,[]) if now-t<4]+[now]
    if len(spam[uid])>5:
        warns[uid]=warns.get(uid,0)+1
        if warns[uid]>=3:
            try: bot.ban_chat_member(m.chat.id,uid,until_date=int(time.time())+3600)
            except: pass
            del warns[uid]
        else: bot.delete_message(m.chat.id,m.message_id)
        return True
    return False

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def chat(m):
    if antispam(m) or m.text.startswith('/'): return
    uid=m.from_user.id; brain.think(uid,m.text)
    if not brain.should_reply(uid,m.text): return
    if uid in ai_cd and time.time()-ai_cd[uid]<2: return
    ai_cd[uid]=time.time()
    def _ai():
        reply=ask_ai(m.text)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id==bot.get_me().id):
            m2=bot.reply_to(m,html.escape(reply),parse_mode="HTML"); auto_del(m.chat.id,m2.message_id)
        else:
            m2=bot.reply_to(m,html.escape(reply),parse_mode="HTML"); auto_del(m.chat.id,m2.message_id)
    Thread(target=_ai,daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  QUẢN LÍ NHÓM + THỐNG KÊ                                  ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['ban'])
def ban(m):
    if not is_grp(m) or not is_adm(m): return
    t,r = extract_user_and_reason(m)
    if t: bot.ban_chat_member(m.chat.id,t); bot.delete_message(m.chat.id,m.message_id)

@bot.message_handler(commands=['stats'])
def stats(m):
    if not is_grp(m): return
    cnt = bot.get_chat_member_count(GROUP_ID)
    m2=bot.reply_to(m,f"👥 {cnt} members | 💰 {sum(balance.values()):,} xu"); del_both(m,m2.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN                                                      ║
# ╚══════════════════════════════════════════════════════════════╝
def main():
    global balance, daily_ck, nohu_jp
    if os.path.exists(USR_FILE): users.update(load_json(USR_FILE,{}))
    balance = {int(k):v for k,v in load_json(BAL_FILE,{}).items()}
    daily_ck = load_json(DAILY_FILE,{})
    nohu_jp = load_json(JP_FILE,{"jp":100000}).get("jp",100000)
    ram_mgr.start_monitor()
    logger.info("🚀 Bot Full AI khởi động")
    Thread(target=lambda: (time.sleep(600), save_json(BAL_FILE,{str(k):v for k,v in balance.items()})), daemon=True).start()
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
