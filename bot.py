# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - AUTO DELETE + CÂU ĐỐ 60S                │
# │  Tự xóa lệnh 3-5s | Game xóa 15-25s | Câu đố timeout 60s              │
# │  Tác giả: palofsc (palo)  |  Ngày: 2026-06-24                          │
# └────────────────────────────────────────────────────────────────────────┘
import sys, io, os, json, time, random, re, html, hashlib, subprocess
import socket, signal, logging, base64, tempfile, asyncio, traceback
import urllib.parse, urllib.request, zipfile, csv, xml.etree.ElementTree as ET
import gc, ctypes, psutil, threading, weakref
from threading import Thread, Lock, Event, Timer
from datetime import datetime, timedelta, date
from collections import deque, defaultdict, OrderedDict, Counter
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, PriorityQueue
from dataclasses import dataclass, field
from io import StringIO, BytesIO
from enum import Enum

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
import telebot; from telebot import types, util; import requests; import pytz

# ─── THƯ VIỆN FILE ──────────────────────────────────────────────────────────
try: import PyPDF2; HAS_PYPDF2 = True
except ImportError: HAS_PYPDF2 = False
try: import docx; HAS_DOCX = True
except ImportError: HAS_DOCX = False
try: from bs4 import BeautifulSoup; HAS_BS4 = True
except ImportError: HAS_BS4 = False
try: import chardet; HAS_CHARDET = True
except ImportError: HAS_CHARDET = False

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI RAM MANAGER                                            ║
# ╚══════════════════════════════════════════════════════════════╝
class MemoryUnit(Enum): BYTES=1; KB=1024; MB=1024**2; GB=1024**3

@dataclass
class MemorySnapshot:
    timestamp: float; rss: int; vms: int; cpu_percent: float; thread_count: int; open_files: int; gc_objects: int

class AIRamManager:
    WARNING_THRESHOLD=0.70; CLEAN_LIGHT=0.75; CLEAN_MEDIUM=0.82; CLEAN_AGGRESSIVE=0.90; CRITICAL=0.95
    def __init__(self, max_ram_mb: int = 512):
        self.max_ram_bytes = max_ram_mb*1024*1024; self.process = psutil.Process(os.getpid())
        self.snapshots: deque = deque(maxlen=100); self.last_clean_time: float = 0
        self.clean_cooldown: float = 30; self.total_cleaned_bytes: int = 0; self.clean_count: int = 0
        self.leak_warnings: int = 0; self.is_cleaning: bool = False; self.clean_lock = Lock()
        self.smart_cache: Dict[str, Tuple[Any, float]] = {}; self.cache_ttl: float = 300
        self.weak_refs: List[weakref.ref] = []; self.active_threads: int = 0; self.max_threads: int = 50

    def get_current_memory(self) -> MemorySnapshot:
        try:
            mem = self.process.memory_info(); cpu = self.process.cpu_percent(interval=0.1)
            threads = self.process.num_threads(); files = 0
            try: files = len(self.process.open_files())
            except: pass
            return MemorySnapshot(time.time(), mem.rss, mem.vms, cpu, threads, files, len(gc.get_objects()))
        except: return MemorySnapshot(time.time(), 0, 0, 0, 0, 0, 0)

    def get_memory_usage_percent(self) -> float: return self.get_current_memory().rss/self.max_ram_bytes
    def get_memory_mb(self) -> float: return self.process.memory_info().rss/(1024*1024)

    def analyze_trend(self) -> str:
        if len(self.snapshots) < 3: return "stable"
        recent = list(self.snapshots)[-5:]; rss_values = [s.rss for s in recent]
        if len(rss_values) < 3: return "stable"
        time_diff = recent[-1].timestamp - recent[0].timestamp
        if time_diff <= 0: return "stable"
        growth_rate = (rss_values[-1] - rss_values[0]) / time_diff
        if growth_rate > 1024*1024: return "critical_growth"
        elif growth_rate > 512*1024: return "rapid_growth"
        elif growth_rate > 100*1024: return "slow_growth"
        return "stable"

    def smart_cache_get(self, key: str) -> Optional[Any]:
        if key in self.smart_cache:
            val, exp = self.smart_cache[key]
            if time.time() < exp: return val
            else: del self.smart_cache[key]
        return None

    def smart_cache_set(self, key: str, value: Any, ttl: float = None):
        if ttl is None: ttl = self.cache_ttl
        self.smart_cache[key] = (value, time.time() + ttl)
        if len(self.smart_cache) > 1000:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:300]: del self.smart_cache[k]

    def clean_level_1(self) -> int:
        freed=0; now=time.time()
        expired=[k for k,(v,exp) in self.smart_cache.items() if now>=exp]
        for k in expired: del self.smart_cache[k]
        freed+=len(expired)*100
        old=len(self.weak_refs); self.weak_refs=[ref for ref in self.weak_refs if ref() is not None]
        freed+=(old-len(self.weak_refs))*50; collected=gc.collect(0); freed+=collected*200; return freed

    def clean_level_2(self) -> int:
        freed=self.clean_level_1(); collected=gc.collect(2); freed+=collected*200
        if len(self.smart_cache)>100:
            sorted_entries=sorted(self.smart_cache.items(),key=lambda x:x[1][1])
            for k,_ in sorted_entries[:len(self.smart_cache)//2]: del self.smart_cache[k]
            freed+=len(self.smart_cache)//2*100
        gc.garbage.clear(); return freed

    def clean_level_3(self) -> int:
        freed=self.clean_level_2()
        if self.smart_cache:
            sorted_entries=sorted(self.smart_cache.items(),key=lambda x:x[1][1])
            for k,_ in sorted_entries[:int(len(self.smart_cache)*0.8)]: del self.smart_cache[k]
            freed+=int(len(self.smart_cache)*0.8)*100
        self.max_threads=max(20,self.max_threads-10)
        try: ctypes.CDLL("libc.so.6").malloc_trim(0); freed+=1024*1024
        except: pass
        for _ in range(3): gc.collect(2)
        gc.garbage.clear(); return freed

    def clean_level_critical(self) -> int:
        freed=self.clean_level_3(); cache_size=len(self.smart_cache); self.smart_cache.clear()
        freed+=cache_size*100; self.max_threads=20; self.weak_refs.clear()
        try: ctypes.CDLL("libc.so.6").malloc_trim(0)
        except: pass
        for _ in range(5): gc.collect(2)
        gc.garbage.clear(); return freed

    def ai_decide_clean(self) -> Tuple[int, str]:
        with self.clean_lock:
            if self.is_cleaning: return 0, "already_cleaning"
            if time.time()-self.last_clean_time < self.clean_cooldown: return 0, "cooldown"
            self.is_cleaning=True
            try:
                usage=self.get_memory_usage_percent(); trend=self.analyze_trend()
                if usage>=self.CRITICAL: freed=self.clean_level_critical(); action="critical_clean"
                elif usage>=self.CLEAN_AGGRESSIVE: freed=self.clean_level_3(); action="aggressive_clean"
                elif usage>=self.CLEAN_MEDIUM: freed=self.clean_level_2(); action="medium_clean"
                elif usage>=self.CLEAN_LIGHT: freed=self.clean_level_1(); action="light_clean"
                elif trend in ["rapid_growth","critical_growth"]: freed=self.clean_level_2(); action="leak_prevention"; self.leak_warnings+=1
                else: gc.collect(0); freed=0; action="stable_no_clean"
                self.last_clean_time=time.time(); self.total_cleaned_bytes+=freed; self.clean_count+=1
                return freed, action
            finally: self.is_cleaning=False

    def monitor_loop(self):
        while True:
            try:
                snapshot=self.get_current_memory(); self.snapshots.append(snapshot)
                if self.get_memory_usage_percent()>=self.WARNING_THRESHOLD: self.ai_decide_clean()
            except: pass
            time.sleep(30)

    def start_monitoring(self):
        Thread(target=self.monitor_loop, daemon=True, name="AIRamMonitor").start()

ram_manager = AIRamManager(max_ram_mb=512)

# ╔══════════════════════════════════════════════════════════════╗
# ║  NÃO (BRAIN)                                               ║
# ╚══════════════════════════════════════════════════════════════╝
class Brain:
    def __init__(self, save_path: str = "brain.json"):
        self.save_path = save_path; self.state: str = "normal"; self.mood: int = 0
        self.learned: defaultdict = defaultdict(int); self.banned_words: set = set(); self.trusted_users: set = set()
        self.stats: Dict[str, Any] = {"msg_processed": 0, "spam_blocked": 0, "ai_calls": 0, "errors": 0,
            "votes_created": 0, "voice_generated": 0, "files_processed": 0, "daily_checkins": 0,
            "nohu_spins": 0, "games_played": 0, "ram_cleans": 0, "ram_freed_mb": 0.0,
            "uptime_start": time.time(), "last_save": time.time()}
        self.decision_log: deque = deque(maxlen=200); self.last_health_check: float = time.time()
        self.repair_mode: bool = False; self.file_lock = Lock(); self.load_state()

    def load_state(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.learned = defaultdict(int, data.get("learned", {}))
                    self.banned_words = set(data.get("banned", [])); self.trusted_users = set(data.get("trusted", []))
                    self.stats.update(data.get("stats", {}))
                    self.stats["uptime_start"] = self.stats.get("uptime_start", time.time())
                    self.state = data.get("state", "normal"); self.mood = data.get("mood", 0)
            except: pass

    def save_state(self):
        with self.file_lock:
            self.stats["last_save"] = time.time(); self.stats["ram_cleans"] = ram_manager.clean_count
            self.stats["ram_freed_mb"] = ram_manager.total_cleaned_bytes / (1024*1024)
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"learned": dict(self.learned), "banned": list(self.banned_words),
                               "trusted": list(self.trusted_users), "stats": self.stats,
                               "state": self.state, "mood": self.mood}, f, ensure_ascii=False, indent=2)
            except: self.stats["errors"] += 1

    def think(self, context: dict) -> str:
        uid = context.get("uid"); txt = context.get("txt", ""); self.stats["msg_processed"] += 1
        for w in re.findall(r'\b\w{3,}\b', txt.lower()): self.learned[w] += 1
        neg = ["bot ngu", "bot dở", "bot lỗi"]; pos = ["bot hay", "bot pro", "cảm ơn bot"]
        if any(p in txt.lower() for p in neg): self.mood -= 2
        elif any(p in txt.lower() for p in pos): self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"
        if len(self.decision_log) % 5 == 0: self.save_state()
        return self.state

    def should_reply(self, uid: int, msg_text: str) -> bool:
        if uid in self.trusted_users: return True
        if self.learned.get(msg_text.lower(), 0) > 5: return random.random() > 0.3
        return random.random() > 0.1

    def get_insult_level(self) -> str:
        if self.state == "aggressive": return "extreme"
        elif self.mood < 0: return "high"
        return "normal"

    def health_check(self) -> str:
        now = time.time()
        if now - self.last_health_check > 300:
            self.last_health_check = now
            if ram_manager.get_memory_usage_percent() >= ram_manager.CLEAN_AGGRESSIVE: ram_manager.ai_decide_clean()
            if self.stats["errors"] > 20: self.repair_mode = True; self.state = "repair"; self.stats["errors"] = 0; return "repair"
            self.save_state()
        return "ok"

brain = Brain()

# ╔══════════════════════════════════════════════════════════════╗
# ║  CẤU HÌNH CHÍNH                                           ║
# ╚══════════════════════════════════════════════════════════════╝
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=50)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
ses = requests.Session()
ses.mount('https://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))
ses.mount('http://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))

ai_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="AI")
voice_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Voice")
file_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="File")
game_executor = ThreadPoolExecutor(max_workers=15, thread_name_prefix="Game")

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI KEYS + KHO CHỬI + BIẾN                                 ║
# ╚══════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0}
]
MAX_FAIL = 3; ck_idx = 0; ck_lock = Lock()

KHO_NORMAL = ["Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.", "Cào phím nhanh, não chậm.", "Ảo tưởng sức mạnh.", "Về nhà rửa bát.", "IQ âm, đừng nói.", "Không ai cần mày.", "Mày là gì? Không là gì.", "Câm mồm, đỡ nhục."]
KHO_HIGH = ["Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?", "Ra đời người ta vả cho.", "Mẹ gọi, về nhà đi.", "Tưởng mình ngầu? Hề vãi.", "Học không lo, cào phím giỏi.", "Tương lai mù mịt như chị Dậu.", "Đời vả mặt, mày cười ngây.", "Không có gì để nói với mày."]
KHO_EXTREME = ["Mày đáng giá bằng cái nút block.", "Tồn tại để làm gì?", "Não mày như ổ đĩa format nhầm.", "Mày là lỗi của tự nhiên.", "Tao chửi mày còn thấy phí thời gian.", "Mày không đáng để tao nhớ tên.", "Cút về lỗ mà mày chui ra.", "Mày là minh chứng cho thất bại của tiến hóa.", "Tao nhìn mày mà tưởng đang xem phim hài.", "Mày sống làm gì?"]
def get_kho():
    lvl = brain.get_insult_level()
    if lvl == "extreme": return KHO_EXTREME
    elif lvl == "high": return KHO_HIGH
    return KHO_NORMAL

lock = Lock(); mem = deque(maxlen=50)
users: Dict[str, str] = {}; spam: Dict[int, List[float]] = {}; warn_counts: Dict[int, int] = {}
mutes: Dict[int, float] = {}; ai_cd: Dict[int, float] = {}; vote_active: Dict[int, Dict] = {}
file_cache: Dict[str, Dict] = {}; user_balance: Dict[int, int] = {}; daily_checkin: Dict[int, str] = {}
nohu_jackpot: int = 0; nohu_history: deque = deque(maxlen=20)
nohu_base = 100000; nohu_fee = 1000; nohu_multiplier = 0.05
member_stats: Dict[str, Any] = {"daily_join": defaultdict(int), "daily_leave": defaultdict(int), "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}, "last_updated": time.time()}
GAME_SESSIONS: Dict[int, Dict] = {}
GAME_LEADERBOARDS: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

BALANCE_FILE = "balances.json"; DAILY_FILE = "daily_checkins.json"; JACKPOT_FILE = "jackpot.json"
USR_FILE = "usr.json"; STATS_FILE = "member_stats.json"; RULES_FILE = "rules.txt"
MAX_FILE_SIZE = 20*1024*1024; MAX_CACHE_SIZE = 50
TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}', re.I)

# ═══════════ AUTO-DELETE CONFIG ═══════════
CMD_DELETE_DELAY = 4        # Xóa lệnh sau 4 giây
GAME_DELETE_DELAY = 20      # Xóa kết quả game sau 20 giây
CAUDO_TIMEOUT = 60          # Câu đố timeout sau 60 giây
AUTO_DELETE_ENABLED = True  # Bật/tắt tự động xóa

# ╔══════════════════════════════════════════════════════════════╗
# ║  AUTO-DELETE SYSTEM (THÔNG MINH)                           ║
# ╚══════════════════════════════════════════════════════════════╝

class AutoDeleteManager:
    """Quản lí tự động xóa tin nhắn với thời gian khác nhau cho từng loại."""
    
    def __init__(self):
        self.delete_queue: Queue = Queue()
        self.delete_tasks: Dict[int, Timer] = {}  # msg_id -> Timer
        self.lock = Lock()
        
    def schedule_delete(self, chat_id: int, msg_id: int, delay: int, msg_type: str = "cmd"):
        """Lên lịch xóa tin nhắn với delay tùy chỉnh."""
        if not AUTO_DELETE_ENABLED: return
        
        def _delete():
            time.sleep(delay)
            try: bot.delete_message(chat_id, msg_id)
            except: pass
            with self.lock:
                if msg_id in self.delete_tasks: del self.delete_tasks[msg_id]
        
        # Hủy timer cũ nếu có
        with self.lock:
            if msg_id in self.delete_tasks:
                self.delete_tasks[msg_id].cancel()
            timer = Timer(delay, lambda: None)  # Timer rỗng
            self.delete_tasks[msg_id] = timer
        
        Thread(target=_delete, daemon=True).start()
    
    def delete_command(self, m, delay: int = None):
        """Xóa lệnh người dùng."""
        if delay is None: delay = CMD_DELETE_DELAY
        self.schedule_delete(m.chat.id, m.message_id, delay, "cmd")
    
    def delete_game_result(self, m, bot_msg_id: int, delay: int = None):
        """Xóa kết quả game (chậm hơn)."""
        if delay is None: delay = GAME_DELETE_DELAY
        self.schedule_delete(m.chat.id, bot_msg_id, delay, "game")
    
    def delete_both(self, m, bot_msg_id: int, cmd_delay: int = None, game_delay: int = None):
        """Xóa cả lệnh và kết quả game."""
        self.delete_command(m, cmd_delay)
        self.delete_game_result(m, bot_msg_id, game_delay)
    
    def cancel_delete(self, msg_id: int):
        """Hủy xóa nếu cần."""
        with self.lock:
            if msg_id in self.delete_tasks:
                self.delete_tasks[msg_id].cancel()
                del self.delete_tasks[msg_id]

auto_delete = AutoDeleteManager()

# ╔══════════════════════════════════════════════════════════════╗
# ║  TIỆN ÍCH (CÓ SMART CACHE)                                 ║
# ╚══════════════════════════════════════════════════════════════╝
def load_json(path: str, default: Any = {}) -> Any:
    cached = ram_manager.smart_cache_get(f"json_{path}")
    if cached is not None: return cached
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f); ram_manager.smart_cache_set(f"json_{path}", data, 60); return data
        except: pass
    return default

def save_json(path: str, data: Any) -> None:
    with lock:
        try:
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
            ram_manager.smart_cache_set(f"json_{path}", data, 60)
        except: pass

def load_users() -> Dict[str, str]: return load_json(USR_FILE, {})
def save_users(data: Dict[str, str]): save_json(USR_FILE, data)
def load_balances() -> Dict[int, int]: return {int(k): v for k, v in load_json(BALANCE_FILE, {}).items()}
def save_balances(data: Dict[int, int]): save_json(BALANCE_FILE, {str(k): v for k, v in data.items()})
def load_daily_checkins() -> Dict[int, str]: return {int(k): v for k, v in load_json(DAILY_FILE, {}).items()}
def save_daily_checkins(data: Dict[int, str]): save_json(DAILY_FILE, {str(k): v for k, v in data.items()})
def load_jackpot() -> int: return load_json(JACKPOT_FILE, {"jackpot": nohu_base}).get("jackpot", nohu_base)
def save_jackpot(jackpot: int): save_json(JACKPOT_FILE, {"jackpot": jackpot, "history": list(nohu_history)})
def load_member_stats() -> Dict:
    data = load_json(STATS_FILE, {"daily_join": {}, "daily_leave": {}, "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}})
    data["daily_join"] = defaultdict(int, data.get("daily_join", {})); data["daily_leave"] = defaultdict(int, data.get("daily_leave", {}))
    return data
def save_member_stats():
    data = dict(member_stats); data["daily_join"] = dict(data["daily_join"]); data["daily_leave"] = dict(data["daily_leave"])
    save_json(STATS_FILE, data)

def del_msg(chat_id: int, msg_id: int, delay: int = 60):
    Thread(target=lambda: (time.sleep(delay), bot.delete_message(chat_id, msg_id)), daemon=True).start()

def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        for admin in bot.get_chat_administrators(chat_id):
            if admin.user.id == user_id: return True
    except: pass
    return False

def is_grp(m) -> bool: return m.chat.id == GROUP_ID

def extract_user_and_reason(message, bot_username: str) -> Tuple[Optional[int], str]:
    target=None; reason=""
    if message.reply_to_message:
        target=message.reply_to_message.from_user.id
        parts=message.text.split(maxsplit=1)
        if len(parts)>1: reason=parts[1]
    else:
        parts=message.text.split(maxsplit=1)
        if len(parts)>1:
            arg=parts[1].strip()
            if arg.isdigit(): target=int(arg)
            else:
                m=re.match(r'@(\w+)',arg)
                if m:
                    try: target=bot.get_chat_member(message.chat.id,m.group(0)).user.id; reason=arg[m.end():].strip()
                    except: pass
                else:
                    nm=re.search(r'\d+',arg)
                    if nm: target=int(nm.group()); reason=arg[nm.end():].strip()
    return target, reason

def parse_duration(reason: str) -> int:
    m=re.search(r'(\d+)\s*(h|m|s|p)',reason.lower())
    if m:
        num=int(m.group(1)); unit=m.group(2)
        if unit=='s': return num
        elif unit=='m': return num*60
        elif unit=='h': return num*3600
        elif unit=='p': return num*60
    return 3600

def get_user_balance(uid: int) -> int:
    if uid not in user_balance: user_balance[uid]=5000; save_balances(user_balance)
    return user_balance[uid]

def add_balance(uid: int, amount: int) -> int:
    bal=get_user_balance(uid); user_balance[uid]=max(0,bal+amount); save_balances(user_balance); return user_balance[uid]

def deduct_balance(uid: int, amount: int) -> bool:
    bal=get_user_balance(uid)
    if bal>=amount: user_balance[uid]=bal-amount; save_balances(user_balance); return True
    return False

# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE TTS VOICE                                          ║
# ╚══════════════════════════════════════════════════════════════╝
GOOGLE_TTS_URL="https://translate.google.com/translate_tts"
GOOGLE_TTS_HEADERS={"User-Agent":"Mozilla/5.0","Accept":"audio/mpeg, audio/*;q=0.9","Referer":"https://translate.google.com/"}
MAX_CHUNK_SIZE=180

@dataclass
class VoiceRequest:
    chat_id: int; reply_id: int; text: str; user_name: str; lang: str="vi"
    created_at: float=field(default_factory=time.time)

voice_queue: Queue=Queue(maxsize=50)

def fetch_google_tts_chunk(text: str, lang: str="vi") -> Optional[bytes]:
    params={"ie":"UTF-8","q":text,"tl":lang,"total":"1","idx":"0","textlen":str(len(text)),"client":"tw-ob","prev":"input","ttsspeed":"1.0"}
    try:
        resp=ses.get(GOOGLE_TTS_URL,params=params,headers=GOOGLE_TTS_HEADERS,timeout=15)
        if resp.status_code==200 and len(resp.content)>100: return resp.content
    except: pass
    return None

def split_text_into_chunks(text: str, max_size: int=MAX_CHUNK_SIZE) -> List[str]:
    if len(text)<=max_size: return [text]
    chunks=[]; separators=['. ','! ','? ',', ','; ',': ',' - ','\n',' ']
    while len(text)>max_size:
        best_pos=max_size
        for sep in separators:
            pos=text.rfind(sep,0,max_size)
            if pos>max_size//2: best_pos=pos+len(sep); break
        if best_pos>max_size or best_pos<=max_size//3: best_pos=max_size
        chunks.append(text[:best_pos].strip()); text=text[best_pos:].strip()
    if text: chunks.append(text)
    return chunks

def generate_voice_google(text: str, lang: str="vi") -> Tuple[Optional[BytesIO], str]:
    clean_text=re.sub(r'[<>"\'{}|\\^~\[\]`]','',text).strip()
    if not clean_text: return None,"Text rỗng."
    chunks=split_text_into_chunks(clean_text); audio_chunks=[]
    for chunk in chunks:
        audio=fetch_google_tts_chunk(chunk,lang)
        if audio: audio_chunks.append(audio)
    if not audio_chunks: return None,"Không thể tạo audio."
    return BytesIO(b"".join(audio_chunks)),"ok"

def voice_worker():
    while True:
        try:
            req: VoiceRequest=voice_queue.get(block=True,timeout=1)
            if not req: continue
            voice_text=req.text[:500].strip()
            if not voice_text: voice_queue.task_done(); continue
            audio,result_msg=generate_voice_google(voice_text,req.lang)
            if audio and result_msg=="ok":
                audio.name=f"voice_{int(time.time())}.mp3"
                try: bot.send_voice(req.chat_id,audio,reply_to_message_id=req.reply_id,caption=f"🎙️ {html.escape(voice_text[:200])}",parse_mode="HTML"); brain.stats["voice_generated"]+=1
                except:
                    audio.seek(0)
                    try: bot.send_audio(req.chat_id,audio,reply_to_message_id=req.reply_id,title="Voice",caption=f"🎙️ {html.escape(voice_text[:200])}",parse_mode="HTML"); brain.stats["voice_generated"]+=1
                    except: pass
            voice_queue.task_done()
        except:
            try: voice_queue.task_done()
            except: pass

for _ in range(4): Thread(target=voice_worker, daemon=True).start()

@bot.message_handler(commands=['voice'])
def voice_cmd(m):
    if not is_grp(m) or antispam(m): return
    users[str(m.from_user.id)]=m.from_user.first_name; save_users(users)
    voice_text=""
    if m.reply_to_message and m.reply_to_message.text: voice_text=m.reply_to_message.text.strip()
    elif m.text.strip()!='/voice':
        parts=m.text.split(maxsplit=1)
        if len(parts)>1: voice_text=parts[1].strip()
    if not voice_text: msg=bot.reply_to(m,"❌ /voice [text] hoặc reply.",parse_mode="HTML"); del_msg(m.chat.id,msg.message_id,10); return
    if len(voice_text)>500: voice_text=voice_text[:500]
    try:
        voice_queue.put_nowait(VoiceRequest(chat_id=m.chat.id,reply_id=m.message_id,text=voice_text,user_name=m.from_user.first_name))
        msg=bot.reply_to(m,"🎙️ Đang tạo voice...",parse_mode="HTML"); auto_delete.delete_command(m,3)
    except: bot.reply_to(m,"⚠️ Hàng đợi voice đầy.",parse_mode="HTML")

# ╔══════════════════════════════════════════════════════════════╗
# ║  ĐIỂM DANH + BALANCE + TOP                                 ║
# ╚══════════════════════════════════════════════════════════════╝
def get_daily_reward(uid: int, consecutive_days: int=1) -> int: return 500+min(consecutive_days-1,6)*200

@bot.message_handler(commands=['daily','diemdanh','checkin'])
def daily_checkin_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; today=date.today().isoformat()
    users[str(uid)]=m.from_user.first_name; save_users(users)
    last_checkin=daily_checkin.get(uid,""); yesterday=(date.today()-timedelta(days=1)).isoformat()
    if last_checkin==today:
        bal=get_user_balance(uid); msg=bot.reply_to(m,f"❌ <b>{html.escape(m.from_user.first_name)}</b>, hôm nay đã điểm danh!\n💰 {bal:,} xu",parse_mode="HTML"); auto_delete.delete_command(m,8); return
    consecutive=1
    if last_checkin==yesterday:
        d=date.today()-timedelta(days=1)
        for i in range(1,7):
            if daily_checkin.get(uid)==(d-timedelta(days=i)).isoformat(): consecutive+=1
            else: break
    reward=get_daily_reward(uid,consecutive); daily_checkin[uid]=today; save_daily_checkins(daily_checkin)
    add_balance(uid,reward); brain.stats["daily_checkins"]+=1
    streak_emoji=["","🔥","🔥🔥","💥","💥💥","⚡","👑"][min(consecutive-1,6)] if consecutive>1 else ""
    msg=bot.reply_to(m,f"✅ <b>ĐIỂM DANH!</b>\n👤 {html.escape(m.from_user.first_name)}\n💰 +{reward:,} xu | 📅 {consecutive} ngày {streak_emoji}\n💎 {get_user_balance(uid):,} xu",parse_mode="HTML")
    auto_delete.delete_command(m,8)

@bot.message_handler(commands=['balance','xu','money'])
def balance_cmd(m):
    if not is_grp(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users)
    target,target_name=uid,m.from_user.first_name
    if m.reply_to_message: target,target_name=m.reply_to_message.from_user.id,m.reply_to_message.from_user.first_name
    bal=get_user_balance(target); msg=bot.reply_to(m,f"💎 <b>{html.escape(target_name)}</b>: <b>{bal:,}</b> xu",parse_mode="HTML")
    auto_delete.delete_command(m,6)

@bot.message_handler(commands=['top','bxh'])
def top_balance_cmd(m):
    if not is_grp(m): return
    sorted_balances=sorted(user_balance.items(),key=lambda x:x[1],reverse=True)[:10]
    text="🏆 <b>BẢNG XẾP HẠNG</b>\n"; medals=["🥇","🥈","🥉"]+["  "]*7
    for i,(uid,bal) in enumerate(sorted_balances):
        name=users.get(str(uid),str(uid)); text+=f"{medals[i]} <b>#{i+1}</b> <a href='tg://user?id={uid}'>{html.escape(name)}</a>: <code>{bal:,}</code> xu\n"
    msg=bot.reply_to(m,text,parse_mode="HTML"); auto_delete.delete_command(m,10)

@bot.message_handler(commands=['give','chuyen'])
def give_money_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users)
    target,amount=None,0
    if m.reply_to_message:
        target=m.reply_to_message.from_user.id; parts=m.text.split()
        if len(parts)>=2:
            try: amount=int(parts[1])
            except: amount=0
    else:
        parts=m.text.split()
        if len(parts)>=3:
            mention_match=re.match(r'@(\w+)',parts[1])
            if mention_match:
                try: target=bot.get_chat_member(m.chat.id,parts[1]).user.id
                except: target=None
            elif parts[1].isdigit(): target=int(parts[1])
            try: amount=int(parts[2])
            except: amount=0
    if not target or target==uid: msg=bot.reply_to(m,"❌ Reply/@mention + số xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if amount<100: msg=bot.reply_to(m,"❌ Tối thiểu 100 xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    fee,total=int(amount*0.05),amount+fee
    if not deduct_balance(uid,total): bal=get_user_balance(uid); msg=bot.reply_to(m,f"❌ Không đủ! Cần <b>{total:,}</b> (phí {fee:,}). Số dư: <b>{bal:,}</b>",parse_mode="HTML"); auto_delete.delete_command(m); return
    add_balance(target,amount); target_name=users.get(str(target),str(target))
    msg=bot.reply_to(m,f"💸 {html.escape(m.from_user.first_name)} → <a href='tg://user?id={target}'>{html.escape(target_name)}</a>: <b>{amount:,}</b> xu (phí {fee:,})",parse_mode="HTML")
    auto_delete.delete_command(m,8)

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI NỔ HŨ                                                  ║
# ╚══════════════════════════════════════════════════════════════╝
SLOT_SYMBOLS=["🍒","🍋","🍊","🍇","💎","🔔","7️⃣"]; SLOT_WEIGHTS=[28,24,20,16,6,4,2]
SLOT_PAYOUTS={"🍒🍒🍒":5,"🍋🍋🍋":8,"🍊🍊🍊":12,"🍇🍇🍇":20,"💎💎💎":50,"🔔🔔🔔":100,"7️⃣7️⃣7️⃣":500}

class AINoHu:
    @staticmethod
    def ai_adjust_weights(jackpot: int) -> List[int]:
        base_weights=SLOT_WEIGHTS.copy()
        if jackpot>nohu_base*3: base_weights[6]=max(1,base_weights[6]-2); base_weights[0]+=2
        elif jackpot>nohu_base*5: base_weights[6]=max(1,base_weights[6]-3); base_weights[1]+=2
        return base_weights

    @staticmethod
    def ai_decide_bonus(jackpot: int) -> float:
        if jackpot<nohu_base: return 0.08
        elif jackpot<nohu_base*2: return 0.05
        elif jackpot<nohu_base*3: return 0.04
        else: return 0.03

ai_nohu=AINoHu()

@bot.message_handler(commands=['nohu','slot','quay'])
def nohu_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    if len(parts)<2:
        jackpot=load_jackpot(); msg=bot.reply_to(m,f"🎰 <b>AI NỔ HŨ</b>\n💰 JACKPOT: <b>{jackpot:,}</b> xu\n🎮 /nohu [cược] (Phí: {nohu_fee:,} xu)\n🏆 7️⃣7️⃣7️⃣ = JACKPOT!",parse_mode="HTML"); auto_delete.delete_command(m,8); return
    try: bet=int(parts[1])
    except: bot.reply_to(m,"❌ Cược phải là số.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if bet<100 or bet>100000: bot.reply_to(m,"❌ 100 - 100,000 xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    total_cost=bet+nohu_fee
    if not deduct_balance(uid,total_cost): bal=get_user_balance(uid); bot.reply_to(m,f"❌ Không đủ! Cần <b>{total_cost:,}</b>. Số dư: <b>{bal:,}</b>",parse_mode="HTML"); auto_delete.delete_command(m); return
    
    jackpot=load_jackpot(); bonus_rate=ai_nohu.ai_decide_bonus(jackpot)
    jackpot_contribution=int(bet*bonus_rate); jackpot+=jackpot_contribution; save_jackpot(jackpot); brain.stats["nohu_spins"]+=1
    
    weights=ai_nohu.ai_adjust_weights(jackpot); col1,col2,col3=[random.choices(SLOT_SYMBOLS,weights=weights,k=1)[0] for _ in range(3)]
    
    if col1==col2==col3:
        if col1=="7️⃣": win_amount=jackpot; add_balance(uid,win_amount); nohu_history.append({"uid":uid,"name":m.from_user.first_name,"amount":win_amount,"time":datetime.now(tz).strftime("%H:%M %d/%m")}); save_jackpot(nohu_base); outcome=f"🎉🎉🎉 <b>JACKPOT!!!</b> +{win_amount:,} xu"; emoji="🏆"
        else: multiplier=SLOT_PAYOUTS.get(f"{col1}{col2}{col3}",2); win_amount=bet*multiplier; add_balance(uid,win_amount); outcome=f"✅ NỔ HŨ! (x{multiplier}) +{win_amount:,} xu"; emoji="🎉"
    elif col1==col2 or col2==col3 or col1==col3: win_amount=int(bet*0.5); add_balance(uid,win_amount); outcome=f"🔄 2 giống: hoàn {win_amount:,} xu"; emoji="🔹"
    else: win_amount=0; outcome=f"💀 Thua -{total_cost:,} xu"; emoji="❌"
    
    msg=bot.reply_to(m,f"{emoji} <b>AI NỔ HŨ</b>\n┌──────────┐\n│ {col1}  {col2}  {col3} │\n└──────────┘\n🎯 {outcome}\n💰 JACKPOT: <b>{load_jackpot():,}</b> xu\n💎 Số dư: <b>{get_user_balance(uid):,}</b> xu",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

@bot.message_handler(commands=['jackpot','jp'])
def jackpot_cmd(m):
    if not is_grp(m): return
    jackpot=load_jackpot(); text=f"🎰 <b>NỔ HŨ JACKPOT</b>\n💰 <b>{jackpot:,} xu</b>\n🎮 /nohu [cược] để quay!\n📜 Lịch sử:\n"
    for h in list(nohu_history)[-5:]: text+=f"🏆 {h['name']} +{h['amount']:,} xu ({h['time']})\n"
    if not nohu_history: text+="  Chưa có ai trúng.\n"
    msg=bot.reply_to(m,text,parse_mode="HTML"); auto_delete.delete_command(m,8)

# ╔══════════════════════════════════════════════════════════════╗
# ║  MINI GAMES (7 GAMES)                                      ║
# ╚══════════════════════════════════════════════════════════════╝
def init_game_state(uid: int, game_type: str) -> Dict:
    if game_type=="taixiu": return {"type":"taixiu","balance":1000,"wins":0,"losses":0}
    elif game_type=="baucua": return {"type":"baucua","balance":1000,"symbols":["🦀","🐟","🦐","🐓","🦌","🎃"],"wins":0,"losses":0}
    elif game_type=="keobuabao": return {"type":"keobuabao","score":0,"bot_score":0,"draws":0}
    elif game_type=="doanso": return {"type":"doanso","secret":random.randint(1,100),"attempts":0,"max_attempts":7}
    elif game_type=="lacxingau": return {"type":"lacxingau","balance":1000,"wins":0,"losses":0}
    elif game_type=="caudo": return {"type":"caudo","score":0,"questions":0,"current":None,"hint_used":False,"timeout_timer":None,"answered":False}
    elif game_type=="xucxac": return {"type":"xucxac","balance":1000,"wins":0,"losses":0}
    return {}

# ─── GAME 1: TÀI XỈU ──────────────────────────────────────────────────
@bot.message_handler(commands=['taixiu'])
def taixiu_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="taixiu": GAME_SESSIONS[uid]=init_game_state(uid,"taixiu")
        g=GAME_SESSIONS.get(uid,{}); msg=bot.reply_to(m,f"🎲 <b>TÀI XỈU</b>\n/taixiu [tai/xiu] [cược]\n💎 Game: <b>{g.get('balance',1000)}</b> xu\nTài (11-18) | Xỉu (3-10)",parse_mode="HTML"); auto_delete.delete_command(m,8); return
    choice,bet=parts[1].lower(),0
    try: bet=int(parts[2])
    except: bot.reply_to(m,"❌ Cược phải là số.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if choice not in ['tai','xiu']: bot.reply_to(m,"❌ 'tai' hoặc 'xiu'.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="taixiu": GAME_SESSIONS[uid]=init_game_state(uid,"taixiu")
    g=GAME_SESSIONS[uid]
    if bet>g["balance"] or bet<1: bot.reply_to(m,f"❌ Số dư game: {g['balance']} xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    dice=[random.randint(1,6) for _ in range(3)]; total=sum(dice); result="tai" if total>=11 else "xiu"
    dice_str=" ".join([["⚀","⚁","⚂","⚃","⚄","⚅"][d-1] for d in dice])
    if choice==result: g["balance"]+=bet; g["wins"]+=1; outcome=f"✅ THẮNG +{bet} xu"
    else: g["balance"]-=bet; g["losses"]+=1; outcome=f"❌ THUA -{bet} xu"
    brain.stats["games_played"]+=1
    msg=bot.reply_to(m,f"🎲 <b>TÀI XỈU</b>\n🎲 {dice_str} = <b>{total}</b> → <b>{result.upper()}</b>\n🎯 Bạn: <b>{choice.upper()}</b>\n💰 {outcome} | 💎 {g['balance']} xu\n📊 W:{g['wins']} L:{g['losses']}",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

# ─── GAME 2: BẦU CUA ──────────────────────────────────────────────────
@bot.message_handler(commands=['baucua'])
def baucua_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    symbol_map={"bau":0,"bầu":0,"cua":1,"ca":2,"cá":2,"tom":3,"tôm":3,"ga":4,"gà":4,"nai":5,"huou":5,"hươu":5}
    game_symbols=["🦀 Bầu","🐟 Cua","🦐 Cá","🐓 Tôm","🦌 Gà","🎃 Nai"]
    if len(parts)<3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="baucua": GAME_SESSIONS[uid]=init_game_state(uid,"baucua")
        g=GAME_SESSIONS.get(uid,{}); msg=bot.reply_to(m,f"🎲 <b>BẦU CUA</b>\n{' | '.join(game_symbols)}\n/baucua [con] [cược]\n💎 Game: <b>{g.get('balance',1000)}</b> xu",parse_mode="HTML"); auto_delete.delete_command(m,10); return
    choice,bet=parts[1].lower(),0
    try: bet=int(parts[2])
    except: bot.reply_to(m,"❌ Cược phải là số.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if choice not in symbol_map: bot.reply_to(m,f"❌ Chọn: {', '.join(symbol_map.keys())}",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="baucua": GAME_SESSIONS[uid]=init_game_state(uid,"baucua")
    g=GAME_SESSIONS[uid]
    if bet>g["balance"] or bet<1: bot.reply_to(m,f"❌ Số dư game: {g['balance']} xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    choice_idx=symbol_map[choice]; roll=[random.randint(0,5) for _ in range(3)]; roll_symbols=[g["symbols"][i] for i in roll]; matches=roll.count(choice_idx)
    if matches>0: win_amount=bet*(matches+1); g["balance"]+=win_amount-bet; g["wins"]+=1; outcome=f"✅ THẮNG +{win_amount-bet} xu (trúng {matches} con)"
    else: g["balance"]-=bet; g["losses"]+=1; outcome=f"❌ THUA -{bet} xu"
    brain.stats["games_played"]+=1
    msg=bot.reply_to(m,f"🎲 <b>BẦU CUA</b>\n🎯 {' '.join(roll_symbols)}\n🎯 Bạn: <b>{g['symbols'][choice_idx]}</b> (trúng {matches}/3)\n💰 {outcome} | 💎 {g['balance']} xu",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

# ─── GAME 3: KÉO BÚA BAO ──────────────────────────────────────────────
@bot.message_handler(commands=['kbb','keobuabao'])
def kbb_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    choices={"keo":"✌️ Kéo","kéo":"✌️ Kéo","bua":"🔨 Búa","búa":"🔨 Búa","bao":"📄 Bao"}
    if len(parts)<2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="keobuabao": GAME_SESSIONS[uid]=init_game_state(uid,"keobuabao")
        g=GAME_SESSIONS.get(uid,{}); msg=bot.reply_to(m,f"✌️ <b>KÉO BÚA BAO</b>\n/kbb [keo/bua/bao]\n👤 {g.get('score',0)} | 🤖 {g.get('bot_score',0)} | 🤝 {g.get('draws',0)}",parse_mode="HTML"); auto_delete.delete_command(m,6); return
    choice=parts[1].lower()
    if choice not in choices: bot.reply_to(m,"❌ keo/bua/bao",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="keobuabao": GAME_SESSIONS[uid]=init_game_state(uid,"keobuabao")
    g=GAME_SESSIONS[uid]; user_choice,bot_choice=choices[choice],random.choice(list(choices.values()))
    ui,bi=list(choices.values()).index(user_choice),list(choices.values()).index(bot_choice)
    if ui==bi: result="🤝 HÒA"; g["draws"]+=1
    elif (ui==0 and bi==2) or (ui==1 and bi==0) or (ui==2 and bi==1): result="✅ THẮNG"; g["score"]+=1
    else: result="❌ THUA"; g["bot_score"]+=1
    brain.stats["games_played"]+=1
    msg=bot.reply_to(m,f"✌️ <b>KÉO BÚA BAO</b>\n👤 {user_choice} vs 🤖 {bot_choice}\n📊 {result}\n🏆 Bạn: <b>{g['score']}</b> | Bot: <b>{g['bot_score']}</b> | Hòa: <b>{g['draws']}</b>",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

# ─── GAME 4: ĐOÁN SỐ ──────────────────────────────────────────────────
@bot.message_handler(commands=['doanso'])
def doanso_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    if len(parts)<2:
        GAME_SESSIONS[uid]=init_game_state(uid,"doanso"); msg=bot.reply_to(m,"🔢 <b>ĐOÁN SỐ</b> (1-100)\n/doanso [số]\nCó <b>7</b> lần đoán!",parse_mode="HTML"); auto_delete.delete_command(m,6); return
    try: guess=int(parts[1])
    except: bot.reply_to(m,"❌ Nhập số 1-100.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if guess<1 or guess>100: bot.reply_to(m,"❌ 1-100.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="doanso": GAME_SESSIONS[uid]=init_game_state(uid,"doanso")
    g=GAME_SESSIONS[uid]; g["attempts"]+=1; secret=g["secret"]; brain.stats["games_played"]+=1
    if guess==secret:
        reward=(8-g["attempts"])*500; add_balance(uid,reward)
        msg=bot.reply_to(m,f"🎉 <b>CHÍNH XÁC!</b> Số <b>{secret}</b> ({g['attempts']} lần)\n💰 +{reward:,} xu",parse_mode="HTML"); del GAME_SESSIONS[uid]
    elif g["attempts"]>=g["max_attempts"]: msg=bot.reply_to(m,f"💀 <b>HẾT LƯỢT!</b> Số là <b>{secret}</b>.",parse_mode="HTML"); del GAME_SESSIONS[uid]
    elif guess<secret: msg=bot.reply_to(m,f"🔢 <b>{guess}</b> → ⬆️ CAO HƠN ({g['max_attempts']-g['attempts']} lần)",parse_mode="HTML")
    else: msg=bot.reply_to(m,f"🔢 <b>{guess}</b> → ⬇️ THẤP HƠN ({g['max_attempts']-g['attempts']} lần)",parse_mode="HTML")
    auto_delete.delete_game_result(m, msg.message_id)

# ─── GAME 5: LẮC XÍ NGẦU ──────────────────────────────────────────────
@bot.message_handler(commands=['lacxingau','lxn'])
def lacxingau_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="lacxingau": GAME_SESSIONS[uid]=init_game_state(uid,"lacxingau")
        g=GAME_SESSIONS.get(uid,{}); msg=bot.reply_to(m,f"🎲 <b>LẮC XÍ NGẦU</b>\n/lxn [tổng 3-18] [cược]\n💎 Game: <b>{g.get('balance',1000)}</b> xu\nTrúng chính xác: x10!",parse_mode="HTML"); auto_delete.delete_command(m,8); return
    try: guess_total,bet=int(parts[1]),int(parts[2])
    except: bot.reply_to(m,"❌ /lxn [tổng 3-18] [cược]",parse_mode="HTML"); auto_delete.delete_command(m); return
    if guess_total<3 or guess_total>18: bot.reply_to(m,"❌ 3-18.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="lacxingau": GAME_SESSIONS[uid]=init_game_state(uid,"lacxingau")
    g=GAME_SESSIONS[uid]
    if bet>g["balance"] or bet<1: bot.reply_to(m,f"❌ Số dư game: {g['balance']} xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    dice=[random.randint(1,6) for _ in range(3)]; total=sum(dice)
    dice_str=" ".join([["⚀","⚁","⚂","⚃","⚄","⚅"][d-1] for d in dice])
    if total==guess_total: win_amount=bet*10; g["balance"]+=win_amount-bet; g["wins"]+=1; outcome=f"🎉 CHÍNH XÁC! +{win_amount-bet} xu (x10)"
    elif abs(total-guess_total)==1: win_amount=int(bet*0.5); g["balance"]+=win_amount-bet; outcome=f"🔄 Gần đúng (lệch 1)! Hoàn {win_amount} xu"
    else: g["balance"]-=bet; g["losses"]+=1; outcome=f"💀 Thua -{bet} xu"
    brain.stats["games_played"]+=1
    msg=bot.reply_to(m,f"🎲 <b>LẮC XÍ NGẦU</b>\n🎲 {dice_str} = <b>{total}</b>\n🎯 Bạn đoán: <b>{guess_total}</b>\n💰 {outcome} | 💎 {g['balance']} xu",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

# ─── GAME 6: CÂU ĐỐ 60 GIÂY (CẢI TIẾN) ────────────────────────────────
CAUDO_LIST = [
    {"q":"Cái gì càng nhiều càng nhẹ?","a":["bong bóng","bong bong","bóng"],"hint":"Nó bay được"},
    {"q":"Con gì đập thì sống, không đập thì chết?","a":["con tim","tim"],"hint":"Liên quan đến cơ thể"},
    {"q":"Cái gì có mắt mà không thấy?","a":["cái kim","kim"],"hint":"Dùng để may vá"},
    {"q":"Cái gì càng rửa càng bẩn?","a":["nước","nuoc"],"hint":"Chất lỏng"},
    {"q":"Con gì đầu dê mình ốc?","a":["con dốc","dốc","doc"],"hint":"Không phải con vật"},
    {"q":"Cái gì có cổ mà không có đầu?","a":["cái áo","áo","ao"],"hint":"Mặc hàng ngày"},
    {"q":"Quần gì rộng nhất?","a":["quần đảo","quan dao"],"hint":"Địa lý"},
    {"q":"Xã gì đông nhất?","a":["xã hội","xa hoi"],"hint":"Liên quan đến con người"},
    {"q":"Núi gì bị chặt ra từng khúc?","a":["núi thái sơn","thái sơn","thai son"],"hint":"Liên quan đến Trung Quốc"},
    {"q":"Cái gì bằng cái vung, vùng xuống ao, đào chẳng thấy, lấy chẳng được?","a":["bóng trăng","mặt trăng","trăng","bong trang","mat trang"],"hint":"Trên trời"},
    {"q":"Cái gì càng cao càng nhỏ?","a":["cái thang","thang"],"hint":"Dùng để leo"},
    {"q":"Con gì ăn lửa với nước than?","a":["con tàu","tàu","tau"],"hint":"Phương tiện giao thông"},
    {"q":"Cái gì có răng mà không có miệng?","a":["cái cưa","cưa","cua"],"hint":"Dùng để cắt gỗ"},
    {"q":"Cái gì đen khi mua, đỏ khi dùng, xám khi vứt?","a":["than","củ than","cu than"],"hint":"Dùng để đốt"},
    {"q":"Cái gì càng kéo càng ngắn?","a":["điếu thuốc","thuốc lá","thuoc la","dieu thuoc"],"hint":"Hút"},
]

@bot.message_handler(commands=['caudo','cd'])
def caudo_cmd(m):
    """Game câu đố với timeout 60 giây: /caudo [đáp án] hoặc /caudo để bắt đầu."""
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    
    # Bắt đầu câu đố mới
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="caudo" or GAME_SESSIONS[uid].get("answered",False):
        puzzle=random.choice(CAUDO_LIST)
        GAME_SESSIONS[uid]={"type":"caudo","score":0,"questions":1,"current":puzzle,"hint_used":False,"timeout_timer":None,"answered":False,"start_time":time.time()}
        
        # Gửi câu đố
        msg=bot.reply_to(m,f"🧩 <b>CÂU ĐỐ #{GAME_SESSIONS[uid]['questions']}</b>\n⏰ <b>{CAUDO_TIMEOUT}s</b>\n📝 <b>{puzzle['q']}</b>\n🤔 /caudo [đáp án]\n💡 /caudo hint (-1 điểm)",parse_mode="HTML")
        auto_delete.delete_command(m,5)
        
        # Timer timeout
        def timeout_caodo():
            time.sleep(CAUDO_TIMEOUT)
            if uid in GAME_SESSIONS and GAME_SESSIONS[uid].get("type")=="caudo" and not GAME_SESSIONS[uid].get("answered",True):
                puzzle_data=GAME_SESSIONS[uid]["current"]
                GAME_SESSIONS[uid]["answered"]=True
                try: bot.send_message(m.chat.id,f"⏰ <b>HẾT GIỜ!</b> ({CAUDO_TIMEOUT}s)\n🧩 Đáp án: <b>{puzzle_data['a'][0]}</b>\n🔄 /caudo để chơi tiếp!",parse_mode="HTML",reply_to_message_id=m.message_id)
                except: pass
        
        Thread(target=timeout_caudo, daemon=True).start()
        return
    
    g=GAME_SESSIONS[uid]
    if g.get("answered",False):
        msg=bot.reply_to(m,"⏰ Câu đố đã kết thúc! /caudo để chơi mới.",parse_mode="HTML"); auto_delete.delete_command(m,5); return
    
    if len(parts)<2:
        elapsed=int(time.time()-g["start_time"]); remaining=max(0,CAUDO_TIMEOUT-elapsed)
        msg=bot.reply_to(m,f"🧩 <b>CÂU ĐỐ #{g['questions']}</b>\n⏰ Còn <b>{remaining}s</b>\n📝 <b>{g['current']['q']}</b>\n🤔 /caudo [đáp án]",parse_mode="HTML"); auto_delete.delete_command(m,5); return
    
    arg=" ".join(parts[1:]).lower().strip()
    
    if arg in ["hint","gợi ý"]:
        if g["hint_used"]: bot.reply_to(m,"❌ Đã dùng gợi ý rồi!",parse_mode="HTML"); auto_delete.delete_command(m); return
        g["hint_used"]=True; g["score"]=max(0,g["score"]-1)
        msg=bot.reply_to(m,f"💡 Gợi ý: {g['current']['hint']}\n🏆 Điểm: {g['score']} (-1)",parse_mode="HTML"); auto_delete.delete_command(m,5); return
    
    correct=any(arg==a.lower() or a.lower() in arg for a in g["current"]["a"])
    if correct:
        elapsed=int(time.time()-g["start_time"]); time_bonus=max(0,int((CAUDO_TIMEOUT-elapsed)/10))
        reward=2000+time_bonus*500; add_balance(uid,reward); g["score"]+=3+time_bonus; g["answered"]=True
        msg=bot.reply_to(m,f"🎉 <b>CHÍNH XÁC!</b> ({elapsed}s)\n💰 +{reward:,} xu (bonus tốc độ: +{time_bonus*500:,})\n🏆 Điểm: <b>{g['score']}</b>\n🔄 /caudo để chơi tiếp!",parse_mode="HTML"); del GAME_SESSIONS[uid]
    else:
        g["score"]=max(0,g["score"]-1)
        elapsed=int(time.time()-g["start_time"]); remaining=max(0,CAUDO_TIMEOUT-elapsed)
        if remaining<=0: g["answered"]=True; msg=bot.reply_to(m,f"⏰ <b>HẾT GIỜ!</b>\n🧩 Đáp án: <b>{g['current']['a'][0]}</b>\n🔄 /caudo để chơi tiếp!",parse_mode="HTML"); del GAME_SESSIONS[uid]
        else: msg=bot.reply_to(m,f"❌ Sai! (-1 điểm)\n⏰ Còn <b>{remaining}s</b>\n🏆 Điểm: <b>{g['score']}</b>\n🤔 /caudo [đáp án]",parse_mode="HTML")
    brain.stats["games_played"]+=1
    auto_delete.delete_both(m, msg.message_id, cmd_delay=4)

# ─── GAME 7: XÚC XẮC MAY MẮN ──────────────────────────────────────────
@bot.message_handler(commands=['xucxac','xx'])
def xucxac_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid=m.from_user.id; users[str(uid)]=m.from_user.first_name; save_users(users); parts=m.text.split()
    if len(parts)<3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="xucxac": GAME_SESSIONS[uid]=init_game_state(uid,"xucxac")
        g=GAME_SESSIONS.get(uid,{}); msg=bot.reply_to(m,f"🎲 <b>XÚC XẮC MAY MẮN</b>\n/xx [số 1-6] [cược]\n💎 Game: <b>{g.get('balance',1000)}</b> xu\nTrúng: x4 | Lệch 1: hoàn 50%",parse_mode="HTML"); auto_delete.delete_command(m,8); return
    try: guess,bet=int(parts[1]),int(parts[2])
    except: bot.reply_to(m,"❌ /xx [số 1-6] [cược]",parse_mode="HTML"); auto_delete.delete_command(m); return
    if guess<1 or guess>6: bot.reply_to(m,"❌ Số 1-6.",parse_mode="HTML"); auto_delete.delete_command(m); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type")!="xucxac": GAME_SESSIONS[uid]=init_game_state(uid,"xucxac")
    g=GAME_SESSIONS[uid]
    if bet>g["balance"] or bet<1: bot.reply_to(m,f"❌ Số dư game: {g['balance']} xu.",parse_mode="HTML"); auto_delete.delete_command(m); return
    dice_result=random.randint(1,6); dice_emoji=["⚀","⚁","⚂","⚃","⚄","⚅"][dice_result-1]
    if guess==dice_result: win_amount=bet*4; g["balance"]+=win_amount-bet; g["wins"]+=1; outcome=f"🎉 TRÚNG! +{win_amount-bet} xu (x4)"
    elif abs(guess-dice_result)==1: win_amount=int(bet*0.5); g["balance"]+=win_amount-bet; outcome=f"🔄 Lệch 1! Hoàn {win_amount} xu"
    else: g["balance"]-=bet; g["losses"]+=1; outcome=f"💀 Thua -{bet} xu"
    brain.stats["games_played"]+=1
    msg=bot.reply_to(m,f"🎲 <b>XÚC XẮC</b>\n🎯 Kết quả: {dice_emoji} <b>{dice_result}</b>\n🎯 Bạn đoán: <b>{guess}</b>\n💰 {outcome} | 💎 {g['balance']} xu",parse_mode="HTML")
    auto_delete.delete_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI + ANTI-SPAM                                            ║
# ╚══════════════════════════════════════════════════════════════╝
def antispam(m) -> bool:
    if is_admin(m.chat.id,m.from_user.id): return False
    uid,now=m.from_user.id,time.time()
    spam[uid]=[t for t in spam.get(uid,[]) if now-t<4]+[now]
    if len(spam[uid])>5:
        warn_counts[uid]=warn_counts.get(uid,0)+1; brain.stats["spam_blocked"]+=1
        try:
            bot.delete_message(m.chat.id,m.message_id)
            if warn_counts[uid]>=3:
                try: bot.ban_chat_member(m.chat.id,uid,until_date=int(time.time())+3600)
                except: pass
                bot.send_message(m.chat.id,f"🚫 <b>{html.escape(m.from_user.first_name)}</b> bị ban 1h vì spam.",parse_mode="HTML"); del warn_counts[uid]
            else:
                w=bot.send_message(m.chat.id,f"⚠️ Spam {warn_counts[uid]}/3 <b>{html.escape(m.from_user.first_name)}</b>",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,15)
        except: pass
        return True
    return False

def ask_ai(prompt: str, uid: Optional[int]=None) -> str:
    global ck_idx
    if brain.state=="sleep": return random.choice(get_kho())
    if len(mem)>=2 and mem[-2]==prompt: return mem[-1]
    sys_msg="Bạn là kẻ cọc cằn, chửi khịa. Xưng 'tao' gọi 'mày'. Dưới 12 từ."
    msgs=[{"role":"system","content":sys_msg}]
    for txt in list(mem)[-8:]: msgs.append({"role":"user","content":txt})
    msgs.append({"role":"user","content":prompt})
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k=AI_KEYS[ck_idx]
            if not k["status"] or k["fail"]>=MAX_FAIL: ck_idx=(ck_idx+1)%len(AI_KEYS); continue
            try:
                resp=ses.post(k["url"],json={"model":k["model"],"messages":msgs,"max_tokens":40,"temperature":0.9},headers={"Authorization":f"Bearer {k['key']}","Content-Type":"application/json"},timeout=8)
                if resp.status_code==200:
                    result=resp.json()['choices'][0]['message']['content'].strip(); result=re.sub(r'[_*`\[\]()]','',result)
                    k["fail"]=0; k["last_used"]=time.time(); mem.append(prompt); mem.append(result); brain.stats["ai_calls"]+=1; return result
                else: k["fail"]+=1
            except: k["fail"]+=1; brain.stats["errors"]+=1
            ck_idx=(ck_idx+1)%len(AI_KEYS)
    if not any(k["status"] for k in AI_KEYS):
        for k in AI_KEYS: k["status"],k["fail"]=True,0
        brain.stats["errors"]=0; brain.state="repair"; return "[Não tự sửa] AI đã reset."
    return random.choice(get_kho())

# ╔══════════════════════════════════════════════════════════════╗
# ║  HANDLERS CƠ BẢN + QUẢN LÍ                                 ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m) or antispam(m): return
    users[str(m.from_user.id)]=m.from_user.first_name; save_users(users); brain.trusted_users.add(m.from_user.id)
    help_text=(f"<b>🧠 Não Robot - Auto Clean</b>\n💎 /daily | 🎰 /nohu | 🎲 /taixiu /baucua /kbb /doanso\n"
               f"🆕 /lxn /caudo /xx - Game mới!\n🎙️ /voice | 📊 /stats /top | 🧠 /ramstatus\n"
               f"🛠️ /ban /mute /unmute /warn\n"
               f"<i>🗑️ Lệnh xóa sau {CMD_DELETE_DELAY}s | Game xóa sau {GAME_DELETE_DELAY}s</i>\n"
               f"<i>⏰ Câu đố timeout {CAUDO_TIMEOUT}s</i>")
    msg=bot.reply_to(m,help_text,parse_mode="HTML"); auto_delete.delete_command(m,15)

@bot.message_handler(commands=['brain'])
def brain_cmd(m):
    if not is_grp(m): return
    if not is_admin(m.chat.id,m.from_user.id): msg=bot.reply_to(m,"⛔ Không đủ quyền.",parse_mode="HTML"); auto_delete.delete_command(m,4); return
    uptime=int(time.time()-brain.stats["uptime_start"]); jackpot=load_jackpot()
    text=(f"🧠 State: <code>{brain.state}</code> | Mood: <code>{brain.mood}</code>\n"
          f"Msgs: <code>{brain.stats['msg_processed']}</code> | AI: <code>{brain.stats['ai_calls']}</code>\n"
          f"Games: <code>{brain.stats['games_played']}</code> | Nổ Hũ: <code>{brain.stats['nohu_spins']}</code>\n"
          f"Jackpot: <code>{jackpot:,}</code> | Voice: <code>{brain.stats['voice_generated']}</code>\n"
          f"RAM: <code>{ram_manager.get_memory_mb():.1f}MB</code> | Dọn: <code>{ram_manager.clean_count}</code> lần\n"
          f"Uptime: <code>{uptime//3600}h{(uptime%3600)//60}m</code>")
    msg=bot.reply_to(m,text,parse_mode="HTML"); auto_delete.delete_command(m,12)

@bot.message_handler(commands=['ramstatus','memory','ram'])
def ram_status_cmd(m):
    if not is_grp(m) and m.from_user.id!=ADMIN_ID: return
    usage_pct=ram_manager.get_memory_usage_percent(); bar_len=20
    filled=int(usage_pct*bar_len); bar="█"*filled+"░"*(bar_len-filled)
    text=(f"🧠 <b>AI RAM MANAGER</b>\n📊 [{bar}] <b>{usage_pct*100:.1f}%</b>\n"
          f"💾 {ram_manager.get_memory_mb():.1f}MB / {ram_manager.max_ram_bytes/1024/1024:.0f}MB\n"
          f"🧹 Dọn: <b>{ram_manager.clean_count}</b> | Freed: <b>{ram_manager.total_cleaned_bytes/1024/1024:.1f}MB</b>")
    msg=bot.reply_to(m,text,parse_mode="HTML"); auto_delete.delete_command(m,10)

@bot.message_handler(commands=['clearcache','dondep'])
def clear_cache_cmd(m):
    if not is_admin(m.chat.id,m.from_user.id) and m.from_user.id!=ADMIN_ID: return
    freed,action=ram_manager.ai_decide_clean()
    msg=bot.reply_to(m,f"✅ <b>DỌN DẸP</b>\n🎯 {action}\n💾 Freed: <b>{freed/1024/1024:.2f}MB</b>\n📊 RAM: <b>{ram_manager.get_memory_mb():.1f}MB</b>",parse_mode="HTML"); auto_delete.delete_command(m,6)

# ─── QUẢN LÍ NHÓM ──────────────────────────────────────────────────────────
@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not is_grp(m) or not is_admin(m.chat.id,m.from_user.id): return
    target,reason=extract_user_and_reason(m,bot.get_me().username)
    if not target: msg=bot.reply_to(m,"❌ Reply/mention/ID.",parse_mode="HTML"); auto_delete.delete_command(m); return
    try: bot.ban_chat_member(m.chat.id,target); bot.delete_message(m.chat.id,m.message_id); w=bot.send_message(m.chat.id,f"🚫 <b>{html.escape(m.from_user.first_name)}</b> đã ban <code>{target}</code>{' - '+reason if reason else ''}",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,30)
    except Exception as e: bot.reply_to(m,f"⚠️ {str(e)[:100]}",parse_mode="HTML"); auto_delete.delete_command(m)

@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    if not is_grp(m) or not is_admin(m.chat.id,m.from_user.id): return
    target,reason=extract_user_and_reason(m,bot.get_me().username)
    if not target: auto_delete.delete_command(m); return
    duration=parse_duration(reason) if reason else 3600
    try:
        until=int(time.time())+duration; bot.restrict_chat_member(m.chat.id,target,until_date=until,can_send_messages=False,can_send_media_messages=False,can_send_other_messages=False,can_add_web_page_previews=False)
        bot.delete_message(m.chat.id,m.message_id); dur_str=f"{duration//3600}h{(duration%3600)//60}m" if duration>=3600 else f"{duration//60}m{duration%60}s"
        w=bot.send_message(m.chat.id,f"🔇 <b>{html.escape(m.from_user.first_name)}</b> mute <code>{target}</code> {dur_str}",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,30); mutes[target]=until
    except Exception as e: bot.reply_to(m,f"⚠️ {str(e)[:100]}",parse_mode="HTML"); auto_delete.delete_command(m)

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    if not is_grp(m) or not is_admin(m.chat.id,m.from_user.id): return
    target,_=extract_user_and_reason(m,bot.get_me().username)
    if not target: auto_delete.delete_command(m); return
    try: bot.restrict_chat_member(m.chat.id,target,can_send_messages=True,can_send_media_messages=True,can_send_other_messages=True,can_add_web_page_previews=True); bot.delete_message(m.chat.id,m.message_id); w=bot.send_message(m.chat.id,f"🔊 Unmute <code>{target}</code>",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,20)
    except: pass
    if target in mutes: del mutes[target]
    auto_delete.delete_command(m)

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    if not is_grp(m) or not is_admin(m.chat.id,m.from_user.id): return
    target,reason=extract_user_and_reason(m,bot.get_me().username)
    if not target: auto_delete.delete_command(m); return
    warn_counts[target]=warn_counts.get(target,0)+1; cnt=warn_counts[target]; bot.delete_message(m.chat.id,m.message_id)
    w=bot.send_message(m.chat.id,f"⚠️ <b>{html.escape(m.from_user.first_name)}</b> warn <code>{target}</code> [{cnt}/3]\n{reason if reason else ''}",parse_mode="HTML"); del_msg(m.chat.id,w.message_id,25)
    if cnt>=3:
        try: bot.ban_chat_member(m.chat.id,target,until_date=int(time.time())+3600); del warn_counts[target]
        except: pass

@bot.message_handler(commands=['stats','memberstats'])
def stats_cmd(m):
    if not is_grp(m): return
    today=date.today().isoformat(); last_7_days=[(date.today()-timedelta(days=i)).isoformat() for i in range(7)]
    today_join=member_stats["daily_join"].get(today,0); today_leave=member_stats["daily_leave"].get(today,0)
    week_join=sum(member_stats["daily_join"].get(d,0) for d in last_7_days)
    try: real_count=bot.get_chat_member_count(GROUP_ID)
    except: real_count=member_stats.get("current_members",0)
    msg=bot.reply_to(m,f"📊 <b>THỐNG KÊ</b>\n👥 Hiện: <b>{real_count}</b> | 📥 Vào: <b>{member_stats['total_joined']}</b> | 📤 Rời: <b>{member_stats['total_left']}</b>\n📅 Hôm nay: +{today_join} -{today_leave} | 7 ngày: +{week_join}",parse_mode="HTML")
    auto_delete.delete_command(m,10)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def handle_text(m):
    if antispam(m) or m.text.startswith('/'): return
    users[str(m.from_user.id)]=m.from_user.first_name; save_users(users)
    brain.think({"uid":m.from_user.id,"txt":m.text,"cmd":False})
    uid=m.from_user.id
    if not brain.should_reply(uid,m.text): return
    if uid in ai_cd and time.time()-ai_cd[uid]<2: msg=bot.reply_to(m,"Đợi 2s.",parse_mode="HTML"); del_msg(m.chat.id,msg.message_id,3); return
    ai_cd[uid]=time.time()
    def _ai():
        reply=ask_ai(m.text,uid)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id==bot.get_me().id): bot.reply_to(m,html.escape(reply),parse_mode="HTML")
        else: msg_reply=bot.reply_to(m,html.escape(reply),parse_mode="HTML"); del_msg(m.chat.id,msg_reply.message_id)
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    today=date.today().isoformat()
    for u in m.new_chat_members:
        if u.id==bot.get_me().id: continue
        users[str(u.id)]=u.first_name
        if str(u.id) not in member_stats.get("join_dates",{}): member_stats["join_dates"][str(u.id)]=today; member_stats["total_joined"]+=1
        member_stats["daily_join"][today]+=1; member_stats["current_members"]+=1; save_users(users); save_member_stats()
        msg=bot.send_message(m.chat.id,f"🔥 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào. {random.choice(get_kho())}",parse_mode="HTML"); del_msg(m.chat.id,msg.message_id,30)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m):
    if not is_grp(m): return
    today=date.today().isoformat(); u=m.left_chat_member
    if u.id==bot.get_me().id: return
    member_stats["daily_leave"][today]+=1; member_stats["total_left"]+=1; member_stats["current_members"]=max(0,member_stats["current_members"]-1); save_member_stats()
    msg=bot.send_message(m.chat.id,f"🍂 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> cút. {random.choice(get_kho())}",parse_mode="HTML"); del_msg(m.chat.id,msg.message_id,30)

# ╔══════════════════════════════════════════════════════════════╗
# ║  BACKGROUND TASKS                                          ║
# ╚══════════════════════════════════════════════════════════════╝
def scheduler_task():
    last_hour=-1
    while True:
        try:
            now=datetime.now(tz); brain.health_check()
            if brain.state=="repair": brain.state="normal"; brain.repair_mode=False
            if now.minute==0 and now.hour!=last_hour and users:
                uid,uname=random.choice(list(users.items())); msg=bot.send_message(GROUP_ID,f"🔔 <b>{now.strftime('%H:%M')}</b> | <a href='tg://user?id={uid}'>{html.escape(uname)}</a>... {random.choice(get_kho())}",parse_mode="HTML"); del_msg(GROUP_ID,msg.message_id,15); last_hour=now.hour
            if now.minute!=0: last_hour=-1
            to_remove=[uid for uid,until in mutes.items() if time.time()>until]
            for uid in to_remove:
                try: bot.restrict_chat_member(GROUP_ID,uid,can_send_messages=True,can_send_media_messages=True,can_send_other_messages=True,can_add_web_page_previews=True)
                except: pass
                del mutes[uid]
            if len(spam)>100:
                for uid,_ in sorted(spam.items(),key=lambda x:x[1][-1] if x[1] else 0)[:10]: del spam[uid]
        except: pass
        time.sleep(15)

def auto_save_task():
    while True:
        time.sleep(600)
        try: save_users(users); brain.save_state(); save_member_stats(); save_balances(user_balance); save_daily_checkins(daily_checkin); save_jackpot(load_jackpot())
        except: pass

# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN                                                      ║
# ╚══════════════════════════════════════════════════════════════╝
def main():
    global user_balance,daily_checkin,nohu_jackpot,member_stats
    loaded_users=load_users()
    if isinstance(loaded_users,dict): users.update(loaded_users)
    user_balance=load_balances(); daily_checkin=load_daily_checkins(); nohu_jackpot=load_jackpot()
    loaded_stats=load_member_stats(); member_stats.update(loaded_stats)
    if not isinstance(member_stats.get("daily_join"),defaultdict): member_stats["daily_join"]=defaultdict(int,member_stats.get("daily_join",{}))
    if not isinstance(member_stats.get("daily_leave"),defaultdict): member_stats["daily_leave"]=defaultdict(int,member_stats.get("daily_leave",{}))
    try: member_stats["current_members"]=bot.get_chat_member_count(GROUP_ID)
    except: member_stats["current_members"]=len(users)
    ram_manager.start_monitoring()
    logger.info(f"🚀 Khởi động: {len(users)} users, Jackpot: {nohu_jackpot:,} xu")
    logger.info(f"🧠 AI RAM | 🎰 AI Nổ Hũ | 🎲 7 Games | 🎙️ Voice")
    logger.info(f"🗑️ Auto-Delete: Lệnh {CMD_DELETE_DELAY}s | Game {GAME_DELETE_DELAY}s | Câu đố {CAUDO_TIMEOUT}s")
    Thread(target=scheduler_task,daemon=True).start()
    Thread(target=auto_save_task,daemon=True).start()
    try: bot.infinity_polling(timeout=30,none_stop=True,interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng: {e}"); brain.stats["errors"]+=1; brain.save_state()
        save_balances(user_balance); save_daily_checkins(daily_checkin); save_jackpot(load_jackpot()); save_member_stats()

if __name__=="__main__":
    main()
