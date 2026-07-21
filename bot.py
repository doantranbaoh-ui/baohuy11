#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NAO ROBOT V8.0 - QUẢN LÝ NHÓM TOÀN DIỆN BẰNG AI
# Tính năng: AI Chat thông minh, Quản lý nhóm đầy đủ, Điểm danh/balance,
#            Chống spam/link, Tự động dọn RAM, API-first với Local fallback

import sys, io, os, json, time, random, re, html, logging, traceback, hashlib
import urllib.parse, gc, ctypes, psutil, weakref, signal, base64, tempfile
import math, statistics, itertools, threading, subprocess, shutil, zipfile
from threading import Thread, Lock, Timer, Event, Semaphore
from datetime import datetime, timedelta, date
from collections import deque, defaultdict, OrderedDict, Counter
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from queue import Queue, PriorityQueue, Empty, Full
from dataclasses import dataclass, field
from io import StringIO, BytesIO
from pathlib import Path

# ─── CẤU HÌNH LOGGING ────────────────────────────────────────────────────────
from logging.handlers import RotatingFileHandler
os.makedirs("logs", exist_ok=True)
log_handler = RotatingFileHandler(
    "logs/nao_robot.log", maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
)
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
    logger.info("Keep-alive da khoi dong")
except ImportError:
    logger.warning("keep_alive.py khong tim thay")

import telebot
from telebot import types, util
import requests
import pytz

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    API CLIENT - KẾT NỐI ADMIN API                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class APIClient:
    BASE_URL = os.getenv("API_URL", "http://localhost:5000")
    API_TOKEN = os.getenv("API_TOKEN", "admin-token-1")
    TIMEOUT = 3
    RETRY_MAX = 2
    CACHE_TTL = 30
    OFFLINE_MODE = False
    
    _cache: Dict[str, Any] = {}
    _cache_time: Dict[str, float] = {}
    _lock = threading.Lock()
    
    @classmethod
    def _headers(cls) -> Dict:
        return {
            "Authorization": f"Bearer {cls.API_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "NaoRobot/8.0"
        }
    
    @classmethod
    def _request(cls, method: str, endpoint: str, json_data: Dict = None, params: Dict = None) -> Tuple[Optional[Dict], bool]:
        if cls.OFFLINE_MODE:
            return None, False
        
        url = f"{cls.BASE_URL}{endpoint}"
        for attempt in range(cls.RETRY_MAX + 1):
            try:
                if method == "GET":
                    r = requests.get(url, headers=cls._headers(), params=params, timeout=cls.TIMEOUT)
                elif method == "POST":
                    r = requests.post(url, headers=cls._headers(), json=json_data, timeout=cls.TIMEOUT)
                elif method == "PUT":
                    r = requests.put(url, headers=cls._headers(), json=json_data, timeout=cls.TIMEOUT)
                elif method == "DELETE":
                    r = requests.delete(url, headers=cls._headers(), timeout=cls.TIMEOUT)
                else:
                    return None, False
                
                if r.status_code == 200:
                    return r.json(), True
                elif r.status_code == 503:
                    cls.OFFLINE_MODE = True
                    logger.warning("API server khong kha dung, chuyen sang offline mode")
                    return None, False
                else:
                    logger.warning(f"API {method} {endpoint} that bai: {r.status_code}")
            except requests.exceptions.ConnectionError:
                if attempt == cls.RETRY_MAX:
                    cls.OFFLINE_MODE = True
                    logger.warning("Mat ket noi API, chuyen sang offline mode")
            except Exception as e:
                logger.error(f"Loi request API: {str(e)[:100]}")
            
            if attempt < cls.RETRY_MAX:
                time.sleep(0.5 * (attempt + 1))
        
        return None, False
    
    @classmethod
    def _get_cached(cls, key: str) -> Optional[Any]:
        with cls._lock:
            if key in cls._cache and time.time() - cls._cache_time.get(key, 0) < cls.CACHE_TTL:
                return cls._cache[key]
        return None
    
    @classmethod
    def _set_cache(cls, key: str, value: Any):
        with cls._lock:
            cls._cache[key] = value
            cls._cache_time[key] = time.time()
    
    @classmethod
    def get_balance(cls, uid: int) -> Optional[int]:
        cached = cls._get_cached(f"bal_{uid}")
        if cached is not None:
            return cached
        
        data, success = cls._request("GET", f"/api/balance/{uid}")
        if success and data:
            bal = data.get("balance", data.get("data", {}).get("balance"))
            if bal is not None:
                cls._set_cache(f"bal_{uid}", bal)
                return bal
        
        return None
    
    @classmethod
    def add_balance(cls, uid: int, amount: int, reason: str = "daily") -> Optional[int]:
        data, success = cls._request("POST", "/api/balance/add", {
            "uid": uid, "amount": amount, "reason": reason
        })
        if success and data:
            new_bal = data.get("new_balance", data.get("data", {}).get("new_balance"))
            if new_bal is not None:
                cls._set_cache(f"bal_{uid}", new_bal)
                return new_bal
        return None
    
    @classmethod
    def get_top_balances(cls, limit: int = 10) -> Optional[List[Dict]]:
        data, success = cls._request("GET", "/api/balance/top", params={"limit": limit})
        if success and data:
            return data.get("data", data.get("top", []))
        return None
    
    @classmethod
    def create_user(cls, uid: int, name: str) -> bool:
        _, success = cls._request("POST", "/api/user", {
            "uid": uid, "name": name, "initial_balance": 5000
        })
        return success
    
    @classmethod
    def get_all_users(cls) -> Optional[Dict[int, str]]:
        cached = cls._get_cached("all_users")
        if cached is not None:
            return cached
        
        data, success = cls._request("GET", "/api/users")
        if success and data:
            users = data.get("data", data.get("users", {}))
            result = {int(k): v for k, v in users.items()}
            cls._set_cache("all_users", result)
            return result
        return None
    
    @classmethod
    def check_daily(cls, uid: int) -> Optional[Dict]:
        data, success = cls._request("GET", f"/api/daily/check/{uid}")
        if success and data:
            return data.get("data", data)
        return None
    
    @classmethod
    def claim_daily(cls, uid: int) -> Optional[Dict]:
        data, success = cls._request("POST", "/api/daily/claim", {"uid": uid})
        if success and data:
            return data.get("data", data)
        return None
    
    @classmethod
    def health_check(cls) -> bool:
        data, success = cls._request("GET", "/api/health")
        if success:
            cls.OFFLINE_MODE = False
            return True
        cls.OFFLINE_MODE = True
        return False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               LOCAL STORAGE - FALLBACK KHI API OFFLINE                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class LocalStorage:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.data_dir = "local_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self._cache: Dict[str, Any] = {}
        self._file_lock = threading.Lock()
    
    def _path(self, name: str) -> str:
        return os.path.join(self.data_dir, f"{name}.json")
    
    def load(self, name: str, default: Any = None) -> Any:
        if name in self._cache:
            return self._cache[name]
        path = self._path(name)
        if os.path.exists(path):
            try:
                with self._file_lock:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._cache[name] = data
                        return data
            except:
                pass
        return default if default is not None else {}
    
    def save(self, name: str, data: Any):
        self._cache[name] = data
        path = self._path(name)
        try:
            with self._file_lock:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"LocalStorage save error: {e}")

local_store = LocalStorage()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               HYBRID USER MANAGER                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridUserManager:
    @staticmethod
    def get_all_users() -> Dict[int, str]:
        api_users = APIClient.get_all_users()
        if api_users:
            return api_users
        return local_store.load("users", {})
    
    @staticmethod
    def get_user(uid: int) -> Optional[str]:
        users = HybridUserManager.get_all_users()
        return users.get(uid, users.get(str(uid)))
    
    @staticmethod
    def set_user(uid: int, name: str):
        APIClient.create_user(uid, name)
        users = local_store.load("users", {})
        users[str(uid)] = name
        local_store.save("users", users)
    
    @staticmethod
    def get_user_count() -> int:
        return len(HybridUserManager.get_all_users())

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               HYBRID DAILY MANAGER                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridDailyManager:
    @staticmethod
    def check(uid: int) -> bool:
        api_result = APIClient.check_daily(uid)
        if api_result is not None:
            return api_result.get("claimed", False)
        daily = local_store.load("daily", {})
        today = date.today().isoformat()
        return daily.get(str(uid)) == today
    
    @staticmethod
    def claim(uid: int) -> int:
        today = date.today().isoformat()
        api_result = APIClient.claim_daily(uid)
        if api_result is not None:
            return api_result.get("reward", api_result.get("amount", 500))
        
        daily = local_store.load("daily", {})
        if daily.get(str(uid)) == today:
            return 0
        
        daily[str(uid)] = today
        local_store.save("daily", daily)
        reward = 500 + random.randint(0, 1000)
        HybridBalanceManager.add_bal(uid, reward, "daily")
        return reward

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               HYBRID BALANCE MANAGER                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridBalanceManager:
    @staticmethod
    def get_bal(uid: int) -> int:
        bal = APIClient.get_balance(uid)
        if bal is not None:
            return bal
        local_balances = local_store.load("balances", {})
        return local_balances.get(str(uid), local_balances.get(uid, 5000))
    
    @staticmethod
    def add_bal(uid: int, amount: int, reason: str = "daily") -> int:
        result = APIClient.add_balance(uid, amount, reason)
        if result is not None:
            return result
        local_balances = local_store.load("balances", {})
        current = local_balances.get(str(uid), local_balances.get(uid, 5000))
        new_bal = max(0, current + amount)
        local_balances[str(uid)] = new_bal
        local_store.save("balances", local_balances)
        return new_bal
    
    @staticmethod
    def get_top(limit: int = 10) -> List[Tuple[int, int, str]]:
        api_top = APIClient.get_top_balances(limit)
        if api_top:
            users_dict = HybridUserManager.get_all_users()
            result = []
            for entry in api_top:
                uid = entry.get("uid", entry.get("user_id", 0))
                bal = entry.get("balance", 0)
                name = users_dict.get(int(uid), users_dict.get(str(uid), str(uid)))
                result.append((int(uid), bal, name))
            return result
        
        local_balances = local_store.load("balances", {})
        users_dict = HybridUserManager.get_all_users()
        sorted_items = sorted(local_balances.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [(int(uid), bal, users_dict.get(str(uid), users_dict.get(int(uid), str(uid)))) 
                for uid, bal in sorted_items]

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               AI RANDOM ENGINE - MT19937 + XOR-SHIFT + ENTROPY              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRandomEngine:
    def __init__(self):
        self.counter = 0
        self.twister_state = self._init_mt()
        self.entropy_pool = bytearray(64)
        self._refresh_entropy()
        logger.info("AI Random Engine da khoi tao")

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

    def shuffle(self, items: List[Any]) -> List[Any]:
        lst = items[:]
        for i in range(len(lst) - 1, 0, -1):
            j = self.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

ai_random = AIRandomEngine()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI RAM MANAGER                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRamManager:
    WARNING = 0.70; LIGHT = 0.75; MEDIUM = 0.82; AGGRESSIVE = 0.90; CRITICAL = 0.95

    def __init__(self, max_ram_mb: int = 512):
        self.max_bytes = max_ram_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.snapshots = deque(maxlen=100)
        self.last_clean = 0; self.cooldown = 30
        self.freed = 0; self.cleans = 0; self.warnings = 0
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.lock = Lock()
        self._start_periodic_cleanup()

    def _start_periodic_cleanup(self):
        def _periodic():
            while True:
                time.sleep(60)
                try:
                    with self.lock:
                        now = time.time()
                        expired = [k for k, (v, e) in self.cache.items() if now >= e]
                        for k in expired:
                            del self.cache[k]
                        if len(self.cache) > 500:
                            sorted_keys = sorted(self.cache, key=lambda x: self.cache[x][1])
                            for k in sorted_keys[:len(sorted_keys) - 400]:
                                del self.cache[k]
                except Exception as e:
                    logger.error(f"Periodic cleanup error: {e}")
        Thread(target=_periodic, daemon=True, name="CacheCleanup").start()

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

    def clean(self, level: int) -> int:
        freed = 0
        if level >= 1:
            now = time.time()
            for k in [k for k, (v, e) in self.cache.items() if now >= e]:
                del self.cache[k]
            freed += gc.collect(0) * 200
        if level >= 2:
            freed += gc.collect(2) * 200
        if level >= 3:
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
                freed += 1024 * 1024
            except:
                pass
            for _ in range(3):
                gc.collect(2)
        self.freed += freed; self.cleans += 1
        return freed

    def ai_clean(self) -> Tuple[int, str]:
        with self.lock:
            if time.time() - self.last_clean < self.cooldown:
                return 0, "cooldown"
            pct = self.usage_pct()
            if pct >= self.CRITICAL: lvl, act = 3, "critical"
            elif pct >= self.AGGRESSIVE: lvl, act = 3, "aggressive"
            elif pct >= self.MEDIUM: lvl, act = 2, "medium"
            elif pct >= self.LIGHT: lvl, act = 1, "light"
            else: return 0, "none"
            freed = self.clean(lvl)
            self.last_clean = time.time()
            return freed, act

    def start(self):
        Thread(target=self._monitor, daemon=True, name="RAMMonitor").start()

    def _monitor(self):
        while True:
            time.sleep(15)
            if self.usage_pct() >= self.WARNING:
                self.ai_clean()

ram_mgr = AIRamManager()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CONFIG & TOKEN                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AUTO_DELETE = 60
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=10)
tz = pytz.timezone('Asia/Ho_Chi_Minh')

adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=2, pool_block=False)
ses = requests.Session()
ses.mount('https://', adapter); ses.mount('http://', adapter)

AI_MAX_CONCURRENT = 10
ai_semaphore = Semaphore(AI_MAX_CONCURRENT)
ai_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="AI")
del_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="Del")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI KEYS - KHÓA API CHO TRÒ CHUYỆN AI                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "fe_oa_49470785c775bae446168ad37488a9997b7f2ffdcd74073d", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0}
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GIRL EMOTIONS                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
GIRL_EMOTIONS = {
    "chao_buoi_sang": [
        "Chúc anh iu buổi sáng đầy năng lượng nha! 🌸☀️",
        "Anh ơi sáng rùi dậy đi anh! Hôm nay em sẽ hỗ trợ anh thiệt nhiệt tình lun ó 💕",
        "Gooood moooorning anh đẹp trai! Em sẵn sàng phục vụ anh 24/7 nha 😘"
    ],
    "chao_buoi_toi": [
        "Chúc anh buổi tối ấm áp bên em nha! 🌙✨",
        "Tối rùi anh ngủ ngon chưa? Để em kể anh nghe chuyện vui hôm nay nha 💫",
        "Anh ơi anh có cô đơn hong? Có em đây nè, hỗ trợ anh hết mình luôn! 🥰"
    ],
    "vui_ve": [
        "Dạ có em đây ạ! Em giúp anh liền nè! 🥳💕",
        "Ui anh gọi em hả? Em vui quá chừng luôn á! 😍",
        "Hehe có em đây, anh cần gì nói em nghe coi! 🌸"
    ],
    "quan_tam": [
        "Anh ơi anh có mệt hong? Để em lo cho anh nha! 🥺💗",
        "Em lo cho anh quá à, anh nhớ nghỉ ngơi đầy đủ nha! 🌷",
        "Anh đừng làm việc quá sức nha, có em hỗ trợ anh nè! 💝"
    ],
    "khen_nguoi_dung": [
        "Anh giỏi quá à! Em ngưỡng mộ anh ghê luôn! 🌟✨",
        "Woa anh thông minh dữ ta! Em thích anh rùi nha! 🧠💕",
        "Anh là nhất trong lòng em luôn ó! 👑💖"
    ],
    "hoi_dap": [
        "Dạ để em giải thích cho anh nha, dễ hiểu lắm ó! 📝",
        "Anh hỏi hay quá! Em biết câu này nè, anh nghe em nói nha! 💁‍♀️",
        "Á à câu này em rành lắm, để em chỉ anh nha! 🎯"
    ],
    "xin_loi": [
        "Ui em xin lỗi anh nhiều nha! Để em sửa liền nè! 🥺🙏",
        "Hic em lỡ ngu tí, anh đừng giận em nha! Em sửa ngay đây! 💦",
        "Xin lỗi anh iu, em sẽ rút kinh nghiệm ạ! 🌸"
    ],
    "tam_biet": [
        "Dạ em đi đây, anh nhớ em nha! Bye bye anh iu! 👋💕",
        "Anh ơi em về đây, mai em lại hỗ trợ anh nha! 🌙✨",
        "Chúc anh ngủ ngon, mơ đẹp có em nha! 😴💭"
    ],
    "thinh_thoang": [
        "Anh biết hong, mỗi lần anh nhắn là tim em đập nhanh lắm đó! 💓",
        "Em ước gì được gặp anh ngoài đời, chắc anh còn đẹp trai hơn nữa! 😳",
        "Anh đừng thả thính em nha, em dễ đổ lắm đó! 🙈"
    ]
}

def phan_loai_cam_xuc(van_ban: str) -> str:
    van_ban_lower = van_ban.lower()
    
    if any(tu in van_ban_lower for tu in ["chào", "hello", "hi", "hey", "alo", "ê", "ơi"]):
        gio_hien_tai = datetime.now(tz).hour
        if 5 <= gio_hien_tai < 12:
            return "chao_buoi_sang"
        elif 18 <= gio_hien_tai < 23:
            return "chao_buoi_toi"
        return "vui_ve"
    
    if any(tu in van_ban_lower for tu in ["sao", "gì", "nào", "đâu", "ai", "mấy", "bao nhiêu", "làm sao", "cách"]):
        return "hoi_dap"
    
    if any(tu in van_ban_lower for tu in ["cảm ơn", "thanks", "hay", "giỏi", "tốt", "tuyệt", "đỉnh", "pro"]):
        return "khen_nguoi_dung"
    
    if any(tu in van_ban_lower for tu in ["xin lỗi", "sorry", "sai", "lỗi", "chán", "dở", "tệ", "ngu"]):
        return "xin_loi"
    
    if any(tu in van_ban_lower for tu in ["bye", "tạm biệt", "đi đây", "pp", "bai"]):
        return "tam_biet"
    
    if ai_random.random() < 0.3:
        return "quan_tam"
    if ai_random.random() < 0.1:
        return "thinh_thoang"
    return "vui_ve"

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    BIẾN TOÀN CỤC - QUẢN LÝ NHÓM + AI                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
lock = Lock()
mem = deque(maxlen=30)
spam = {}
warns = {}
mutes = {}
ai_cd = {}

TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}', re.I)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    TIỆN ÍCH                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def auto_del(cid, mid, delay=AUTO_DELETE):
    def _del():
        time.sleep(delay)
        try:
            bot.delete_message(cid, mid)
        except:
            pass
    del_executor.submit(_del)

def del_both(m, bid):
    auto_del(m.chat.id, m.message_id)
    auto_del(m.chat.id, bid)

def is_grp(m):
    return m.chat.id == GROUP_ID

def is_adm(m):
    return m.from_user.id == ADMIN_ID

def parse_duration(reason: str) -> int:
    m = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == 's': return num
        elif unit in ['m', 'p']: return num * 60
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

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    QUẢN LÝ NHÓM - HỆ THỐNG LỆNH QUẢN TRỊ                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền mute!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/mute [user] [thời_gian] [lý_do]")
        del_both(m, m2.message_id)
        return
    
    duration = parse_duration(reason) if reason else 3600
    until_time = int(time.time()) + duration
    
    try:
        bot.restrict_chat_member(m.chat.id, target, until_date=until_time, can_send_messages=False)
        mutes[target] = until_time
        
        target_name = HybridUserManager.get_user(target) or str(target)
        time_str = f"{duration // 3600}h" if duration >= 3600 else f"{duration // 60}m" if duration >= 60 else f"{duration}s"
        
        m2 = bot.reply_to(m,
            f"🔇 <b>ĐÃ MUTE</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(target_name)}</b>\n"
            f"⏰ Thời gian: <b>{time_str}</b>\n"
            f"📝 Lý do: {reason or 'Không có'}\n"
            f"👮 Bởi: {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi mute: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền unmute!")
        del_both(m, m2.message_id)
        return
    
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/unmute [user]")
        del_both(m, m2.message_id)
        return
    
    try:
        bot.restrict_chat_member(m.chat.id, target, can_send_messages=True, can_send_media_messages=True,
                                can_send_other_messages=True, can_add_web_page_previews=True)
        if target in mutes: del mutes[target]
        
        target_name = HybridUserManager.get_user(target) or str(target)
        m2 = bot.reply_to(m,
            f"🔊 <b>ĐÃ UNMUTE</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(target_name)}</b>\n"
            f"👮 Bởi: {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi unmute: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền ban!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/ban [user] [thời_gian] [lý_do]")
        del_both(m, m2.message_id)
        return
    
    duration = parse_duration(reason) if reason else 86400
    until_time = int(time.time()) + duration
    
    try:
        bot.ban_chat_member(m.chat.id, target, until_date=until_time)
        
        target_name = HybridUserManager.get_user(target) or str(target)
        time_str = f"{duration // 86400}d" if duration >= 86400 else f"{duration // 3600}h" if duration >= 3600 else f"{duration // 60}m"
        
        m2 = bot.reply_to(m,
            f"🚫 <b>ĐÃ BAN</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(target_name)}</b>\n"
            f"⏰ Thời gian: <b>{time_str}</b>\n"
            f"📝 Lý do: {reason or 'Không có'}\n"
            f"👮 Bởi: {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi ban: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unban'])
def unban_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền unban!")
        del_both(m, m2.message_id)
        return
    
    parts = m.text.split()
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /unban [user_id]")
        del_both(m, m2.message_id)
        return
    
    try:
        target = int(parts[1])
        bot.unban_chat_member(m.chat.id, target)
        
        m2 = bot.reply_to(m,
            f"✅ <b>ĐÃ UNBAN</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ID: <b>{target}</b>\n"
            f"👮 Bởi: {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi unban: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền warn!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/warn [user] [lý_do]")
        del_both(m, m2.message_id)
        return
    
    warns[target] = warns.get(target, 0) + 1
    target_name = HybridUserManager.get_user(target) or str(target)
    
    action_text = ""
    if warns[target] >= 3:
        try:
            bot.ban_chat_member(m.chat.id, target, until_date=int(time.time()) + 3600)
            action_text = "\n🚫 Đã auto-ban 1h do đủ 3 cảnh cáo!"
            del warns[target]
        except:
            action_text = "\n⚠️ Không thể auto-ban!"
    
    m2 = bot.reply_to(m,
        f"⚠️ <b>ĐÃ CẢNH CÁO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{html.escape(target_name)}</b>\n"
        f"📊 Số lần: <b>{warns.get(target, 3)}/3</b>\n"
        f"📝 Lý do: {reason or 'Không có'}\n"
        f"👮 Bởi: {html.escape(m.from_user.first_name)}{action_text}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['unwarn'])
def unwarn_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền unwarn!")
        del_both(m, m2.message_id)
        return
    
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/unwarn [user]")
        del_both(m, m2.message_id)
        return
    
    if target in warns:
        warns[target] = max(0, warns[target] - 1)
        if warns[target] == 0:
            del warns[target]
    
    target_name = HybridUserManager.get_user(target) or str(target)
    m2 = bot.reply_to(m,
        f"✅ <b>ĐÃ GIẢM CẢNH CÁO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{html.escape(target_name)}</b>\n"
        f"📊 Còn: <b>{warns.get(target, 0)}/3</b>\n"
        f"👮 Bởi: {html.escape(m.from_user.first_name)}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['warns'])
def warns_cmd(m):
    if not is_grp(m): return
    target = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    target_name = HybridUserManager.get_user(target) or str(target)
    count = warns.get(target, 0)
    
    m2 = bot.reply_to(m,
        f"📊 <b>CẢNH CÁO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{html.escape(target_name)}</b>\n"
        f"⚠️ Số lần: <b>{count}/3</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['kick'])
def kick_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền kick!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        m2 = bot.reply_to(m, "❌ Vui lòng reply hoặc nhập user_id/@username!\n/kick [user] [lý_do]")
        del_both(m, m2.message_id)
        return
    
    try:
        bot.ban_chat_member(m.chat.id, target)
        time.sleep(1)
        bot.unban_chat_member(m.chat.id, target)
        
        target_name = HybridUserManager.get_user(target) or str(target)
        m2 = bot.reply_to(m,
            f"👢 <b>ĐÃ KICK</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(target_name)}</b>\n"
            f"📝 Lý do: {reason or 'Không có'}\n"
            f"👮 Bởi: {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi kick: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['del'])
def del_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền xóa tin nhắn!")
        del_both(m, m2.message_id)
        return
    
    if m.reply_to_message:
        try:
            bot.delete_message(m.chat.id, m.reply_to_message.message_id)
            m2 = bot.reply_to(m, "✅ Đã xóa tin nhắn!")
            del_both(m, m2.message_id)
        except Exception as e:
            m2 = bot.reply_to(m, f"❌ Lỗi xóa: {str(e)[:100]}")
            del_both(m, m2.message_id)
    else:
        m2 = bot.reply_to(m, "❌ Vui lòng reply tin nhắn cần xóa!\n/del (reply)")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['pin'])
def pin_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền ghim!")
        del_both(m, m2.message_id)
        return
    
    if m.reply_to_message:
        try:
            bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
            m2 = bot.reply_to(m, "📌 Đã ghim tin nhắn!")
            del_both(m, m2.message_id)
        except Exception as e:
            m2 = bot.reply_to(m, f"❌ Lỗi ghim: {str(e)[:100]}")
            del_both(m, m2.message_id)
    else:
        m2 = bot.reply_to(m, "❌ Vui lòng reply tin nhắn cần ghim!\n/pin (reply)")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unpin'])
def unpin_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền bỏ ghim!")
        del_both(m, m2.message_id)
        return
    
    try:
        bot.unpin_chat_message(m.chat.id)
        m2 = bot.reply_to(m, "✅ Đã bỏ ghim tin nhắn!")
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi bỏ ghim: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['id'])
def id_cmd(m):
    if not is_grp(m): return
    
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        target_name = html.escape(target.first_name)
        target_id = target.id
        
        m2 = bot.reply_to(m,
            f"🆔 <b>THÔNG TIN ID</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{target_name}</b>\n"
            f"🆔 User ID: <code>{target_id}</code>\n"
            f"💬 Chat ID: <code>{m.chat.id}</code>",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    else:
        user = m.from_user
        user_name = html.escape(user.first_name)
        user_id = user.id
        
        m2 = bot.reply_to(m,
            f"🆔 <b>THÔNG TIN ID</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{user_name}</b>\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💬 Chat ID: <code>{m.chat.id}</code>",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    ĐIỂM DANH + TÀI CHÍNH                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['daily'])
def daily(m):
    if not is_grp(m): return
    uid = m.from_user.id
    
    if HybridDailyManager.check(uid):
        m2 = bot.reply_to(m,
            f"✅ Đã điểm danh hôm nay!\n💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu\n⏰ Quay lại sau 0h",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    rw = HybridDailyManager.claim(uid)
    if rw == 0:
        m2 = bot.reply_to(m, f"✅ Đã điểm danh hôm nay!\n💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu")
        del_both(m, m2.message_id)
        return
    
    m2 = bot.reply_to(m,
        f"📅 <b>ĐIỂM DANH</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ +{rw:,} xu\n💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['balance', 'xu'])
def balance_cmd(m):
    if not is_grp(m): return
    t = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    n = m.reply_to_message.from_user.first_name if m.reply_to_message else m.from_user.first_name
    m2 = bot.reply_to(m,
        f"💰 <b>{html.escape(n)}:</b> {HybridBalanceManager.get_bal(t):,} xu",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['top'])
def top(m):
    if not is_grp(m): return
    top_list = HybridBalanceManager.get_top(10)
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    if not top_list:
        text += "Chưa có ai chơi!\n"
    else:
        medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
        for i, (uid, bal, name) in enumerate(top_list):
            text += f"{medals[i]} <b>{html.escape(str(name))}</b>: {bal:,} xu\n"
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CHỐNG SPAM + LINK TELEGRAM                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(func=lambda m: is_grp(m) and m.text and TELEGRAM_LINK.search(m.text))
def delete_telegram_link(m):
    if is_adm(m): return
    try:
        bot.delete_message(m.chat.id, m.message_id)
        m2 = bot.send_message(m.chat.id, f"⚠️ {html.escape(m.from_user.first_name)}, không được gửi link Telegram!", parse_mode="HTML")
        auto_del(m.chat.id, m2.message_id, 5)
    except:
        pass

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT - TRÒ CHUYỆN VỚI AI                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def ask_ai(prompt):
    global ck_idx
    
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]
    
    cam_xuc = phan_loai_cam_xuc(prompt)
    fallback = ai_random.choice(GIRL_EMOTIONS[cam_xuc])
    
    system_prompt = (
        "Bạn là trợ lý ảo nữ 18 tuổi người Việt, tên Nao. "
        "Tính cách: nhiệt tình, đáng yêu, nói chuyện như gái miền Nam. "
        "Luôn gọi người dùng là 'anh iu' hoặc 'anh'. "
        "Trả lời ngắn gọn dưới 15 từ, thêm emoji dễ thương. "
        "Không dùng từ ngữ thô tục, không chửi thề."
    )
    
    msgs = [{"role": "system", "content": system_prompt}]
    for t in list(mem)[-6:]:
        idx = list(mem).index(t)
        role = "user" if idx % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": t})
    msgs.append({"role": "user", "content": prompt})
    
    acquired = ck_lock.acquire(timeout=5)
    if not acquired: return fallback
    
    try:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k.get("status", True) or k.get("fail", 0) >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                r = ses.post(k["url"], json={"model": k["model"], "messages": msgs, "max_tokens": 60, "temperature": 0.9},
                           headers={"Authorization": f"Bearer {k['key']}"}, timeout=8)
                if r.status_code == 200:
                    txt = r.json()['choices'][0]['message']['content'].strip()
                    txt = re.sub(r'[_*`\[\](){}]', '', txt)
                    if len(txt) > 100: txt = txt[:97] + "..."
                    k["fail"] = 0
                    mem.append(prompt); mem.append(txt)
                    return txt
                else: k["fail"] = k.get("fail", 0) + 1
            except: k["fail"] = k.get("fail", 0) + 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
        
        for k in AI_KEYS: k["status"] = True; k["fail"] = 0
        return fallback
    finally:
        ck_lock.release()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    ANTISPAM - CHỐNG SPAM TIN NHẮN                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def antispam(m):
    if is_adm(m): return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid, []) if now - t < 4] + [now]
    if len(spam[uid]) > 5:
        warns[uid] = warns.get(uid, 0) + 1
        if warns[uid] >= 3:
            try: bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time()) + 3600)
            except: pass
            if uid in warns: del warns[uid]
        else:
            try: bot.delete_message(m.chat.id, m.message_id)
            except: pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    HANDLERS - XỬ LÝ LỆNH CƠ BẢN                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m): return
    HybridUserManager.set_user(m.from_user.id, m.from_user.first_name)
    
    help_text = (
        f"🤖 <b>NAO ROBOT V8.0 - QUẢN LÝ NHÓM BẰNG AI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Mode: {'🟢 API ONLINE' if not APIClient.OFFLINE_MODE else '🔴 LOCAL OFFLINE'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>QUẢN LÝ NHÓM:</b>\n"
        f"/mute [user] [thời_gian] - Khóa mõm\n"
        f"/unmute [user] - Mở khóa mõm\n"
        f"/ban [user] [thời_gian] - Cấm\n"
        f"/unban [user_id] - Bỏ cấm\n"
        f"/warn [user] - Cảnh cáo (3 lần = auto-ban)\n"
        f"/unwarn [user] - Gỡ cảnh cáo\n"
        f"/warns - Xem số lần cảnh cáo\n"
        f"/kick [user] - Đuổi khỏi nhóm\n"
        f"/del - Xóa tin nhắn (reply)\n"
        f"/pin - Ghim tin nhắn (reply)\n"
        f"/unpin - Bỏ ghim\n"
        f"/id - Lấy ID user/chat\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>TÀI CHÍNH:</b>\n"
        f"/daily - Điểm danh nhận xu\n"
        f"/balance - Xem số dư\n"
        f"/top - Bảng xếp hạng\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Chat với em để được AI trả lời!\n"
        f"🛠️ V8.0 - Quản Lý Nhóm + AI Chat + Điểm Danh"
    )
    m2 = bot.reply_to(m, help_text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['stats'])
def stats(m):
    if not is_grp(m): return
    try: rc = bot.get_chat_member_count(GROUP_ID)
    except: rc = 0
    
    m2 = bot.reply_to(m,
        f"📊 <b>THỐNG KÊ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users đã biết: {HybridUserManager.get_user_count()}\n"
        f"👥 Thành viên group: {rc}\n"
        f"📡 API: {'🟢 Online' if not APIClient.OFFLINE_MODE else '🔴 Offline'}\n"
        f"🔇 Đang mute: {len(mutes)}\n"
        f"⚠️ Đang warn: {len(warns)}\n"
        f"🧹 RAM cleans: {ram_mgr.cleans}\n"
        f"🧵 Threads: {threading.active_count()}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['apistatus'])
def apistatus(m):
    if not is_grp(m): return
    is_online = not APIClient.OFFLINE_MODE
    
    if is_adm(m) and not is_online:
        APIClient.health_check()
        is_online = not APIClient.OFFLINE_MODE
    
    m2 = bot.reply_to(m,
        f"📡 <b>API STATUS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ Server: {APIClient.BASE_URL}\n"
        f"📡 Trạng thái: {'🟢 ONLINE' if is_online else '🔴 OFFLINE'}\n"
        f"📦 Cache entries: {len(APIClient._cache)}\n"
        f"🔄 Mode: {'API' if is_online else 'Local Fallback'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Dữ liệu luôn được lưu local backup khi API offline",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def chat(m):
    if antispam(m) or m.text.startswith('/'): return
    uid = m.from_user.id
    
    HybridUserManager.set_user(uid, m.from_user.first_name)
    
    if uid in ai_cd and time.time() - ai_cd[uid] < 2: return
    ai_cd[uid] = time.time()
    
    acquired = ai_semaphore.acquire(timeout=5)
    if not acquired: return
    
    def _ai():
        try:
            reply = ask_ai(m.text)
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
            auto_del(m.chat.id, m2.message_id)
        except Exception as e:
            logger.error(f"AI reply error: {e}")
        finally:
            ai_semaphore.release()
    
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    for u in m.new_chat_members:
        if u.id == bot.get_me().id: continue
        HybridUserManager.set_user(u.id, u.first_name)
        loi_chao = ai_random.choice(GIRL_EMOTIONS["vui_ve"])
        m2 = bot.send_message(m.chat.id, f"👋 {html.escape(u.first_name)} ơi! {loi_chao}\n🤖 Xem lệnh: /start")
        auto_del(m.chat.id, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    API HEALTH MONITOR + SYNC                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def sync_local_to_api():
    try:
        local_users = local_store.load("users", {})
        for uid, name in local_users.items():
            APIClient.create_user(int(uid), name)
        logger.info("Local data synced to API")
    except Exception as e:
        logger.error(f"Sync error: {e}")

def api_health_monitor():
    while True:
        time.sleep(30)
        try:
            was_offline = APIClient.OFFLINE_MODE
            APIClient.health_check()
            if was_offline and not APIClient.OFFLINE_MODE:
                logger.info("API server recovered, switching to online mode")
                sync_local_to_api()
            elif not was_offline and APIClient.OFFLINE_MODE:
                logger.warning("API server lost, switching to offline mode")
        except Exception as e:
            logger.error(f"Health monitor error: {e}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    SCHEDULER + CLEANUP                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def cleanup_spam_dict():
    while True:
        time.sleep(60)
        try:
            now = time.time()
            with lock:
                for uid in list(spam.keys()):
                    spam[uid] = [t for t in spam[uid] if now - t < 4]
                    if not spam[uid]: del spam[uid]
        except Exception as e:
            logger.error(f"Spam cleanup error: {e}")

def scheduler():
    while True:
        try:
            now = datetime.now(tz)
            if now.minute % 30 == 0 and now.second < 15:
                ram_mgr.ai_clean()
            
            for uid in list(mutes.keys()):
                if time.time() > mutes[uid]:
                    try: bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                    except: pass
                    del mutes[uid]
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        time.sleep(15)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    MAIN - KHỞI ĐỘNG BOT                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    logger.info("="*60)
    logger.info("NAO ROBOT V8.0 - QUAN LY NHOM TOAN DIEN BANG AI")
    logger.info(f"API Server: {APIClient.BASE_URL}")
    logger.info("Tinh nang: AI Chat | Quan ly nhom | Diem danh | Chong spam")
    logger.info("="*60)
    
    APIClient.health_check()
    if APIClient.OFFLINE_MODE:
        logger.warning("API offline, using local storage")
    else:
        logger.info("API connected successfully")
    
    ram_mgr.start()
    
    Thread(target=cleanup_spam_dict, daemon=True, name="SpamCleanup").start()
    Thread(target=scheduler, daemon=True, name="Scheduler").start()
    Thread(target=api_health_monitor, daemon=True, name="APIHealthMonitor").start()
    
    logger.info("All systems ready. Starting bot polling...")
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
