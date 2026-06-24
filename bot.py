# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - 2000 DÒNG FULL AI                           │
# │  AI Brain + AI RAM + AI Nổ Hũ + AI Câu Đố + 10+ Mini Games + 18 Voice     │
# │  + Auto Delete 15s + Quản lí nhóm + Điểm danh + Tài chính + Thống kê      │
# │  + Anti-Spam + Anti-Link + File Reader + Scheduler + Auto Save            │
# │  Tác giả: palofsc (palo)  |  Ngày: 2026-06-24                              │
# └────────────────────────────────────────────────────────────────────────────┘
import sys, io, os, json, time, random, re, html, logging, hashlib, base64
import urllib.parse, urllib.request, gc, ctypes, psutil, weakref, signal
import tempfile, zipfile, csv, traceback
from threading import Thread, Lock, Timer, Event
from datetime import datetime, timedelta, date
from collections import deque, defaultdict, OrderedDict, Counter
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, PriorityQueue
from dataclasses import dataclass, field
from io import StringIO, BytesIO
from enum import Enum

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("NaoRobot")

# ─── ENCODING ──────────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ─── KEEP ALIVE ────────────────────────────────────────────────────────────────
try:
    from keep_alive import keep_alive; keep_alive()
    logger.info("Keep-alive activated")
except ImportError:
    logger.warning("keep_alive not found")

# ─── THƯ VIỆN NGOÀI ───────────────────────────────────────────────────────────
import telebot; from telebot import types, util; import requests; import pytz

# ─── THƯ VIỆN FILE OPTIONAL ────────────────────────────────────────────────────
try: import PyPDF2; HAS_PYPDF2 = True
except ImportError: HAS_PYPDF2 = False
try: import docx; HAS_DOCX = True
except ImportError: HAS_DOCX = False
try: from bs4 import BeautifulSoup; HAS_BS4 = True
except ImportError: HAS_BS4 = False
try: import chardet; HAS_CHARDET = True
except ImportError: HAS_CHARDET = False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           AI RAM MANAGER                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRamManager:
    """
    AI quản lí RAM - Tự động giám sát, phân tích và dọn dẹp bộ nhớ.
    Các mức: Light (75%), Medium (82%), Aggressive (90%), Critical (95%)
    """
    WARNING_THRESHOLD = 0.70; CLEAN_LIGHT = 0.75; CLEAN_MEDIUM = 0.82
    CLEAN_AGGRESSIVE = 0.90; CRITICAL = 0.95

    def __init__(self, max_ram_mb: int = 512):
        self.max_ram_bytes = max_ram_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.snapshots: deque = deque(maxlen=100)
        self.last_clean_time: float = 0
        self.clean_cooldown: float = 30
        self.total_cleaned_bytes: int = 0
        self.clean_count: int = 0
        self.leak_warnings: int = 0
        self.is_cleaning: bool = False
        self.clean_lock = Lock()
        self.smart_cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl: float = 300
        logger.info(f"🧠 AI RAM Manager initialized. Max RAM: {max_ram_mb}MB")

    def get_memory_mb(self) -> float:
        """RAM hiện tại tính bằng MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def get_memory_usage_percent(self) -> float:
        """Phần trăm RAM đã sử dụng so với giới hạn."""
        return self.process.memory_info().rss / self.max_ram_bytes

    def analyze_trend(self) -> str:
        """AI phân tích xu hướng tăng trưởng RAM."""
        if len(self.snapshots) < 3: return "stable"
        recent = list(self.snapshots)[-5:]
        if len(recent) < 3: return "stable"
        time_diff = recent[-1][0] - recent[0][0]
        if time_diff <= 0: return "stable"
        growth_rate = (recent[-1][1] - recent[0][1]) / time_diff
        if growth_rate > 1024 * 1024: return "critical_growth"
        elif growth_rate > 512 * 1024: return "rapid_growth"
        elif growth_rate > 100 * 1024: return "slow_growth"
        return "stable"

    def smart_cache_get(self, key: str) -> Optional[Any]:
        """Lấy từ cache thông minh có TTL."""
        if key in self.smart_cache:
            value, expiry = self.smart_cache[key]
            if time.time() < expiry: return value
            else: del self.smart_cache[key]
        return None

    def smart_cache_set(self, key: str, value: Any, ttl: float = None):
        """Lưu vào cache thông minh."""
        if ttl is None: ttl = self.cache_ttl
        self.smart_cache[key] = (value, time.time() + ttl)
        if len(self.smart_cache) > 1000:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:300]: del self.smart_cache[k]

    def _clean_level_1(self) -> int:
        """Dọn nhẹ: Clear cache hết hạn + gc thế hệ 0."""
        freed = 0; now = time.time()
        expired = [k for k, (v, exp) in self.smart_cache.items() if now >= exp]
        for k in expired: del self.smart_cache[k]
        freed += len(expired) * 100
        collected = gc.collect(0); freed += collected * 200
        return freed

    def _clean_level_2(self) -> int:
        """Dọn vừa: Level 1 + GC full + xóa 50% cache."""
        freed = self._clean_level_1(); collected = gc.collect(2); freed += collected * 200
        if len(self.smart_cache) > 100:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:len(self.smart_cache)//2]: del self.smart_cache[k]
            freed += len(self.smart_cache)//2 * 100
        gc.garbage.clear(); return freed

    def _clean_level_3(self) -> int:
        """Dọn mạnh (90%): Level 2 + xóa 80% cache + malloc_trim."""
        freed = self._clean_level_2()
        if self.smart_cache:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:int(len(self.smart_cache)*0.8)]: del self.smart_cache[k]
        try: ctypes.CDLL("libc.so.6").malloc_trim(0); freed += 1024 * 1024
        except: pass
        for _ in range(3): gc.collect(2)
        gc.garbage.clear(); return freed

    def _clean_critical(self) -> int:
        """Dọn khẩn cấp (95%): Level 3 + xóa toàn bộ cache."""
        freed = self._clean_level_3()
        cache_size = len(self.smart_cache); self.smart_cache.clear(); freed += cache_size * 100
        try: ctypes.CDLL("libc.so.6").malloc_trim(0)
        except: pass
        for _ in range(5): gc.collect(2)
        gc.garbage.clear(); return freed

    def ai_decide_clean(self) -> Tuple[int, str]:
        """AI quyết định mức độ dọn dẹp dựa trên % RAM và xu hướng."""
        with self.clean_lock:
            if self.is_cleaning: return 0, "already_cleaning"
            if time.time() - self.last_clean_time < self.clean_cooldown: return 0, "cooldown"
            self.is_cleaning = True
            try:
                usage_pct = self.get_memory_usage_percent()
                trend = self.analyze_trend()
                if usage_pct >= self.CRITICAL: freed = self._clean_critical(); action = "critical_clean"
                elif usage_pct >= self.CLEAN_AGGRESSIVE: freed = self._clean_level_3(); action = "aggressive_clean"
                elif usage_pct >= self.CLEAN_MEDIUM: freed = self._clean_level_2(); action = "medium_clean"
                elif usage_pct >= self.CLEAN_LIGHT: freed = self._clean_level_1(); action = "light_clean"
                elif trend in ["rapid_growth", "critical_growth"]:
                    freed = self._clean_level_2(); action = "leak_prevention"; self.leak_warnings += 1
                else: gc.collect(0); freed = 0; action = "stable_no_clean"
                self.last_clean_time = time.time()
                self.total_cleaned_bytes += freed; self.clean_count += 1
                return freed, action
            finally: self.is_cleaning = False

    def monitor_loop(self):
        """Vòng lặp giám sát RAM mỗi 30 giây."""
        while True:
            try:
                self.snapshots.append((time.time(), self.process.memory_info().rss))
                if self.get_memory_usage_percent() >= self.WARNING_THRESHOLD:
                    self.ai_decide_clean()
            except: pass
            time.sleep(30)

    def start_monitoring(self):
        """Khởi động giám sát RAM."""
        Thread(target=self.monitor_loop, daemon=True, name="AIRamMonitor").start()
        logger.info("🧠 AI RAM Monitor started (30s interval)")

# Khởi tạo AI RAM Manager toàn cục
ram_manager = AIRamManager(max_ram_mb=512)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           AI BRAIN - NÃO ĐIỀU KHIỂN                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class Brain:
    """Não điều khiển bot - tự học, tự sửa, tự quyết định."""
    def __init__(self, save_path: str = "brain.json"):
        self.save_path = save_path
        self.state: str = "normal"  # normal | aggressive | sleep | repair
        self.mood: int = 0          # -10 đến 10
        self.learned: defaultdict = defaultdict(int)
        self.banned_words: set = set()
        self.trusted_users: set = set()
        self.stats: Dict[str, Any] = {
            "msg_processed": 0, "spam_blocked": 0, "ai_calls": 0,
            "errors": 0, "voice_generated": 0, "nohu_spins": 0,
            "games_played": 0, "daily_checkins": 0, "files_processed": 0,
            "ram_cleans": 0, "ram_freed_mb": 0.0, "auto_deleted": 0,
            "uptime_start": time.time(), "last_save": time.time()
        }
        self.decision_log: deque = deque(maxlen=200)
        self.last_health_check: float = time.time()
        self.repair_mode: bool = False
        self.file_lock = Lock()
        self.load_state()
        logger.info("🧠 AI Brain initialized")

    def load_state(self):
        """Tải trạng thái từ file JSON."""
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.learned = defaultdict(int, data.get("learned", {}))
                    self.banned_words = set(data.get("banned", []))
                    self.trusted_users = set(data.get("trusted", []))
                    self.stats.update(data.get("stats", {}))
                    self.stats["uptime_start"] = self.stats.get("uptime_start", time.time())
                    self.state = data.get("state", "normal")
                    self.mood = data.get("mood", 0)
            except Exception as e:
                logger.error(f"Brain load error: {e}")

    def save_state(self):
        """Lưu trạng thái xuống file JSON."""
        with self.file_lock:
            self.stats["last_save"] = time.time()
            self.stats["ram_cleans"] = ram_manager.clean_count
            self.stats["ram_freed_mb"] = ram_manager.total_cleaned_bytes / (1024 * 1024)
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "learned": dict(self.learned),
                        "banned": list(self.banned_words),
                        "trusted": list(self.trusted_users),
                        "stats": self.stats,
                        "state": self.state,
                        "mood": self.mood
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Brain save error: {e}")

    def think(self, uid: int, txt: str) -> str:
        """Phân tích tin nhắn, cập nhật mood và học từ."""
        self.stats["msg_processed"] += 1
        # Học từ vựng
        words = re.findall(r'\b\w{3,}\b', txt.lower())
        for w in words: self.learned[w] += 1
        # Điều chỉnh mood
        neg = ["bot ngu", "bot dở", "bot lỗi", "mày ngu", "bot chậm", "óc chó"]
        pos = ["bot hay", "bot pro", "cảm ơn bot", "bot tốt", "bot giỏi", "bot đỉnh"]
        if any(p in txt.lower() for p in neg): self.mood -= 2
        elif any(p in txt.lower() for p in pos): self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        # Cập nhật state
        self.state = "aggressive" if self.mood < -5 else "normal"
        # Ghi log quyết định
        self.decision_log.append({
            "time": datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S"),
            "uid": uid, "decision": self.state, "mood": self.mood
        })
        # Lưu định kỳ
        if len(self.decision_log) % 10 == 0: self.save_state()
        return self.state

    def should_reply(self, uid: int, msg_text: str) -> bool:
        """AI quyết định có nên trả lời không."""
        if uid in self.trusted_users: return True
        if self.learned.get(msg_text.lower(), 0) > 5: return random.random() > 0.3
        return random.random() > 0.1

    def get_insult_level(self) -> str:
        """Mức độ chửi dựa trên mood."""
        if self.state == "aggressive": return "extreme"
        elif self.mood < 0: return "high"
        return "normal"

    def health_check(self) -> str:
        """Kiểm tra sức khỏe định kỳ."""
        now = time.time()
        if now - self.last_health_check > 300:  # Mỗi 5 phút
            self.last_health_check = now
            # Kiểm tra RAM
            if ram_manager.get_memory_usage_percent() >= ram_manager.CLEAN_AGGRESSIVE:
                ram_manager.ai_decide_clean()
            # Tự sửa nếu quá nhiều lỗi
            if self.stats["errors"] > 20:
                self.repair_mode = True; self.state = "repair"
                self.stats["errors"] = 0; logger.warning("Brain entering repair mode")
                return "repair"
            self.save_state()
        return "ok"

# Khởi tạo Brain toàn cục
brain = Brain()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           CẤU HÌNH CHÍNH                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=50)
tz = pytz.timezone('Asia/Ho_Chi_Minh')
ses = requests.Session()
ses.mount('https://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))
ses.mount('http://', requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500, max_retries=3, pool_block=False))

# Thread pools
ai_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="AI")
voice_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Voice")
game_executor = ThreadPoolExecutor(max_workers=15, thread_name_prefix="Game")
file_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="File")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           AI KEYS (TỰ SỬA)                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AI_KEYS: List[Dict[str, Any]] = [
    {
        "key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",
        "url": "https://api.byesu.com/v1/chat/completions",
        "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0
    },
    {
        "key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3",
        "url": "https://api.byesu.com/v1/chat/completions",
        "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0
    },
    {
        "key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034",
        "url": "https://api.freemodel.dev/v1/chat/completions",
        "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0
    }
]
MAX_FAIL = 3; ck_idx = 0; ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           KHO CHỬI (THEO MOOD)                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
KHO_NORMAL: List[str] = [
    "Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.",
    "Cào phím nhanh, não chậm.", "Ảo tưởng sức mạnh.", "Về nhà rửa bát.",
    "IQ âm, đừng nói.", "Không ai cần mày.", "Mày là gì? Không là gì.",
    "Câm mồm, đỡ nhục.", "Mõm làng, bớt nói.", "Ngứa mồm à? Gãi đi."
]
KHO_HIGH: List[str] = [
    "Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?",
    "Ra đời người ta vả cho.", "Mẹ gọi, về nhà đi.", "Tưởng mình ngầu? Hề vãi.",
    "Học không lo, cào phím giỏi.", "Tương lai mù mịt như chị Dậu.",
    "Đời vả mặt, mày cười ngây.", "Không có gì để nói với mày."
]
KHO_EXTREME: List[str] = [
    "Mày đáng giá bằng cái nút block.", "Tồn tại để làm gì? Để tao chửi à?",
    "Não mày như ổ đĩa format nhầm.", "Mày là lỗi của tự nhiên, bug của xã hội.",
    "Tao chửi mày còn thấy phí thời gian.", "Mày không đáng để tao nhớ tên.",
    "Cút về lỗ mà mày chui ra.", "Mày là minh chứng cho thất bại của tiến hóa.",
    "Tao nhìn mày mà tưởng đang xem phim hài.", "Mày sống làm gì?"
]

def get_kho() -> List[str]:
    """Lấy kho chửi phù hợp với mood hiện tại."""
    lvl = brain.get_insult_level()
    if lvl == "extreme": return KHO_EXTREME
    elif lvl == "high": return KHO_HIGH
    return KHO_NORMAL

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           BIẾN TOÀN CỤC                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
lock = Lock()
mem: deque = deque(maxlen=50)               # Bộ nhớ hội thoại AI
users: Dict[str, str] = {}                  # uid -> first_name
spam: Dict[int, List[float]] = {}           # uid -> timestamps
warn_counts: Dict[int, int] = {}            # uid -> số warn
mutes: Dict[int, float] = {}                # uid -> thời điểm hết mute
ai_cd: Dict[int, float] = {}                # uid -> cooldown AI
user_balance: Dict[int, int] = {}           # uid -> số xu
daily_checkin: Dict[int, str] = {}          # uid -> ngày checkin cuối
nohu_jackpot: int = 100000                  # Jackpot nổ hũ
nohu_history: deque = deque(maxlen=20)      # Lịch sử nổ hũ
nohu_fee: int = 1000                        # Phí mỗi lần quay
nohu_multiplier: float = 0.05               # % tiền vào jackpot
member_stats: Dict[str, Any] = {            # Thống kê thành viên
    "daily_join": defaultdict(int),
    "daily_leave": defaultdict(int),
    "total_joined": 0, "total_left": 0,
    "current_members": 0, "join_dates": {}
}
GAME_SESSIONS: Dict[int, Dict] = {}         # uid -> game state
USED_RIDDLES: Dict[int, List[str]] = defaultdict(list)  # uid -> câu đố đã dùng

# File paths
USR_FILE = "usr.json"
BALANCE_FILE = "balances.json"
DAILY_FILE = "daily_checkins.json"
JACKPOT_FILE = "jackpot.json"
STATS_FILE = "member_stats.json"

# Regex patterns
TELEGRAM_LINK = re.compile(
    r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}',
    re.I
)

# ═══════════════ AUTO DELETE CONFIG ═══════════════
AUTO_DELETE_DELAY: int = 15          # Tất cả tin nhắn tự xóa sau 15 giây
AUTO_DELETE_ENABLED: bool = True     # Bật/tắt tự động xóa

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           TIỆN ÍCH CHUNG                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def load_json(path: str, default: Any = None) -> Any:
    """Đọc file JSON với smart cache."""
    if default is None: default = {}
    cached = ram_manager.smart_cache_get(f"json_{path}")
    if cached is not None: return cached
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                ram_manager.smart_cache_set(f"json_{path}", data, 60)
                return data
        except Exception as e:
            logger.error(f"Load JSON error {path}: {e}")
    return default

def save_json(path: str, data: Any) -> None:
    """Ghi file JSON thread-safe với smart cache."""
    with lock:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            ram_manager.smart_cache_set(f"json_{path}", data, 60)
        except Exception as e:
            logger.error(f"Save JSON error {path}: {e}")

def load_users() -> Dict[str, str]: return load_json(USR_FILE, {})
def save_users(data: Dict[str, str]): save_json(USR_FILE, data)

def load_balances() -> Dict[int, int]:
    data = load_json(BALANCE_FILE, {})
    return {int(k): v for k, v in data.items()}

def save_balances(data: Dict[int, int]):
    save_json(BALANCE_FILE, {str(k): v for k, v in data.items()})

def load_daily_checkins() -> Dict[int, str]:
    data = load_json(DAILY_FILE, {})
    return {int(k): v for k, v in data.items()}

def save_daily_checkins(data: Dict[int, str]):
    save_json(DAILY_FILE, {str(k): v for k, v in data.items()})

def load_jackpot() -> int:
    data = load_json(JACKPOT_FILE, {"jackpot": 100000})
    return data.get("jackpot", 100000)

def save_jackpot(jackpot: int):
    save_json(JACKPOT_FILE, {"jackpot": jackpot, "history": list(nohu_history)})

def load_member_stats() -> Dict:
    data = load_json(STATS_FILE, {
        "daily_join": {}, "daily_leave": {}, "total_joined": 0,
        "total_left": 0, "current_members": 0, "join_dates": {}
    })
    data["daily_join"] = defaultdict(int, data.get("daily_join", {}))
    data["daily_leave"] = defaultdict(int, data.get("daily_leave", {}))
    return data

def save_member_stats():
    data = dict(member_stats)
    data["daily_join"] = dict(data["daily_join"])
    data["daily_leave"] = dict(data["daily_leave"])
    save_json(STATS_FILE, data)

# ─── AUTO DELETE ──────────────────────────────────────────────────────────────
def auto_del(chat_id: int, msg_id: int, delay: int = AUTO_DELETE_DELAY):
    """Tự động xóa tin nhắn sau delay giây."""
    if AUTO_DELETE_ENABLED:
        def _del():
            time.sleep(delay)
            try: bot.delete_message(chat_id, msg_id)
            except: pass
        Thread(target=_del, daemon=True).start()

def del_both(m, bot_msg_id: int):
    """Xóa cả lệnh người dùng và phản hồi bot."""
    auto_del(m.chat.id, m.message_id)
    auto_del(m.chat.id, bot_msg_id)

# ─── KIỂM TRA QUYỀN ───────────────────────────────────────────────────────────
def is_admin(m) -> bool:
    """Kiểm tra user có phải admin không."""
    return m.from_user.id == ADMIN_ID

def is_grp(m) -> bool:
    """Kiểm tra tin nhắn có từ group mục tiêu không."""
    return m.chat.id == GROUP_ID

# ─── QUẢN LÍ TIỀN ─────────────────────────────────────────────────────────────
def get_user_balance(uid: int) -> int:
    """Lấy số dư của user, tạo mới nếu chưa có."""
    if uid not in user_balance:
        user_balance[uid] = 5000
        save_balances(user_balance)
    return user_balance[uid]

def add_balance(uid: int, amount: int) -> int:
    """Thêm tiền cho user."""
    bal = get_user_balance(uid)
    user_balance[uid] = max(0, bal + amount)
    save_balances(user_balance)
    return user_balance[uid]

def deduct_balance(uid: int, amount: int) -> bool:
    """Trừ tiền user, trả về True nếu đủ."""
    bal = get_user_balance(uid)
    if bal >= amount:
        user_balance[uid] = bal - amount
        save_balances(user_balance)
        return True
    return False

# ─── PARSE DURATION ───────────────────────────────────────────────────────────
def parse_duration(reason: str) -> int:
    """Phân tích thời gian từ chuỗi (1h, 30m, 45s...)."""
    m = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if m:
        num = int(m.group(1)); unit = m.group(2)
        if unit == 's': return num
        elif unit == 'm' or unit == 'p': return num * 60
        elif unit == 'h': return num * 3600
    return 3600  # Mặc định 1 giờ

# ─── EXTRACT USER ─────────────────────────────────────────────────────────────
def extract_user_and_reason(message, bot_username: str) -> Tuple[Optional[int], str]:
    """Lấy user_id và lý do từ lệnh."""
    target = None; reason = ""
    if message.reply_to_message:
        target = message.reply_to_message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1: reason = parts[1]
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg.isdigit():
                target = int(arg)
            else:
                mention_match = re.match(r'@(\w+)', arg)
                if mention_match:
                    try:
                        target = bot.get_chat_member(message.chat.id, mention_match.group(0)).user.id
                        reason = arg[mention_match.end():].strip()
                    except: pass
                else:
                    num_match = re.search(r'\d+', arg)
                    if num_match:
                        target = int(num_match.group())
                        reason = arg[num_match.end():].strip()
    return target, reason

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CÂU ĐỐ RANDOM - KHÔNG TRÙNG                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AICauDo:
    """AI tạo câu đố thông minh - không trùng lặp - đa dạng chủ đề."""
    
    # Thư viện câu đố mẹo phong phú
    RIDDLES = [
        {"q": "Có 1 đàn chuột điếc đi qua cầu, hỏi có mấy con?", "a": ["24 con", "24", "hai tư"], "h": "Điếc = hư tai = hai tư = 24"},
        {"q": "Cái gì càng kéo càng ngắn?", "a": ["điếu thuốc", "thuốc lá", "dieu thuoc"], "h": "Hút vào sẽ ngắn dần"},
        {"q": "Cái gì có răng mà không có miệng?", "a": ["cái cưa", "cưa", "cua", "cái lược", "lược"], "h": "Dụng cụ cắt/ chải"},
        {"q": "Cái gì đen khi mua, đỏ khi dùng, xám khi vứt?", "a": ["than", "củ than", "cu than"], "h": "Dùng để đốt, nướng"},
        {"q": "Con gì sinh ra đã biết bơi?", "a": ["con cá", "cá", "ca", "nòng nọc"], "h": "Sống dưới nước"},
        {"q": "Cái gì càng nhiều lửa càng ít?", "a": ["cây nến", "nến", "nen"], "h": "Thắp sáng"},
        {"q": "Cái gì luôn đến nhưng không bao giờ đến?", "a": ["ngày mai", "tương lai", "ngay mai", "tuong lai"], "h": "Thời gian"},
        {"q": "Cái gì càng ít càng nhiều?", "a": ["bóng tối", "bong toi"], "h": "Đối lập với ánh sáng"},
        {"q": "Con gì đập thì sống, không đập thì chết?", "a": ["con tim", "tim"], "h": "Cơ quan trong cơ thể"},
        {"q": "Cái gì có mắt mà không thấy?", "a": ["cái kim", "kim"], "h": "Dùng để may vá"},
        {"q": "Cái gì càng rửa càng bẩn?", "a": ["nước", "nuoc"], "h": "Chất lỏng trong suốt"},
        {"q": "Cái gì có cổ mà không có đầu?", "a": ["cái áo", "áo", "ao", "cái chai", "chai"], "h": "Mặc hàng ngày/ đựng nước"},
        {"q": "Quần gì rộng nhất?", "a": ["quần đảo", "quan dao"], "h": "Địa lý - biển đảo"},
        {"q": "Xã gì đông nhất?", "a": ["xã hội", "xa hoi"], "h": "Liên quan đến con người"},
        {"q": "Núi gì bị chặt ra từng khúc?", "a": ["núi thái sơn", "thái sơn", "thai son"], "h": "Liên quan đến Trung Quốc"},
        {"q": "Cái gì bằng cái vung, vùng xuống ao, đào chẳng thấy, lấy chẳng được?", "a": ["bóng trăng", "mặt trăng", "trăng"], "h": "Trên trời"},
        {"q": "Cái gì càng cao càng nhỏ?", "a": ["cái thang", "thang"], "h": "Dùng để leo trèo"},
        {"q": "Cái gì càng đi càng nhỏ?", "a": ["cục tẩy", "tẩy", "tay"], "h": "Dùng trong học tập"},
        {"q": "Cái gì vừa bằng hạt đỗ, ăn cả làng?", "a": ["hạt muối", "muối", "muoi"], "h": "Gia vị"},
        {"q": "Cái gì càng nhiều người dùng càng nhỏ?", "a": ["cục xà phòng", "xà phòng", "xa phong"], "h": "Tắm giặt"},
    ]
    
    @staticmethod
    def generate(difficulty: int = 1, used_answers: set = None) -> Dict:
        """
        AI tạo câu đố mới dựa trên độ khó.
        difficulty: 1-5 (càng cao càng khó)
        used_answers: set các đáp án đã dùng để tránh trùng
        """
        if used_answers is None:
            used_answers = set()
        
        # Lọc câu đố có sẵn chưa dùng
        available = [r for r in AICauDo.RIDDLES if r["a"][0] not in used_answers]
        
        # 70% dùng câu đố có sẵn, 30% AI tự tạo
        if available and random.random() < 0.7:
            return random.choice(available)
        
        # AI tự tạo câu đố mới
        templates = [
            # Template 1: Con gì...?
            lambda: {
                "q": f"Con gì {random.choice(['ăn', 'sợ', 'thích', 'không bao giờ'])} {random.choice(['lửa', 'nước', 'bóng tối', 'ánh sáng'])}?",
                "a": [random.choice(["rồng", "ma", "quỷ", "tiên", "cá"])],
                "h": "Sinh vật huyền thoại/ tự nhiên"
            },
            # Template 2: Cái gì có X mà không có Y?
            lambda: {
                "q": f"Cái gì có {random.choice(['mắt', 'miệng', 'tai', 'chân', 'răng'])} mà không có {random.choice(['mắt', 'miệng', 'tai', 'chân', 'răng'])}?",
                "a": [random.choice(["cái kim", "cái bàn", "cái ghế", "cái cưa", "cái lược"])],
                "h": "Đồ vật quen thuộc"
            },
            # Template 3: Đố mẹo toán
            lambda: {
                "q": f"Có {random.randint(3, 10)} {random.choice(['quả', 'cái', 'con'])} {random.choice(['táo', 'cam', 'chuối'])}, {random.choice(['ăn', 'cho', 'bán'])} {random.randint(1, 5)} {random.choice(['quả', 'cái', 'con'])}, còn mấy?",
                "a": [str(random.randint(1, 10))],
                "h": "Tính toán cơ bản"
            },
            # Template 4: Đố chữ
            lambda: {
                "q": f"Từ gì có {random.randint(3, 5)} chữ cái, bắt đầu bằng '{random.choice(['m', 'b', 'c', 't', 'n'])}', là {random.choice(['đồ vật', 'con vật', 'món ăn'])}?",
                "a": [random.choice(["bàn", "cá", "thịt", "nước", "mèo"])],
                "h": "Đoán từ"
            },
        ]
        
        result = random.choice(templates)()
        # Đảm bảo có gợi ý
        if "h" not in result:
            result["h"] = "Suy nghĩ kỹ nhé!"
        return result

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        AI NỔ HŨ - THÔNG MINH                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AINoHu:
    """AI điều khiển tỉ lệ nổ hũ thông minh dựa trên jackpot."""
    
    SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
    WEIGHTS = [28, 24, 20, 16, 6, 4, 2]
    PAYOUTS = {
        "🍒🍒🍒": 5, "🍋🍋🍋": 8, "🍊🍊🍊": 12, "🍇🍇🍇": 20,
        "💎💎💎": 50, "🔔🔔🔔": 100, "7️⃣7️⃣7️⃣": 500
    }
    
    @staticmethod
    def adjust_weights(jackpot: int) -> List[int]:
        """Điều chỉnh tỉ lệ: jackpot càng cao -> càng khó trúng 7️⃣."""
        w = AINoHu.WEIGHTS.copy()
        if jackpot > 300000:
            w[6] = max(1, w[6] - 2); w[0] += 2
        elif jackpot > 500000:
            w[6] = max(1, w[6] - 3); w[1] += 2
        return w
    
    @staticmethod
    def bonus_rate(jackpot: int) -> float:
        """AI quyết định % bonus thêm vào jackpot."""
        if jackpot < 100000: return 0.08
        elif jackpot < 200000: return 0.05
        elif jackpot < 300000: return 0.04
        return 0.03
    
    @staticmethod
    def spin(jackpot: int, bet: int) -> Tuple[str, str, str, int, str]:
        """Quay nổ hũ và trả về kết quả."""
        weights = AINoHu.adjust_weights(jackpot)
        c1 = random.choices(AINoHu.SYMBOLS, weights=weights, k=1)[0]
        c2 = random.choices(AINoHu.SYMBOLS, weights=weights, k=1)[0]
        c3 = random.choices(AINoHu.SYMBOLS, weights=weights, k=1)[0]
        
        if c1 == c2 == c3:
            if c1 == "7️⃣":
                return c1, c2, c3, jackpot, "jackpot"
            mult = AINoHu.PAYOUTS.get(f"{c1}{c2}{c3}", 2)
            return c1, c2, c3, bet * mult, f"triple_{mult}"
        elif c1 == c2 or c2 == c3 or c1 == c3:
            return c1, c2, c3, int(bet * 0.5), "double"
        return c1, c2, c3, 0, "lose"

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    18 GIỌNG VIỆT NAM RANDOM                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
VOICE_LIST: List[Dict[str, Any]] = [
    {"name": "🇻🇳 Hà Nội (Chậm)",       "lang": "vi", "speed": 0.8},
    {"name": "🇻🇳 Hà Nội (Vừa)",        "lang": "vi", "speed": 1.0},
    {"name": "🇻🇳 Hà Nội (Nhanh)",      "lang": "vi", "speed": 1.3},
    {"name": "🇻🇳 Sài Gòn (Chậm)",      "lang": "vi", "speed": 0.7},
    {"name": "🇻🇳 Sài Gòn (Vừa)",       "lang": "vi", "speed": 1.0},
    {"name": "🇻🇳 Sài Gòn (Nhanh)",     "lang": "vi", "speed": 1.4},
    {"name": "🇻🇳 Nhẹ nhàng",           "lang": "vi", "speed": 0.6},
    {"name": "🇻🇳 Trầm ấm",            "lang": "vi", "speed": 0.9},
    {"name": "🇻🇳 Cao vút",            "lang": "vi", "speed": 1.5},
    {"name": "🇻🇳 Lơ lớ (Tây)",        "lang": "vi", "speed": 0.75},
    {"name": "🇻🇳 Robot 🤖",           "lang": "vi", "speed": 0.5},
    {"name": "🇻🇳 Sành điệu",          "lang": "vi", "speed": 1.2},
    {"name": "🇻🇳 Bà cụ",              "lang": "vi", "speed": 0.55},
    {"name": "🇻🇳 Em bé",              "lang": "vi", "speed": 1.6},
    {"name": "🇻🇳 Phát thanh viên",    "lang": "vi", "speed": 1.05},
    {"name": "🇻🇳 Hài hước",           "lang": "vi", "speed": 1.1},
    {"name": "🇻🇳 Nghiêm túc",         "lang": "vi", "speed": 0.85},
    {"name": "🇻🇳 Miền Trung (Huế)",   "lang": "vi", "speed": 0.95},
]

# Google TTS config
TTS_URL = "https://translate.google.com/translate_tts"
TTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "audio/mpeg, audio/*;q=0.9",
    "Referer": "https://translate.google.com/"
}
MAX_CHUNK = 180

@dataclass
class VoiceRequest:
    chat_id: int
    reply_id: int
    text: str
    user_name: str
    voice: Optional[Dict] = None

voice_queue: Queue = Queue(maxsize=50)

def fetch_tts_chunk(text: str, lang: str = "vi", speed: float = 1.0) -> Optional[bytes]:
    """Tải 1 đoạn MP3 từ Google Translate TTS."""
    params = {
        "ie": "UTF-8", "q": text, "tl": lang, "total": "1", "idx": "0",
        "textlen": str(len(text)), "client": "tw-ob", "prev": "input",
        "ttsspeed": str(speed)
    }
    try:
        resp = ses.get(TTS_URL, params=params, headers=TTS_HEADERS, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 100:
            return resp.content
    except Exception as e:
        logger.error(f"TTS fetch error: {e}")
    return None

def split_chunks(text: str, max_size: int = MAX_CHUNK) -> List[str]:
    """Chia text thành các đoạn nhỏ để gửi TTS."""
    if len(text) <= max_size:
        return [text]
    chunks = []
    separators = ['. ', '! ', '? ', ', ', '; ', ': ', ' - ', '\n', ' ']
    while len(text) > max_size:
        best_pos = max_size
        for sep in separators:
            pos = text.rfind(sep, 0, max_size)
            if pos > max_size // 2:
                best_pos = pos + len(sep); break
        if best_pos > max_size or best_pos <= max_size // 3:
            best_pos = max_size
        chunks.append(text[:best_pos].strip())
        text = text[best_pos:].strip()
    if text: chunks.append(text)
    return chunks

def generate_voice(text: str, speed: float = 1.0) -> Optional[BytesIO]:
    """Tạo voice từ text, trả về BytesIO chứa MP3."""
    clean = re.sub(r'[<>"\'{}|\\^~\[\]`]', '', text).strip()
    if not clean: return None
    chunks = split_chunks(clean)
    audio_data = b""
    for chunk in chunks:
        data = fetch_tts_chunk(chunk, "vi", speed)
        if data: audio_data += data
    return BytesIO(audio_data) if audio_data else None

def voice_worker():
    """Worker xử lý hàng đợi voice."""
    while True:
        try:
            req: VoiceRequest = voice_queue.get(block=True, timeout=1)
            if not req: continue
            text = req.text[:500].strip()
            if not text: voice_queue.task_done(); continue
            
            voice = req.voice if req.voice else random.choice(VOICE_LIST)
            audio = generate_voice(text, voice["speed"])
            
            if audio:
                audio.name = f"voice_{int(time.time())}.mp3"
                cap = f"🎙️ {html.escape(text[:150])}\n🗣️ <b>{voice['name']}</b>"
                try:
                    bot.send_voice(req.chat_id, audio, reply_to_message_id=req.reply_id,
                                   caption=cap, parse_mode="HTML")
                    brain.stats["voice_generated"] += 1
                except Exception:
                    try:
                        audio.seek(0)
                        bot.send_audio(req.chat_id, audio, reply_to_message_id=req.reply_id,
                                       title="Voice", caption=cap, parse_mode="HTML")
                        brain.stats["voice_generated"] += 1
                    except: pass
            else:
                try:
                    bot.send_message(req.chat_id,
                                     f"❌ {html.escape(req.user_name)}, không thể tạo giọng nói.",
                                     reply_to_message_id=req.reply_id, parse_mode="HTML")
                except: pass
            voice_queue.task_done()
        except Exception as e:
            logger.error(f"Voice worker error: {e}")
            try: voice_queue.task_done()
            except: pass

# Khởi động 4 voice workers
for _ in range(4):
    Thread(target=voice_worker, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           MINI GAMES ENGINE                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def init_game(uid: int, game_type: str) -> Dict:
    """Khởi tạo phiên game mới cho user."""
    if game_type == "taixiu":
        return {"type": "taixiu", "bal": 1000, "w": 0, "l": 0}
    elif game_type == "baucua":
        return {"type": "baucua", "bal": 1000, "sym": ["🦀", "🐟", "🦐", "🐓", "🦌", "🎃"], "w": 0, "l": 0}
    elif game_type == "kbb":
        return {"type": "kbb", "score": 0, "bot": 0, "draw": 0}
    elif game_type == "doanso":
        return {"type": "doanso", "secret": random.randint(1, 100), "att": 0, "max": 7}
    elif game_type == "lxn":
        return {"type": "lxn", "bal": 1000, "w": 0, "l": 0}
    elif game_type == "xx":
        return {"type": "xx", "bal": 1000, "w": 0, "l": 0}
    elif game_type == "caudo":
        return {"type": "caudo", "score": 0, "qnum": 0, "cur": None, "hint": False, "ans": False, "start": 0}
    return {}

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           LỆNH VOICE                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['voice'])
def voice_cmd(m):
    """Lệnh /voice - Chuyển text thành giọng nói với 18 giọng random."""
    if not is_grp(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    
    # Lấy text
    txt = ""
    if m.reply_to_message and m.reply_to_message.text:
        txt = m.reply_to_message.text.strip()
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1: txt = parts[1].strip()
    
    # Nếu không có text -> hiển thị danh sách giọng
    if not txt:
        voice_list_text = "🎙️ <b>18 GIỌNG VIỆT NAM RANDOM</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, v in enumerate(VOICE_LIST, 1):
            voice_list_text += f"{i}. {v['name']} (x{v['speed']})\n"
        voice_list_text += "━━━━━━━━━━━━━━━━━━━━\n📝 /voice [text] - Random giọng\n📝 /voice [số 1-18] [text] - Chọn giọng"
        msg = bot.reply_to(m, voice_list_text, parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    # Kiểm tra nếu chọn số giọng
    selected_voice = None
    parts = txt.split(maxsplit=1)
    if parts[0].isdigit():
        idx = int(parts[0])
        if 1 <= idx <= len(VOICE_LIST):
            selected_voice = VOICE_LIST[idx - 1]
            txt = parts[1] if len(parts) > 1 else ""
        else:
            msg = bot.reply_to(m, f"❌ Chọn số 1-{len(VOICE_LIST)}.", parse_mode="HTML")
            del_both(m, msg.message_id); return
    
    if not txt:
        msg = bot.reply_to(m, "❌ Cần text để đọc.", parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    if len(txt) > 500: txt = txt[:500]
    
    # Đưa vào hàng đợi
    req = VoiceRequest(chat_id=m.chat.id, reply_id=m.message_id, text=txt,
                       user_name=m.from_user.first_name, voice=selected_voice)
    try:
        voice_queue.put_nowait(req)
        vn = selected_voice["name"] if selected_voice else "🎲 Random..."
        msg = bot.reply_to(m, f"🎙️ Đang tạo voice...\n🗣️ {vn}", parse_mode="HTML")
        auto_del(m.chat.id, m.message_id, 12)
        auto_del(m.chat.id, msg.message_id, 12)
    except:
        msg = bot.reply_to(m, "⚠️ Hàng đợi voice đầy, thử lại sau.", parse_mode="HTML")
        del_both(m, msg.message_id)

@bot.message_handler(commands=['voices', 'giongnoi', 'listvoice'])
def list_voice_cmd(m):
    """Hiển thị danh sách 18 giọng."""
    if not is_grp(m): return
    text = "🎙️ <b>18 GIỌNG VIỆT NAM</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, v in enumerate(VOICE_LIST, 1):
        text += f"<b>{i}.</b> {v['name']} | Tốc độ: x{v['speed']}\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n📝 /voice - Random | /voice [số] [text] - Chọn"
    msg = bot.reply_to(m, text, parse_mode="HTML"); del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: TÀI XỈU                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['taixiu'])
def taixiu_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu":
            GAME_SESSIONS[uid] = init_game(uid, "taixiu")
        g = GAME_SESSIONS[uid]
        msg = bot.reply_to(m, f"🎲 <b>TÀI XỈU</b>\n/taixiu [tai/xiu] [cược]\n💎 Game: {g['bal']} xu\nTài (11-18) | Xỉu (3-10)", parse_mode="HTML")
        del_both(m, msg.message_id); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: msg = bot.reply_to(m, "❌ Cược phải là số.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if ch not in ['tai', 'xiu']: msg = bot.reply_to(m, "❌ 'tai' hoặc 'xiu'.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu":
        GAME_SESSIONS[uid] = init_game(uid, "taixiu")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: msg = bot.reply_to(m, f"❌ Số dư game: {g['bal']} xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    dice = [random.randint(1, 6) for _ in range(3)]; total = sum(dice)
    res = "tai" if total >= 11 else "xiu"
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    if ch == res: g["bal"] += bt; g["w"] += 1; out = f"✅ THẮNG +{bt} xu"
    else: g["bal"] -= bt; g["l"] += 1; out = f"❌ THUA -{bt} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"🎲 <b>TÀI XỈU</b>\n🎲 {ds} = <b>{total}</b> → <b>{res.upper()}</b>\n🎯 Bạn: {ch.upper()}\n💰 {out} | 💎 {g['bal']} xu\n📊 W:{g['w']} L:{g['l']}", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: BẦU CUA                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['baucua'])
def baucua_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    sm = {"bau": 0, "bầu": 0, "cua": 1, "ca": 2, "cá": 2, "tom": 3, "tôm": 3, "ga": 4, "gà": 4, "nai": 5, "huou": 5, "hươu": 5}
    gs = ["🦀 Bầu", "🐟 Cua", "🦐 Cá", "🐓 Tôm", "🦌 Gà", "🎃 Nai"]
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "baucua":
            GAME_SESSIONS[uid] = init_game(uid, "baucua")
        g = GAME_SESSIONS[uid]
        msg = bot.reply_to(m, f"🎲 <b>BẦU CUA</b>\n{' | '.join(gs)}\n/baucua [con] [cược]\n💎 Game: {g['bal']} xu", parse_mode="HTML")
        del_both(m, msg.message_id); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: msg = bot.reply_to(m, "❌ Cược phải là số.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if ch not in sm: msg = bot.reply_to(m, f"❌ Chọn: {', '.join(sm.keys())}", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "baucua":
        GAME_SESSIONS[uid] = init_game(uid, "baucua")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: msg = bot.reply_to(m, f"❌ Số dư game: {g['bal']} xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    ci = sm[ch]; roll = [random.randint(0, 5) for _ in range(3)]
    rs = [g["sym"][i] for i in roll]; match = roll.count(ci)
    if match > 0: wa = bt * (match + 1); g["bal"] += wa - bt; g["w"] += 1; out = f"✅ THẮNG +{wa - bt} xu (trúng {match} con)"
    else: g["bal"] -= bt; g["l"] += 1; out = f"❌ THUA -{bt} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"🎲 <b>BẦU CUA</b>\n🎯 {' '.join(rs)}\n🎯 Bạn: <b>{g['sym'][ci]}</b> (trúng {match}/3)\n💰 {out} | 💎 {g['bal']} xu", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: KÉO BÚA BAO                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['kbb', 'keobuabao'])
def kbb_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    chs = {"keo": "✌️ Kéo", "kéo": "✌️ Kéo", "bua": "🔨 Búa", "búa": "🔨 Búa", "bao": "📄 Bao"}
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "kbb":
            GAME_SESSIONS[uid] = init_game(uid, "kbb")
        g = GAME_SESSIONS[uid]
        msg = bot.reply_to(m, f"✌️ <b>KÉO BÚA BAO</b>\n/kbb [keo/bua/bao]\n👤 {g['score']} | 🤖 {g['bot']} | 🤝 {g['draw']}", parse_mode="HTML")
        del_both(m, msg.message_id); return
    ch = parts[1].lower()
    if ch not in chs: msg = bot.reply_to(m, "❌ keo/bua/bao", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "kbb":
        GAME_SESSIONS[uid] = init_game(uid, "kbb")
    g = GAME_SESSIONS[uid]
    uc, bc = chs[ch], random.choice(list(chs.values()))
    ui, bi = list(chs.values()).index(uc), list(chs.values()).index(bc)
    if ui == bi: r = "🤝 HÒA"; g["draw"] += 1
    elif (ui == 0 and bi == 2) or (ui == 1 and bi == 0) or (ui == 2 and bi == 1): r = "✅ THẮNG"; g["score"] += 1
    else: r = "❌ THUA"; g["bot"] += 1
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"✌️ <b>KÉO BÚA BAO</b>\n👤 {uc} vs 🤖 {bc}\n📊 {r}\n🏆 Bạn: {g['score']} | Bot: {g['bot']} | Hòa: {g['draw']}", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: ĐOÁN SỐ                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['doanso'])
def doanso_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 2:
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
        msg = bot.reply_to(m, "🔢 <b>ĐOÁN SỐ</b> (1-100)\n/doanso [số]\nCó <b>7</b> lần đoán!", parse_mode="HTML")
        del_both(m, msg.message_id); return
    try: gs = int(parts[1])
    except: msg = bot.reply_to(m, "❌ Nhập số 1-100.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if gs < 1 or gs > 100: msg = bot.reply_to(m, "❌ 1-100.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "doanso":
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
    g = GAME_SESSIONS[uid]; g["att"] += 1; brain.stats["games_played"] += 1
    if gs == g["secret"]:
        rw = (8 - g["att"]) * 500; add_balance(uid, rw)
        msg = bot.reply_to(m, f"🎉 <b>CHÍNH XÁC!</b> Số {g['secret']} ({g['att']} lần)\n💰 +{rw:,} xu", parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        msg = bot.reply_to(m, f"💀 <b>HẾT LƯỢT!</b> Số là {g['secret']}.", parse_mode="HTML")
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]: msg = bot.reply_to(m, f"🔢 {gs} → ⬆️ CAO HƠN ({g['max'] - g['att']} lần)", parse_mode="HTML")
    else: msg = bot.reply_to(m, f"🔢 {gs} → ⬇️ THẤP HƠN ({g['max'] - g['att']} lần)", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: LẮC XÍ NGẦU                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['lxn', 'lacxingau'])
def lxn_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "lxn":
            GAME_SESSIONS[uid] = init_game(uid, "lxn")
        g = GAME_SESSIONS[uid]
        msg = bot.reply_to(m, f"🎲 <b>LẮC XÍ NGẦU</b>\n/lxn [tổng 3-18] [cược]\n💎 Game: {g['bal']} xu\nTrúng chính xác: x10!", parse_mode="HTML")
        del_both(m, msg.message_id); return
    try: gt, bt = int(parts[1]), int(parts[2])
    except: msg = bot.reply_to(m, "❌ /lxn [tổng 3-18] [cược]", parse_mode="HTML"); del_both(m, msg.message_id); return
    if gt < 3 or gt > 18: msg = bot.reply_to(m, "❌ 3-18.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "lxn":
        GAME_SESSIONS[uid] = init_game(uid, "lxn")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: msg = bot.reply_to(m, f"❌ Số dư game: {g['bal']} xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    dice = [random.randint(1, 6) for _ in range(3)]; total = sum(dice)
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    if total == gt: wa = bt * 10; g["bal"] += wa - bt; g["w"] += 1; out = f"🎉 CHÍNH XÁC! +{wa - bt} xu (x10)"
    elif abs(total - gt) == 1: wa = int(bt * 0.5); g["bal"] += wa - bt; out = f"🔄 Gần đúng! Hoàn {wa} xu"
    else: g["bal"] -= bt; g["l"] += 1; out = f"💀 Thua -{bt} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"🎲 <b>LẮC XÍ NGẦU</b>\n🎲 {ds} = <b>{total}</b>\n🎯 Bạn đoán: <b>{gt}</b>\n💰 {out} | 💎 {g['bal']} xu", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           GAME: XÚC XẮC MAY MẮN                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['xx', 'xucxac'])
def xx_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "xx":
            GAME_SESSIONS[uid] = init_game(uid, "xx")
        g = GAME_SESSIONS[uid]
        msg = bot.reply_to(m, f"🎲 <b>XÚC XẮC MAY MẮN</b>\n/xx [số 1-6] [cược]\n💎 Game: {g['bal']} xu\nTrúng: x4 | Lệch 1: hoàn 50%", parse_mode="HTML")
        del_both(m, msg.message_id); return
    try: gs, bt = int(parts[1]), int(parts[2])
    except: msg = bot.reply_to(m, "❌ /xx [số 1-6] [cược]", parse_mode="HTML"); del_both(m, msg.message_id); return
    if gs < 1 or gs > 6: msg = bot.reply_to(m, "❌ 1-6.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "xx":
        GAME_SESSIONS[uid] = init_game(uid, "xx")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: msg = bot.reply_to(m, f"❌ Số dư game: {g['bal']} xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    dr = random.randint(1, 6); de = "⚀⚁⚂⚃⚄⚅"[dr-1]
    if gs == dr: wa = bt * 4; g["bal"] += wa - bt; g["w"] += 1; out = f"🎉 TRÚNG! +{wa - bt} xu (x4)"
    elif abs(gs - dr) == 1: wa = int(bt * 0.5); g["bal"] += wa - bt; out = f"🔄 Lệch 1! Hoàn {wa} xu"
    else: g["bal"] -= bt; g["l"] += 1; out = f"💀 Thua -{bt} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"🎲 <b>XÚC XẮC</b>\n🎯 KQ: {de} <b>{dr}</b>\n🎯 Bạn: <b>{gs}</b>\n💰 {out} | 💎 {g['bal']} xu", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      GAME: CÂU ĐỐ AI RANDOM                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['caudo', 'cd'])
def caudo_cmd(m):
    """
    Game câu đố AI Random:
    - AI tạo câu đố mới không trùng lặp
    - Độ khó tăng theo điểm số
    - Timeout 60 giây
    - Có hint và bonus tốc độ
    """
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    users[str(uid)] = m.from_user.first_name; save_users(users)
    
    # Bắt đầu câu đố mới
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "caudo" or GAME_SESSIONS[uid].get("ans", False):
        prev_score = GAME_SESSIONS[uid].get("score", 0) if uid in GAME_SESSIONS else 0
        difficulty = min(5, 1 + prev_score // 5)
        
        # Lấy câu đố mới không trùng
        used = set(USED_RIDDLES.get(uid, []))
        riddle = AICauDo.generate(difficulty, used)
        USED_RIDDLES[uid].append(riddle["a"][0])
        if len(USED_RIDDLES[uid]) > 100: USED_RIDDLES[uid] = USED_RIDDLES[uid][-100:]
        
        GAME_SESSIONS[uid] = {
            "type": "caudo", "score": prev_score,
            "qnum": GAME_SESSIONS[uid].get("qnum", 0) + 1 if uid in GAME_SESSIONS else 1,
            "cur": riddle, "hint": False, "ans": False, "start": time.time(),
            "diff": difficulty
        }
        
        diff_emoji = ["🟢", "🟡", "🟠", "🔴", "💀"][difficulty - 1]
        msg = bot.reply_to(m,
            f"🧩 <b>CÂU ĐỐ AI #{GAME_SESSIONS[uid]['qnum']}</b>\n"
            f"⏰ <b>60s</b> | Độ khó: {diff_emoji} <b>{difficulty}/5</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>{riddle['q']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤔 /caudo [đáp án] để trả lời\n"
            f"💡 /caudo hint (-1 điểm)",
            parse_mode="HTML"
        ); del_both(m, msg.message_id)
        
        # Timer timeout 60s
        def timeout_caudo(uid_ref, chat_id):
            time.sleep(60)
            if uid_ref in GAME_SESSIONS and GAME_SESSIONS[uid_ref].get("type") == "caudo":
                if not GAME_SESSIONS[uid_ref].get("ans", True):
                    r = GAME_SESSIONS[uid_ref]["cur"]
                    GAME_SESSIONS[uid_ref]["ans"] = True
                    try:
                        bot.send_message(chat_id,
                            f"⏰ <b>HẾT GIỜ!</b>\n"
                            f"🧩 Đáp án: <b>{r['a'][0]}</b>\n"
                            f"💡 {r.get('h', 'Không có gợi ý')}\n"
                            f"🔄 /caudo để chơi tiếp!",
                            parse_mode="HTML"
                        )
                    except: pass
        Thread(target=timeout_caudo, args=(uid, m.chat.id), daemon=True).start()
        return
    
    # Xử lý trả lời
    g = GAME_SESSIONS[uid]
    if g.get("ans", False):
        msg = bot.reply_to(m, "⏰ Câu đố đã kết thúc!\n🔄 /caudo để chơi câu mới.", parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    if len(parts) < 2:
        elapsed = int(time.time() - g["start"]); rem = max(0, 60 - elapsed)
        msg = bot.reply_to(m,
            f"🧩 <b>CÂU ĐỐ #{g['qnum']}</b>\n"
            f"⏰ Còn <b>{rem}s</b>\n"
            f"📝 <b>{g['cur']['q']}</b>\n"
            f"🤔 /caudo [đáp án]", parse_mode="HTML"
        ); del_both(m, msg.message_id); return
    
    arg = " ".join(parts[1:]).lower().strip()
    
    # Hint
    if arg in ["hint", "gợi ý", "goi y"]:
        if g["hint"]: msg = bot.reply_to(m, "❌ Đã dùng gợi ý rồi!", parse_mode="HTML"); del_both(m, msg.message_id); return
        g["hint"] = True; g["score"] = max(0, g["score"] - 1)
        elapsed = int(time.time() - g["start"]); rem = max(0, 60 - elapsed)
        msg = bot.reply_to(m, f"💡 <b>GỢI Ý:</b> {g['cur']['h']}\n⏰ Còn {rem}s\n🏆 Điểm: {g['score']} (-1)", parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    # Kiểm tra đáp án
    correct = any(arg == a.lower() or a.lower() in arg or arg in a.lower()
                  for a in g["cur"]["a"])
    
    if correct:
        elapsed = int(time.time() - g["start"])
        time_bonus = max(0, int((60 - elapsed) / 5))
        base_reward = 2000 + g["diff"] * 1000
        reward = base_reward + time_bonus * 500
        add_balance(uid, reward)
        g["score"] += 3 + time_bonus; g["ans"] = True
        
        time_emoji = "⚡" if elapsed < 10 else "⏱️" if elapsed < 30 else "🐢"
        msg = bot.reply_to(m,
            f"🎉 <b>CHÍNH XÁC!</b> {time_emoji} ({elapsed}s)\n"
            f"🧩 Đáp án: <b>{g['cur']['a'][0]}</b>\n"
            f"💰 Thưởng: <b>+{reward:,}</b> xu\n"
            f"🏆 Điểm: <b>{g['score']}</b>\n"
            f"📊 Độ khó sau: <b>{min(5, 1 + g['score'] // 5)}/5</b>\n"
            f"🔄 /caudo để chơi tiếp!",
            parse_mode="HTML"
        ); del_both(m, msg.message_id)
    else:
        g["score"] = max(0, g["score"] - 1)
        elapsed = int(time.time() - g["start"]); rem = max(0, 60 - elapsed)
        if rem <= 0:
            g["ans"] = True
            msg = bot.reply_to(m, f"⏰ HẾT GIỜ!\n🧩 Đáp án: <b>{g['cur']['a'][0]}</b>\n🔄 /caudo để tiếp!", parse_mode="HTML")
        else:
            hint_msg = f"\n💡 {g['cur']['h'][:50]}..." if not g["hint"] and elapsed > 30 else ""
            msg = bot.reply_to(m, f"❌ <b>SAI!</b> (-1)\n⏰ Còn {rem}s\n🏆 {g['score']}{hint_msg}", parse_mode="HTML")
        del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           NỔ HŨ + ĐIỂM DANH + TÀI CHÍNH                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['nohu', 'slot', 'quay'])
def nohu_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    users[str(uid)] = m.from_user.first_name; save_users(users)
    
    if len(parts) < 2:
        jp = load_jackpot()
        msg = bot.reply_to(m, f"🎰 <b>AI NỔ HŨ</b>\n💰 JACKPOT: <b>{jp:,}</b> xu\n🎮 /nohu [cược] (Phí: {nohu_fee:,} xu)\n🏆 7️⃣7️⃣7️⃣ = JACKPOT!", parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    try: bet = int(parts[1])
    except: msg = bot.reply_to(m, "❌ Cược phải là số.", parse_mode="HTML"); del_both(m, msg.message_id); return
    if bet < 100 or bet > 100000: msg = bot.reply_to(m, "❌ 100 - 100,000 xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    total = bet + nohu_fee
    if not deduct_balance(uid, total):
        msg = bot.reply_to(m, f"❌ Không đủ! Cần <b>{total:,}</b> xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    global nohu_jackpot
    jp = load_jackpot()
    br = AINoHu.bonus_rate(jp)
    jp += int(bet * br)
    save_jackpot(jp)
    nohu_jackpot = jp
    brain.stats["nohu_spins"] += 1
    
    c1, c2, c3, win, typ = AINoHu.spin(jp, bet)
    result_text = f"{c1} {c2} {c3}"
    
    if typ == "jackpot":
        add_balance(uid, win)
        nohu_history.append({"name": m.from_user.first_name, "amount": win, "time": datetime.now(tz).strftime("%H:%M %d/%m")})
        nohu_jackpot = 100000; save_jackpot(100000)
        out = f"🎉🎉🎉 <b>JACKPOT!!!</b> +{win:,} xu"; em = "🏆"
    elif typ.startswith("triple"):
        add_balance(uid, win)
        mult = typ.split("_")[1]; out = f"✅ NỔ HŨ! (x{mult}) +{win:,} xu"; em = "🎉"
    elif typ == "double":
        add_balance(uid, win); out = f"🔄 2 giống: hoàn {win:,} xu"; em = "🔹"
    else:
        out = f"💀 Thua -{total:,} xu"; em = "❌"
    
    msg = bot.reply_to(m,
        f"{em} <b>AI NỔ HŨ</b>\n"
        f"┌──────────┐\n"
        f"│ {c1}  {c2}  {c3} │\n"
        f"└──────────┘\n"
        f"🎯 {out}\n"
        f"💰 JACKPOT: <b>{nohu_jackpot:,}</b> xu\n"
        f"💎 Số dư: <b>{get_user_balance(uid):,}</b> xu",
        parse_mode="HTML"
    ); del_both(m, msg.message_id)

@bot.message_handler(commands=['daily', 'diemdanh', 'checkin'])
def daily_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; today = date.today().isoformat()
    users[str(uid)] = m.from_user.first_name; save_users(users)
    
    if daily_checkin.get(uid) == today:
        msg = bot.reply_to(m, f"❌ <b>{html.escape(m.from_user.first_name)}</b>, đã điểm danh hôm nay!\n💰 {get_user_balance(uid):,} xu", parse_mode="HTML")
        del_both(m, msg.message_id); return
    
    reward = random.randint(500, 1500)
    daily_checkin[uid] = today; save_daily_checkins(daily_checkin)
    add_balance(uid, reward)
    brain.stats["daily_checkins"] += 1
    
    msg = bot.reply_to(m, f"✅ <b>ĐIỂM DANH!</b>\n👤 {html.escape(m.from_user.first_name)}\n💰 +{reward:,} xu\n💎 {get_user_balance(uid):,} xu", parse_mode="HTML")
    del_both(m, msg.message_id)

@bot.message_handler(commands=['balance', 'xu', 'money'])
def balance_cmd(m):
    if not is_grp(m): return
    target = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    name = m.reply_to_message.from_user.first_name if m.reply_to_message else m.from_user.first_name
    msg = bot.reply_to(m, f"💎 <b>{html.escape(name)}</b>: <b>{get_user_balance(target):,}</b> xu", parse_mode="HTML")
    del_both(m, msg.message_id)

@bot.message_handler(commands=['top', 'bxh'])
def top_cmd(m):
    if not is_grp(m): return
    sorted_bal = sorted(user_balance.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n"; medals = ["🥇", "🥈", "🥉"] + ["  "] * 7
    for i, (uid, bal) in enumerate(sorted_bal):
        name = users.get(str(uid), str(uid))
        text += f"{medals[i]} <b>#{i+1}</b> <a href='tg://user?id={uid}'>{html.escape(name)}</a>: <code>{bal:,}</code> xu\n"
    msg = bot.reply_to(m, text, parse_mode="HTML"); del_both(m, msg.message_id)

@bot.message_handler(commands=['give', 'chuyen'])
def give_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; target = None; amount = 0
    
    if m.reply_to_message:
        target = m.reply_to_message.from_user.id
        parts = m.text.split()
        if len(parts) >= 2:
            try: amount = int(parts[1])
            except: amount = 0
    else:
        parts = m.text.split()
        if len(parts) >= 3:
            if parts[1].startswith('@'):
                try: target = bot.get_chat_member(m.chat.id, parts[1]).user.id
                except: target = None
            elif parts[1].isdigit(): target = int(parts[1])
            try: amount = int(parts[2])
            except: amount = 0
    
    if not target or target == uid or amount < 100:
        msg = bot.reply_to(m, "❌ /give [@mention/reply] [số xu]", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    fee = int(amount * 0.05); total = amount + fee
    if not deduct_balance(uid, total):
        msg = bot.reply_to(m, f"❌ Không đủ! Cần {total:,} xu.", parse_mode="HTML"); del_both(m, msg.message_id); return
    
    add_balance(target, amount)
    target_name = users.get(str(target), str(target))
    msg = bot.reply_to(m, f"💸 {html.escape(m.from_user.first_name)} → <a href='tg://user?id={target}'>{html.escape(target_name)}</a>: <b>{amount:,}</b> xu", parse_mode="HTML")
    del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           AI CHAT + ANTI-SPAM                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def ask_ai(prompt: str) -> str:
    """Gọi AI chat với cơ chế xoay vòng key và cache."""
    global ck_idx
    if brain.state == "sleep": return random.choice(get_kho())
    if len(mem) >= 2 and mem[-2] == prompt: return mem[-1]
    
    sys_msg = "Bạn là kẻ cọc cằn, chửi khịa trẻ trâu. Xưng 'tao' gọi 'mày'. Trả lời dưới 12 từ, không emoji."
    msgs = [{"role": "system", "content": sys_msg}]
    for t in list(mem)[-8:]: msgs.append({"role": "user", "content": t})
    msgs.append({"role": "user", "content": prompt})
    
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS); continue
            try:
                resp = ses.post(k["url"],
                    json={"model": k["model"], "messages": msgs, "max_tokens": 40, "temperature": 0.9},
                    headers={"Authorization": f"Bearer {k['key']}", "Content-Type": "application/json"},
                    timeout=8)
                if resp.status_code == 200:
                    result = resp.json()['choices'][0]['message']['content'].strip()
                    result = re.sub(r'[_*`\[\]()]', '', result)
                    k["fail"] = 0; k["last_used"] = time.time()
                    mem.append(prompt); mem.append(result)
                    brain.stats["ai_calls"] += 1
                    return result
                else: k["fail"] += 1
            except: k["fail"] += 1; brain.stats["errors"] += 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
    
    # Tự sửa nếu tất cả key die
    if not any(k["status"] for k in AI_KEYS):
        for k in AI_KEYS: k["status"], k["fail"] = True, 0
        brain.stats["errors"] = 0; brain.state = "repair"
        logger.warning("All AI keys reset")
        return "[Não tự sửa] AI đã reset. Thử lại sau 5s."
    return random.choice(get_kho())

def antispam(m) -> bool:
    """Kiểm tra spam: >5 tin/4s -> warn, 3 warn -> ban 1h."""
    if is_admin(m): return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid, []) if now - t < 4] + [now]
    if len(spam[uid]) > 5:
        warn_counts[uid] = warn_counts.get(uid, 0) + 1
        brain.stats["spam_blocked"] += 1
        try:
            bot.delete_message(m.chat.id, m.message_id)
            if warn_counts[uid] >= 3:
                try: bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time()) + 3600)
                except: pass
                del warn_counts[uid]
        except: pass
        return True
    return False

def antilink(m) -> bool:
    """Xóa link Telegram."""
    if is_admin(m): return False
    text = (m.text or "") + (m.caption or "")
    if TELEGRAM_LINK.search(text):
        try: bot.delete_message(m.chat.id, m.message_id)
        except: pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           QUẢN LÍ NHÓM                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target: msg = bot.reply_to(m, "❌ Reply/mention/ID.", parse_mode="HTML"); del_both(m, msg.message_id); return
    try: bot.ban_chat_member(m.chat.id, target); bot.delete_message(m.chat.id, m.message_id)
    except Exception as e: bot.reply_to(m, f"⚠️ {str(e)[:100]}", parse_mode="HTML"); auto_del(m.chat.id, m.message_id)

@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target: auto_del(m.chat.id, m.message_id); return
    duration = parse_duration(reason) if reason else 3600
    try:
        until = int(time.time()) + duration
        bot.restrict_chat_member(m.chat.id, target, until_date=until,
                                 can_send_messages=False, can_send_media_messages=False,
                                 can_send_other_messages=False, can_add_web_page_previews=False)
        bot.delete_message(m.chat.id, m.message_id); mutes[target] = until
    except: pass

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if not target: auto_del(m.chat.id, m.message_id); return
    try:
        bot.restrict_chat_member(m.chat.id, target, can_send_messages=True,
                                 can_send_media_messages=True, can_send_other_messages=True,
                                 can_add_web_page_previews=True)
        bot.delete_message(m.chat.id, m.message_id)
    except: pass
    if target in mutes: del mutes[target]

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target: auto_del(m.chat.id, m.message_id); return
    warn_counts[target] = warn_counts.get(target, 0) + 1; cnt = warn_counts[target]
    bot.delete_message(m.chat.id, m.message_id)
    if cnt >= 3:
        try: bot.ban_chat_member(m.chat.id, target, until_date=int(time.time()) + 3600); del warn_counts[target]
        except: pass

@bot.message_handler(commands=['stats', 'memberstats'])
def stats_cmd(m):
    if not is_grp(m): return
    try: real_count = bot.get_chat_member_count(GROUP_ID)
    except: real_count = member_stats.get("current_members", 0)
    msg = bot.reply_to(m,
        f"📊 <b>THỐNG KÊ</b>\n"
        f"👥 Hiện tại: <b>{real_count}</b>\n"
        f"📥 Tổng vào: <b>{member_stats['total_joined']}</b>\n"
        f"📤 Tổng rời: <b>{member_stats['total_left']}</b>\n"
        f"💰 Tổng xu: <b>{sum(user_balance.values()):,}</b>",
        parse_mode="HTML"
    ); del_both(m, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           HANDLERS CƠ BẢN                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start_cmd(m):
    if not is_grp(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    brain.trusted_users.add(m.from_user.id)
    
    help_text = (
        f"<b>🧠 NÃO ROBOT - FULL AI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎙️ /voice [text] - 18 giọng VN Random\n"
        f"🎰 /nohu [cược] - AI Nổ Hũ\n"
        f"🎲 /taixiu /baucua /kbb /doanso /lxn /xx - Games\n"
        f"🧩 /caudo - AI Câu Đố Random\n"
        f"💎 /daily /balance /top /give\n"
        f"🛠️ /ban /mute /unmute /warn /stats\n"
        f"🧠 /ramstatus - Xem RAM\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>🗑️ Tự xóa sau {AUTO_DELETE_DELAY}s | 🤖 AI tự học & tự sửa</i>"
    )
    msg = bot.reply_to(m, help_text, parse_mode="HTML"); del_both(m, msg.message_id)

@bot.message_handler(commands=['brain', 'ramstatus'])
def brain_cmd(m):
    if not is_grp(m): return
    uptime = int(time.time() - brain.stats["uptime_start"])
    text = (
        f"🧠 <b>TRẠNG THÁI NÃO</b>\n"
        f"State: <code>{brain.state}</code> | Mood: <code>{brain.mood}</code>\n"
        f"Msgs: <code>{brain.stats['msg_processed']}</code> | AI: <code>{brain.stats['ai_calls']}</code>\n"
        f"Games: <code>{brain.stats['games_played']}</code> | Nổ Hũ: <code>{brain.stats['nohu_spins']}</code>\n"
        f"Voice: <code>{brain.stats['voice_generated']}</code> | Daily: <code>{brain.stats['daily_checkins']}</code>\n"
        f"RAM: <code>{ram_manager.get_memory_mb():.1f}MB</code> | Dọn: <code>{ram_manager.clean_count}</code> lần\n"
        f"Freed: <code>{ram_manager.total_cleaned_bytes/1024/1024:.1f}MB</code>\n"
        f"Errors: <code>{brain.stats['errors']}</code> | Uptime: <code>{uptime//3600}h{(uptime%3600)//60}m</code>"
    )
    msg = bot.reply_to(m, text, parse_mode="HTML"); del_both(m, msg.message_id)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def handle_text(m):
    """Xử lý chat thường + AI."""
    if antispam(m) or antilink(m) or m.text.startswith('/'): return
    
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    brain.think(m.from_user.id, m.text)
    
    uid = m.from_user.id
    if not brain.should_reply(uid, m.text): return
    if uid in ai_cd and time.time() - ai_cd[uid] < 2: return
    ai_cd[uid] = time.time()
    
    def _ai_response():
        reply = ask_ai(m.text)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id):
            msg = bot.reply_to(m, html.escape(reply), parse_mode="HTML"); auto_del(m.chat.id, msg.message_id)
        else:
            msg = bot.reply_to(m, html.escape(reply), parse_mode="HTML"); auto_del(m.chat.id, msg.message_id)
    ai_executor.submit(_ai_response)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    today = date.today().isoformat()
    for u in m.new_chat_members:
        if u.id == bot.get_me().id: continue
        users[str(u.id)] = u.first_name
        member_stats["daily_join"][today] += 1
        member_stats["total_joined"] += 1
        member_stats["current_members"] += 1
        save_users(users); save_member_stats()
        msg = bot.send_message(m.chat.id, f"🔥 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào. {random.choice(get_kho())}", parse_mode="HTML")
        auto_del(m.chat.id, msg.message_id)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m):
    if not is_grp(m): return
    today = date.today().isoformat()
    u = m.left_chat_member
    if u.id == bot.get_me().id: return
    member_stats["daily_leave"][today] += 1
    member_stats["total_left"] += 1
    member_stats["current_members"] = max(0, member_stats["current_members"] - 1)
    save_member_stats()
    msg = bot.send_message(m.chat.id, f"🍂 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> cút. {random.choice(get_kho())}", parse_mode="HTML")
    auto_del(m.chat.id, msg.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           BACKGROUND TASKS                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def scheduler_task():
    """Tác vụ nền: thông báo giờ, unmute, dọn dẹp."""
    last_hour = -1
    while True:
        try:
            now = datetime.now(tz)
            brain.health_check()
            if brain.state == "repair": brain.state = "normal"; brain.repair_mode = False
            
            # Thông báo mỗi giờ
            if now.minute == 0 and now.hour != last_hour and users:
                uid, uname = random.choice(list(users.items()))
                msg = bot.send_message(GROUP_ID,
                    f"🔔 <b>{now.strftime('%H:%M')}</b> | <a href='tg://user?id={uid}'>{html.escape(uname)}</a>... {random.choice(get_kho())}",
                    parse_mode="HTML")
                auto_del(GROUP_ID, msg.message_id); last_hour = now.hour
            if now.minute != 0: last_hour = -1
            
            # Tự động unmute
            to_remove = [uid for uid, until in mutes.items() if time.time() > until]
            for uid in to_remove:
                try: bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                except: pass
                del mutes[uid]
            
            # Dọn spam cũ
            if len(spam) > 100:
                for uid in sorted(spam, key=lambda x: spam[x][-1] if spam[x] else 0)[:10]:
                    del spam[uid]
        except: pass
        time.sleep(15)

def auto_save_task():
    """Tự động lưu dữ liệu mỗi 10 phút."""
    while True:
        time.sleep(600)
        try:
            save_users(users); brain.save_state(); save_member_stats()
            save_balances(user_balance); save_daily_checkins(daily_checkin)
            save_jackpot(nohu_jackpot)
        except: pass

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           MAIN                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    """Điểm vào chính của bot."""
    global user_balance, daily_checkin, nohu_jackpot, member_stats
    
    # Tải dữ liệu
    loaded = load_users()
    if isinstance(loaded, dict): users.update(loaded)
    
    user_balance = load_balances()
    daily_checkin = load_daily_checkins()
    nohu_jackpot = load_jackpot()
    
    stats = load_member_stats()
    member_stats.update(stats)
    if not isinstance(member_stats.get("daily_join"), defaultdict):
        member_stats["daily_join"] = defaultdict(int, member_stats.get("daily_join", {}))
    if not isinstance(member_stats.get("daily_leave"), defaultdict):
        member_stats["daily_leave"] = defaultdict(int, member_stats.get("daily_leave", {}))
    
    try: member_stats["current_members"] = bot.get_chat_member_count(GROUP_ID)
    except: member_stats["current_members"] = len(users)
    
    # Khởi động AI RAM Manager
    ram_manager.start_monitoring()
    
    logger.info(f"🚀 NÃO ROBOT FULL AI KHỞI ĐỘNG")
    logger.info(f"👥 {len(users)} users | 💰 Jackpot: {nohu_jackpot:,} xu")
    logger.info(f"🧠 AI Brain + AI RAM + AI Nổ Hũ + AI Câu Đố")
    logger.info(f"🎲 7 Games | 🎙️ 18 Voice | 🗑️ Auto Delete {AUTO_DELETE_DELAY}s")
    
    # Khởi động background tasks
    Thread(target=scheduler_task, daemon=True).start()
    Thread(target=auto_save_task, daemon=True).start()
    
    # Bắt đầu polling
    try: bot.infinity_polling(timeout=30, none_stop=True, interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng: {e}")
        brain.stats["errors"] += 1; brain.save_state()
        save_balances(user_balance); save_daily_checkins(daily_checkin)
        save_jackpot(nohu_jackpot); save_member_stats()

if __name__ == "__main__":
    main()
