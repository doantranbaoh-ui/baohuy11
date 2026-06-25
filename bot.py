# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  NAO ROBOT v5.0.0 - 1500 DÒNG - 12 MINI GAMES + 18 GIỌNG BẮC VIỆT      ║
# ║  Tác giả: palofsc (palo) | Ngày: 2026-06-25 | Python 3.9+              ║
# ║  TÍNH NĂNG: 12 Games Bão X10 | Nổ Hũ | AI Chat | Voice TTS | Auto Mod  ║
# ╚══════════════════════════════════════════════════════════════════════════╝

import sys, io, os, json, time, random, re, html, logging, traceback, hashlib
import urllib.parse, gc, ctypes, psutil, weakref, signal, base64, tempfile
import math, statistics, itertools, threading
from threading import Thread, Lock, Timer, Event
from datetime import datetime, timedelta, date
from collections import deque, defaultdict, OrderedDict, Counter
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, PriorityQueue, Empty
from dataclasses import dataclass, field
from io import StringIO, BytesIO

# ─── LOGGING ──────────────────────────────────────────────────────────
from logging.handlers import RotatingFileHandler
os.makedirs("logs", exist_ok=True)
log_handler = RotatingFileHandler("logs/nao_robot.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger("NaoRobot")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from keep_alive import keep_alive
    keep_alive()
    logger.info("Keep-alive started")
except ImportError:
    logger.warning("keep_alive.py not found")

import telebot
from telebot import types, util
import requests
import pytz

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║               AI RANDOM ENGINE - MT19937 + XOR-SHIFT + ENTROPY          ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class AIRandomEngine:
    def __init__(self):
        self.counter = 0
        self.twister_state = self._init_mt()
        self.entropy_pool = bytearray(64)
        self._refresh_entropy()
        logger.info("AI Random Engine initialized")

    def _refresh_entropy(self):
        sources = [
            str(time.time_ns()).encode(),
            str(psutil.Process(os.getpid()).memory_info().rss).encode(),
            str(psutil.cpu_percent(interval=0.01)).encode(),
            str(threading.current_thread().ident).encode(),
            os.urandom(32)
        ]
        try:
            with open('/dev/urandom', 'rb') as f:
                sources.append(f.read(32))
        except:
            pass
        self.entropy_pool = bytearray(hashlib.sha512(b"".join(sources)).digest())

    def _init_mt(self) -> List[int]:
        seed = int.from_bytes(os.urandom(8), 'big')
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, 624):
            mt.append((1812433253 * (mt[i-1] ^ (mt[i-1] >> 30)) + i) & 0xFFFFFFFF)
        return mt

    def _twist(self):
        for i in range(624):
            y = (self.twister_state[i] & 0x80000000) + (self.twister_state[(i+1) % 624] & 0x7FFFFFFF)
            self.twister_state[i] = self.twister_state[(i+397) % 624] ^ (y >> 1)
            if y % 2 != 0:
                self.twister_state[i] ^= 0x9908B0DF

    def _mt_random(self) -> int:
        self.counter += 1
        if self.counter >= 624:
            self._twist()
            self.counter = 0
        y = self.twister_state[self.counter]
        y ^= (y >> 11)
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= (y >> 18)
        return y & 0xFFFFFFFF

    def _xor_shift(self, x: int) -> int:
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        return x & 0xFFFFFFFFFFFFFFFF

    def randint(self, min_val: int, max_val: int) -> int:
        if min_val >= max_val:
            return min_val
        range_size = max_val - min_val + 1
        mt_val = self._mt_random()
        xs_val = self._xor_shift(mt_val + self.counter)
        combined = mt_val ^ xs_val
        result = min_val + (combined % range_size)
        if self.counter % 100 == 0:
            self._refresh_entropy()
        return result

    def choice(self, items: List[Any]) -> Any:
        if not items:
            return None
        return items[self.randint(0, len(items) - 1)]

    def random(self) -> float:
        return self.randint(0, 2**53) / (2**53)

ai_random = AIRandomEngine()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    AI RAM MANAGER                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class AIRamManager:
    WARNING = 0.70
    LIGHT = 0.75
    MEDIUM = 0.82
    AGGRESSIVE = 0.90
    CRITICAL = 0.95

    def __init__(self, max_ram_mb: int = 512):
        self.max_bytes = max_ram_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.snapshots = deque(maxlen=100)
        self.last_clean = 0
        self.cooldown = 30
        self.freed = 0
        self.cleans = 0
        self.warnings = 0
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.lock = Lock()

    def usage_pct(self) -> float:
        return self.process.memory_info().rss / self.max_bytes

    def usage_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def cache_get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            v, exp = self.cache[key]
            if time.time() < exp:
                return v
            else:
                del self.cache[key]
        return None

    def cache_set(self, key: str, value: Any, ttl: float = 300):
        self.cache[key] = (value, time.time() + ttl)
        if len(self.cache) > 1000:
            for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:300]:
                del self.cache[k]

    def clean(self, level: int) -> int:
        freed = 0
        if level >= 1:
            now = time.time()
            for k in [k for k, (v, e) in self.cache.items() if now >= e]:
                del self.cache[k]
            freed += gc.collect(0) * 200
        if level >= 2:
            freed += gc.collect(2) * 200
            if len(self.cache) > 100:
                for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:len(self.cache)//2]:
                    del self.cache[k]
        if level >= 3:
            if self.cache:
                for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:int(len(self.cache)*0.8)]:
                    del self.cache[k]
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
                freed += 1024 * 1024
            except:
                pass
            for _ in range(3):
                gc.collect(2)
        self.freed += freed
        self.cleans += 1
        return freed

    def ai_clean(self) -> Tuple[int, str]:
        with self.lock:
            if time.time() - self.last_clean < self.cooldown:
                return 0, "cooldown"
            pct = self.usage_pct()
            if pct >= self.CRITICAL:
                lvl, act = 3, "critical"
            elif pct >= self.AGGRESSIVE:
                lvl, act = 3, "aggressive"
            elif pct >= self.MEDIUM:
                lvl, act = 2, "medium"
            elif pct >= self.LIGHT:
                lvl, act = 1, "light"
            else:
                return 0, "none"
            freed = self.clean(lvl)
            self.last_clean = time.time()
            return freed, act

    def monitor(self):
        while True:
            time.sleep(30)
            if self.usage_pct() >= self.WARNING:
                self.ai_clean()

    def start(self):
        Thread(target=self.monitor, daemon=True).start()

ram_mgr = AIRamManager()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    AI BRAIN                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class Brain:
    def __init__(self):
        self.state = "normal"
        self.mood = 0
        self.learned = defaultdict(int)
        self.trusted = set()
        self.stats = {"msgs": 0, "spam": 0, "ai": 0, "err": 0, "games": 0, "voice": 0, "nohu": 0, "start": time.time()}

    def think(self, uid, txt):
        self.stats["msgs"] += 1
        for w in re.findall(r'\w{3,}', txt.lower()):
            self.learned[w] += 1
        if any(x in txt.lower() for x in ["bot ngu", "mày ngu"]):
            self.mood -= 2
        elif any(x in txt.lower() for x in ["bot hay", "cảm ơn"]):
            self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"

    def should_reply(self, uid, txt):
        return uid in self.trusted or ai_random.random() > 0.1

    def insult_level(self):
        if self.state == "aggressive":
            return "extreme"
        if self.mood < 0:
            return "high"
        return "normal"

brain = Brain()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    CONFIG & TOKEN                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
AUTO_DELETE = 120
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=50)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
ses = requests.Session()
ses.mount('https://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))

ai_executor = ThreadPoolExecutor(max_workers=20)
voice_executor = ThreadPoolExecutor(max_workers=8)
game_executor = ThreadPoolExecutor(max_workers=15)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    AI KEYS (DÙNG ENV TRONG PRODUCTION)                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0}
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    KHO CHỬI                                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝
KHO_NORMAL = ["Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.", "Cào phím nhanh, não chậm.", "Về nhà rửa bát.", "IQ âm, đừng nói.", "Không ai cần mày.", "Câm mồm, đỡ nhục."]
KHO_HIGH = ["Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?", "Tưởng mình ngầu? Hề vãi.", "Học không lo, cào phím giỏi.", "Đời vả mặt, mày cười ngây."]
KHO_EXTREME = ["Mày đáng giá bằng cái nút block.", "Não mày như ổ đĩa format nhầm.", "Cút về lỗ mà mày chui ra.", "Mày là lỗi của tự nhiên.", "Tao chửi mày còn thấy phí thời gian."]

def get_kho():
    lvl = brain.insult_level()
    if lvl == "extreme":
        return KHO_EXTREME
    if lvl == "high":
        return KHO_HIGH
    return KHO_NORMAL

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    BIẾN TOÀN CỤC                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
lock = Lock()
mem = deque(maxlen=50)
users = {}
spam = {}
warns = {}
mutes = {}
ai_cd = {}
balance = {}
daily_ck = {}
nohu_jp = 100000
nohu_hist = deque(maxlen=20)
nohu_fee = 1000
nohu_mult = 0.05
GAME_SESSIONS = {}
USED_RIDDLES = defaultdict(list)
member_stats = {"daily_join": defaultdict(int), "daily_leave": defaultdict(int), "total_joined": 0, "total_left": 0, "current_members": 0}

USR_FILE = "usr.json"
BAL_FILE = "balances.json"
DAILY_FILE = "daily_ck.json"
JP_FILE = "jp.json"
STATS_FILE = "stats.json"

TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}', re.I)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    TIỆN ÍCH                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def load_json(p, d={}):
    cached = ram_mgr.cache_get(f"json_{p}")
    if cached is not None:
        return cached
    if os.path.exists(p):
        try:
            with open(p, 'r') as f:
                data = json.load(f)
                ram_mgr.cache_set(f"json_{p}", data, 60)
                return data
        except:
            pass
    return d

def save_json(p, d):
    with lock:
        try:
            with open(p, 'w') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            ram_mgr.cache_set(f"json_{p}", d, 60)
        except:
            pass

def auto_del(cid, mid, delay=AUTO_DELETE):
    def _del():
        time.sleep(delay)
        try:
            bot.delete_message(cid, mid)
        except:
            pass
    Thread(target=_del, daemon=True).start()

def del_both(m, bid):
    auto_del(m.chat.id, m.message_id)
    auto_del(m.chat.id, bid)

def is_grp(m):
    return m.chat.id == GROUP_ID

def is_adm(m):
    return m.from_user.id == ADMIN_ID

def get_bal(uid):
    if uid not in balance:
        balance[uid] = 5000
        save_json(BAL_FILE, {str(k): v for k, v in balance.items()})
    return balance[uid]

def add_bal(uid, amt):
    bal = get_bal(uid)
    balance[uid] = max(0, bal + amt)
    save_json(BAL_FILE, {str(k): v for k, v in balance.items()})

def deduct_bal(uid, amt):
    if get_bal(uid) >= amt:
        balance[uid] = get_bal(uid) - amt
        save_json(BAL_FILE, {str(k): v for k, v in balance.items()})
        return True
    return False

def parse_duration(reason: str) -> int:
    m = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == 's':
            return num
        elif unit in ['m', 'p']:
            return num * 60
        elif unit == 'h':
            return num * 3600
    return 3600

def extract_user_and_reason(message, bot_username: str) -> Tuple[Optional[int], str]:
    target = None
    reason = ""
    if message.reply_to_message:
        target = message.reply_to_message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            reason = parts[1]
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg.isdigit():
                target = int(arg)
            else:
                m = re.match(r'@(\w+)', arg)
                if m:
                    try:
                        target = bot.get_chat_member(message.chat.id, m.group(0)).user.id
                        reason = arg[m.end():].strip()
                    except:
                        pass
                else:
                    nm = re.search(r'\d+', arg)
                    if nm:
                        target = int(nm.group())
                        reason = arg[nm.end():].strip()
    return target, reason

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    BÃO X10 ENGINE                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def bao_x10(bet: int) -> Tuple[int, bool]:
    """
    Cơ chế Bão X10: 10% cơ hội nhân 10 tiền cược.
    Trả về: (tiền thưởng thêm, có bão hay không)
    """
    if ai_random.random() < 0.10:
        return bet * 10, True
    return 0, False

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║               18 GIỌNG BẮC THUẦN VIỆT + TTS ENGINE (ĐÃ FIX)             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
VOICE_LIST: List[Dict[str, Any]] = [
    {"name": "Hà Nội gốc (Chậm)", "speed": 0.7, "emoji": "🐢"},
    {"name": "Hà Nội gốc (Vừa)", "speed": 1.0, "emoji": "🎙️"},
    {"name": "Hà Nội gốc (Nhanh)", "speed": 1.3, "emoji": "⚡"},
    {"name": "Hà Nội nhẹ nhàng", "speed": 0.6, "emoji": "🌸"},
    {"name": "Hà Nội trầm ấm", "speed": 0.85, "emoji": "🎵"},
    {"name": "Hà Nội cao vút", "speed": 1.5, "emoji": "🎶"},
    {"name": "Hà Nội sành điệu", "speed": 1.2, "emoji": "💅"},
    {"name": "Hà Nội bà cụ", "speed": 0.55, "emoji": "👵"},
    {"name": "Hà Nội em bé", "speed": 1.6, "emoji": "👶"},
    {"name": "Hà Nội phát thanh viên", "speed": 1.05, "emoji": "📻"},
    {"name": "Hà Nội hài hước", "speed": 1.1, "emoji": "🤣"},
    {"name": "Hà Nội nghiêm túc", "speed": 0.9, "emoji": "🧐"},
    {"name": "Hà Nội thì thầm", "speed": 0.5, "emoji": "🤫"},
    {"name": "Hà Nội lơ lớ (Tây)", "speed": 0.75, "emoji": "👽"},
    {"name": "Hà Nội robot 🤖", "speed": 0.45, "emoji": "🤖"},
    {"name": "Hà Nội truyền cảm", "speed": 0.95, "emoji": "🎭"},
    {"name": "Hà Nội thể thao", "speed": 1.4, "emoji": "🏃"},
    {"name": "Hà Nội DJ remix", "speed": 1.7, "emoji": "🎧"},
]

TTS_URL = "https://translate.google.com/translate_tts"
TTS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "audio/mpeg", "Referer": "https://translate.google.com/"}
MAX_CHUNK = 180
TTS_RETRY = 3
TTS_TIMEOUT = 15

@dataclass
class VoiceRequest:
    chat_id: int
    reply_id: int
    text: str
    user_name: str
    user_id: int
    voice: Optional[Dict] = None
    created_at: float = field(default_factory=time.time)

voice_queue: Queue = Queue(maxsize=50)

def fetch_tts(text: str, speed: float = 1.0) -> Optional[bytes]:
    params = {"ie": "UTF-8", "q": text, "tl": "vi", "total": "1", "idx": "0", "textlen": str(len(text)), "client": "tw-ob", "prev": "input", "ttsspeed": str(speed)}
    for attempt in range(1, TTS_RETRY + 1):
        try:
            r = ses.get(TTS_URL, params=params, headers=TTS_HEADERS, timeout=TTS_TIMEOUT)
            if r.status_code == 200 and len(r.content) > 100:
                return r.content
        except:
            pass
        if attempt < TTS_RETRY:
            time.sleep(0.5 * attempt)
    return None

def split_tts(text: str) -> List[str]:
    if len(text) <= MAX_CHUNK:
        return [text]
    chunks = []
    seps = ['. ', '! ', '? ', ', ', '; ', ': ', ' - ', '\n', ' ']
    while len(text) > MAX_CHUNK:
        best = MAX_CHUNK
        for s in seps:
            p = text.rfind(s, 0, MAX_CHUNK)
            if p > MAX_CHUNK // 2:
                best = p + len(s)
                break
        if best > MAX_CHUNK or best <= MAX_CHUNK // 3:
            best = MAX_CHUNK
        chunks.append(text[:best].strip())
        text = text[best:].strip()
    if text:
        chunks.append(text)
    return chunks

def gen_voice(text: str, speed: float = 1.0) -> Tuple[Optional[BytesIO], int, int, float]:
    clean = re.sub(r'[<>"\'{}|\\^~\[\]`]', '', text).strip()
    if not clean:
        return None, 0, 0, 0.0
    chunks = split_tts(clean)
    total = len(chunks)
    audio = b""
    success = 0
    start = time.time()
    for i, c in enumerate(chunks):
        data = fetch_tts(c, speed)
        if data:
            audio += data
            success += 1
        if i < total - 1:
            time.sleep(0.15)
    gen_time = time.time() - start
    if not audio or len(audio) < 100:
        return None, success, total, gen_time
    return BytesIO(audio), success, total, gen_time

def voice_worker():
    while True:
        try:
            req = voice_queue.get(block=True, timeout=1)
            if not req:
                voice_queue.task_done()
                continue
            txt = req.text[:500].strip()
            if not txt:
                voice_queue.task_done()
                continue
            v = req.voice if req.voice else ai_random.choice(VOICE_LIST)
            status = bot.send_message(req.chat_id, f"🎙️ Đang tạo giọng nói...\n👤 {html.escape(req.user_name)}\n🗣️ {v['emoji']} {v['name']}", reply_to_message_id=req.reply_id, parse_mode="HTML")
            audio, success, total, gen_time = gen_voice(txt, v["speed"])
            try:
                bot.delete_message(req.chat_id, status.message_id)
            except:
                pass
            if audio and isinstance(audio, BytesIO) and audio.getbuffer().nbytes > 100:
                audio.name = f"voice_{int(time.time())}.mp3"
                cap = (f"🎙️ <b>GIỌNG NÓI</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                       f"👤 <b>Người dùng:</b> {html.escape(req.user_name)}\n"
                       f"🗣️ <b>Giọng:</b> {v['emoji']} {v['name']}\n"
                       f"⚡ <b>Tốc độ:</b> x{v['speed']}\n"
                       f"📝 <b>Nội dung:</b> <i>{html.escape(txt[:200])}</i>\n"
                       f"━━━━━━━━━━━━━━━━━━━━\n"
                       f"📊 <b>Âm thanh:</b> {audio.getbuffer().nbytes/1024:.1f}KB | ⏱️ {gen_time:.1f}s | ✅ {success}/{total}")
                try:
                    bot.send_voice(req.chat_id, audio, reply_to_message_id=req.reply_id, caption=cap, parse_mode="HTML")
                    brain.stats["voice"] += 1
                except:
                    try:
                        audio.seek(0)
                        bot.send_audio(req.chat_id, audio, reply_to_message_id=req.reply_id, caption=cap, parse_mode="HTML", title=f"Voice - {v['name']}")
                        brain.stats["voice"] += 1
                    except:
                        bot.send_message(req.chat_id, "❌ Lỗi gửi audio.", reply_to_message_id=req.reply_id)
            else:
                bot.send_message(req.chat_id, f"❌ <b>Không thể tạo giọng nói</b>\n👤 {html.escape(req.user_name)}\n🗣️ {v['emoji']} {v['name']}\n⚠️ {success}/{total} chunks\n💡 Thử text ngắn hơn.", reply_to_message_id=req.reply_id, parse_mode="HTML")
            voice_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logger.error(f"Voice worker error: {traceback.format_exc()}")
            try:
                voice_queue.task_done()
            except:
                pass

for _ in range(4):
    Thread(target=voice_worker, daemon=True).start()
logger.info("4 voice workers started")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    12 MINI GAMES ENGINE - BÃO X10                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def init_game(uid, gt):
    bases = {"bal": 1000, "w": 0, "l": 0}
    if gt == "taixiu":
        return {"type": "taixiu", **bases}
    if gt == "baucua":
        return {"type": "baucua", "sym": ["Cua", "Ca", "Tom", "Ga", "Nai", "Bau"], **bases}
    if gt == "kbb":
        return {"type": "kbb", "score": 0, "bot": 0, "draw": 0}
    if gt == "doanso":
        return {"type": "doanso", "secret": ai_random.randint(1, 100), "att": 0, "max": 7}
    if gt == "lxn":
        return {"type": "lxn", **bases}
    if gt == "xx":
        return {"type": "xx", **bases}
    if gt == "caudo":
        return {"type": "caudo", "score": 0, "qnum": 0, "cur": None, "hint": False, "ans": False, "start": 0}
    if gt == "chanle":
        return {"type": "chanle", **bases}
    if gt == "caothap":
        return {"type": "caothap", **bases}
    if gt == "doanso2":
        return {"type": "doanso2", "secret": ai_random.randint(1, 100), "att": 0, "max": 5}
    if gt == "keo":
        return {"type": "keo", "bal": 1000, "w": 0, "l": 0}
    if gt == "bingo":
        return {"type": "bingo", "bal": 1000, "w": 0, "l": 0}
    return {}

# ─── GAME 1: TÀI XỈU ────────────────────────────────────────────────────
@bot.message_handler(commands=['taixiu'])
def taixiu(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "taixiu")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🎲 <b>TÀI XỈU BÃO X10</b>\n━━━━━━━━━━━━\n/taixiu [tai/xiu] [cuoc]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ Cược phải là số.")
        del_both(m, m2.message_id)
        return
    if ch not in ['tai', 'xiu']:
        m2 = bot.reply_to(m, "❌ Chọn tai hoặc xiu.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "taixiu")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư game: {g['bal']:,} xu")
        del_both(m, m2.message_id)
        return
    dice = [ai_random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    res = "tai" if total >= 11 else "xiu"
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res:
        win = bt * 3 + bao_bonus
        g["bal"] += win
        g["w"] += 1
        out = f"🎉 Thắng +{win:,}" + (" 💥 BÃO X10!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        g["l"] += 1
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🎲 <b>TÀI XỈU</b>\n━━━━━━━━━━━━\n{d}\nTổng: {total} → {res.upper()}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 2: BẦU CUA ────────────────────────────────────────────────────
@bot.message_handler(commands=['baucua'])
def baucua(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    sm = {"bau": 0, "cua": 1, "ca": 2, "tom": 3, "ga": 4, "nai": 5}
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "baucua")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🦀 <b>BẦU CUA BÃO X10</b>\n━━━━━━━━━━━━\n/baucua [bau/cua/ca/tom/ga/nai] [cuoc]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ Cược phải là số.")
        del_both(m, m2.message_id)
        return
    if ch not in sm:
        m2 = bot.reply_to(m, f"❌ Chọn: {', '.join(sm)}")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "baucua")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư game: {g['bal']:,} xu")
        del_both(m, m2.message_id)
        return
    ci = sm[ch]
    roll = [ai_random.randint(0, 5) for _ in range(3)]
    rs = [g["sym"][i] for i in roll]
    match = roll.count(ci)
    bao_bonus, is_bao = bao_x10(bt)
    if match > 0:
        win = bt * match * 3 + bao_bonus
        g["bal"] += win
        g["w"] += 1
        out = f"🎉 Thắng +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        g["l"] += 1
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🦀 <b>BẦU CUA</b>\n━━━━━━━━━━━━\n{' '.join(rs)}\nTrúng {match} con\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 3: KÉO BÚA BAO ───────────────────────────────────────────────
@bot.message_handler(commands=['kbb'])
def kbb(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    chs = {"keo": "Kéo", "bua": "Búa", "bao": "Bao"}
    if len(parts) < 2:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "kbb")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"✊ <b>KÉO BÚA BAO BÃO X10</b>\n━━━━━━━━━━━━\n/kbb [keo/bua/bao]\n🏆 Bạn: {g['score']} | 🤖 Bot: {g['bot']} | 🤝 Hòa: {g['draw']}", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    ch = parts[1].lower()
    if ch not in chs:
        m2 = bot.reply_to(m, "❌ Chọn: keo/bua/bao")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "kbb")
    g = GAME_SESSIONS[uid]
    uc, bc = chs[ch], ai_random.choice(list(chs.values()))
    ui, bi = list(chs.values()).index(uc), list(chs.values()).index(bc)
    bao_bonus, is_bao = bao_x10(3)
    if ui == bi:
        r = "🤝 Hòa"
        g["draw"] += 1
    elif (ui == 0 and bi == 2) or (ui == 1 and bi == 0) or (ui == 2 and bi == 1):
        pts = 3 + bao_bonus
        g["score"] += pts
        r = f"🎉 Thắng +{pts}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        r = "💔 Thua"
        g["bot"] += 1
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"✊ <b>KÉO BÚA BAO</b>\n━━━━━━━━━━━━\n{uc} vs {bc}\n{r}\n🏆 Bạn: {g['score']} | 🤖 Bot: {g['bot']} | 🤝 Hòa: {g['draw']}", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 4: ĐOÁN SỐ ────────────────────────────────────────────────────
@bot.message_handler(commands=['doanso'])
def doanso(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 2:
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
        m2 = bot.reply_to(m, "🔢 <b>ĐOÁN SỐ BÃO X10</b>\n━━━━━━━━━━━━\n/doanso [so] (1-100)\n🎯 7 lần đoán", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gs = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ Nhập số.")
        del_both(m, m2.message_id)
        return
    if gs < 1 or gs > 100:
        m2 = bot.reply_to(m, "❌ 1-100.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
    g = GAME_SESSIONS[uid]
    g["att"] += 1
    brain.stats["games"] += 1
    if gs == g["secret"]:
        base = (8 - g["att"]) * 500 * 3
        bao_bonus, is_bao = bao_x10(base // 3)
        rw = base + bao_bonus
        add_bal(uid, rw)
        m2 = bot.reply_to(m, f"🎉 <b>CHÍNH XÁC!</b> Số {g['secret']} ({g['att']} lần)\n+{rw:,} xu" + (" 💥 BÃO!!!" if is_bao else ""), parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        m2 = bot.reply_to(m, f"💔 HẾT LƯỢT! Số {g['secret']}", parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]:
        m2 = bot.reply_to(m, f"📈 CAO HƠN ({g['max'] - g['att']} lần)")
    else:
        m2 = bot.reply_to(m, f"📉 THẤP HƠN ({g['max'] - g['att']} lần)")
    del_both(m, m2.message_id)

# ─── GAME 5: LẮC XI NGẦU ───────────────────────────────────────────────
@bot.message_handler(commands=['lxn'])
def lxn(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "lxn")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🎲 <b>LẮC XI NGẦU BÃO X10</b>\n━━━━━━━━━━━━\n/lxn [tổng 3-18] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gt, bt = int(parts[1]), int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /lxn [3-18] [cược]")
        del_both(m, m2.message_id)
        return
    if gt < 3 or gt > 18:
        m2 = bot.reply_to(m, "❌ 3-18.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "lxn")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    dice = [ai_random.randint(1, 6) for _ in range(3)]
    total = sum(dice)
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    bao_bonus, is_bao = bao_x10(bt)
    if total == gt:
        win = bt * 10 + bao_bonus
        g["bal"] += win
        out = f"🎉 CHÍNH XÁC! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    elif abs(total - gt) == 1:
        win = int(bt * 0.5)
        g["bal"] += win
        out = f"🤏 Gần đúng! Hoàn {win:,}"
    else:
        g["bal"] -= bt
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🎲 <b>LẮC XI NGẦU</b>\n━━━━━━━━━━━━\n{ds} = {total}\nĐoán: {gt}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 6: XÚC XẮC ────────────────────────────────────────────────────
@bot.message_handler(commands=['xx'])
def xx(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "xx")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🎲 <b>XÚC XẮC BÃO X10</b>\n━━━━━━━━━━━━\n/xx [số 1-6] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gs, bt = int(parts[1]), int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /xx [1-6] [cược]")
        del_both(m, m2.message_id)
        return
    if gs < 1 or gs > 6:
        m2 = bot.reply_to(m, "❌ 1-6.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "xx")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    dr = ai_random.randint(1, 6)
    de = "⚀⚁⚂⚃⚄⚅"[dr-1]
    bao_bonus, is_bao = bao_x10(bt)
    if gs == dr:
        win = bt * 4 + bao_bonus
        g["bal"] += win
        out = f"🎉 TRÚNG! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    elif abs(gs - dr) == 1:
        win = int(bt * 0.5)
        g["bal"] += win
        out = f"🤏 Gần đúng! Hoàn {win:,}"
    else:
        g["bal"] -= bt
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🎲 <b>XÚC XẮC</b>\n━━━━━━━━━━━━\n{de} {dr}\nĐoán: {gs}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 7: CÂU ĐỐ ─────────────────────────────────────────────────────
CAUDO_LIST = [
    {"q": "Có đàn chuột điếc đi qua cầu, mấy con?", "a": ["24", "hai tư"], "h": "Điếc = hư tai → hai tư"},
    {"q": "Cái gì càng kéo càng ngắn?", "a": ["điếu thuốc", "thuốc lá"], "h": "Hút thuốc"},
    {"q": "Cái gì có răng không miệng?", "a": ["cái cưa", "cưa", "lược"], "h": "Cắt/chải"},
    {"q": "Cái gì đen-mua, đỏ-dùng, xám-vứt?", "a": ["than", "củ than"], "h": "Đốt"},
    {"q": "Cái gì càng nhiều lửa càng ít?", "a": ["cây nến", "nến"], "h": "Thắp sáng"},
    {"q": "Luôn đến nhưng không bao giờ đến?", "a": ["ngày mai", "tương lai"], "h": "Thời gian"},
    {"q": "Cái gì đập thì sống, không đập thì chết?", "a": ["con tim", "tim"], "h": "Nhịp đập"},
    {"q": "Cái gì càng rửa càng bẩn?", "a": ["nước"], "h": "Rửa đồ"},
    {"q": "Cái gì càng cháy càng cao?", "a": ["ngọn lửa", "lửa"], "h": "Cháy"},
    {"q": "Vừa bằng quả mướp, ăn cướp cả làng?", "a": ["hạt tiêu", "tiêu"], "h": "Gia vị cay"},
]

@bot.message_handler(commands=['caudo'])
def caudo(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "caudo" or GAME_SESSIONS[uid].get("ans", False):
        r = ai_random.choice(CAUDO_LIST)
        old_score = GAME_SESSIONS[uid].get("score", 0) if uid in GAME_SESSIONS else 0
        old_qnum = GAME_SESSIONS[uid].get("qnum", 0) + 1 if uid in GAME_SESSIONS else 1
        GAME_SESSIONS[uid] = {"type": "caudo", "score": old_score, "qnum": old_qnum, "cur": r, "hint": False, "ans": False, "start": time.time()}
        m2 = bot.reply_to(m, f"🧩 <b>CÂU ĐỐ #{GAME_SESSIONS[uid]['qnum']}</b>\n━━━━━━━━━━━━\n⏱️ 60s\n📝 {r['q']}\n\n/caudo [đáp án]\n/caudo hint (gợi ý -1đ)", parse_mode="HTML")
        del_both(m, m2.message_id)
        def timeout():
            time.sleep(60)
            if uid in GAME_SESSIONS and not GAME_SESSIONS[uid].get("ans", True):
                GAME_SESSIONS[uid]["ans"] = True
                bot.send_message(m.chat.id, f"⏰ Hết giờ! Đáp án: {r['a'][0]}")
        Thread(target=timeout, daemon=True).start()
        return
    g = GAME_SESSIONS[uid]
    if g.get("ans", False):
        m2 = bot.reply_to(m, "⏰ Hết giờ!")
        del_both(m, m2.message_id)
        return
    if len(parts) < 2:
        rem = max(0, 60 - int(time.time() - g["start"]))
        m2 = bot.reply_to(m, f"⏱️ Còn {rem}s\n📝 {g['cur']['q']}")
        del_both(m, m2.message_id)
        return
    arg = " ".join(parts[1:]).lower().strip()
    if arg in ["hint", "goi y"]:
        if g["hint"]:
            m2 = bot.reply_to(m, "❌ Đã dùng hint.")
            del_both(m, m2.message_id)
            return
        g["hint"] = True
        g["score"] = max(0, g["score"] - 1)
        m2 = bot.reply_to(m, f"💡 Gợi ý: {g['cur']['h']}")
        del_both(m, m2.message_id)
        return
    if any(arg == a.lower() or a.lower() in arg for a in g["cur"]["a"]):
        elapsed = int(time.time() - g["start"])
        bonus = max(0, (60 - elapsed) // 10)
        base_rw = 2000 + bonus * 500
        bao_bonus, is_bao = bao_x10(base_rw)
        rw = base_rw + bao_bonus
        add_bal(uid, rw)
        g["score"] += 3 + bonus
        g["ans"] = True
        m2 = bot.reply_to(m, f"🎉 <b>Chính xác!</b> +{rw:,} xu" + (" 💥 BÃO!!!" if is_bao else "") + f"\n⭐ Điểm: {g['score']}", parse_mode="HTML")
        del_both(m, m2.message_id)
    else:
        g["score"] = max(0, g["score"] - 1)
        rem = max(0, 60 - int(time.time() - g["start"]))
        if rem <= 0:
            g["ans"] = True
            m2 = bot.reply_to(m, f"⏰ Hết giờ! Đáp án: {g['cur']['a'][0]}")
            del_both(m, m2.message_id)
        else:
            m2 = bot.reply_to(m, f"❌ Sai! ({rem}s)")
            del_both(m, m2.message_id)

# ─── GAME 8: CHẴN LẺ ────────────────────────────────────────────────────
@bot.message_handler(commands=['chanle'])
def chanle(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "chanle")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🔢 <b>CHẴN LẺ BÃO X10</b>\n━━━━━━━━━━━━\n/chanle [chan/le] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ Cược số.")
        del_both(m, m2.message_id)
        return
    if ch not in ['chan', 'le']:
        m2 = bot.reply_to(m, "❌ chan/le.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "chanle")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    num = ai_random.randint(1, 100)
    res = "chan" if num % 2 == 0 else "le"
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res:
        win = bt * 3 + bao_bonus
        g["bal"] += win
        g["w"] += 1
        out = f"🎉 Thắng +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        g["l"] += 1
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🔢 <b>CHẴN LẺ</b>\n━━━━━━━━━━━━\nSố {num} → {res.upper()}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 9: CAO THẤP ───────────────────────────────────────────────────
@bot.message_handler(commands=['caothap'])
def caothap(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "caothap")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"📊 <b>CAO THẤP BÃO X10</b>\n━━━━━━━━━━━━\n/caothap [cao/thap] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ Cược số.")
        del_both(m, m2.message_id)
        return
    if ch not in ['cao', 'thap']:
        m2 = bot.reply_to(m, "❌ cao/thap.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "caothap")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    num = ai_random.randint(1, 100)
    res = "cao" if num > 50 else "thap"
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res:
        win = bt * 3 + bao_bonus
        g["bal"] += win
        g["w"] += 1
        out = f"🎉 Thắng +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        g["l"] += 1
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"📊 <b>CAO THẤP</b>\n━━━━━━━━━━━━\nSố {num} → {res.upper()}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 10: KÉO LUI ───────────────────────────────────────────────────
@bot.message_handler(commands=['keo'])
def keo(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "keo")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🎰 <b>KÉO LUI BÃO X10</b>\n━━━━━━━━━━━━\n/keo [0-9] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gs, bt = int(parts[1]), int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /keo [0-9] [cược]")
        del_both(m, m2.message_id)
        return
    if gs < 0 or gs > 9:
        m2 = bot.reply_to(m, "❌ 0-9.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "keo")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    result = ai_random.randint(0, 9)
    bao_bonus, is_bao = bao_x10(bt)
    if gs == result:
        win = bt * 5 + bao_bonus
        g["bal"] += win
        out = f"🎉 TRÚNG! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🎰 <b>KÉO LUI</b>\n━━━━━━━━━━━━\nSố: {result}\nĐoán: {gs}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 11: BINGO ─────────────────────────────────────────────────────
@bot.message_handler(commands=['bingo'])
def bingo(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS:
            GAME_SESSIONS[uid] = init_game(uid, "bingo")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m, f"🎱 <b>BINGO BÃO X10</b>\n━━━━━━━━━━━━\n/bingo [1-36] [cược]\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gs, bt = int(parts[1]), int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /bingo [1-36] [cược]")
        del_both(m, m2.message_id)
        return
    if gs < 1 or gs > 36:
        m2 = bot.reply_to(m, "❌ 1-36.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "bingo")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1:
        m2 = bot.reply_to(m, f"❌ Số dư: {g['bal']:,}")
        del_both(m, m2.message_id)
        return
    result = ai_random.randint(1, 36)
    bao_bonus, is_bao = bao_x10(bt)
    if gs == result:
        win = bt * 8 + bao_bonus
        g["bal"] += win
        out = f"🎉 TRÚNG! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    else:
        g["bal"] -= bt
        out = f"💔 Thua -{bt:,}"
    brain.stats["games"] += 1
    m2 = bot.reply_to(m, f"🎱 <b>BINGO</b>\n━━━━━━━━━━━━\nSố: {result}\nĐoán: {gs}\n{out}\n💰 Game: {g['bal']:,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── GAME 12: ĐOÁN SỐ SIÊU TỐC ──────────────────────────────────────────
@bot.message_handler(commands=['doanso2'])
def doanso2(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 2:
        GAME_SESSIONS[uid] = init_game(uid, "doanso2")
        m2 = bot.reply_to(m, "⚡ <b>ĐOÁN SỐ SIÊU TỐC BÃO X10</b>\n━━━━━━━━━━━━\n/doanso2 [so] (1-100)\n🎯 5 lần đoán", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        gs = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ Nhập số.")
        del_both(m, m2.message_id)
        return
    if gs < 1 or gs > 100:
        m2 = bot.reply_to(m, "❌ 1-100.")
        del_both(m, m2.message_id)
        return
    if uid not in GAME_SESSIONS:
        GAME_SESSIONS[uid] = init_game(uid, "doanso2")
    g = GAME_SESSIONS[uid]
    g["att"] += 1
    brain.stats["games"] += 1
    if gs == g["secret"]:
        base = (6 - g["att"]) * 800 * 5
        bao_bonus, is_bao = bao_x10(base // 5)
        rw = base + bao_bonus
        add_bal(uid, rw)
        m2 = bot.reply_to(m, f"⚡ <b>CHÍNH XÁC!</b> +{rw:,} xu" + (" 💥 BÃO!!!" if is_bao else ""), parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        m2 = bot.reply_to(m, f"💔 HẾT LƯỢT! Số {g['secret']}", parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]:
        m2 = bot.reply_to(m, f"📈 CAO HƠN ({g['max'] - g['att']} lần)")
    else:
        m2 = bot.reply_to(m, f"📉 THẤP HƠN ({g['max'] - g['att']} lần)")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    NỔ HŨ + ĐIỂM DANH + TÀI CHÍNH                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['nohu'])
def nohu_cmd(m):
    global nohu_jp
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()
    if len(parts) < 2:
        m2 = bot.reply_to(m, f"🎰 <b>NỔ HŨ</b>\n━━━━━━━━━━━━\n💰 JP: {nohu_jp:,} xu\n🎫 Phí: {nohu_fee:,} xu/lượt\n\n/nohu [cược]", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    try:
        bet = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ Nhập số.")
        del_both(m, m2.message_id)
        return
    if bet < 100 or bet > 100000:
        m2 = bot.reply_to(m, "❌ 100-100k.")
        del_both(m, m2.message_id)
        return
    total = bet + nohu_fee
    if not deduct_bal(uid, total):
        m2 = bot.reply_to(m, f"❌ Không đủ! Cần {total:,}")
        del_both(m, m2.message_id)
        return
    nohu_jp += int(bet * nohu_mult)
    bao_bonus, is_bao = bao_x10(bet)
    c1, c2, c3 = [ai_random.choice(["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]) for _ in range(3)]
    if c1 == c2 == c3:
        if c1 == "7️⃣":
            win = nohu_jp + bao_bonus
            add_bal(uid, win)
            nohu_hist.append({"name": m.from_user.first_name, "amount": win})
            nohu_jp = 100000
            out = f"🎉 JACKPOT! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
        else:
            win = bet * 5 + bao_bonus
            add_bal(uid, win)
            out = f"🎉 Nổ! +{win:,}" + (" 💥 BÃO!!!" if is_bao else "")
    elif c1 == c2 or c2 == c3 or c1 == c3:
        win = int(bet * 0.5)
        add_bal(uid, win)
        out = f"🤏 Hoàn {win:,}"
    else:
        out = f"💔 Thua -{total:,}"
    brain.stats["nohu"] += 1
    m2 = bot.reply_to(m, f"🎰 <b>NỔ HŨ</b>\n━━━━━━━━━━━━\n{c1}{c2}{c3}\n{out}\n💰 Số dư: {get_bal(uid):,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['daily'])
def daily(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    today = date.today().isoformat()
    if daily_ck.get(uid) == today:
        m2 = bot.reply_to(m, f"✅ Đã điểm danh\n💰 Số dư: {get_bal(uid):,} xu")
        del_both(m, m2.message_id)
        return
    daily_ck[uid] = today
    rw = 500 + ai_random.randint(0, 1000)
    add_bal(uid, rw)
    m2 = bot.reply_to(m, f"📅 <b>ĐIỂM DANH</b>\n━━━━━━━━━━━━\n+{rw:,} xu\n💰 Số dư: {get_bal(uid):,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['balance', 'xu'])
def balance_cmd(m):
    if not is_grp(m):
        return
    t = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    n = m.reply_to_message.from_user.first_name if m.reply_to_message else m.from_user.first_name
    m2 = bot.reply_to(m, f"💰 <b>{html.escape(n)}:</b> {get_bal(t):,} xu", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['top'])
def top(m):
    if not is_grp(m):
        return
    sb = sorted(balance.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n━━━━━━━━━━━━\n"
    for i, (uid, bal) in enumerate(sb):
        name = users.get(str(uid), str(uid))
        text += f"{i+1}. {html.escape(name)}: {bal:,} xu\n"
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['give'])
def give(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    target = None
    amt = 0
    if m.reply_to_message:
        target = m.reply_to_message.from_user.id
        parts = m.text.split()
        amt = int(parts[1]) if len(parts) > 1 else 0
    else:
        parts = m.text.split()
        if len(parts) > 2:
            if parts[1].startswith('@'):
                try:
                    target = bot.get_chat_member(m.chat.id, parts[1]).user.id
                except:
                    pass
            elif parts[1].isdigit():
                target = int(parts[1])
            amt = int(parts[2]) if len(parts) > 2 else 0
    if not target or amt < 100:
        m2 = bot.reply_to(m, "❌ /give @mention [số]")
        del_both(m, m2.message_id)
        return
    fee = int(amt * 0.05)
    if not deduct_bal(uid, amt + fee):
        m2 = bot.reply_to(m, "❌ Không đủ xu.")
        del_both(m, m2.message_id)
        return
    add_bal(target, amt)
    m2 = bot.reply_to(m, f"✅ Đã chuyển {amt:,} xu (phí {fee:,})", parse_mode="HTML")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT + ANTI-SPAM                                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def ask_ai(prompt):
    global ck_idx
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]
    msgs = [{"role": "system", "content": "Cộc cằn, chửi khía, dưới 12 từ."}]
    for t in list(mem)[-8:]:
        msgs.append({"role": "user", "content": t})
    msgs.append({"role": "user", "content": prompt})
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                r = ses.post(k["url"], json={"model": k["model"], "messages": msgs, "max_tokens": 40}, headers={"Authorization": f"Bearer {k['key']}"}, timeout=8)
                if r.status_code == 200:
                    txt = r.json()['choices'][0]['message']['content'].strip()
                    txt = re.sub(r'[_*`\[\]()]', '', txt)
                    k["fail"] = 0
                    mem.append(prompt)
                    mem.append(txt)
                    brain.stats["ai"] += 1
                    return txt
                else:
                    k["fail"] += 1
            except:
                k["fail"] += 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
    for k in AI_KEYS:
        k["status"], k["fail"] = True, 0
    return ai_random.choice(get_kho())

def antispam(m):
    if is_adm(m):
        return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid, []) if now - t < 4] + [now]
    if len(spam[uid]) > 5:
        warns[uid] = warns.get(uid, 0) + 1
        if warns[uid] >= 3:
            try:
                bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time()) + 3600)
            except:
                pass
            del warns[uid]
        else:
            try:
                bot.delete_message(m.chat.id, m.message_id)
            except:
                pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    HANDLERS                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_json(USR_FILE, users)
    brain.trusted.add(m.from_user.id)
    help_text = (
        "🤖 <b>NAO ROBOT - ĐỘT PHÁ AI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>12 GAMES BÃO X10:</b>\n"
        "/taixiu /baucua /kbb /doanso\n"
        "/lxn /xx /caudo /chanle\n"
        "/caothap /keo /bingo /doanso2\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎰 /nohu | 📅 /daily | 💰 /balance\n"
        "🏆 /top | 💸 /give\n"
        "🎙️ /voice [text] - 18 giọng Bắc\n"
        "🔨 /ban /mute /unmute /warn\n"
        "📊 /stats | /ramstatus"
    )
    m2 = bot.reply_to(m, help_text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['voice'])
def voice_cmd(m):
    if not is_grp(m):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_json(USR_FILE, users)
    txt = ""
    if m.reply_to_message and m.reply_to_message.text:
        txt = m.reply_to_message.text.strip()
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1:
            txt = parts[1].strip()
    if not txt:
        vl = "🎙️ <b>18 GIỌNG BẮC THUẦN VIỆT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, v in enumerate(VOICE_LIST, 1):
            vl += f"{i}. {v['emoji']} <b>{v['name']}</b> (x{v['speed']})\n"
        vl += "━━━━━━━━━━━━━━━━━━━━\n"
        vl += "/voice [text] - Random giọng\n"
        vl += "/voice [số] [text] - Chọn giọng"
        m2 = bot.reply_to(m, vl, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    if len(txt) > 500:
        txt = txt[:500]
    selected = None
    parts = txt.split(maxsplit=1)
    if parts[0].isdigit():
        idx = int(parts[0])
        if 1 <= idx <= 18:
            selected = VOICE_LIST[idx - 1]
            txt = parts[1] if len(parts) > 1 else ""
    if not txt:
        m2 = bot.reply_to(m, "❌ Cần text để đọc.")
        del_both(m, m2.message_id)
        return
    req = VoiceRequest(chat_id=m.chat.id, reply_id=m.message_id, text=txt, user_name=m.from_user.first_name, user_id=m.from_user.id, voice=selected)
    try:
        voice_queue.put_nowait(req)
        m2 = bot.reply_to(m, "🎙️ Đã nhận yêu cầu...")
        auto_del(m.chat.id, m2.message_id, 10)
    except:
        m2 = bot.reply_to(m, "⚠️ Hàng đợi đầy, thử lại sau.")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['ban'])
def ban(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if target:
        try:
            bot.ban_chat_member(m.chat.id, target)
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass

@bot.message_handler(commands=['mute'])
def mute(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        return
    dur = parse_duration(reason) if reason else 3600
    try:
        bot.restrict_chat_member(m.chat.id, target, until_date=int(time.time()) + dur, can_send_messages=False)
        bot.delete_message(m.chat.id, m.message_id)
        mutes[target] = int(time.time()) + dur
    except:
        pass

@bot.message_handler(commands=['unmute'])
def unmute(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if target:
        try:
            bot.restrict_chat_member(m.chat.id, target, can_send_messages=True)
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass
        if target in mutes:
            del mutes[target]

@bot.message_handler(commands=['warn'])
def warn(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        return
    warns[target] = warns.get(target, 0) + 1
    cnt = warns[target]
    try:
        bot.delete_message(m.chat.id, m.message_id)
    except:
        pass
    if cnt >= 3:
        try:
            bot.ban_chat_member(m.chat.id, target, until_date=int(time.time()) + 3600)
            del warns[target]
        except:
            pass

@bot.message_handler(commands=['stats'])
def stats(m):
    if not is_grp(m):
        return
    try:
        rc = bot.get_chat_member_count(GROUP_ID)
    except:
        rc = 0
    m2 = bot.reply_to(m, f"📊 <b>THỐNG KÊ</b>\n━━━━━━━━━━━━\n👥 Thành viên: {rc}\n💬 AI: {brain.stats['ai']}\n🎮 Games: {brain.stats['games']}\n🎰 Nổ hũ: {brain.stats['nohu']}\n🎙️ Voice: {brain.stats['voice']}", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['ramstatus'])
def ramstatus(m):
    if not is_grp(m):
        return
    m2 = bot.reply_to(m, f"💾 <b>RAM STATUS</b>\n━━━━━━━━━━━━\n📊 Usage: {ram_mgr.usage_mb():.1f}MB\n🧹 Cleans: {ram_mgr.cleans}\n💨 Freed: {ram_mgr.freed/1024/1024:.1f}MB", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def chat(m):
    if antispam(m) or m.text.startswith('/'):
        return
    uid = m.from_user.id
    if not brain.should_reply(uid, m.text):
        return
    if uid in ai_cd and time.time() - ai_cd[uid] < 2:
        return
    ai_cd[uid] = time.time()
    def _ai():
        reply = ask_ai(m.text)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id):
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
            auto_del(m.chat.id, m2.message_id)
        else:
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
            auto_del(m.chat.id, m2.message_id)
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m):
        return
    for u in m.new_chat_members:
        if u.id == bot.get_me().id:
            continue
        users[str(u.id)] = u.first_name
        save_json(USR_FILE, users)
        member_stats["daily_join"][date.today().isoformat()] += 1
        member_stats["total_joined"] += 1
        member_stats["current_members"] += 1
        m2 = bot.send_message(m.chat.id, f"👋 Chào mừng {html.escape(u.first_name)}!")
        auto_del(m.chat.id, m2.message_id)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m):
    if not is_grp(m):
        return
    u = m.left_chat_member
    if u.id == bot.get_me().id:
        return
    member_stats["daily_leave"][date.today().isoformat()] += 1
    member_stats["total_left"] += 1
    member_stats["current_members"] = max(0, member_stats["current_members"] - 1)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    BACKGROUND TASKS                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def scheduler():
    last = -1
    while True:
        try:
            now = datetime.now(tz)
            if now.minute == 0 and now.hour != last and users:
                uid, un = ai_random.choice(list(users.items()))
                msg = bot.send_message(GROUP_ID, f"🕐 {now.strftime('%H:%M')} | {un}... {ai_random.choice(get_kho())}")
                auto_del(GROUP_ID, msg.message_id)
                last = now.hour
            if now.minute != 0:
                last = -1
            for uid in [u for u, until in mutes.items() if time.time() > until]:
                try:
                    bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                except:
                    pass
                del mutes[uid]
        except:
            pass
        time.sleep(15)

def auto_save():
    while True:
        time.sleep(600)
        try:
            save_json(USR_FILE, users)
            save_json(BAL_FILE, {str(k): v for k, v in balance.items()})
            save_json(DAILY_FILE, daily_ck)
            save_json(JP_FILE, {"jp": nohu_jp})
        except:
            pass

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                    MAIN                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def main():
    global balance, daily_ck, nohu_jp
    if os.path.exists(USR_FILE):
        users.update(load_json(USR_FILE, {}))
    balance = {int(k): v for k, v in load_json(BAL_FILE, {}).items()}
    daily_ck = load_json(DAILY_FILE, {})
    nohu_jp = load_json(JP_FILE, {"jp": 100000}).get("jp", 100000)
    ram_mgr.start()
    logger.info(f"NAO ROBOT v5.0.0 KHỞI ĐỘNG\nUsers: {len(users)} | JP: {nohu_jp:,} xu\n12 Games Bão X10 | 18 Giọng Bắc | AI Chat")
    Thread(target=scheduler, daemon=True).start()
    Thread(target=auto_save, daemon=True).start()
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
