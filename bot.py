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

# ─── LOGGING ──────────────────────────────────────────────────────────────────
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
    logger.info("Keep-alive started")
except ImportError:
    logger.warning("keep_alive.py not found")

import telebot
from telebot import types, util
import requests
import pytz

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    API CLIENT - KẾT NỐI ADMIN API                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class APIClient:
    """Client kết nối đến Admin API Server với cơ chế retry + fallback."""
    
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
            "User-Agent": "NaoRobot/7.0"
        }
    
    @classmethod
    def _request(cls, method: str, endpoint: str, json_data: Dict = None, params: Dict = None) -> Tuple[Optional[Dict], bool]:
        """Gửi request đến API, trả về (data, success)."""
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
                    logger.warning("API server unavailable, switching to offline mode")
                    return None, False
                else:
                    logger.warning(f"API {method} {endpoint} failed: {r.status_code}")
            except requests.exceptions.ConnectionError:
                if attempt == cls.RETRY_MAX:
                    cls.OFFLINE_MODE = True
                    logger.warning("API connection failed, switching to offline mode")
            except Exception as e:
                logger.error(f"API request error: {str(e)[:100]}")
            
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
    
    # ═══════════════════════════════════════════════════════════
    # BALANCE API
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def get_balance(cls, uid: int) -> Optional[int]:
        """Lấy số dư từ API, trả về None nếu thất bại."""
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
    def add_balance(cls, uid: int, amount: int, reason: str = "game") -> Optional[int]:
        """Thêm xu qua API."""
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
    def deduct_balance(cls, uid: int, amount: int, reason: str = "game") -> Optional[bool]:
        """Trừ xu qua API, trả về True/False/None."""
        data, success = cls._request("POST", "/api/balance/deduct", {
            "uid": uid, "amount": amount, "reason": reason
        })
        if success and data:
            status = data.get("status", "")
            if status == "success":
                new_bal = data.get("new_balance", data.get("data", {}).get("new_balance"))
                if new_bal is not None:
                    cls._set_cache(f"bal_{uid}", new_bal)
                return True
            return False
        return None
    
    @classmethod
    def get_top_balances(cls, limit: int = 10) -> Optional[List[Dict]]:
        """Lấy bảng xếp hạng từ API."""
        data, success = cls._request("GET", "/api/balance/top", params={"limit": limit})
        if success and data:
            return data.get("data", data.get("top", []))
        return None
    
    # ═══════════════════════════════════════════════════════════
    # USER API
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def get_user(cls, uid: int) -> Optional[Dict]:
        """Lấy thông tin user từ API."""
        data, success = cls._request("GET", f"/api/user/{uid}")
        if success and data:
            return data.get("data", data)
        return None
    
    @classmethod
    def create_user(cls, uid: int, name: str) -> bool:
        """Tạo user mới qua API."""
        _, success = cls._request("POST", "/api/user", {
            "uid": uid, "name": name, "initial_balance": 5000
        })
        return success
    
    @classmethod
    def get_all_users(cls) -> Optional[Dict[int, str]]:
        """Lấy tất cả users từ API."""
        cached = cls._get_cached("all_users")
        if cached is not None:
            return cached
        
        data, success = cls._request("GET", "/api/users")
        if success and data:
            users = data.get("data", data.get("users", {}))
            # Convert string keys to int
            result = {int(k): v for k, v in users.items()}
            cls._set_cache("all_users", result)
            return result
        return None
    
    # ═══════════════════════════════════════════════════════════
    # GAME CONFIG API
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def get_game_config(cls) -> Optional[Dict]:
        """Lấy cấu hình game từ API."""
        data, success = cls._request("GET", "/api/config/game")
        if success and data:
            return data.get("data", data)
        return None
    
    # ═══════════════════════════════════════════════════════════
    # DAILY API
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def check_daily(cls, uid: int) -> Optional[Dict]:
        """Kiểm tra điểm danh qua API."""
        data, success = cls._request("GET", f"/api/daily/check/{uid}")
        if success and data:
            return data.get("data", data)
        return None
    
    @classmethod
    def claim_daily(cls, uid: int) -> Optional[Dict]:
        """Điểm danh qua API."""
        data, success = cls._request("POST", f"/api/daily/claim", {"uid": uid})
        if success and data:
            return data.get("data", data)
        return None
    
    # ═══════════════════════════════════════════════════════════
    # NOHU (JACKPOT) API
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def get_nohu_jp(cls) -> Optional[int]:
        """Lấy jackpot hiện tại từ API."""
        data, success = cls._request("GET", "/api/nohu/jp")
        if success and data:
            return data.get("jp", data.get("data", {}).get("jp"))
        return None
    
    @classmethod
    def update_nohu_jp(cls, amount: int, action: str = "add") -> Optional[int]:
        """Cập nhật jackpot qua API."""
        data, success = cls._request("POST", "/api/nohu/update", {
            "amount": amount, "action": action
        })
        if success and data:
            return data.get("new_jp", data.get("data", {}).get("new_jp"))
        return None
    
    # ═══════════════════════════════════════════════════════════
    # HEALTH CHECK
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def health_check(cls) -> bool:
        """Kiểm tra API server có online không."""
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
    """Lưu trữ local, dùng khi API offline."""
    
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
# ║               HYBRID BALANCE MANAGER - API ƯU TIÊN, LOCAL FALLBACK          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridBalanceManager:
    """Quản lý balance: ưu tiên API, fallback local."""
    
    @staticmethod
    def get_bal(uid: int) -> int:
        """Lấy số dư - API trước, local sau."""
        # Thử API
        bal = APIClient.get_balance(uid)
        if bal is not None:
            return bal
        
        # Fallback local
        local_balances = local_store.load("balances", {})
        if str(uid) in local_balances:
            return local_balances[str(uid)]
        if uid in local_balances:
            return local_balances[uid]
        
        # Default
        default = 5000
        local_balances[str(uid)] = default
        local_store.save("balances", local_balances)
        return default
    
    @staticmethod
    def add_bal(uid: int, amount: int, reason: str = "game") -> int:
        """Thêm xu."""
        # Thử API
        result = APIClient.add_balance(uid, amount, reason)
        if result is not None:
            return result
        
        # Fallback local
        local_balances = local_store.load("balances", {})
        current = local_balances.get(str(uid), local_balances.get(uid, 5000))
        new_bal = max(0, current + amount)
        local_balances[str(uid)] = new_bal
        local_store.save("balances", local_balances)
        return new_bal
    
    @staticmethod
    def deduct_bal(uid: int, amount: int, reason: str = "game") -> bool:
        """Trừ xu, trả về True nếu thành công."""
        # Thử API
        result = APIClient.deduct_balance(uid, amount, reason)
        if result is not None:
            return result
        
        # Fallback local
        local_balances = local_store.load("balances", {})
        current = local_balances.get(str(uid), local_balances.get(uid, 5000))
        if current >= amount:
            local_balances[str(uid)] = current - amount
            local_store.save("balances", local_balances)
            return True
        return False
    
    @staticmethod
    def get_top(limit: int = 10) -> List[Tuple[int, int, str]]:
        """Lấy top balances."""
        # Thử API
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
        
        # Fallback local
        local_balances = local_store.load("balances", {})
        users_dict = HybridUserManager.get_all_users()
        sorted_items = sorted(local_balances.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [(int(uid), bal, users_dict.get(str(uid), users_dict.get(int(uid), str(uid)))) 
                for uid, bal in sorted_items]

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               HYBRID USER MANAGER                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridUserManager:
    """Quản lý users: ưu tiên API, fallback local."""
    
    @staticmethod
    def get_all_users() -> Dict[int, str]:
        """Lấy tất cả users."""
        # Thử API
        api_users = APIClient.get_all_users()
        if api_users:
            return api_users
        
        # Fallback local
        return local_store.load("users", {})
    
    @staticmethod
    def get_user(uid: int) -> Optional[str]:
        """Lấy tên user."""
        users = HybridUserManager.get_all_users()
        return users.get(uid, users.get(str(uid)))
    
    @staticmethod
    def set_user(uid: int, name: str):
        """Lưu user."""
        # Thử API
        APIClient.create_user(uid, name)
        
        # Luôn lưu local làm backup
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
    """Quản lý điểm danh: ưu tiên API, fallback local."""
    
    @staticmethod
    def check(uid: int) -> bool:
        """Kiểm tra đã điểm danh hôm nay chưa."""
        # Thử API
        api_result = APIClient.check_daily(uid)
        if api_result is not None:
            return api_result.get("claimed", False)
        
        # Fallback local
        daily = local_store.load("daily", {})
        today = date.today().isoformat()
        return daily.get(str(uid)) == today
    
    @staticmethod
    def claim(uid: int) -> int:
        """Điểm danh, trả về số xu nhận được."""
        today = date.today().isoformat()
        
        # Thử API
        api_result = APIClient.claim_daily(uid)
        if api_result is not None:
            reward = api_result.get("reward", api_result.get("amount", 500))
            return reward
        
        # Fallback local
        daily = local_store.load("daily", {})
        if daily.get(str(uid)) == today:
            return 0
        
        daily[str(uid)] = today
        local_store.save("daily", daily)
        
        reward = 500 + random.randint(0, 1000)
        HybridBalanceManager.add_bal(uid, reward, "daily")
        return reward

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               HYBRID NOHU (JACKPOT) MANAGER                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class HybridNohuManager:
    """Quản lý nổ hũ: ưu tiên API, fallback local."""
    
    @staticmethod
    def get_jp() -> int:
        """Lấy jackpot hiện tại."""
        # Thử API
        api_jp = APIClient.get_nohu_jp()
        if api_jp is not None:
            return api_jp
        
        # Fallback local
        jp_data = local_store.load("jp", {"jp": 100000})
        return jp_data.get("jp", 100000)
    
    @staticmethod
    def update_jp(amount: int, action: str = "add") -> int:
        """Cập nhật jackpot."""
        # Thử API
        api_result = APIClient.update_nohu_jp(amount, action)
        if api_result is not None:
            return api_result
        
        # Fallback local
        jp_data = local_store.load("jp", {"jp": 100000})
        if action == "add":
            jp_data["jp"] = jp_data.get("jp", 100000) + amount
        elif action == "set":
            jp_data["jp"] = amount
        elif action == "reset":
            jp_data["jp"] = 100000
        local_store.save("jp", jp_data)
        return jp_data["jp"]

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               API HEALTH MONITOR                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def api_health_monitor():
    """Giám sát trạng thái API, tự động chuyển đổi mode."""
    while True:
        time.sleep(30)
        try:
            was_offline = APIClient.OFFLINE_MODE
            APIClient.health_check()
            if was_offline and not APIClient.OFFLINE_MODE:
                logger.info("API server recovered, switching to online mode")
                # Đồng bộ dữ liệu local lên API nếu cần
                sync_local_to_api()
            elif not was_offline and APIClient.OFFLINE_MODE:
                logger.warning("API server lost, switching to offline mode")
        except Exception as e:
            logger.error(f"Health monitor error: {e}")

def sync_local_to_api():
    """Đồng bộ dữ liệu local lên API."""
    try:
        local_users = local_store.load("users", {})
        for uid, name in local_users.items():
            APIClient.create_user(int(uid), name)
        
        local_balances = local_store.load("balances", {})
        for uid, bal in local_balances.items():
            current_api = APIClient.get_balance(int(uid))
            if current_api is not None and current_api < bal:
                diff = bal - current_api
                APIClient.add_balance(int(uid), diff, "sync")
        
        logger.info("Local data synced to API")
    except Exception as e:
        logger.error(f"Sync error: {e}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               AI RANDOM ENGINE - MT19937 + XOR-SHIFT + ENTROPY              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRandomEngine:
    """Bộ sinh số ngẫu nhiên AI - Mersenne Twister + XOR Shift + Entropy Pool."""
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
tho_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="Tho")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI KEYS - KHÓA API                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0}
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
# ║                    BIẾN TOÀN CỤC                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
lock = Lock()
mem = deque(maxlen=30)
spam = {}
warns = {}
mutes = {}
ai_cd = {}
GAME_SESSIONS = {}

GAME_MIN_BET = 100
GAME_MAX_BET = 100000
GAME_SESSION_TIMEOUT = 1800
nohu_fee = 1000
nohu_mult = 0.05

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
# ║                    BÃO X10 ENGINE                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def bao_x10(bet: int) -> Tuple[int, bool]:
    if ai_random.random() < 0.10:
        return bet * 10, True
    return 0, False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME ENGINE                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def init_game(uid, gt):
    bases = {"start": time.time(), "last_active": time.time()}
    game_types = {
        "taixiu": {"type": "taixiu", "w": 0, "l": 0, **bases},
        "baucua": {"type": "baucua", "w": 0, "l": 0, **bases},
        "kbb": {"type": "kbb", "score": 0, "bot": 0, "draw": 0, **bases},
        "doanso": {"type": "doanso", "secret": ai_random.randint(1, 100), "att": 0, "max": 7, **bases},
        "lxn": {"type": "lxn", "w": 0, "l": 0, **bases},
        "xx": {"type": "xx", "w": 0, "l": 0, **bases},
        "caudo": {"type": "caudo", "score": 0, "qnum": 0, **bases},
        "chanle": {"type": "chanle", "w": 0, "l": 0, **bases},
        "caothap": {"type": "caothap", "w": 0, "l": 0, **bases},
        "doanso2": {"type": "doanso2", "secret": ai_random.randint(1, 100), "att": 0, "max": 5, **bases},
        "keo": {"type": "keo", "w": 0, "l": 0, **bases},
        "bingo": {"type": "bingo", "w": 0, "l": 0, **bases},
        "rongho": {"type": "rongho", "w": 0, "l": 0, **bases},
        "chanle2": {"type": "chanle2", "w": 0, "l": 0, **bases},
        "3cay": {"type": "3cay", "w": 0, "l": 0, **bases},
        "slot": {"type": "slot", "w": 0, "l": 0, "spins": 0, **bases},
        "bauslot": {"type": "bauslot", "w": 0, "l": 0, **bases},
        "doanso3": {"type": "doanso3", "secret": ai_random.randint(1, 50), "att": 0, "max": 3, **bases}
    }
    return game_types.get(gt, {"type": gt, **bases})

def is_valid_bet(uid, amount) -> Tuple[bool, str]:
    if amount < GAME_MIN_BET:
        return False, f"❌ Cược tối thiểu {GAME_MIN_BET:,} xu"
    if amount > GAME_MAX_BET:
        return False, f"❌ Cược tối đa {GAME_MAX_BET:,} xu"
    if HybridBalanceManager.get_bal(uid) < amount:
        return False, f"❌ Không đủ xu! Số dư: {HybridBalanceManager.get_bal(uid):,} xu\n💰 Nhận thêm: /daily"
    return True, ""

def resolve_bet(uid, bet_amount, won: bool, multiplier: float = 1.0) -> Tuple[int, bool, str]:
    bao_bonus, is_bao = bao_x10(bet_amount)
    if won:
        win_amount = int(bet_amount * multiplier) + bao_bonus
        HybridBalanceManager.add_bal(uid, win_amount, "game_win")
        out = f"🎉 Thắng +{win_amount:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
        return win_amount, is_bao, out
    else:
        HybridBalanceManager.deduct_bal(uid, bet_amount, "game_lose")
        out = f"💔 Thua -{bet_amount:,} xu"
        return -bet_amount, False, out

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 1: TÀI XỈU                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['taixiu'])
def taixiu(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu":
            GAME_SESSIONS[uid] = init_game(uid, "taixiu")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🎲 <b>TÀI XỈU BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Luật: 3 xúc xắc, 3-10=Xỉu, 11-18=Tài\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n"
            f"💰 Thắng: x2 tiền cược\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/taixiu [tai/xiu] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /taixiu [tai/xiu] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['tai', 'xiu']:
        m2 = bot.reply_to(m, "❌ Chọn tai hoặc xiu")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu":
        GAME_SESSIONS[uid] = init_game(uid, "taixiu")
    g = GAME_SESSIONS[uid]
    g["last_active"] = time.time()
    
    d1, d2, d3 = ai_random.randint(1, 6), ai_random.randint(1, 6), ai_random.randint(1, 6)
    total = d1 + d2 + d3
    res = "tai" if total >= 11 else "xiu"
    won = (ch == res)
    _, _, out = resolve_bet(uid, bt, won, multiplier=2)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    dice_map = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    m2 = bot.reply_to(m,
        f"🎲 <b>TÀI XỈU</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"{dice_map[d1]} {dice_map[d2]} {dice_map[d3]} = <b>{total}</b> → <b>{'TÀI' if res == 'tai' else 'XỈU'}</b>\n"
        f"{out}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 2: BẦU CUA                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['baucua'])
def baucua(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    syms = ["Cua", "Ca", "Tom", "Ga", "Nai", "Bau"]
    sym_emoji = {"Cua": "🦀", "Ca": "🐟", "Tom": "🦐", "Ga": "🐔", "Nai": "🦌", "Bau": "🎃"}
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "baucua":
            GAME_SESSIONS[uid] = init_game(uid, "baucua")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🎲 <b>BẦU CUA BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Chọn: Cua/Ca/Tom/Ga/Nai/Bau\n"
            f"💰 Trúng 1 = x2 | 2 = x5 | 3 = x20\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"/baucua [con] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower().capitalize()
    if ch not in syms:
        m2 = bot.reply_to(m, f"❌ Chọn: {'/'.join(syms)}")
        del_both(m, m2.message_id)
        return
    
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /baucua [con] [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "baucua":
        GAME_SESSIONS[uid] = init_game(uid, "baucua")
    g = GAME_SESSIONS[uid]
    g["last_active"] = time.time()
    
    r1, r2, r3 = ai_random.choice(syms), ai_random.choice(syms), ai_random.choice(syms)
    count = sum(1 for r in [r1, r2, r3] if r == ch)
    
    if count == 3:
        won, mult = True, 20
    elif count == 2:
        won, mult = True, 5
    elif count == 1:
        won, mult = True, 2
    else:
        won, mult = False, 0
    
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎲 <b>BẦU CUA</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"{sym_emoji[r1]} {sym_emoji[r2]} {sym_emoji[r3]}\n"
        f"Bạn chọn: {sym_emoji[ch]} <b>{ch}</b> → Trúng {count} lần\n"
        f"{out}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 3: KÉO BÚA BAO                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['kbb'])
def kbb(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "kbb":
            GAME_SESSIONS[uid] = init_game(uid, "kbb")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"✊ <b>KÉO BÚA BAO BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Chọn: keo/bua/bao\n"
            f"💰 Thắng: x3 | Hòa: hoàn tiền\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"/kbb [keo/bua/bao] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Score: {g['score']} | 🤖 Bot: {g['bot']} | 🤝 Hòa: {g['draw']}\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /kbb [keo/bua/bao] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['keo', 'bua', 'bao']:
        m2 = bot.reply_to(m, "❌ Chọn keo/bua/bao")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "kbb":
        GAME_SESSIONS[uid] = init_game(uid, "kbb")
    g = GAME_SESSIONS[uid]
    
    bot_ch = ai_random.choice(['keo', 'bua', 'bao'])
    emoji_map = {'keo': '✌️', 'bua': '👊', 'bao': '🖐️'}
    
    if ch == bot_ch:
        HybridBalanceManager.add_bal(uid, bt, "game_draw")
        out = "🤝 Hòa! Hoàn tiền"
        g["draw"] += 1
    elif (ch == 'keo' and bot_ch == 'bao') or (ch == 'bua' and bot_ch == 'keo') or (ch == 'bao' and bot_ch == 'bua'):
        _, _, out = resolve_bet(uid, bt, True, multiplier=3)
        g["score"] += 1
    else:
        _, _, out = resolve_bet(uid, bt, False)
        g["bot"] += 1
    
    m2 = bot.reply_to(m,
        f"✊ <b>KÉO BÚA BAO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Bạn: {emoji_map[ch]} | 🤖 Bot: {emoji_map[bot_ch]}\n"
        f"{out}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Bạn: {g['score']} | 🤖 Bot: {g['bot']} | 🤝 Hòa: {g['draw']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 4: ĐOÁN SỐ                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['doanso'])
def doanso(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
        m2 = bot.reply_to(m,
            f"🔢 <b>ĐOÁN SỐ 1-100 - BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Đoán số 1-100, 7 lần đoán\n"
            f"💰 1 lần = x50 | 2 = x25 | 3 = x15 | 4-7 = x10\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/doanso [số] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: gs = int(parts[1]); bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /doanso [số 1-100] [cược]")
        del_both(m, m2.message_id)
        return
    
    if gs < 1 or gs > 100:
        m2 = bot.reply_to(m, "❌ Số từ 1-100")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "doanso":
        GAME_SESSIONS[uid] = init_game(uid, "doanso")
    g = GAME_SESSIONS[uid]
    g["att"] += 1
    
    if gs == g["secret"]:
        multipliers = {1: 50, 2: 25, 3: 15, 4: 10, 5: 10, 6: 10, 7: 10}
        mult = multipliers.get(g["att"], 5)
        _, _, out = resolve_bet(uid, bt, True, multiplier=mult)
        m2 = bot.reply_to(m,
            f"🎉 <b>CHÍNH XÁC!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số: <b>{g['secret']}</b> | Lần {g['att']} (x{mult})\n{out}\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        HybridBalanceManager.deduct_bal(uid, bt, "game_lose")
        m2 = bot.reply_to(m,
            f"💔 <b>HẾT LƯỢT!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số đúng: <b>{g['secret']}</b>\n💔 Thua -{bt:,} xu\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]:
        m2 = bot.reply_to(m, f"📈 <b>CAO HƠN!</b> Còn {g['max'] - g['att']} lần")
    else:
        m2 = bot.reply_to(m, f"📉 <b>THẤP HƠN!</b> Còn {g['max'] - g['att']} lần")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 5: LỚN XỈU NHỎ                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['lxn'])
def lxn(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "lxn":
            GAME_SESSIONS[uid] = init_game(uid, "lxn")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎯 <b>LỚN XỈU NHỎ BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số 1-100: Lớn(>50) / Xỉu(<50) / Nhỏ(=50)\n"
            f"💰 Lớn/Xỉu: x2 | Nhỏ: x20\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/lxn [lon/xiu/nho] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2]) if len(parts) > 2 else 0
    except: bt = 0
    
    if ch not in ['lon', 'xiu', 'nho'] or bt == 0:
        m2 = bot.reply_to(m, "❌ /lxn [lon/xiu/nho] [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "lxn":
        GAME_SESSIONS[uid] = init_game(uid, "lxn")
    g = GAME_SESSIONS[uid]
    
    num = ai_random.randint(1, 100)
    if num > 50: res = "lon"
    elif num < 50: res = "xiu"
    else: res = "nho"
    
    won = (ch == res)
    mult = 20 if res == "nho" and won else 2
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎯 <b>LỚN XỈU NHỎ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Số: <b>{num}</b> → <b>{'LỚN' if res == 'lon' else 'XỈU' if res == 'xiu' else 'NHỎ'}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 6: XÚC XẮC                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['xx'])
def xx(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "xx":
            GAME_SESSIONS[uid] = init_game(uid, "xx")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎲 <b>XÚC XẮC BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Đoán tổng 2 xúc xắc (2-12)\n"
            f"💰 Đúng: x10 | Lệch 1: x5 | Lệch 2: x2\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/xx [số 2-12] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: gs = int(parts[1]); bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /xx [số 2-12] [cược]")
        del_both(m, m2.message_id)
        return
    
    if gs < 2 or gs > 12:
        m2 = bot.reply_to(m, "❌ Số từ 2-12")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "xx":
        GAME_SESSIONS[uid] = init_game(uid, "xx")
    g = GAME_SESSIONS[uid]
    
    d1, d2 = ai_random.randint(1, 6), ai_random.randint(1, 6)
    total = d1 + d2
    diff = abs(total - gs)
    
    if diff == 0:
        won, mult = True, 10
    elif diff == 1:
        won, mult = True, 5
    elif diff == 2:
        won, mult = True, 2
    else:
        won, mult = False, 0
    
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎲 <b>XÚC XẮC</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 {d1} + {d2} = <b>{total}</b> | Bạn đoán: <b>{gs}</b> (Lệch {diff})\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 7-18: (GIỮ NGUYÊN TỪ CODE GỐC)                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# [Giữ nguyên code gốc cho các game: caudo, chanle, caothap, doanso2, keo, bingo,
#  rongho, chanle2, 3cay, slot, bauslot, doanso3 - chỉ thay get_bal/add_bal/deduct_bal
#  bằng HybridBalanceManager]

@bot.message_handler(commands=['chanle'])
def chanle(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "chanle":
            GAME_SESSIONS[uid] = init_game(uid, "chanle")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🔢 <b>CHẴN LẺ BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số 1-100, đoán chẵn/lẻ\n💰 Thắng: x2\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/chanle [chan/le] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /chanle [chan/le] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['chan', 'le']:
        m2 = bot.reply_to(m, "❌ Chọn chan hoặc le")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "chanle":
        GAME_SESSIONS[uid] = init_game(uid, "chanle")
    g = GAME_SESSIONS[uid]
    
    num = ai_random.randint(1, 100)
    res = "chan" if num % 2 == 0 else "le"
    won = (ch == res)
    _, _, out = resolve_bet(uid, bt, won, multiplier=2)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🔢 <b>CHẴN LẺ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Số: <b>{num}</b> → <b>{'CHẴN' if num % 2 == 0 else 'LẺ'}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['caothap'])
def caothap(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "caothap":
            GAME_SESSIONS[uid] = init_game(uid, "caothap")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"📊 <b>CAO THẤP BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 2 số 1-100, đoán số sau cao/thấp hơn số trước\n"
            f"💰 Thắng: x2\n💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/caothap [cao/thap] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /caothap [cao/thap] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['cao', 'thap']:
        m2 = bot.reply_to(m, "❌ Chọn cao hoặc thap")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "caothap":
        GAME_SESSIONS[uid] = init_game(uid, "caothap")
    g = GAME_SESSIONS[uid]
    
    n1 = ai_random.randint(1, 100)
    n2 = ai_random.randint(1, 100)
    res = "cao" if n2 > n1 else "thap" if n2 < n1 else "bang"
    
    if res == "bang":
        HybridBalanceManager.add_bal(uid, bt, "game_draw")
        out = "🤝 Bằng! Hoàn tiền"
    else:
        won = (ch == res)
        _, _, out = resolve_bet(uid, bt, won, multiplier=2)
        if won: g["w"] += 1
        else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"📊 <b>CAO THẤP</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Số 1: <b>{n1}</b> | Số 2: <b>{n2}</b> → <b>{'CAO' if res == 'cao' else 'THẤP' if res == 'thap' else 'BẰNG'}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['doanso2'])
def doanso2(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        GAME_SESSIONS[uid] = init_game(uid, "doanso2")
        m2 = bot.reply_to(m,
            f"🔢 <b>ĐOÁN SỐ 2 (5 LƯỢT) - BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Đoán số 1-100, 5 lần đoán\n"
            f"💰 1 lần = x30 | 2 = x20 | 3 = x10 | 4-5 = x5\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/doanso2 [số] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: gs = int(parts[1]); bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /doanso2 [số 1-100] [cược]")
        del_both(m, m2.message_id)
        return
    
    if gs < 1 or gs > 100:
        m2 = bot.reply_to(m, "❌ Số từ 1-100")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "doanso2":
        GAME_SESSIONS[uid] = init_game(uid, "doanso2")
    g = GAME_SESSIONS[uid]
    g["att"] += 1
    
    if gs == g["secret"]:
        multipliers = {1: 30, 2: 20, 3: 10, 4: 5, 5: 5}
        mult = multipliers.get(g["att"], 3)
        _, _, out = resolve_bet(uid, bt, True, multiplier=mult)
        m2 = bot.reply_to(m,
            f"🎉 <b>CHÍNH XÁC!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số: <b>{g['secret']}</b> | Lần {g['att']} (x{mult})\n{out}\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        HybridBalanceManager.deduct_bal(uid, bt, "game_lose")
        m2 = bot.reply_to(m,
            f"💔 <b>HẾT LƯỢT!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số đúng: <b>{g['secret']}</b>\n💔 Thua -{bt:,} xu\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]:
        m2 = bot.reply_to(m, f"📈 <b>CAO HƠN!</b> Còn {g['max'] - g['att']} lần")
    else:
        m2 = bot.reply_to(m, f"📉 <b>THẤP HƠN!</b> Còn {g['max'] - g['att']} lần")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['keo'])
def keo(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "keo":
            GAME_SESSIONS[uid] = init_game(uid, "keo")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎰 <b>KÉO BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 3 biểu tượng, giống 3 = x30, giống 2 = x5\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/keo [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: bt = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ /keo [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "keo":
        GAME_SESSIONS[uid] = init_game(uid, "keo")
    g = GAME_SESSIONS[uid]
    
    syms = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
    c1, c2, c3 = ai_random.choice(syms), ai_random.choice(syms), ai_random.choice(syms)
    
    if c1 == c2 == c3:
        won, mult = True, 30
    elif c1 == c2 or c2 == c3 or c1 == c3:
        won, mult = True, 5
    else:
        won, mult = False, 0
    
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎰 <b>KÉO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"┌─────┐\n│{c1}│{c2}│{c3}│\n└─────┘\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['bingo'])
def bingo(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "bingo":
            GAME_SESSIONS[uid] = init_game(uid, "bingo")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎱 <b>BINGO BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Đoán số 1-75\n💰 Đúng: x30\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/bingo [số] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: gs = int(parts[1]); bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /bingo [số 1-75] [cược]")
        del_both(m, m2.message_id)
        return
    
    if gs < 1 or gs > 75:
        m2 = bot.reply_to(m, "❌ Số từ 1-75")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "bingo":
        GAME_SESSIONS[uid] = init_game(uid, "bingo")
    g = GAME_SESSIONS[uid]
    
    num = ai_random.randint(1, 75)
    won = (gs == num)
    _, _, out = resolve_bet(uid, bt, won, multiplier=30)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎱 <b>BINGO</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Số ra: <b>{num}</b> | Bạn đoán: <b>{gs}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['rongho'])
def rongho(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "rongho":
            GAME_SESSIONS[uid] = init_game(uid, "rongho")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🐉 <b>RỒNG HỔ BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Rồng vs Hổ, bài ai cao hơn thắng\n"
            f"💰 Thắng: x2\n💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/rongho [rong/ho] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /rongho [rong/ho] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['rong', 'ho']:
        m2 = bot.reply_to(m, "❌ Chọn rong hoặc ho")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "rongho":
        GAME_SESSIONS[uid] = init_game(uid, "rongho")
    g = GAME_SESSIONS[uid]
    
    rong = ai_random.randint(1, 13); ho = ai_random.randint(1, 13)
    cards = {1: "A", 11: "J", 12: "Q", 13: "K"}
    rong_str = cards.get(rong, str(rong)); ho_str = cards.get(ho, str(ho))
    
    if rong > ho: res = "rong"
    elif ho > rong: res = "ho"
    else: res = "hoa"
    
    won = (ch == res)
    if res == "hoa":
        HybridBalanceManager.add_bal(uid, bt, "game_draw")
        out = "🤝 Hòa! Hoàn tiền cược"
    else:
        _, _, out = resolve_bet(uid, bt, won, multiplier=2)
    if won: g["w"] += 1
    elif res != "hoa": g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🐉 <b>RỒNG HỔ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🐉 Rồng: <b>{rong_str}</b> | 🐯 Hổ: <b>{ho_str}</b>\n"
        f"🎯 Kết quả: <b>{'RỒNG' if res == 'rong' else 'HỔ' if res == 'ho' else 'HÒA'}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['chanle2'])
def chanle2(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "chanle2":
            GAME_SESSIONS[uid] = init_game(uid, "chanle2")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🔢 <b>CHẴN LẺ 2 BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Tổng 2 số 1-50, đoán chẵn/lẻ\n💰 Thắng: x4\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/chanle2 [chan/le] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    ch = parts[1].lower()
    try: bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /chanle2 [chan/le] [cược]")
        del_both(m, m2.message_id)
        return
    
    if ch not in ['chan', 'le']:
        m2 = bot.reply_to(m, "❌ Chọn chan hoặc le")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "chanle2":
        GAME_SESSIONS[uid] = init_game(uid, "chanle2")
    g = GAME_SESSIONS[uid]
    
    n1, n2 = ai_random.randint(1, 50), ai_random.randint(1, 50)
    total = n1 + n2
    res = "chan" if total % 2 == 0 else "le"
    won = (ch == res)
    _, _, out = resolve_bet(uid, bt, won, multiplier=4)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🔢 <b>CHẴN LẺ 2</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 {n1} + {n2} = <b>{total}</b> → <b>{'CHẴN' if total % 2 == 0 else 'LẺ'}</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['3cay'])
def ba_cay(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "3cay":
            GAME_SESSIONS[uid] = init_game(uid, "3cay")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🃏 <b>3 CÂY BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 So 3 lá bài, ai cao điểm hơn thắng\n"
            f"💰 Thắng: x5\n💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/3cay [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: bt = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ /3cay [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "3cay":
        GAME_SESSIONS[uid] = init_game(uid, "3cay")
    g = GAME_SESSIONS[uid]
    
    suits = ["♠", "♥", "♦", "♣"]
    user_cards = [ai_random.randint(1, 13) for _ in range(3)]
    bot_cards = [ai_random.randint(1, 13) for _ in range(3)]
    cards_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
    
    user_score = sum(min(c, 10) for c in user_cards) % 10
    bot_score = sum(min(c, 10) for c in bot_cards) % 10
    
    user_display = " ".join(f"{cards_map.get(c, str(c))}{ai_random.choice(suits)}" for c in user_cards)
    bot_display = " ".join(f"{cards_map.get(c, str(c))}{ai_random.choice(suits)}" for c in bot_cards)
    
    if user_score > bot_score: won = True
    elif user_score < bot_score: won = False
    else: won = None
    
    if won is None:
        HybridBalanceManager.add_bal(uid, bt, "game_draw")
        out = "🤝 Hòa! Hoàn tiền cược"
    else:
        _, _, out = resolve_bet(uid, bt, won, multiplier=5)
    if won: g["w"] += 1
    elif won is not None: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🃏 <b>3 CÂY</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Bạn: {user_display} → <b>{user_score} điểm</b>\n"
        f"🤖 Bot: {bot_display} → <b>{bot_score} điểm</b>\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['slot'])
def slot_machine(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "slot":
            GAME_SESSIONS[uid] = init_game(uid, "slot")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎰 <b>SLOT MACHINE BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 3 cột, khớp biểu tượng để thắng\n"
            f"💎 777 = x50 | 🍒🍒🍒 = x10 | Giống đôi = x2\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/slot [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"🎰 Đã quay: {g['spins']} | 🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: bt = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ /slot [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "slot":
        GAME_SESSIONS[uid] = init_game(uid, "slot")
    g = GAME_SESSIONS[uid]
    g["spins"] += 1
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
    c1, c2, c3 = ai_random.choice(symbols), ai_random.choice(symbols), ai_random.choice(symbols)
    
    if c1 == c2 == c3:
        if c1 == "7️⃣": mult = 50
        elif c1 == "💎": mult = 25
        else: mult = 10
        won = True
    elif c1 == c2 or c2 == c3 or c1 == c3:
        mult = 2; won = True
    else:
        won = False; mult = 0
    
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎰 <b>SLOT MACHINE</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"┌─────┐\n│{c1}│{c2}│{c3}│\n└─────┘\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎰 Đã quay: {g['spins']} | 🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['bauslot'])
def bau_slot(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "bauslot":
            GAME_SESSIONS[uid] = init_game(uid, "bauslot")
        g = GAME_SESSIONS[uid]
        m2 = bot.reply_to(m,
            f"🎰 <b>BẦU CUA SLOT BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 3 cột bầu cua, giống 3 = x20, giống 2 = x3\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/bauslot [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: bt = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ /bauslot [cược]")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "bauslot":
        GAME_SESSIONS[uid] = init_game(uid, "bauslot")
    g = GAME_SESSIONS[uid]
    
    syms = ["🐄", "🦀", "🐟", "🐔", "🦌", "🦐"]
    c1, c2, c3 = ai_random.choice(syms), ai_random.choice(syms), ai_random.choice(syms)
    
    if c1 == c2 == c3: won, mult = True, 20
    elif c1 == c2 or c2 == c3 or c1 == c3: won, mult = True, 3
    else: won, mult = False, 0
    
    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won: g["w"] += 1
    else: g["l"] += 1
    
    m2 = bot.reply_to(m,
        f"🎰 <b>BẦU CUA SLOT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"┌─────┐\n│{c1}│{c2}│{c3}│\n└─────┘\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['doanso3'])
def doanso3(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    
    if len(parts) < 3:
        GAME_SESSIONS[uid] = init_game(uid, "doanso3")
        m2 = bot.reply_to(m,
            f"⚡ <b>ĐOÁN SỐ SIÊU TỐC 3 LƯỢT - BÃO X10</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Đoán số 1-50, chỉ 3 lần đoán\n"
            f"💰 1 lần = x50 | 2 lần = x25 | 3 lần = x10\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n━━━━━━━━━━━━━━━━━━━━\n"
            f"/doanso3 [số] [cược]\n💵 Cược: {GAME_MIN_BET:,}-{GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: gs = int(parts[1]); bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /doanso3 [số 1-50] [cược]")
        del_both(m, m2.message_id)
        return
    
    if gs < 1 or gs > 50:
        m2 = bot.reply_to(m, "❌ Số từ 1-50")
        del_both(m, m2.message_id)
        return
    
    valid, err = is_valid_bet(uid, bt)
    if not valid:
        m2 = bot.reply_to(m, err, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "doanso3":
        GAME_SESSIONS[uid] = init_game(uid, "doanso3")
    g = GAME_SESSIONS[uid]
    g["att"] += 1
    
    if gs == g["secret"]:
        multipliers = {1: 50, 2: 25, 3: 10}
        mult = multipliers.get(g["att"], 5)
        _, _, out = resolve_bet(uid, bt, True, multiplier=mult)
        m2 = bot.reply_to(m,
            f"⚡ <b>CHÍNH XÁC!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số: <b>{g['secret']}</b> | Lần {g['att']} (x{mult})\n{out}\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        HybridBalanceManager.deduct_bal(uid, bt, "game_lose")
        m2 = bot.reply_to(m,
            f"💔 <b>HẾT LƯỢT!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số đúng: <b>{g['secret']}</b>\n💔 Thua -{bt:,} xu\n"
            f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif gs < g["secret"]:
        m2 = bot.reply_to(m, f"📈 <b>CAO HƠN!</b> Còn {g['max'] - g['att']} lần")
    else:
        m2 = bot.reply_to(m, f"📉 <b>THẤP HƠN!</b> Còn {g['max'] - g['att']} lần")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    NỔ HŨ + ĐIỂM DANH + TÀI CHÍNH                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['nohu'])
def nohu_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id
    parts = m.text.split()
    jp = HybridNohuManager.get_jp()
    
    if len(parts) < 2:
        m2 = bot.reply_to(m,
            f"🎰 <b>NỔ HŨ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 JP: {jp:,} xu\n🎫 Phí: {nohu_fee:,} xu/lượt\n"
            f"💥 Bão X10: 10% cơ hội nhân 10\n\n/nohu [cược]",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    try: bet = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ Nhập số.")
        del_both(m, m2.message_id)
        return
    
    if bet < 100 or bet > 100000:
        m2 = bot.reply_to(m, "❌ Cược từ 100 - 100,000 xu.")
        del_both(m, m2.message_id)
        return
    
    total = bet + nohu_fee
    if not HybridBalanceManager.deduct_bal(uid, total, "nohu"):
        m2 = bot.reply_to(m, f"❌ Không đủ! Cần {total:,} xu\n💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu")
        del_both(m, m2.message_id)
        return
    
    HybridNohuManager.update_jp(int(bet * nohu_mult), "add")
    bao_bonus, is_bao = bao_x10(bet)
    c1, c2, c3 = [ai_random.choice(["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]) for _ in range(3)]
    
    if c1 == c2 == c3:
        if c1 == "7️⃣":
            win = jp + bao_bonus
            HybridBalanceManager.add_bal(uid, win, "nohu_jackpot")
            HybridNohuManager.update_jp(100000, "reset")
            out = f"🎉 JACKPOT! +{win:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
        else:
            win = bet * 5 + bao_bonus
            HybridBalanceManager.add_bal(uid, win, "nohu_win")
            out = f"🎉 Nổ! +{win:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
    elif c1 == c2 or c2 == c3 or c1 == c3:
        win = int(bet * 0.5)
        HybridBalanceManager.add_bal(uid, win, "nohu_refund")
        out = f"🤏 Hoàn {win:,} xu"
    else:
        out = f"💔 Thua -{total:,} xu"
    
    m2 = bot.reply_to(m,
        f"🎰 <b>NỔ HŨ</b>\n━━━━━━━━━━━━━━━━━━━━\n{c1}{c2}{c3}\n{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n💰 JP: {HybridNohuManager.get_jp():,} xu\n"
        f"💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

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

@bot.message_handler(commands=['give'])
def give(m):
    if not is_grp(m): return
    uid = m.from_user.id
    target = None; amt = 0
    
    if m.reply_to_message:
        target = m.reply_to_message.from_user.id
        parts = m.text.split()
        try: amt = int(parts[1]) if len(parts) > 1 else 0
        except: pass
    else:
        parts = m.text.split()
        if len(parts) > 2:
            if parts[1].startswith('@'):
                try: target = bot.get_chat_member(m.chat.id, parts[1]).user.id
                except: pass
            elif parts[1].isdigit(): target = int(parts[1])
            try: amt = int(parts[2])
            except: pass
    
    if not target or amt < 100:
        m2 = bot.reply_to(m,
            "❌ <b>Cách dùng:</b>\n• /give [số xu] (reply)\n"
            "• /give @username [số xu]\n• /give [user_id] [số xu]\n"
            "💵 Tối thiểu: 100 xu\n💸 Phí: 5%",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    if target == uid:
        m2 = bot.reply_to(m, "❌ Không thể tự chuyển cho mình!")
        del_both(m, m2.message_id)
        return
    
    fee = int(amt * 0.05); total = amt + fee
    
    if not HybridBalanceManager.deduct_bal(uid, total, "transfer_out"):
        m2 = bot.reply_to(m,
            f"❌ Không đủ xu!\n💰 Cần: {total:,} xu (gồm {fee:,} phí)\n"
            f"💰 Số dư: {HybridBalanceManager.get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    HybridBalanceManager.add_bal(target, amt, "transfer_in")
    target_name = HybridUserManager.get_user(target) or str(target)
    m2 = bot.reply_to(m,
        f"✅ <b>CHUYỂN XU</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 {amt:,} xu → {html.escape(target_name)}\n"
        f"💵 Phí: {fee:,} xu\n💰 Số dư: <b>{HybridBalanceManager.get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT                                                   ║
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
# ║                    ANTISPAM                                                 ║
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
# ║                    HANDLERS                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m): return
    HybridUserManager.set_user(m.from_user.id, m.from_user.first_name)
    
    help_text = (
        f"🤖 <b>NAO ROBOT V7.0 - API-DRIVEN</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Mode: {'🟢 API ONLINE' if not APIClient.OFFLINE_MODE else '🔴 LOCAL OFFLINE'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>18 GAMES BÃO X10:</b>\n"
        "/taixiu /baucua /kbb /doanso /lxn /xx\n"
        "/chanle /caothap /doanso2 /keo /bingo\n"
        "/rongho /chanle2 /3cay /slot /bauslot /doanso3\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎰 /nohu | 📅 /daily | 💰 /balance\n"
        "🏆 /top | 💸 /give\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ V7.0 - API Ưu Tiên | Local Fallback | Auto Sync"
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
        f"👥 Users: {HybridUserManager.get_user_count()}\n"
        f"👥 Group: {rc}\n"
        f"📡 API: {'🟢 Online' if not APIClient.OFFLINE_MODE else '🔴 Offline'}\n"
        f"🎮 Game sessions: {len(GAME_SESSIONS)}\n"
        f"🧹 RAM cleans: {ram_mgr.cleans}\n"
        f"🧵 Threads: {threading.active_count()}\n"
        f"📮 Voice queue: {voice_queue.qsize()}/{voice_queue.maxsize}",
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

@bot.message_handler(commands=['sync'])
def sync_cmd(m):
    if not is_grp(m) or not is_adm(m): return
    
    if APIClient.OFFLINE_MODE:
        m2 = bot.reply_to(m, "❌ API đang offline, không thể đồng bộ!")
        del_both(m, m2.message_id)
        return
    
    m2 = bot.reply_to(m, "🔄 Đang đồng bộ dữ liệu local → API...")
    
    def do_sync():
        sync_local_to_api()
        bot.send_message(m.chat.id, "✅ Đồng bộ hoàn tất!")
    
    Thread(target=do_sync, daemon=True).start()
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

def cleanup_game_sessions():
    while True:
        time.sleep(300)
        try:
            now = time.time()
            with lock:
                to_del = [uid for uid, g in GAME_SESSIONS.items()
                         if now - g.get('last_active', g.get('start', 0)) > GAME_SESSION_TIMEOUT]
                for uid in to_del: del GAME_SESSIONS[uid]
        except Exception as e:
            logger.error(f"Game cleanup error: {e}")

def scheduler():
    """Scheduler đơn giản."""
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
# ║                    MAIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    logger.info("="*60)
    logger.info("NAO ROBOT V7.0 STARTING...")
    logger.info(f"API Server: {APIClient.BASE_URL}")
    logger.info("Architecture: API-First | Local Fallback | Auto Sync")
    logger.info("="*60)
    
    # Kiểm tra API
    APIClient.health_check()
    if APIClient.OFFLINE_MODE:
        logger.warning("API offline, using local storage")
    else:
        logger.info("API connected successfully")
    
    ram_mgr.start()
    
    Thread(target=cleanup_spam_dict, daemon=True, name="SpamCleanup").start()
    Thread(target=cleanup_game_sessions, daemon=True, name="GameCleanup").start()
    Thread(target=scheduler, daemon=True, name="Scheduler").start()
    Thread(target=api_health_monitor, daemon=True, name="APIHealthMonitor").start()
    
    logger.info("All systems ready. Starting bot polling...")
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
