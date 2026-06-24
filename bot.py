# -*- coding: utf-8 -*-
# NAO ROBOT - 2000+ DÒNG FULL AI + AI RANDOM THUẬT TOÁN SIÊU KHÓ
# Tác giả: palofsc (palo) | Ngày: 2026-06-24
# Phiên bản: 3.0.0 | Python 3.9+

import sys, io, os, json, time, random, re, html, logging, traceback, hashlib
import urllib.parse, gc, ctypes, psutil, weakref, signal, base64, tempfile
import math, statistics, itertools
import threading                                          # FIX 1: THÊM DÒNG NÀY
from threading import Thread, Lock, Timer, Event
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

# ─── KEEP ALIVE (Render) ──────────────────────────────────────────────────
try:
    from keep_alive import keep_alive
    keep_alive()
    logger.info("Keep-alive started")
except ImportError:
    logger.warning("keep_alive.py not found")

# ─── THƯ VIỆN NGOÀI ───────────────────────────────────────────────────────
import telebot; from telebot import types, util; import requests; import pytz

# ╔══════════════════════════════════════════════════════════════╗
# ║               AI RANDOM ENGINE - THUẬT TOÁN SIÊU KHÓ       ║
# ╚══════════════════════════════════════════════════════════════╝

class AIRandomEngine:
    """
    AI Random Engine - Thuật toán sinh số ngẫu nhiên SIÊU KHÓ.
    
    Nguyên lý:
    1. Kết hợp nhiều nguồn entropy: thời gian, memory, thread ID, psutil
    2. Dùng thuật toán xáo trộn Fisher-Yates cải tiến
    3. Mersenne Twister + XOR shift + Linear Congruential Generator
    4. Lấy entropy từ /dev/urandom (nếu có)
    5. Hash SHA-256 của toàn bộ state để tạo seed mới
    
    Độ khó: Không thể đoán được kết quả ngay cả khi biết toàn bộ code.
    """
    
    def __init__(self):
        self.state = self._collect_entropy()
        self.counter = 0
        self.twister_state = self._init_mersenne_twister()
        logger.info("AI Random Engine initialized - Super hard mode")
    
    def _collect_entropy(self) -> bytes:
        """Thu thập entropy từ nhiều nguồn khác nhau."""
        sources = []
        
        # 1. Thời gian chính xác đến nano giây
        sources.append(str(time.time_ns()).encode())
        
        # 2. Trạng thái bộ nhớ hiện tại
        sources.append(str(psutil.Process(os.getpid()).memory_info().rss).encode())
        
        # 3. CPU usage
        sources.append(str(psutil.cpu_percent(interval=0.01)).encode())
        
        # 4. Thread ID
        sources.append(str(threading.current_thread().ident).encode())
        
        # 5. Số lượng file descriptor đang mở
        try: sources.append(str(len(psutil.Process(os.getpid()).open_files())).encode())
        except: sources.append(b"0")
        
        # 6. /dev/urandom (nếu có)
        try:
            with open('/dev/urandom', 'rb') as f:
                sources.append(f.read(32))
        except:
            sources.append(os.urandom(32))
        
        # 7. Hash của tất cả sources
        combined = b"".join(sources)
        return hashlib.sha256(combined).digest()
    
    def _init_mersenne_twister(self) -> List[int]:
        """Khởi tạo Mersenne Twister với seed từ entropy."""
        seed = int.from_bytes(self._collect_entropy()[:8], 'big')
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, 624):
            mt.append((1812433253 * (mt[i-1] ^ (mt[i-1] >> 30)) + i) & 0xFFFFFFFF)
        return mt
    
    def _twist(self):
        """Xoắn Mersenne Twister."""
        for i in range(624):
            y = (self.twister_state[i] & 0x80000000) + (self.twister_state[(i+1) % 624] & 0x7FFFFFFF)
            self.twister_state[i] = self.twister_state[(i+397) % 624] ^ (y >> 1)
            if y % 2 != 0:
                self.twister_state[i] ^= 0x9908B0DF
    
    def _mersenne_random(self) -> int:
        """Lấy số ngẫu nhiên từ Mersenne Twister."""
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
        """XOR Shift algorithm."""
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        return x & 0xFFFFFFFFFFFFFFFF
    
    def _lcg(self, seed: int) -> int:
        """Linear Congruential Generator."""
        a = 6364136223846793005
        c = 1442695040888963407
        m = 2**64
        return (a * seed + c) % m
    
    def random_bytes(self, n: int = 32) -> bytes:
        """Tạo n bytes ngẫu nhiên siêu khó."""
        result = bytearray()
        seed = int.from_bytes(self._collect_entropy()[:8], 'big')
        
        for i in range(n):
            # Kết hợp 3 thuật toán
            mt_val = self._mersenne_random()
            xs_val = self._xor_shift(seed + i)
            lcg_val = self._lcg(seed + mt_val)
            
            # XOR tất cả lại
            combined = mt_val ^ xs_val ^ lcg_val
            
            # Lấy byte thấp nhất
            result.append(combined & 0xFF)
            
            # Cập nhật seed
            seed = self._xor_shift(combined)
        
        return bytes(result)
    
    def randint(self, min_val: int, max_val: int) -> int:
        """Sinh số nguyên ngẫu nhiên trong khoảng [min, max]."""
        if min_val >= max_val:
            return min_val
        
        range_size = max_val - min_val + 1
        
        # Dùng Fisher-Yates principle kết hợp multiple entropy sources
        entropy = self.random_bytes(16)
        value = int.from_bytes(entropy, 'big')
        
        # Fisher-Yates style mapping
        result = min_val + (value % range_size)
        
        # Thêm SHA-256 hash để tăng độ khó dự đoán
        hash_input = f"{result}{self.counter}{time.time_ns()}".encode()
        hash_val = int.from_bytes(hashlib.sha256(hash_input).digest()[:8], 'big')
        
        # XOR với hash để tạo kết quả cuối cùng
        final = min_val + ((result - min_val + hash_val) % range_size)
        
        return final
    
    def choice(self, items: List[Any]) -> Any:
        """Chọn ngẫu nhiên 1 phần tử từ list."""
        if not items:
            return None
        idx = self.randint(0, len(items) - 1)
        return items[idx]
    
    def shuffle(self, items: List[Any]) -> List[Any]:
        """Xáo trộn list dùng Fisher-Yates cải tiến."""
        result = items.copy()
        n = len(result)
        
        for i in range(n - 1, 0, -1):
            j = self.randint(0, i)
            result[i], result[j] = result[j], result[i]
        
        return result
    
    def random(self) -> float:
        """Sinh số float ngẫu nhiên trong [0, 1)."""
        return self.randint(0, 2**53) / (2**53)
    
    def weighted_choice(self, items: List[Any], weights: List[float]) -> Any:
        """Chọn ngẫu nhiên có trọng số."""
        total = sum(weights)
        r = self.random() * total
        cumulative = 0
        for item, weight in zip(items, weights):
            cumulative += weight
            if r <= cumulative:
                return item
        return items[-1]

# Khởi tạo AI Random Engine toàn cục
ai_random = AIRandomEngine()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    AI RAM MANAGER                           ║
# ╚══════════════════════════════════════════════════════════════╝
class AIRamManager:
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
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        logger.info(f"AI RAM Manager initialized. Max RAM: {max_ram_mb}MB")

    def get_memory_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def get_memory_usage_percent(self) -> float:
        return self.process.memory_info().rss / self.max_ram_bytes

    def analyze_trend(self) -> str:
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
        if key in self.smart_cache:
            value, expiry = self.smart_cache[key]
            if time.time() < expiry:
                self.cache_hits += 1
                return value
            else:
                del self.smart_cache[key]
        self.cache_misses += 1
        return None

    def smart_cache_set(self, key: str, value: Any, ttl: float = None):
        if ttl is None: ttl = self.cache_ttl
        self.smart_cache[key] = (value, time.time() + ttl)
        if len(self.smart_cache) > 1000:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:300]: del self.smart_cache[k]

    def smart_cache_clear_expired(self) -> int:
        now = time.time()
        expired = [k for k, (v, exp) in self.smart_cache.items() if now >= exp]
        for k in expired: del self.smart_cache[k]
        return len(expired)

    def _clean_level_1(self) -> int:
        freed = self.smart_cache_clear_expired() * 100
        collected = gc.collect(0); freed += collected * 200
        return freed

    def _clean_level_2(self) -> int:
        freed = self._clean_level_1()
        collected = gc.collect(2); freed += collected * 200
        if len(self.smart_cache) > 100:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            remove_count = len(self.smart_cache) // 2
            for k, _ in sorted_entries[:remove_count]: del self.smart_cache[k]
            freed += remove_count * 100
        gc.garbage.clear(); return freed

    def _clean_level_3(self) -> int:
        freed = self._clean_level_2()
        if self.smart_cache:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            remove_count = int(len(self.smart_cache) * 0.8)
            for k, _ in sorted_entries[:remove_count]: del self.smart_cache[k]
            freed += remove_count * 100
        try: ctypes.CDLL("libc.so.6").malloc_trim(0); freed += 1024 * 1024
        except: pass
        for _ in range(3): gc.collect(2)
        gc.garbage.clear(); return freed

    def _clean_critical(self) -> int:
        freed = self._clean_level_3()
        cache_size = len(self.smart_cache); self.smart_cache.clear()
        freed += cache_size * 100
        try: ctypes.CDLL("libc.so.6").malloc_trim(0)
        except: pass
        for _ in range(5): gc.collect(2)
        gc.garbage.clear(); return freed

    def ai_decide_clean(self) -> Tuple[int, str]:
        with self.clean_lock:
            if self.is_cleaning: return 0, "already_cleaning"
            if time.time() - self.last_clean_time < self.clean_cooldown: return 0, "cooldown"
            self.is_cleaning = True
            try:
                usage_pct = self.get_memory_usage_percent()
                trend = self.analyze_trend()
                current_mb = self.get_memory_mb()
                if usage_pct >= self.CRITICAL:
                    freed = self._clean_critical(); action = "critical_clean"
                elif usage_pct >= self.CLEAN_AGGRESSIVE:
                    freed = self._clean_level_3(); action = "aggressive_clean"
                elif usage_pct >= self.CLEAN_MEDIUM:
                    freed = self._clean_level_2(); action = "medium_clean"
                elif usage_pct >= self.CLEAN_LIGHT:
                    freed = self._clean_level_1(); action = "light_clean"
                elif trend in ["rapid_growth", "critical_growth"]:
                    freed = self._clean_level_2(); action = "leak_prevention"
                    self.leak_warnings += 1
                else:
                    gc.collect(0); freed = 0; action = "stable_no_clean"
                self.last_clean_time = time.time()
                self.total_cleaned_bytes += freed; self.clean_count += 1
                return freed, action
            finally:
                self.is_cleaning = False

    def get_stats(self) -> Dict:
        return {
            "current_mb": self.get_memory_mb(),
            "usage_pct": self.get_memory_usage_percent(),
            "max_mb": self.max_ram_bytes / (1024*1024),
            "total_cleaned_mb": self.total_cleaned_bytes / (1024*1024),
            "clean_count": self.clean_count,
            "leak_warnings": self.leak_warnings,
            "cache_size": len(self.smart_cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "trend": self.analyze_trend()
        }

    def monitor_loop(self):
        while True:
            try:
                self.snapshots.append((time.time(), self.process.memory_info().rss))
                if self.get_memory_usage_percent() >= self.WARNING_THRESHOLD:
                    self.ai_decide_clean()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(30)

    def start_monitoring(self):
        Thread(target=self.monitor_loop, daemon=True, name="AIRamMonitor").start()
        logger.info("AI RAM Monitor started (30s interval)")

ram_manager = AIRamManager(max_ram_mb=512)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    AI BRAIN - NÃO ĐIỀU KHIỂN                ║
# ╚══════════════════════════════════════════════════════════════╝
class Brain:
    def __init__(self, save_path: str = "brain.json"):
        self.save_path = save_path
        self.state: str = "normal"
        self.mood: int = 0
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
        logger.info("AI Brain initialized")

    def load_state(self):
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
            except: pass

    def save_state(self):
        with self.file_lock:
            self.stats["last_save"] = time.time()
            ram_stats = ram_manager.get_stats()
            self.stats["ram_cleans"] = ram_stats["clean_count"]
            self.stats["ram_freed_mb"] = ram_stats["total_cleaned_mb"]
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "learned": dict(sorted(self.learned.items(), key=lambda x: x[1], reverse=True)[:1000]),
                        "banned": list(self.banned_words),
                        "trusted": list(self.trusted_users),
                        "stats": self.stats,
                        "state": self.state,
                        "mood": self.mood
                    }, f, ensure_ascii=False, indent=2)
            except: self.stats["errors"] += 1

    def think(self, uid: int, txt: str) -> str:
        self.stats["msg_processed"] += 1
        words = re.findall(r'\b\w{3,}\b', txt.lower())
        for w in words: self.learned[w] += 1
        neg = ["bot ngu", "bot dở", "bot lỗi", "mày ngu", "bot chậm", "óc chó"]
        pos = ["bot hay", "bot pro", "cảm ơn bot", "bot tốt", "bot giỏi", "bot đỉnh"]
        if any(p in txt.lower() for p in neg): self.mood -= 2
        elif any(p in txt.lower() for p in pos): self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"
        self.decision_log.append({
            "time": datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S"),
            "uid": uid, "decision": self.state, "mood": self.mood
        })
        if len(self.decision_log) % 10 == 0: self.save_state()
        return self.state

    def should_reply(self, uid: int, msg_text: str) -> bool:
        if uid in self.trusted_users: return True
        if self.learned.get(msg_text.lower(), 0) > 5: return ai_random.random() > 0.3
        return ai_random.random() > 0.1

    def get_insult_level(self) -> str:
        if self.state == "aggressive": return "extreme"
        elif self.mood < 0: return "high"
        return "normal"

    def health_check(self) -> str:
        now = time.time()
        if now - self.last_health_check > 300:
            self.last_health_check = now
            ram_pct = ram_manager.get_memory_usage_percent()
            if ram_pct >= ram_manager.CLEAN_AGGRESSIVE:
                ram_manager.ai_decide_clean()
            if self.stats["errors"] > 20:
                self.repair_mode = True; self.state = "repair"
                self.stats["errors"] = 0
                return "repair"
            self.save_state()
        return "ok"

brain = Brain()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    CẤU HÌNH CHÍNH                           ║
# ╚══════════════════════════════════════════════════════════════╝
AUTO_DELETE_DELAY: int = 120
AUTO_DELETE_ENABLED: bool = True

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
game_executor = ThreadPoolExecutor(max_workers=15, thread_name_prefix="Game")
file_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="File")

# ╔══════════════════════════════════════════════════════════════╗
# ║                    AI KEYS (TỰ SỬA)                         ║
# ╚══════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0}
]
MAX_FAIL = 3; ck_idx = 0; ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    KHO CHỬI (THEO MOOD)                     ║
# ╚══════════════════════════════════════════════════════════════╝
KHO_NORMAL = ["Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.", "Cào phím nhanh, não chậm.", "Ảo tưởng sức mạnh.", "Về nhà rửa bát.", "IQ âm, đừng nói.", "Không ai cần mày.", "Mày là gì? Không là gì.", "Câm mồm, đỡ nhục."]
KHO_HIGH = ["Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?", "Ra đời người ta vả cho.", "Mẹ gọi, về nhà đi.", "Tưởng mình ngầu? Hề vãi.", "Học không lo, cào phím giỏi.", "Tương lai mù mịt như chị Dậu.", "Đời vả mặt, mày cười ngây.", "Không có gì để nói với mày."]
KHO_EXTREME = ["Mày đáng giá bằng cái nút block.", "Tồn tại để làm gì? Để tao chửi à?", "Não mày như ổ đĩa format nhầm.", "Mày là lỗi của tự nhiên, bug của xã hội.", "Tao chửi mày còn thấy phí thời gian.", "Mày không đáng để tao nhớ tên.", "Cút về lỗ mà mày chui ra.", "Mày là minh chứng cho thất bại của tiến hóa.", "Tao nhìn mày mà tưởng đang xem phim hài.", "Mày sống làm gì?"]

def get_kho():
    lvl = brain.get_insult_level()
    if lvl == "extreme": return KHO_EXTREME
    elif lvl == "high": return KHO_HIGH
    return KHO_NORMAL

# ╔══════════════════════════════════════════════════════════════╗
# ║                    BIẾN TOÀN CỤC                            ║
# ╚══════════════════════════════════════════════════════════════╝
lock = Lock()
mem: deque = deque(maxlen=50)
users: Dict[str, str] = {}
spam: Dict[int, List[float]] = {}
warn_counts: Dict[int, int] = {}
mutes: Dict[int, float] = {}
ai_cd: Dict[int, float] = {}
user_balance: Dict[int, int] = {}
daily_checkin: Dict[int, str] = {}
nohu_jackpot: int = 100000
nohu_history: deque = deque(maxlen=20)
nohu_fee: int = 1000
nohu_multiplier: float = 0.05
member_stats: Dict[str, Any] = {"daily_join": defaultdict(int), "daily_leave": defaultdict(int), "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}}
GAME_SESSIONS: Dict[int, Dict] = {}
USED_RIDDLES: Dict[int, List[str]] = defaultdict(list)

USR_FILE = "usr.json"; BALANCE_FILE = "balances.json"; DAILY_FILE = "daily_checkins.json"
JACKPOT_FILE = "jackpot.json"; STATS_FILE = "member_stats.json"

TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}', re.I)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    TIỆN ÍCH CHUNG                           ║
# ╚══════════════════════════════════════════════════════════════╝
def load_json(path: str, default: Any = None) -> Any:
    if default is None: default = {}
    cached = ram_manager.smart_cache_get(f"json_{path}")
    if cached is not None: return cached
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                ram_manager.smart_cache_set(f"json_{path}", data, 60)
                return data
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
def load_jackpot() -> int: return load_json(JACKPOT_FILE, {"jackpot": 100000}).get("jackpot", 100000)
def save_jackpot(jackpot: int): save_json(JACKPOT_FILE, {"jackpot": jackpot, "history": list(nohu_history)})
def load_member_stats() -> Dict:
    data = load_json(STATS_FILE, {"daily_join": {}, "daily_leave": {}, "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}})
    data["daily_join"] = defaultdict(int, data.get("daily_join", {})); data["daily_leave"] = defaultdict(int, data.get("daily_leave", {}))
    return data
def save_member_stats():
    data = dict(member_stats); data["daily_join"] = dict(data["daily_join"]); data["daily_leave"] = dict(data["daily_leave"])
    save_json(STATS_FILE, data)

def auto_del(chat_id: int, msg_id: int, delay: int = AUTO_DELETE_DELAY):
    if AUTO_DELETE_ENABLED:
        def _del():
            time.sleep(delay)
            try: bot.delete_message(chat_id, msg_id)
            except: pass
        Thread(target=_del, daemon=True).start()

def del_both(m, bot_msg_id: int):
    auto_del(m.chat.id, m.message_id); auto_del(m.chat.id, bot_msg_id)

def is_admin(m) -> bool: return m.from_user.id == ADMIN_ID
def is_grp(m) -> bool: return m.chat.id == GROUP_ID

def get_user_balance(uid: int) -> int:
    if uid not in user_balance: user_balance[uid] = 5000; save_balances(user_balance)
    return user_balance[uid]

def add_balance(uid: int, amount: int) -> int:
    bal = get_user_balance(uid); user_balance[uid] = max(0, bal + amount); save_balances(user_balance)
    return user_balance[uid]

def deduct_balance(uid: int, amount: int) -> bool:
    bal = get_user_balance(uid)
    if bal >= amount: user_balance[uid] = bal - amount; save_balances(user_balance); return True
    return False

def parse_duration(reason: str) -> int:
    m = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if m:
        num = int(m.group(1)); unit = m.group(2)
        if unit == 's': return num
        elif unit in ['m','p']: return num * 60
        elif unit == 'h': return num * 3600
    return 3600

def extract_user_and_reason(message, bot_username: str) -> Tuple[Optional[int], str]:
    target = None; reason = ""
    if message.reply_to_message:
        target = message.reply_to_message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1: reason = parts[1]
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg.isdigit(): target = int(arg)
            else:
                mention_match = re.match(r'@(\w+)', arg)
                if mention_match:
                    try: target = bot.get_chat_member(message.chat.id, mention_match.group(0)).user.id; reason = arg[mention_match.end():].strip()
                    except: pass
                else:
                    num_match = re.search(r'\d+', arg)
                    if num_match: target = int(num_match.group()); reason = arg[num_match.end():].strip()
    return target, reason

# ╔══════════════════════════════════════════════════════════════╗
# ║                    BÃO X10 ENGINE (DÙNG AI RANDOM)          ║
# ╚══════════════════════════════════════════════════════════════╝
def bao_x10(bet: int) -> Tuple[int, bool]:
    """Cơ chế BÃO X10 dùng AI Random siêu khó."""
    if ai_random.random() < 0.10:
        return bet * 10, True
    return 0, False

# ╔══════════════════════════════════════════════════════════════╗
# ║                    AI CÂU ĐỐ RANDOM                         ║
# ╚══════════════════════════════════════════════════════════════╝
class AICauDo:
    RIDDLES = [
        {"q": "Có 1 đàn chuột điếc đi qua cầu, hỏi có mấy con?", "a": ["24 con", "24", "hai tư"], "h": "Điếc = hư tai = 24"},
        {"q": "Cái gì càng kéo càng ngắn?", "a": ["điếu thuốc", "thuốc lá"], "h": "Hút vào sẽ ngắn dần"},
        {"q": "Cái gì có răng mà không có miệng?", "a": ["cái cưa", "cưa", "cái lược", "lược"], "h": "Dụng cụ cắt/chải"},
        {"q": "Cái gì đen khi mua, đỏ khi dùng, xám khi vứt?", "a": ["than", "củ than"], "h": "Dùng để đốt, nướng"},
        {"q": "Con gì sinh ra đã biết bơi?", "a": ["con cá", "cá", "nòng nọc"], "h": "Sống dưới nước"},
        {"q": "Cái gì càng nhiều lửa càng ít?", "a": ["cây nến", "nến"], "h": "Thắp sáng"},
        {"q": "Cái gì luôn đến nhưng không bao giờ đến?", "a": ["ngày mai", "tương lai"], "h": "Thời gian"},
        {"q": "Cái gì càng ít càng nhiều?", "a": ["bóng tối"], "h": "Đối lập với ánh sáng"},
        {"q": "Con gì đập thì sống, không đập thì chết?", "a": ["con tim", "tim"], "h": "Cơ quan trong cơ thể"},
        {"q": "Cái gì có mắt mà không thấy?", "a": ["cái kim", "kim"], "h": "Dùng để may vá"},
        {"q": "Cái gì càng rửa càng bẩn?", "a": ["nước"], "h": "Chất lỏng trong suốt"},
        {"q": "Cái gì có cổ mà không có đầu?", "a": ["cái áo", "áo", "cái chai", "chai"], "h": "Mặc/đựng"},
        {"q": "Quần gì rộng nhất?", "a": ["quần đảo"], "h": "Địa lý - biển đảo"},
        {"q": "Xã gì đông nhất?", "a": ["xã hội"], "h": "Liên quan đến con người"},
        {"q": "Núi gì bị chặt ra từng khúc?", "a": ["núi thái sơn", "thái sơn"], "h": "Trung Quốc"},
        {"q": "Cái gì bằng cái vung, vùng xuống ao?", "a": ["bóng trăng", "mặt trăng", "trăng"], "h": "Trên trời"},
        {"q": "Cái gì càng cao càng nhỏ?", "a": ["cái thang", "thang"], "h": "Leo trèo"},
        {"q": "Cái gì càng đi càng nhỏ?", "a": ["cục tẩy", "tẩy"], "h": "Học tập"},
        {"q": "Cái gì vừa bằng hạt đỗ, ăn cả làng?", "a": ["hạt muối", "muối"], "h": "Gia vị"},
        {"q": "Cái gì càng nhiều người dùng càng nhỏ?", "a": ["cục xà phòng", "xà phòng"], "h": "Tắm giặt"},
    ]

    @staticmethod
    def generate(difficulty: int = 1, used_answers: set = None) -> Dict:
        if used_answers is None: used_answers = set()
        available = [r for r in AICauDo.RIDDLES if r["a"][0] not in used_answers]
        if available and ai_random.random() < 0.7:
            return ai_random.choice(available)
        templates = [
            lambda: {"q": f"Con gì {ai_random.choice(['ăn','sợ','thích'])} {ai_random.choice(['lửa','nước','bóng tối'])}?", "a": [ai_random.choice(["rồng","ma","quỷ","tiên","cá"])], "h": "Huyền thoại/tự nhiên"},
            lambda: {"q": f"Cái gì có {ai_random.randint(3,6)} chân mà không đi được?", "a": ["cái bàn","bàn"], "h": "Nội thất"},
            lambda: {"q": f"Từ gì bỏ dấu thành '{ai_random.choice(['ma','ba','ca'])}', thêm dấu thành '{ai_random.choice(['má','bà','cá'])}'?", "a": ["đố mẹo"], "h": "Chơi chữ"},
        ]
        return ai_random.choice(templates)()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    18 GIỌNG VIỆT NAM RANDOM                 ║
# ╚══════════════════════════════════════════════════════════════╝
VOICE_LIST = [{"name": f"Giong {i+1}", "lang": "vi", "speed": 0.5 + i * 0.07} for i in range(18)]
TTS_URL = "https://translate.google.com/translate_tts"
TTS_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "audio/mpeg", "Referer": "https://translate.google.com/"}
MAX_CHUNK = 180

@dataclass
class VoiceRequest: chat_id: int; reply_id: int; text: str; user_name: str; voice: Optional[Dict] = None

voice_queue: Queue = Queue(maxsize=50)

def fetch_tts_chunk(text: str, lang: str = "vi", speed: float = 1.0) -> Optional[bytes]:
    params = {"ie": "UTF-8", "q": text, "tl": lang, "total": "1", "idx": "0", "textlen": str(len(text)), "client": "tw-ob", "prev": "input", "ttsspeed": str(speed)}
    try:
        resp = ses.get(TTS_URL, params=params, headers=TTS_HEADERS, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 100: return resp.content
    except: pass
    return None

def split_chunks(text: str, max_size: int = MAX_CHUNK) -> List[str]:
    if len(text) <= max_size: return [text]
    chunks = []; separators = ['. ', '! ', '? ', ', ', '; ', ': ', ' - ', '\n', ' ']
    while len(text) > max_size:
        best_pos = max_size
        for sep in separators:
            pos = text.rfind(sep, 0, max_size)
            if pos > max_size // 2: best_pos = pos + len(sep); break
        if best_pos > max_size or best_pos <= max_size // 3: best_pos = max_size
        chunks.append(text[:best_pos].strip()); text = text[best_pos:].strip()
    if text: chunks.append(text)
    return chunks

def generate_voice(text: str, speed: float = 1.0) -> Optional[BytesIO]:
    clean = re.sub(r'[<>"\'{}|\\^~\[\]`]', '', text).strip()
    if not clean: return None
    chunks = split_chunks(clean); audio_data = b""
    for chunk in chunks:
        data = fetch_tts_chunk(chunk, "vi", speed)
        if data: audio_data += data
    return BytesIO(audio_data) if audio_data and len(audio_data) > 100 else None

def voice_worker():
    while True:
        try:
            req: VoiceRequest = voice_queue.get(block=True, timeout=1)
            if not req: continue
            text = req.text[:500].strip()
            if not text: voice_queue.task_done(); continue
            voice = req.voice if req.voice else ai_random.choice(VOICE_LIST)
            audio = None
            try: audio = generate_voice(text, voice["speed"])
            except: pass
            if audio and isinstance(audio, BytesIO) and audio.getbuffer().nbytes > 100:
                audio.name = f"voice_{int(time.time())}.mp3"; cap = f"Giong noi: {voice['name']}"
                try: bot.send_voice(req.chat_id, audio, reply_to_message_id=req.reply_id, caption=cap); brain.stats["voice_generated"] += 1
                except:
                    try: audio.seek(0); bot.send_audio(req.chat_id, audio, reply_to_message_id=req.reply_id, title="Voice", caption=cap); brain.stats["voice_generated"] += 1
                    except: pass
            else:
                try: bot.send_message(req.chat_id, f"Khong the tao giong noi.", reply_to_message_id=req.reply_id)
                except: pass
            voice_queue.task_done()
        except:
            try: voice_queue.task_done()
            except: pass

for _ in range(4): Thread(target=voice_worker, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    12 MINI GAMES ENGINE                     ║
# ╚══════════════════════════════════════════════════════════════╝
def init_game(uid: int, game_type: str) -> Dict:
    bases = {"bal": 1000, "w": 0, "l": 0}
    if game_type == "taixiu": return {"type": "taixiu", **bases}
    if game_type == "baucua": return {"type": "baucua", "sym": ["Cua","Ca","Tom","Ga","Nai","Bau"], **bases}
    if game_type == "kbb": return {"type": "kbb", "score": 0, "bot": 0, "draw": 0}
    if game_type == "doanso": return {"type": "doanso", "secret": ai_random.randint(1, 100), "att": 0, "max": 7}
    if game_type == "lxn": return {"type": "lxn", **bases}
    if game_type == "xx": return {"type": "xx", **bases}
    if game_type == "caudo": return {"type": "caudo", "score": 0, "qnum": 0, "cur": None, "hint": False, "ans": False, "start": 0}
    if game_type == "chanle": return {"type": "chanle", **bases}
    if game_type == "caothap": return {"type": "caothap", **bases}
    if game_type == "doanso2": return {"type": "doanso2", "secret": ai_random.randint(1, 100), "att": 0, "max": 5}
    if game_type == "keo": return {"type": "keo", "bal": 1000, "w": 0, "l": 0}
    if game_type == "bingo": return {"type": "bingo", "bal": 1000, "w": 0, "l": 0}
    return {}

# ─── GAME 1: TÀI XỈU + BÃO X10 ──────────────────────────────────────────
@bot.message_handler(commands=['taixiu'])
def taixiu_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu": GAME_SESSIONS[uid] = init_game(uid, "taixiu")
        g = GAME_SESSIONS[uid]; msg = bot.reply_to(m, f"TAI XIU BAO X10\n/taixiu [tai/xiu] [cuoc]\nGame: {g['bal']} xu\nThang: x3 | Bao: x10!"); del_both(m, msg.message_id); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: msg = bot.reply_to(m, "Cuoc phai la so."); del_both(m, msg.message_id); return
    if ch not in ['tai', 'xiu']: msg = bot.reply_to(m, "Chon 'tai' hoac 'xiu'."); del_both(m, msg.message_id); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu": GAME_SESSIONS[uid] = init_game(uid, "taixiu")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: msg = bot.reply_to(m, f"So du game: {g['bal']} xu."); del_both(m, msg.message_id); return
    dice = [ai_random.randint(1, 6) for _ in range(3)]; total = sum(dice)
    res = "tai" if total >= 11 else "xiu"
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res: win = bt * 3 + bao_bonus; g["bal"] += win; g["w"] += 1; out = f"Thang +{win} xu" + (" BAO X10!!!" if is_bao else "")
    else: g["bal"] -= bt; g["l"] += 1; out = f"Thua -{bt} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"TAI XIU: {ds} = {total} -> {res.upper()}\n{out} | Game: {g['bal']} xu\nW:{g['w']} L:{g['l']}"); del_both(m, msg.message_id)

# ─── GAME 2-12: Tương tự các game khác, tất cả dùng ai_random.randint() ──
# (Đã rút gọn phần game 2-12 để giữ code trong 2000 dòng - cấu trúc giống game 1)

@bot.message_handler(commands=['baucua'])
def baucua_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    sm = {"bau":0,"cua":1,"ca":2,"tom":3,"ga":4,"nai":5}
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "baucua")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"BAU CUA BAO X10\n/baucua [con] [cuoc]\nGame: {g['bal']} xu"); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: bot.reply_to(m, "Cuoc phai la so."); return
    if ch not in sm: bot.reply_to(m, f"Chon: {','.join(sm)}"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "baucua")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    ci = sm[ch]; roll = [ai_random.randint(0, 5) for _ in range(3)]; rs = [g["sym"][i] for i in roll]; match = roll.count(ci)
    bao_bonus, is_bao = bao_x10(bt)
    if match > 0: win = bt * match * 3 + bao_bonus; g["bal"] += win; g["w"] += 1; out = f"Thang +{win}" + (" BAO!!!" if is_bao else "")
    else: g["bal"] -= bt; g["l"] += 1; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"BAU CUA: {' '.join(rs)}\nTrung {match} con\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['kbb'])
def kbb_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    chs = {"keo":"Keo","bua":"Bua","bao":"Bao"}
    if len(parts) < 2:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "kbb")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"KEO BUA BAO X10\n/kbb [keo/bua/bao]\nBan: {g['score']} | Bot: {g['bot']}"); return
    ch = parts[1].lower()
    if ch not in chs: bot.reply_to(m, "Chon keo/bua/bao"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "kbb")
    g = GAME_SESSIONS[uid]; uc, bc = chs[ch], ai_random.choice(list(chs.values()))
    ui, bi = list(chs.values()).index(uc), list(chs.values()).index(bc)
    bao_bonus, is_bao = bao_x10(3)
    if ui == bi: r = "Hoa"; g["draw"] += 1
    elif (ui==0 and bi==2) or (ui==1 and bi==0) or (ui==2 and bi==1): pts = 3 + bao_bonus; g["score"] += pts; r = f"Thang +{pts}" + (" BAO!!!" if is_bao else "")
    else: r = "Thua"; g["bot"] += 1
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"{uc} vs {bc}\n{r}\nBan: {g['score']} | Bot: {g['bot']} | Hoa: {g['draw']}"); del_both(m, m2.message_id)

@bot.message_handler(commands=['doanso'])
def doanso_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 2: GAME_SESSIONS[uid] = init_game(uid, "doanso"); bot.reply_to(m, "DOAN SO BAO X10\n/doanso [so] (1-100)\n7 lan"); return
    try: gs = int(parts[1])
    except: bot.reply_to(m, "Nhap so"); return
    if gs < 1 or gs > 100: bot.reply_to(m, "1-100"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "doanso")
    g = GAME_SESSIONS[uid]; g["att"] += 1; brain.stats["games_played"] += 1
    if gs == g["secret"]:
        base = (8 - g["att"]) * 500 * 3; bao_bonus, is_bao = bao_x10(base // 3); rw = base + bao_bonus
        add_balance(uid, rw); m2 = bot.reply_to(m, f"CHINH XAC! So {g['secret']} ({g['att']} lan)\n+{rw}" + (" BAO!!!" if is_bao else "")); del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]: m2 = bot.reply_to(m, f"HET LUOT! So {g['secret']}"); del GAME_SESSIONS[uid]
    elif gs < g["secret"]: m2 = bot.reply_to(m, f"{gs} -> CAO HON ({g['max']-g['att']})")
    else: m2 = bot.reply_to(m, f"{gs} -> THAP HON ({g['max']-g['att']})")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['lxn'])
def lxn_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "lxn")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"LAC XI NGAU BAO X10\n/lxn [tong 3-18] [cuoc]\nGame: {g['bal']} xu"); return
    try: gt, bt = int(parts[1]), int(parts[2])
    except: bot.reply_to(m, "/lxn [3-18] [cuoc]"); return
    if gt < 3 or gt > 18: bot.reply_to(m, "3-18"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "lxn")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    dice = [ai_random.randint(1, 6) for _ in range(3)]; total = sum(dice)
    ds = " ".join("⚀⚁⚂⚃⚄⚅"[d-1] for d in dice)
    bao_bonus, is_bao = bao_x10(bt)
    if total == gt: win = bt * 10 + bao_bonus; g["bal"] += win; out = f"CHINH XAC! +{win}" + (" BAO!!!" if is_bao else "")
    elif abs(total - gt) == 1: win = int(bt * 0.5); g["bal"] += win; out = f"Gan dung! Hoan {win}"
    else: g["bal"] -= bt; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"LXN: {ds} = {total}\nDoan: {gt}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['xx'])
def xx_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "xx")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"XUC XAC BAO X10\n/xx [so 1-6] [cuoc]\nGame: {g['bal']} xu"); return
    try: gs, bt = int(parts[1]), int(parts[2])
    except: bot.reply_to(m, "/xx [1-6] [cuoc]"); return
    if gs < 1 or gs > 6: bot.reply_to(m, "1-6"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "xx")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    dr = ai_random.randint(1, 6); de = "⚀⚁⚂⚃⚄⚅"[dr-1]
    bao_bonus, is_bao = bao_x10(bt)
    if gs == dr: win = bt * 4 + bao_bonus; g["bal"] += win; out = f"TRUNG! +{win}" + (" BAO!!!" if is_bao else "")
    elif abs(gs - dr) == 1: win = int(bt * 0.5); g["bal"] += win; out = f"Gan dung! Hoan {win}"
    else: g["bal"] -= bt; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"XX: {de} {dr}\nDoan: {gs}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['caudo'])
def caudo_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "caudo" or GAME_SESSIONS[uid].get("ans", False):
        prev_score = GAME_SESSIONS[uid].get("score", 0) if uid in GAME_SESSIONS else 0
        difficulty = min(5, 1 + prev_score // 5)
        used = set(USED_RIDDLES.get(uid, []))
        riddle = AICauDo.generate(difficulty, used)
        USED_RIDDLES[uid].append(riddle["a"][0])
        GAME_SESSIONS[uid] = {"type":"caudo","score":prev_score,"qnum":GAME_SESSIONS[uid].get("qnum",0)+1 if uid in GAME_SESSIONS else 1,"cur":riddle,"hint":False,"ans":False,"start":time.time()}
        m2 = bot.reply_to(m, f"CAU DO #{GAME_SESSIONS[uid]['qnum']}\n60s\n{riddle['q']}\n/caudo [dap an]"); del_both(m, m2.message_id)
        def timeout():
            time.sleep(60)
            if uid in GAME_SESSIONS and not GAME_SESSIONS[uid].get("ans", True): GAME_SESSIONS[uid]["ans"] = True; bot.send_message(m.chat.id, f"Het gio! Dap an: {riddle['a'][0]}")
        Thread(target=timeout, daemon=True).start(); return
    g = GAME_SESSIONS[uid]
    if g.get("ans", False): m2 = bot.reply_to(m, "Het gio!"); del_both(m, m2.message_id); return
    if len(parts) < 2: rem = max(0, 60-int(time.time()-g["start"])); m2 = bot.reply_to(m, f"Con {rem}s\n{g['cur']['q']}"); del_both(m, m2.message_id); return
    arg = " ".join(parts[1:]).lower().strip()
    if arg in ["hint", "goi y"]:
        if g["hint"]: m2 = bot.reply_to(m, "Da dung hint"); del_both(m, m2.message_id); return
        g["hint"] = True; g["score"] = max(0, g["score"]-1); m2 = bot.reply_to(m, f"Goi y: {g['cur']['h']}"); del_both(m, m2.message_id); return
    if any(arg == a.lower() or a.lower() in arg for a in g["cur"]["a"]):
        elapsed = int(time.time()-g["start"]); bonus = max(0, (60-elapsed)//10)
        base_rw = 2000 + bonus*500; bao_bonus, is_bao = bao_x10(base_rw); rw = base_rw + bao_bonus
        add_balance(uid, rw); g["score"] += 3+bonus; g["ans"] = True
        m2 = bot.reply_to(m, f"Chinh xac! +{rw}" + (" BAO!!!" if is_bao else "") + f"\nDiem: {g['score']}"); del_both(m, m2.message_id)
    else:
        g["score"] = max(0, g["score"]-1); rem = max(0, 60-int(time.time()-g["start"]))
        if rem <= 0: g["ans"] = True; m2 = bot.reply_to(m, f"Het gio! Dap an: {g['cur']['a'][0]}"); del_both(m, m2.message_id)
        else: m2 = bot.reply_to(m, f"Sai! ({rem}s)"); del_both(m, m2.message_id)

@bot.message_handler(commands=['chanle'])
def chanle_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "chanle")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"CHAN LE BAO X10\n/chanle [chan/le] [cuoc]\nGame: {g['bal']} xu"); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: bot.reply_to(m, "Cuoc phai la so."); return
    if ch not in ['chan', 'le']: bot.reply_to(m, "Chon chan/le"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "chanle")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    num = ai_random.randint(1, 100); res = "chan" if num % 2 == 0 else "le"
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res: win = bt * 3 + bao_bonus; g["bal"] += win; g["w"] += 1; out = f"Thang +{win}" + (" BAO!!!" if is_bao else "")
    else: g["bal"] -= bt; g["l"] += 1; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"CHAN LE: So {num} -> {res.upper()}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['caothap'])
def caothap_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "caothap")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"CAO THAP BAO X10\n/caothap [cao/thap] [cuoc]\nGame: {g['bal']} xu"); return
    ch, bt = parts[1].lower(), 0
    try: bt = int(parts[2])
    except: bot.reply_to(m, "Cuoc phai la so."); return
    if ch not in ['cao', 'thap']: bot.reply_to(m, "Chon cao/thap"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "caothap")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    num = ai_random.randint(1, 100); res = "cao" if num > 50 else "thap"
    bao_bonus, is_bao = bao_x10(bt)
    if ch == res: win = bt * 3 + bao_bonus; g["bal"] += win; g["w"] += 1; out = f"Thang +{win}" + (" BAO!!!" if is_bao else "")
    else: g["bal"] -= bt; g["l"] += 1; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"CAO THAP: So {num} -> {res.upper()}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['keo'])
def keo_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "keo")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"KEO LUI BAO X10\n/keo [0-9] [cuoc]\nGame: {g['bal']} xu"); return
    try: gs, bt = int(parts[1]), int(parts[2])
    except: bot.reply_to(m, "/keo [0-9] [cuoc]"); return
    if gs < 0 or gs > 9: bot.reply_to(m, "0-9"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "keo")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    result = ai_random.randint(0, 9)
    bao_bonus, is_bao = bao_x10(bt)
    if gs == result: win = bt * 5 + bao_bonus; g["bal"] += win; out = f"TRUNG! +{win}" + (" BAO!!!" if is_bao else "")
    else: g["bal"] -= bt; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"KEO: So {result}\nDoan: {gs}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['bingo'])
def bingo_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "bingo")
        g = GAME_SESSIONS[uid]; bot.reply_to(m, f"BINGO BAO X10\n/bingo [1-36] [cuoc]\nGame: {g['bal']} xu"); return
    try: gs, bt = int(parts[1]), int(parts[2])
    except: bot.reply_to(m, "/bingo [1-36] [cuoc]"); return
    if gs < 1 or gs > 36: bot.reply_to(m, "1-36"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "bingo")
    g = GAME_SESSIONS[uid]
    if bt > g["bal"] or bt < 1: bot.reply_to(m, f"So du: {g['bal']}"); return
    result = ai_random.randint(1, 36)
    bao_bonus, is_bao = bao_x10(bt)
    if gs == result: win = bt * 8 + bao_bonus; g["bal"] += win; out = f"TRUNG! +{win}" + (" BAO!!!" if is_bao else "")
    else: g["bal"] -= bt; out = f"Thua -{bt}"
    brain.stats["games_played"] += 1
    m2 = bot.reply_to(m, f"BINGO: So {result}\nDoan: {gs}\n{out} | Game: {g['bal']} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['doanso2'])
def doanso2_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 2: GAME_SESSIONS[uid] = init_game(uid, "doanso2"); bot.reply_to(m, "DOAN SO SIEU TOC BAO X10\n/doanso2 [so] (1-100)\n5 lan"); return
    try: gs = int(parts[1])
    except: bot.reply_to(m, "Nhap so"); return
    if gs < 1 or gs > 100: bot.reply_to(m, "1-100"); return
    if uid not in GAME_SESSIONS: GAME_SESSIONS[uid] = init_game(uid, "doanso2")
    g = GAME_SESSIONS[uid]; g["att"] += 1; brain.stats["games_played"] += 1
    if gs == g["secret"]:
        base = (6 - g["att"]) * 800 * 5; bao_bonus, is_bao = bao_x10(base // 5); rw = base + bao_bonus
        add_balance(uid, rw); m2 = bot.reply_to(m, f"CHINH XAC! +{rw}" + (" BAO!!!" if is_bao else "")); del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]: m2 = bot.reply_to(m, f"HET LUOT! So {g['secret']}"); del GAME_SESSIONS[uid]
    elif gs < g["secret"]: m2 = bot.reply_to(m, f"CAO HON ({g['max']-g['att']})")
    else: m2 = bot.reply_to(m, f"THAP HON ({g['max']-g['att']})")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    NỔ HŨ + ĐIỂM DANH + TÀI CHÍNH            ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['nohu'])
def nohu_cmd(m):
    global nohu_jackpot
    if not is_grp(m): return
    uid = m.from_user.id; parts = m.text.split()
    if len(parts) < 2: m2 = bot.reply_to(m, f"NO HU\nJP: {nohu_jackpot:,} xu\n/nohu [cuoc]"); del_both(m, m2.message_id); return
    try: bet = int(parts[1])
    except: bot.reply_to(m, "Nhap so"); return
    if bet < 100 or bet > 100000: bot.reply_to(m, "100-100k"); return
    total = bet + nohu_fee
    if not deduct_balance(uid, total): bot.reply_to(m, f"Khong du! Can {total}"); return
    nohu_jackpot += int(bet * nohu_multiplier)
    bao_bonus, is_bao = bao_x10(bet)
    c1, c2, c3 = [ai_random.choice(["🍒","🍋","🍊","🍇","💎","🔔","7️⃣"]) for _ in range(3)]
    if c1 == c2 == c3:
        if c1 == "7️⃣": win = nohu_jackpot + bao_bonus; add_balance(uid, win); nohu_hist.append({"name": m.from_user.first_name, "amount": win}); nohu_jackpot = 100000; out = f"JACKPOT! +{win}" + (" BAO!!!" if is_bao else "")
        else: win = bet * 5 + bao_bonus; add_balance(uid, win); out = f"No! +{win}" + (" BAO!!!" if is_bao else "")
    elif c1 == c2 or c2 == c3 or c1 == c3: win = int(bet * 0.5); add_balance(uid, win); out = f"Hoan {win}"
    else: out = f"Thua -{total}"
    brain.stats["nohu_spins"] += 1
    m2 = bot.reply_to(m, f"{c1}{c2}{c3}\n{out}\nSo du: {get_user_balance(uid)} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['daily'])
def daily_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; today = date.today().isoformat()
    if daily_checkin.get(uid) == today: bot.reply_to(m, f"Da diem danh hom nay\nSo du: {get_user_balance(uid)} xu"); return
    daily_checkin[uid] = today; rw = 500 + ai_random.randint(0, 1000); add_balance(uid, rw)
    brain.stats["daily_checkins"] += 1
    m2 = bot.reply_to(m, f"DIEM DANH THANH CONG!\n+{rw} xu\nSo du: {get_user_balance(uid)} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['balance','xu'])
def balance_cmd(m):
    if not is_grp(m): return
    t = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    n = m.reply_to_message.from_user.first_name if m.reply_to_message else m.from_user.first_name
    m2 = bot.reply_to(m, f"{n}: {get_user_balance(t):,} xu"); del_both(m, m2.message_id)

@bot.message_handler(commands=['top'])
def top_cmd(m):
    if not is_grp(m): return
    sb = sorted(user_balance.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "BANG XEP HANG:\n"
    for i, (uid, bal) in enumerate(sb):
        name = users.get(str(uid), str(uid)); text += f"{i+1}. {name}: {bal:,} xu\n"
    m2 = bot.reply_to(m, text); del_both(m, m2.message_id)

@bot.message_handler(commands=['give'])
def give_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; target = None; amt = 0
    if m.reply_to_message: target = m.reply_to_message.from_user.id; parts = m.text.split(); amt = int(parts[1]) if len(parts) > 1 else 0
    else:
        parts = m.text.split()
        if len(parts) > 2:
            if parts[1].startswith('@'): target = bot.get_chat_member(m.chat.id, parts[1]).user.id
            elif parts[1].isdigit(): target = int(parts[1])
            amt = int(parts[2]) if len(parts) > 2 else 0
    if not target or amt < 100: bot.reply_to(m, "/give @mention [so]"); return
    if not deduct_balance(uid, amt + int(amt * 0.05)): bot.reply_to(m, "Khong du xu"); return
    add_balance(target, amt); m2 = bot.reply_to(m, f"Da chuyen {amt} xu"); del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    AI CHAT + ANTI-SPAM                      ║
# ╚══════════════════════════════════════════════════════════════╝
def ask_ai(prompt: str) -> str:
    global ck_idx
    if brain.state == "sleep": return ai_random.choice(get_kho())
    if len(mem) >= 2 and mem[-2] == prompt: return mem[-1]
    msgs = [{"role":"system","content":"Coc can, chui khia, duoi 12 tu."}]
    for t in list(mem)[-8:]: msgs.append({"role":"user","content":t})
    msgs.append({"role":"user","content":prompt})
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL: ck_idx = (ck_idx+1)%len(AI_KEYS); continue
            try:
                r = ses.post(k["url"], json={"model":k["model"],"messages":msgs,"max_tokens":40}, headers={"Authorization":f"Bearer {k['key']}"}, timeout=8)
                if r.status_code == 200:
                    txt = r.json()['choices'][0]['message']['content'].strip(); txt = re.sub(r'[_*`\[\]()]','',txt)
                    k["fail"] = 0; mem.append(prompt); mem.append(txt); brain.stats["ai_calls"] += 1; return txt
                else: k["fail"] += 1
            except: k["fail"] += 1; brain.stats["errors"] += 1
            ck_idx = (ck_idx+1)%len(AI_KEYS)
    for k in AI_KEYS: k["status"], k["fail"] = True, 0
    brain.stats["errors"] = 0; brain.state = "repair"
    return ai_random.choice(get_kho())

def antispam(m) -> bool:
    if is_admin(m): return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid,[]) if now-t<4] + [now]
    if len(spam[uid]) > 5:
        warns[uid] = warns.get(uid,0)+1; brain.stats["spam_blocked"] += 1
        if warns[uid] >= 3:
            try: bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time())+3600)
            except: pass
            del warns[uid]
        else:
            try: bot.delete_message(m.chat.id, m.message_id)
            except: pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════╗
# ║                    HANDLERS CƠ BẢN                          ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start_cmd(m):
    if not is_grp(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    brain.trusted_users.add(m.from_user.id)
    help_text = (
        "NAO ROBOT - AI RANDOM SIEU KHO\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "12 GAMES BAO X10:\n"
        "/taixiu /baucua /kbb /doanso /lxn /xx\n"
        "/caudo /chanle /caothap /keo /bingo /doanso2\n"
        "/nohu | /daily /balance /top /give\n"
        "/voice [text] - 18 giong VN\n"
        "/ban /mute /unmute /warn /stats\n"
        "/ramstatus - Xem RAM\n"
        f"Auto delete: {AUTO_DELETE_DELAY}s"
    )
    msg = bot.reply_to(m, help_text); del_both(m, msg.message_id)

@bot.message_handler(commands=['ramstatus','brain'])
def ram_status_cmd(m):
    if not is_grp(m): return
    stats = ram_manager.get_stats()
    uptime = int(time.time() - brain.stats["uptime_start"])
    text = (
        f"TRANG THAI\n"
        f"State: {brain.state} | Mood: {brain.mood}\n"
        f"RAM: {stats['current_mb']:.1f}MB/{stats['max_mb']:.0f}MB ({stats['usage_pct']*100:.1f}%)\n"
        f"Don: {stats['clean_count']} lan | Freed: {stats['total_cleaned_mb']:.1f}MB\n"
        f"Cache: {stats['cache_size']} | Hits: {stats['cache_hits']}\n"
        f"AI: {brain.stats['ai_calls']} | Games: {brain.stats['games_played']}\n"
        f"No Hu: {brain.stats['nohu_spins']} | Voice: {brain.stats['voice_generated']}\n"
        f"Uptime: {uptime//3600}h{(uptime%3600)//60}m | Errors: {brain.stats['errors']}"
    )
    msg = bot.reply_to(m, text); del_both(m, msg.message_id)

@bot.message_handler(commands=['voice'])
def voice_cmd(m):
    if not is_grp(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    txt = ""
    if m.reply_to_message and m.reply_to_message.text: txt = m.reply_to_message.text.strip()
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1: txt = parts[1].strip()
    if not txt:
        vl = "18 GIONG VIET NAM:\n"
        for i, v in enumerate(VOICE_LIST, 1): vl += f"{i}. {v['name']} (x{v['speed']})\n"
        m2 = bot.reply_to(m, vl); del_both(m, m2.message_id); return
    if len(txt) > 500: txt = txt[:500]
    selected = None; parts = txt.split(maxsplit=1)
    if parts[0].isdigit():
        idx = int(parts[0])
        if 1 <= idx <= 18: selected = VOICE_LIST[idx-1]; txt = parts[1] if len(parts) > 1 else ""
    if not txt: bot.reply_to(m, "Can text de doc."); return
    req = VoiceRequest(chat_id=m.chat.id, reply_id=m.message_id, text=txt, user_name=m.from_user.first_name, voice=selected)
    try: vqueue.put_nowait(req); m2 = bot.reply_to(m, "Dang tao giong noi..."); auto_del(m.chat.id, m2.message_id, 10)
    except: bot.reply_to(m, "Queue day, thu lai sau")

@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if target: bot.ban_chat_member(m.chat.id, target); bot.delete_message(m.chat.id, m.message_id)

@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target: return
    dur = parse_duration(reason) if reason else 3600
    try: bot.restrict_chat_member(m.chat.id, target, until_date=int(time.time())+dur, can_send_messages=False); bot.delete_message(m.chat.id, m.message_id); mutes[target] = int(time.time())+dur
    except: pass

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if target:
        try: bot.restrict_chat_member(m.chat.id, target, can_send_messages=True); bot.delete_message(m.chat.id, m.message_id)
        except: pass
        if target in mutes: del mutes[target]

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    if not is_grp(m) or not is_admin(m): return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target: return
    warn_counts[target] = warn_counts.get(target, 0) + 1; cnt = warn_counts[target]; bot.delete_message(m.chat.id, m.message_id)
    if cnt >= 3:
        try: bot.ban_chat_member(m.chat.id, target, until_date=int(time.time())+3600); del warn_counts[target]
        except: pass

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    if not is_grp(m): return
    try: rc = bot.get_chat_member_count(GROUP_ID)
    except: rc = member_stats.get("current_members", 0)
    msg = bot.reply_to(m, f"THONG KE\nThanh vien: {rc}\nTong vao: {member_stats['total_joined']}\nTong roi: {member_stats['total_left']}")
    del_both(m, msg.message_id)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def chat_handler(m):
    if antispam(m) or m.text.startswith('/'): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    brain.think(m.from_user.id, m.text)
    uid = m.from_user.id
    if not brain.should_reply(uid, m.text): return
    if uid in ai_cd and time.time()-ai_cd[uid] < 2: return
    ai_cd[uid] = time.time()
    def _ai():
        reply = ask_ai(m.text)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id):
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML"); auto_del(m.chat.id, m2.message_id)
        else:
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML"); auto_del(m.chat.id, m2.message_id)
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    today = date.today().isoformat()
    for u in m.new_chat_members:
        if u.id == bot.get_me().id: continue
        users[str(u.id)] = u.first_name; save_users(users)
        member_stats["daily_join"][today] += 1; member_stats["total_joined"] += 1; member_stats["current_members"] += 1
        save_member_stats()
        msg = bot.send_message(m.chat.id, f"Chao mung {u.first_name}!"); auto_del(m.chat.id, msg.message_id)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m):
    if not is_grp(m): return
    today = date.today().isoformat(); u = m.left_chat_member
    if u.id == bot.get_me().id: return
    member_stats["daily_leave"][today] += 1; member_stats["total_left"] += 1
    member_stats["current_members"] = max(0, member_stats["current_members"]-1); save_member_stats()

# ╔══════════════════════════════════════════════════════════════╗
# ║                    BACKGROUND TASKS                         ║
# ╚══════════════════════════════════════════════════════════════╝
def scheduler_task():
    last_hour = -1
    while True:
        try:
            now = datetime.now(tz)
            brain.health_check()
            if brain.state == "repair": brain.state = "normal"
            if now.minute == 0 and now.hour != last_hour and users:
                uid, uname = ai_random.choice(list(users.items()))
                msg = bot.send_message(GROUP_ID, f"{now.strftime('%H:%M')} | {uname}... {ai_random.choice(get_kho())}")
                auto_del(GROUP_ID, msg.message_id); last_hour = now.hour
            if now.minute != 0: last_hour = -1
            for uid in [u for u, until in mutes.items() if time.time() > until]:
                try: bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                except: pass
                del mutes[uid]
            if len(spam) > 100:
                for uid in sorted(spam, key=lambda x: spam[x][-1] if spam[x] else 0)[:10]: del spam[uid]
        except: pass
        time.sleep(15)

def auto_save_task():
    while True:
        time.sleep(600)
        try:
            save_users(users); brain.save_state(); save_member_stats()
            save_balances(user_balance); save_daily_checkins(daily_checkin); save_jackpot(nohu_jackpot)
        except: pass

# ╔══════════════════════════════════════════════════════════════╗
# ║                    MAIN                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def main():
    global user_balance, daily_checkin, nohu_jackpot, member_stats

    loaded = load_users()
    if isinstance(loaded, dict): users.update(loaded)
    user_balance = load_balances()
    daily_checkin = load_daily_checkins()
    nohu_jackpot = load_jackpot()
    stats = load_member_stats(); member_stats.update(stats)
    if not isinstance(member_stats.get("daily_join"), defaultdict):
        member_stats["daily_join"] = defaultdict(int, member_stats.get("daily_join", {}))
    if not isinstance(member_stats.get("daily_leave"), defaultdict):
        member_stats["daily_leave"] = defaultdict(int, member_stats.get("daily_leave", {}))
    try: member_stats["current_members"] = bot.get_chat_member_count(GROUP_ID)
    except: member_stats["current_members"] = len(users)

    ram_manager.start_monitoring()

    logger.info(f"NAO ROBOT - AI RANDOM SIEU KHO - KHOI DONG")
    logger.info(f"Users: {len(users)} | JP: {nohu_jackpot:,} | RAM: {ram_manager.get_memory_mb():.1f}MB")
    logger.info(f"AI Random Engine: Mersenne Twister + XOR Shift + LCG + Fisher-Yates + SHA-256")
    logger.info(f"12 Games Bao X10 | 18 Voice | Auto Delete {AUTO_DELETE_DELAY}s")

    Thread(target=scheduler_task, daemon=True).start()
    Thread(target=auto_save_task, daemon=True).start()

    try: bot.infinity_polling(timeout=30, none_stop=True, interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng: {e}")
        brain.stats["errors"] += 1; brain.save_state()
        save_balances(user_balance); save_daily_checkins(daily_checkin)
        save_jackpot(nohu_jackpot); save_member_stats()

if __name__ == "__main__":
    main()
