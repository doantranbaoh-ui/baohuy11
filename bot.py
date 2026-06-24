# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - AI RAM MANAGER                           │
# │  AI tự động dọn dẹp 90% bộ nhớ - Chống tràn RAM - Tối ưu hiệu suất     │
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
    from keep_alive import keep_alive
    keep_alive()
except ImportError:
    pass

# ─── THƯ VIỆN NGOÀI ───────────────────────────────────────────────────────
import telebot
from telebot import types, util
import requests
import pytz

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
# ║  AI RAM MANAGER - QUẢN LÍ BỘ NHỚ THÔNG MINH                ║
# ╚══════════════════════════════════════════════════════════════╝

class MemoryUnit(Enum):
    BYTES = 1
    KB = 1024
    MB = 1024 ** 2
    GB = 1024 ** 3

@dataclass
class MemorySnapshot:
    """Ảnh chụp trạng thái bộ nhớ tại một thời điểm."""
    timestamp: float
    rss: int           # Resident Set Size (RAM thực)
    vms: int           # Virtual Memory Size
    cpu_percent: float
    thread_count: int
    open_files: int
    gc_objects: int

class AIRamManager:
    """
    AI quản lí RAM - Tự động giám sát, phân tích và dọn dẹp bộ nhớ.
    
    Nguyên lí hoạt động:
    1. Giám sát liên tục mức sử dụng RAM (mỗi 30s)
    2. Phân tích xu hướng tăng trưởng bộ nhớ bằng AI đơn giản
    3. Khi RAM vượt ngưỡng -> tự động dọn dẹp theo cấp độ
    4. Ghi log và cảnh báo khi phát hiện memory leak
    5. Tối ưu cache, session, thread pool định kỳ
    """
    
    # Ngưỡng RAM (bytes) - 90% là mục tiêu dọn dẹp
    WARNING_THRESHOLD = 0.70   # Cảnh báo ở 70%
    CLEAN_LIGHT = 0.75         # Dọn nhẹ ở 75%
    CLEAN_MEDIUM = 0.82        # Dọn vừa ở 82%
    CLEAN_AGGRESSIVE = 0.90    # Dọn mạnh ở 90% (MỤC TIÊU)
    CRITICAL = 0.95            # Khẩn cấp ở 95%
    
    def __init__(self, max_ram_mb: int = 512):
        self.max_ram_bytes = max_ram_mb * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.snapshots: deque = deque(maxlen=100)
        self.last_clean_time: float = 0
        self.clean_cooldown: float = 30  # Giây giữa các lần dọn
        self.total_cleaned_bytes: int = 0
        self.clean_count: int = 0
        self.leak_warnings: int = 0
        self.is_cleaning: bool = False
        self.clean_lock = Lock()
        
        # Cache thông minh với TTL
        self.smart_cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl: float = 300  # 5 phút mặc định
        
        # Weak references để tránh memory leak
        self.weak_refs: List[weakref.ref] = []
        
        # Thread pool thông minh - tự co giãn
        self.active_threads: int = 0
        self.max_threads: int = 50
        self.idle_threads: int = 0
        
        logger.info(f"🧠 AI RAM Manager khởi tạo. Max RAM: {max_ram_mb}MB")

    def get_current_memory(self) -> MemorySnapshot:
        """Lấy ảnh chụp bộ nhớ hiện tại."""
        try:
            mem_info = self.process.memory_info()
            cpu = self.process.cpu_percent(interval=0.1)
            threads = self.process.num_threads()
            open_files = len(self.process.open_files()) if hasattr(self.process, 'open_files') else 0
            gc_objects = len(gc.get_objects())
            
            return MemorySnapshot(
                timestamp=time.time(),
                rss=mem_info.rss,
                vms=mem_info.vms,
                cpu_percent=cpu,
                thread_count=threads,
                open_files=open_files,
                gc_objects=gc_objects
            )
        except Exception as e:
            logger.error(f"Lỗi lấy memory snapshot: {e}")
            return MemorySnapshot(time.time(), 0, 0, 0, 0, 0, 0)

    def get_memory_usage_percent(self) -> float:
        """Phần trăm RAM đã sử dụng so với giới hạn."""
        snapshot = self.get_current_memory()
        return snapshot.rss / self.max_ram_bytes

    def get_memory_mb(self) -> float:
        """RAM hiện tại tính bằng MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def analyze_trend(self) -> str:
        """AI phân tích xu hướng tăng trưởng RAM."""
        if len(self.snapshots) < 3:
            return "stable"
        
        recent = list(self.snapshots)[-5:]
        rss_values = [s.rss for s in recent]
        
        if len(rss_values) < 3:
            return "stable"
        
        # Tính tốc độ tăng (bytes/giây)
        time_diff = recent[-1].timestamp - recent[0].timestamp
        if time_diff <= 0:
            return "stable"
        
        mem_diff = rss_values[-1] - rss_values[0]
        growth_rate = mem_diff / time_diff  # bytes/second
        
        if growth_rate > 1024 * 1024:  # > 1MB/s
            return "critical_growth"
        elif growth_rate > 512 * 1024:  # > 512KB/s
            return "rapid_growth"
        elif growth_rate > 100 * 1024:  # > 100KB/s
            return "slow_growth"
        else:
            return "stable"

    def smart_cache_get(self, key: str) -> Optional[Any]:
        """Lấy từ cache thông minh (có TTL)."""
        if key in self.smart_cache:
            value, expiry = self.smart_cache[key]
            if time.time() < expiry:
                return value
            else:
                del self.smart_cache[key]
        return None

    def smart_cache_set(self, key: str, value: Any, ttl: float = None):
        """Lưu vào cache thông minh."""
        if ttl is None:
            ttl = self.cache_ttl
        self.smart_cache[key] = (value, time.time() + ttl)
        # Nếu cache quá lớn (>1000 entries), xóa 30% cũ nhất
        if len(self.smart_cache) > 1000:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            for k, _ in sorted_entries[:300]:
                del self.smart_cache[k]

    def register_weak_ref(self, obj: Any):
        """Đăng ký weak reference để tránh memory leak."""
        self.weak_refs.append(weakref.ref(obj))
        # Dọn weak refs đã chết
        self.weak_refs = [ref for ref in self.weak_refs if ref() is not None]

    # ═══════════════════════════════════════════════════════════
    # CÁC CẤP ĐỘ DỌN DẸP
    # ═══════════════════════════════════════════════════════════

    def clean_level_1(self) -> int:
        """Dọn nhẹ (Light Clean): Clear cache hết hạn + gc collect thế hệ 0."""
        freed = 0
        
        # Xóa cache hết hạn
        now = time.time()
        expired_keys = [k for k, (v, exp) in self.smart_cache.items() if now >= exp]
        for k in expired_keys:
            del self.smart_cache[k]
        freed += len(expired_keys) * 100  # Ước tính
        
        # Xóa weak refs chết
        old_len = len(self.weak_refs)
        self.weak_refs = [ref for ref in self.weak_refs if ref() is not None]
        freed += (old_len - len(self.weak_refs)) * 50
        
        # GC thế hệ 0 (nhanh nhất)
        collected = gc.collect(0)
        freed += collected * 200
        
        logger.info(f"🧹 Clean Level 1: ~{freed/1024:.1f}KB freed, {len(expired_keys)} cache entries")
        return freed

    def clean_level_2(self) -> int:
        """Dọn vừa (Medium Clean): Level 1 + GC full + xóa 50% cache."""
        freed = self.clean_level_1()
        
        # GC toàn bộ
        collected = gc.collect(2)
        freed += collected * 200
        
        # Xóa 50% cache cũ nhất (giữ lại cache quan trọng)
        if len(self.smart_cache) > 100:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            remove_count = len(self.smart_cache) // 2
            for k, _ in sorted_entries[:remove_count]:
                del self.smart_cache[k]
            freed += remove_count * 100
        
        # Giải phóng các object không dùng
        gc.garbage.clear()
        
        logger.info(f"🧹🧹 Clean Level 2: ~{freed/1024:.1f}KB freed")
        return freed

    def clean_level_3(self) -> int:
        """Dọn mạnh (Aggressive Clean - 90%): Level 2 + xóa 80% cache + reset thread pool."""
        freed = self.clean_level_2()
        
        # Xóa 80% cache
        if self.smart_cache:
            sorted_entries = sorted(self.smart_cache.items(), key=lambda x: x[1][1])
            remove_count = int(len(self.smart_cache) * 0.8)
            for k, _ in sorted_entries[:remove_count]:
                del self.smart_cache[k]
            freed += remove_count * 100
        
        # Giới hạn thread pool
        self.max_threads = max(20, self.max_threads - 10)
        
        # Giải phóng memory bằng C malloc_trim (Linux)
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
            freed += 1024 * 1024  # Ước tính 1MB
        except:
            pass
        
        # Force garbage collection
        for _ in range(3):
            gc.collect(2)
        
        gc.garbage.clear()
        
        logger.warning(f"🧹🧹🧹 Clean Level 3 (90%): ~{freed/1024/1024:.1f}MB freed")
        return freed

    def clean_level_critical(self) -> int:
        """Dọn khẩn cấp (Critical - 95%): Level 3 + reset toàn bộ cache + restart nhẹ."""
        freed = self.clean_level_3()
        
        # Xóa toàn bộ cache
        cache_size = len(self.smart_cache)
        self.smart_cache.clear()
        freed += cache_size * 100
        
        # Reset thread pool về mức tối thiểu
        self.max_threads = 20
        
        # Giải phóng toàn bộ weak refs
        self.weak_refs.clear()
        
        # Gọi malloc_trim mạnh
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except:
            pass
        
        # GC nhiều lần
        for _ in range(5):
            gc.collect(2)
        
        gc.garbage.clear()
        
        logger.critical(f"🚨 Clean CRITICAL: ~{freed/1024/1024:.1f}MB freed")
        return freed

    # ═══════════════════════════════════════════════════════════
    # AI QUYẾT ĐỊNH DỌN DẸP
    # ═══════════════════════════════════════════════════════════

    def ai_decide_clean(self) -> Tuple[int, str]:
        """
        AI phân tích và quyết định mức độ dọn dẹp.
        Trả về (bytes_freed, action_description).
        """
        with self.clean_lock:
            if self.is_cleaning:
                return 0, "already_cleaning"
            
            # Kiểm tra cooldown
            if time.time() - self.last_clean_time < self.clean_cooldown:
                return 0, "cooldown"
            
            self.is_cleaning = True
            
            try:
                usage_percent = self.get_memory_usage_percent()
                trend = self.analyze_trend()
                current_mb = self.get_memory_mb()
                
                # AI quyết định dựa trên % RAM + xu hướng
                if usage_percent >= self.CRITICAL:
                    logger.critical(f"🚨 RAM {usage_percent*100:.1f}% - DỌN KHẨN CẤP!")
                    freed = self.clean_level_critical()
                    action = "critical_clean"
                elif usage_percent >= self.CLEAN_AGGRESSIVE:
                    logger.warning(f"⚠️ RAM {usage_percent*100:.1f}% - DỌN MẠNH 90%!")
                    freed = self.clean_level_3()
                    action = "aggressive_clean"
                elif usage_percent >= self.CLEAN_MEDIUM:
                    logger.info(f"📊 RAM {usage_percent*100:.1f}% - DỌN VỪA")
                    freed = self.clean_level_2()
                    action = "medium_clean"
                elif usage_percent >= self.CLEAN_LIGHT:
                    logger.info(f"📉 RAM {usage_percent*100:.1f}% - DỌN NHẸ")
                    freed = self.clean_level_1()
                    action = "light_clean"
                elif trend in ["rapid_growth", "critical_growth"]:
                    logger.warning(f"📈 Phát hiện memory leak! RAM {usage_percent*100:.1f}% - DỌN CHỦ ĐỘNG")
                    freed = self.clean_level_2()
                    action = "leak_prevention"
                    self.leak_warnings += 1
                else:
                    # RAM ổn định, chỉ GC nhẹ
                    gc.collect(0)
                    freed = 0
                    action = "stable_no_clean"
                
                self.last_clean_time = time.time()
                self.total_cleaned_bytes += freed
                self.clean_count += 1
                
                return freed, action
            finally:
                self.is_cleaning = False

    def monitor_loop(self):
        """Vòng lặp giám sát RAM liên tục."""
        while True:
            try:
                snapshot = self.get_current_memory()
                self.snapshots.append(snapshot)
                
                usage_percent = self.get_memory_usage_percent()
                
                # Luôn dọn nếu vượt ngưỡng
                if usage_percent >= self.WARNING_THRESHOLD:
                    freed, action = self.ai_decide_clean()
                    
                    if action not in ["stable_no_clean", "cooldown", "already_cleaning"]:
                        logger.info(
                            f"📊 RAM: {self.get_memory_mb():.1f}MB/{self.max_ram_bytes/1024/1024:.0f}MB "
                            f"({usage_percent*100:.1f}%) | Action: {action} | "
                            f"Freed: {freed/1024/1024:.2f}MB"
                        )
                
                # Ghi log định kỳ mỗi 5 phút
                if random.random() < 0.03:  # ~5 phút 1 lần
                    logger.info(
                        f"💾 RAM Status: {self.get_memory_mb():.1f}MB | "
                        f"Cache: {len(self.smart_cache)} | "
                        f"Threads: {self.active_threads} | "
                        f"GC Objects: {snapshot.gc_objects}"
                    )
                
            except Exception as e:
                logger.error(f"Lỗi monitor RAM: {e}")
            
            time.sleep(30)  # Kiểm tra mỗi 30 giây

    def start_monitoring(self):
        """Khởi động giám sát RAM trong thread riêng."""
        monitor_thread = Thread(target=self.monitor_loop, daemon=True, name="AIRamMonitor")
        monitor_thread.start()
        logger.info("🧠 AI RAM Monitor đã khởi động (kiểm tra mỗi 30s)")

# Khởi tạo AI RAM Manager toàn cục
ram_manager = AIRamManager(max_ram_mb=512)

# ╔══════════════════════════════════════════════════════════════╗
# ║  NÃO (BRAIN) - TÍCH HỢP RAM MANAGER                        ║
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
            "errors": 0, "votes_created": 0, "voice_generated": 0,
            "files_processed": 0, "daily_checkins": 0, "nohu_spins": 0,
            "games_played": 0, "ram_cleans": 0, "ram_freed_mb": 0.0,
            "uptime_start": time.time(), "last_save": time.time()
        }
        self.decision_log: deque = deque(maxlen=200)
        self.last_health_check: float = time.time()
        self.repair_mode: bool = False
        self.file_lock = Lock()
        self.load_state()

    def load_state(self):
        if os.path.exists(self.save_path):
            try:
                with open(self.save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.learned = defaultdict(int, data.get("learned", {}))
                    self.banned_words = set(data.get("banned", []))
                    self.trusted_users = set(data.get("trusted", []))
                    saved = data.get("stats", {})
                    self.stats.update(saved)
                    self.stats["uptime_start"] = self.stats.get("uptime_start", time.time())
                    self.state = data.get("state", "normal")
                    self.mood = data.get("mood", 0)
            except: pass

    def save_state(self):
        with self.file_lock:
            self.stats["last_save"] = time.time()
            self.stats["ram_cleans"] = ram_manager.clean_count
            self.stats["ram_freed_mb"] = ram_manager.total_cleaned_bytes / (1024 * 1024)
            try:
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump({"learned": dict(self.learned), "banned": list(self.banned_words),
                               "trusted": list(self.trusted_users), "stats": self.stats,
                               "state": self.state, "mood": self.mood}, f, ensure_ascii=False, indent=2)
            except: self.stats["errors"] += 1

    def think(self, context: dict) -> str:
        uid = context.get("uid"); txt = context.get("txt", "")
        self.stats["msg_processed"] += 1
        words = re.findall(r'\b\w{3,}\b', txt.lower())
        for w in words: self.learned[w] += 1
        neg = ["bot ngu", "bot dở", "bot lỗi", "mày ngu"]
        pos = ["bot hay", "bot pro", "cảm ơn bot", "bot tốt"]
        if any(p in txt.lower() for p in neg): self.mood -= 2
        elif any(p in txt.lower() for p in pos): self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"
        self.decision_log.append({"time": datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S"),
                                  "uid": uid, "decision": self.state, "mood": self.mood})
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
            # Tích hợp kiểm tra RAM vào health check
            ram_usage = ram_manager.get_memory_usage_percent()
            if ram_usage >= ram_manager.CLEAN_AGGRESSIVE:
                ram_manager.ai_decide_clean()
            if self.stats["errors"] > 20:
                self.repair_mode = True; self.state = "repair"; self.stats["errors"] = 0
                return "repair"
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

# Thread pools với giới hạn RAM
ai_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="AI")
voice_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Voice")
file_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="File")
game_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="Game")

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI KEYS                                                   ║
# ╚══════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {"key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3", "url": "https://api.byesu.com/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0},
    {"key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034", "url": "https://api.freemodel.dev/v1/chat/completions", "model": "gpt-4o", "status": True, "fail": 0, "last_used": 0}
]
MAX_FAIL = 3; ck_idx = 0; ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════╗
# ║  KHO CHỬI + BIẾN TOÀN CỤC                                  ║
# ╚══════════════════════════════════════════════════════════════╝
KHO_NORMAL = ["Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.", "Cào phím nhanh, não chậm.", "Ảo tưởng sức mạnh.", "Về nhà rửa bát.", "IQ âm, đừng nói.", "Không ai cần mày.", "Mày là gì? Không là gì.", "Câm mồm, đỡ nhục."]
KHO_HIGH = ["Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?", "Ra đời người ta vả cho.", "Mẹ gọi, về nhà đi.", "Tưởng mình ngầu? Hề vãi.", "Học không lo, cào phím giỏi.", "Tương lai mù mịt như chị Dậu.", "Đời vả mặt, mày cười ngây.", "Không có gì để nói với mày."]
KHO_EXTREME = ["Mày đáng giá bằng cái nút block.", "Tồn tại để làm gì? Để tao chửi à?", "Não mày như ổ đĩa format nhầm.", "Mày là lỗi của tự nhiên.", "Tao chửi mày còn thấy phí thời gian.", "Mày không đáng để tao nhớ tên.", "Cút về lỗ mà mày chui ra.", "Mày là minh chứng cho thất bại của tiến hóa.", "Tao nhìn mày mà tưởng đang xem phim hài.", "Mày sống làm gì?"]
def get_kho():
    lvl = brain.get_insult_level()
    if lvl == "extreme": return KHO_EXTREME
    elif lvl == "high": return KHO_HIGH
    return KHO_NORMAL

lock = Lock(); mem = deque(maxlen=50)
users: Dict[str, str] = {}
spam: Dict[int, List[float]] = {}
warn_counts: Dict[int, int] = {}
mutes: Dict[int, float] = {}
ai_cd: Dict[int, float] = {}
vote_active: Dict[int, Dict] = {}
file_cache: Dict[str, Dict] = {}
user_balance: Dict[int, int] = {}
daily_checkin: Dict[int, str] = {}
nohu_jackpot: int = 0
nohu_history: deque = deque(maxlen=20)
nohu_base = 100000; nohu_fee = 1000; nohu_multiplier = 0.05; nohu_last_reset = time.time()
member_stats: Dict[str, Any] = {"daily_join": defaultdict(int), "daily_leave": defaultdict(int), "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}, "last_updated": time.time()}
GAME_SESSIONS: Dict[int, Dict] = {}
AI_GENERATED_GAMES: Dict[str, Dict] = {}
GAME_LEADERBOARDS: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
GAME_ACHIEVEMENTS: Dict[int, List[str]] = defaultdict(list)

BALANCE_FILE = "balances.json"; DAILY_FILE = "daily_checkins.json"
JACKPOT_FILE = "jackpot.json"; GAMES_FILE = "ai_games.json"
LEADERBOARD_FILE = "leaderboards.json"
USR_FILE = "usr.json"; STATS_FILE = "member_stats.json"; RULES_FILE = "rules.txt"
MAX_FILE_SIZE = 20 * 1024 * 1024; MAX_CACHE_SIZE = 50
TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}', re.I)

# ╔══════════════════════════════════════════════════════════════╗
# ║  TIỆN ÍCH CHUNG (TÍCH HỢP SMART CACHE)                     ║
# ╚══════════════════════════════════════════════════════════════╝
def load_json(path: str, default: Any = {}) -> Any:
    cached = ram_manager.smart_cache_get(f"json_{path}")
    if cached is not None:
        return cached
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                ram_manager.smart_cache_set(f"json_{path}", data, 60)  # Cache 60s
                return data
        except: pass
    return default

def save_json(path: str, data: Any) -> None:
    with lock:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            ram_manager.smart_cache_set(f"json_{path}", data, 60)
        except Exception as e: logger.error(f"Lỗi save {path}: {e}")

def load_users() -> Dict[str, str]: return load_json(USR_FILE, {})
def save_users(data: Dict[str, str]): save_json(USR_FILE, data)
def load_balances() -> Dict[int, int]:
    data = load_json(BALANCE_FILE, {})
    return {int(k): v for k, v in data.items()}
def save_balances(data: Dict[int, int]): save_json(BALANCE_FILE, {str(k): v for k, v in data.items()})
def load_daily_checkins() -> Dict[int, str]:
    data = load_json(DAILY_FILE, {})
    return {int(k): v for k, v in data.items()}
def save_daily_checkins(data: Dict[int, str]): save_json(DAILY_FILE, {str(k): v for k, v in data.items()})
def load_jackpot() -> int:
    data = load_json(JACKPOT_FILE, {"jackpot": nohu_base, "history": []})
    return data.get("jackpot", nohu_base)
def save_jackpot(jackpot: int): save_json(JACKPOT_FILE, {"jackpot": jackpot, "history": list(nohu_history), "last_reset": nohu_last_reset})
def load_member_stats() -> Dict:
    data = load_json(STATS_FILE, {"daily_join": {}, "daily_leave": {}, "total_joined": 0, "total_left": 0, "current_members": 0, "join_dates": {}, "last_updated": time.time()})
    data["daily_join"] = defaultdict(int, data.get("daily_join", {}))
    data["daily_leave"] = defaultdict(int, data.get("daily_leave", {}))
    return data
def save_member_stats():
    data = dict(member_stats)
    data["daily_join"] = dict(data["daily_join"]); data["daily_leave"] = dict(data["daily_leave"])
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
                m = re.match(r'@(\w+)', arg)
                if m:
                    try: target = bot.get_chat_member(message.chat.id, m.group(0)).user.id; reason = arg[m.end():].strip()
                    except: pass
                else:
                    nm = re.search(r'\d+', arg)
                    if nm: target = int(nm.group()); reason = arg[nm.end():].strip()
    return target, reason

def parse_duration(reason: str) -> int:
    m = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if m:
        num = int(m.group(1)); unit = m.group(2)
        if unit == 's': return num
        elif unit == 'm': return num * 60
        elif unit == 'h': return num * 3600
        elif unit == 'p': return num * 60
    return 3600

def get_user_balance(uid: int) -> int:
    if uid not in user_balance: user_balance[uid] = 5000; save_balances(user_balance)
    return user_balance[uid]

def add_balance(uid: int, amount: int) -> int:
    bal = get_user_balance(uid)
    user_balance[uid] = max(0, bal + amount)
    save_balances(user_balance)
    return user_balance[uid]

def deduct_balance(uid: int, amount: int) -> bool:
    bal = get_user_balance(uid)
    if bal >= amount: user_balance[uid] = bal - amount; save_balances(user_balance); return True
    return False

# ╔══════════════════════════════════════════════════════════════╗
# ║  LỆNH QUẢN LÍ RAM - /ramstatus                             ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['ramstatus', 'memory', 'ram'])
def ram_status_cmd(m):
    """Xem trạng thái RAM và thống kê dọn dẹp."""
    if not is_grp(m) and m.from_user.id != ADMIN_ID: return
    
    snapshot = ram_manager.get_current_memory()
    usage_pct = ram_manager.get_memory_usage_percent()
    
    # Tạo biểu đồ RAM đơn giản
    bar_len = 20
    filled = int(usage_pct * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    text = (
        f"🧠 <b>AI RAM MANAGER STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 RAM: <b>{ram_manager.get_memory_mb():.1f}MB</b> / {ram_manager.max_ram_bytes/1024/1024:.0f}MB\n"
        f"📈 [{bar}] <b>{usage_pct*100:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 Số lần dọn: <b>{ram_manager.clean_count}</b>\n"
        f"💾 Tổng RAM đã giải phóng: <b>{ram_manager.total_cleaned_bytes/1024/1024:.2f}MB</b>\n"
        f"⚠️ Cảnh báo leak: <b>{ram_manager.leak_warnings}</b>\n"
        f"📦 Cache entries: <b>{len(ram_manager.smart_cache)}</b>\n"
        f"🧵 Threads: <b>{snapshot.thread_count}</b>\n"
        f"🗑️ GC Objects: <b>{snapshot.gc_objects:,}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Xu hướng: <b>{ram_manager.analyze_trend()}</b>\n"
        f"⏱️ Lần dọn cuối: <b>{datetime.fromtimestamp(ram_manager.last_clean_time).strftime('%H:%M:%S') if ram_manager.last_clean_time > 0 else 'Chưa'}</b>"
    )
    msg = bot.reply_to(m, text, parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 45)

@bot.message_handler(commands=['clearcache', 'dondep'])
def clear_cache_cmd(m):
    """Lệnh dọn dẹp thủ công (admin only)."""
    if not is_admin(m.chat.id, m.from_user.id) and m.from_user.id != ADMIN_ID:
        return
    
    status_msg = bot.reply_to(m, "🧹 Đang dọn dẹp bộ nhớ...", parse_mode="HTML")
    
    def _clean():
        freed, action = ram_manager.ai_decide_clean()
        try: bot.delete_message(m.chat.id, status_msg.message_id)
        except: pass
        
        text = (
            f"✅ <b>DỌN DẸP HOÀN TẤT</b>\n"
            f"🎯 Hành động: <b>{action}</b>\n"
            f"💾 RAM giải phóng: <b>{freed/1024/1024:.2f}MB</b>\n"
            f"📊 RAM hiện tại: <b>{ram_manager.get_memory_mb():.1f}MB</b>\n"
            f"📦 Cache còn: <b>{len(ram_manager.smart_cache)}</b> entries"
        )
        msg = bot.reply_to(m, text, parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 30)
    
    Thread(target=_clean, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  GOOGLE TTS + GAMES + ĐIỂM DANH + NỔ HŨ + QUẢN LÍ         ║
# ╚══════════════════════════════════════════════════════════════╝

# ─── GOOGLE TTS ──────────────────────────────────────────────────────────
GOOGLE_TTS_URL = "https://translate.google.com/translate_tts"
GOOGLE_TTS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "audio/mpeg, audio/*;q=0.9", "Referer": "https://translate.google.com/"}
MAX_CHUNK_SIZE = 180

@dataclass
class VoiceRequest:
    chat_id: int; reply_id: int; text: str; user_name: str; lang: str = "vi"
    created_at: float = field(default_factory=time.time)

voice_queue: Queue = Queue(maxsize=50)

def fetch_google_tts_chunk(text: str, lang: str = "vi") -> Optional[bytes]:
    params = {"ie": "UTF-8", "q": text, "tl": lang, "total": "1", "idx": "0", "textlen": str(len(text)), "client": "tw-ob", "prev": "input", "ttsspeed": "1.0"}
    try:
        resp = ses.get(GOOGLE_TTS_URL, params=params, headers=GOOGLE_TTS_HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100: return resp.content
    except: pass
    return None

def split_text_into_chunks(text: str, max_size: int = MAX_CHUNK_SIZE) -> List[str]:
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

def generate_voice_google(text: str, lang: str = "vi") -> Tuple[Optional[BytesIO], str]:
    clean_text = re.sub(r'[<>"\'{}|\\^~\[\]`]', '', text).strip()
    if not clean_text: return None, "Text rỗng."
    chunks = split_text_into_chunks(clean_text); audio_chunks = []
    for chunk in chunks:
        audio = fetch_google_tts_chunk(chunk, lang)
        if audio: audio_chunks.append(audio)
    if not audio_chunks: return None, "Không thể tạo audio."
    return BytesIO(b"".join(audio_chunks)), "ok"

def voice_worker():
    while True:
        try:
            req: VoiceRequest = voice_queue.get(block=True, timeout=1)
            if not req: continue
            voice_text = req.text[:500].strip()
            if not voice_text: voice_queue.task_done(); continue
            audio, result_msg = generate_voice_google(voice_text, req.lang)
            if audio and result_msg == "ok":
                audio.name = f"voice_{int(time.time())}.mp3"
                try: bot.send_voice(req.chat_id, audio, reply_to_message_id=req.reply_id, caption=f"🎙️ {html.escape(voice_text[:200])}", parse_mode="HTML"); brain.stats["voice_generated"] += 1
                except:
                    audio.seek(0)
                    try: bot.send_audio(req.chat_id, audio, reply_to_message_id=req.reply_id, title="Voice", caption=f"🎙️ {html.escape(voice_text[:200])}", parse_mode="HTML"); brain.stats["voice_generated"] += 1
                    except: pass
            else:
                try: bot.send_message(req.chat_id, f"❌ {html.escape(req.user_name)}, không thể tạo giọng nói.\n<i>{result_msg}</i>", reply_to_message_id=req.reply_id, parse_mode="HTML")
                except: pass
            voice_queue.task_done()
        except:
            try: voice_queue.task_done()
            except: pass

for _ in range(4): Thread(target=voice_worker, daemon=True).start()

@bot.message_handler(commands=['voice'])
def voice_cmd(m):
    if not is_grp(m) or antispam(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    voice_text = ""
    if m.reply_to_message and m.reply_to_message.text: voice_text = m.reply_to_message.text.strip()
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1: voice_text = parts[1].strip()
    if not voice_text: msg = bot.reply_to(m, "❌ /voice [text] hoặc reply.", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 10); return
    if len(voice_text) > 500: voice_text = voice_text[:500]
    try:
        voice_queue.put_nowait(VoiceRequest(chat_id=m.chat.id, reply_id=m.message_id, text=voice_text, user_name=m.from_user.first_name))
        msg = bot.reply_to(m, "🎙️ Đang tạo voice...", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 5)
    except: bot.reply_to(m, "⚠️ Hàng đợi voice đầy.", parse_mode="HTML")

# ─── ĐIỂM DANH ──────────────────────────────────────────────────────────
def get_daily_reward(uid: int, consecutive_days: int = 1) -> int:
    return 500 + min(consecutive_days - 1, 6) * 200

@bot.message_handler(commands=['daily', 'diemdanh', 'checkin'])
def daily_checkin_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid = m.from_user.id; today = date.today().isoformat()
    users[str(uid)] = m.from_user.first_name; save_users(users)
    last_checkin = daily_checkin.get(uid, ""); yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last_checkin == today:
        bal = get_user_balance(uid)
        msg = bot.reply_to(m, f"❌ <b>{html.escape(m.from_user.first_name)}</b>, hôm nay đã điểm danh rồi!\n💰 Số dư: <b>{bal:,}</b> xu", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 15); return
    
    consecutive = 1
    if last_checkin == yesterday:
        d = date.today() - timedelta(days=1)
        for i in range(1, 7):
            if daily_checkin.get(uid) == (d - timedelta(days=i)).isoformat(): consecutive += 1
            else: break
    
    reward = get_daily_reward(uid, consecutive)
    daily_checkin[uid] = today; save_daily_checkins(daily_checkin); add_balance(uid, reward); brain.stats["daily_checkins"] += 1
    streak_emoji = ["", "🔥", "🔥🔥", "💥", "💥💥", "⚡", "👑"][min(consecutive-1, 6)] if consecutive > 1 else ""
    msg = bot.reply_to(m, f"✅ <b>ĐIỂM DANH!</b>\n👤 <b>{html.escape(m.from_user.first_name)}</b>\n💰 +{reward:,} xu | 📅 Chuỗi: <b>{consecutive}</b> ngày {streak_emoji}\n💎 Số dư: <b>{get_user_balance(uid):,}</b> xu", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(commands=['balance', 'xu', 'money'])
def balance_cmd(m):
    if not is_grp(m): return
    uid = m.from_user.id; users[str(uid)] = m.from_user.first_name; save_users(users)
    target = uid; target_name = m.from_user.first_name
    if m.reply_to_message: target = m.reply_to_message.from_user.id; target_name = m.reply_to_message.from_user.first_name
    bal = get_user_balance(target)
    msg = bot.reply_to(m, f"💎 <b>{html.escape(target_name)}</b> có <b>{bal:,}</b> xu.", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 20)

# ─── NỔ HŨ ──────────────────────────────────────────────────────────────
SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
SLOT_WEIGHTS = [30, 25, 20, 15, 5, 3, 2]
SLOT_PAYOUTS = {"🍒🍒🍒": 5, "🍋🍋🍋": 8, "🍊🍊🍊": 12, "🍇🍇🍇": 20, "💎💎💎": 50, "🔔🔔🔔": 100, "7️⃣7️⃣7️⃣": 500}

@bot.message_handler(commands=['nohu', 'slot', 'quay'])
def nohu_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid = m.from_user.id; users[str(uid)] = m.from_user.first_name; save_users(users)
    parts = m.text.split()
    if len(parts) < 2:
        jackpot = load_jackpot()
        msg = bot.reply_to(m, f"🎰 <b>NỔ HŨ</b>\n💰 JACKPOT: <b>{jackpot:,}</b> xu\n🎮 /nohu [cược] (Phí: {nohu_fee:,} xu)", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 20); return
    try: bet = int(parts[1])
    except: msg = bot.reply_to(m, "❌ Cược phải là số.", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 5); return
    if bet < 100 or bet > 100000: bot.reply_to(m, "❌ Cược 100 - 100,000 xu.", parse_mode="HTML"); return
    total_cost = bet + nohu_fee
    if not deduct_balance(uid, total_cost): bal = get_user_balance(uid); bot.reply_to(m, f"❌ Không đủ xu! Cần <b>{total_cost:,}</b>. Số dư: <b>{bal:,}</b>", parse_mode="HTML"); return
    
    jackpot = load_jackpot(); jackpot_contribution = int(bet * nohu_multiplier); jackpot += jackpot_contribution; save_jackpot(jackpot); brain.stats["nohu_spins"] += 1
    col1, col2, col3 = [random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=1)[0] for _ in range(3)]
    result = f"{col1}{col2}{col3}"
    
    if col1 == col2 == col3:
        if col1 == "7️⃣":
            win_amount = jackpot; add_balance(uid, win_amount); nohu_history.append({"uid": uid, "name": m.from_user.first_name, "amount": win_amount, "time": datetime.now(tz).strftime("%H:%M %d/%m")}); save_jackpot(nohu_base)
            outcome = f"🎉🎉🎉 <b>JACKPOT!!!</b> +{win_amount:,} xu"; emoji = "🏆"
        else:
            multiplier = SLOT_PAYOUTS.get(result, 2); win_amount = bet * multiplier; add_balance(uid, win_amount)
            outcome = f"✅ NỔ HŨ! (x{multiplier}) +{win_amount:,} xu"; emoji = "🎉"
    elif col1 == col2 or col2 == col3 or col1 == col3:
        win_amount = int(bet * 0.5); add_balance(uid, win_amount)
        outcome = f"🔄 2 giống: hoàn {win_amount:,} xu"; emoji = "🔹"
    else:
        win_amount = 0; outcome = f"💀 Thua -{total_cost:,} xu"; emoji = "❌"
    
    msg = bot.reply_to(m, f"{emoji} <b>NỔ HŨ</b>\n┌──────────┐\n│ {col1}  {col2}  {col3} │\n└──────────┘\n🎯 {outcome}\n💰 JACKPOT: <b>{load_jackpot():,}</b> xu\n💎 Số dư: <b>{get_user_balance(uid):,}</b> xu", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

# ─── GAMES ──────────────────────────────────────────────────────────────
def init_game_state(uid: int, game_type: str) -> Dict:
    if game_type == "taixiu": return {"type": "taixiu", "balance": 1000, "wins": 0, "losses": 0}
    elif game_type == "baucua": return {"type": "baucua", "balance": 1000, "symbols": ["🦀", "🐟", "🦐", "🐓", "🦌", "🎃"], "wins": 0, "losses": 0}
    elif game_type == "keobuabao": return {"type": "keobuabao", "score": 0, "bot_score": 0, "draws": 0}
    elif game_type == "doanso": return {"type": "doanso", "secret": random.randint(1, 100), "attempts": 0, "max_attempts": 7}
    return {}

@bot.message_handler(commands=['taixiu'])
def taixiu_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid = m.from_user.id; users[str(uid)] = m.from_user.first_name; save_users(users); parts = m.text.split()
    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu": GAME_SESSIONS[uid] = init_game_state(uid, "taixiu")
        g = GAME_SESSIONS.get(uid, {})
        msg = bot.reply_to(m, f"🎲 <b>TÀI XỈU</b>\n/taixiu [tai/xiu] [cược]\n💎 Số dư game: <b>{g.get('balance', 1000)}</b> xu\nTài (11-18) | Xỉu (3-10)", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 20); return
    choice = parts[1].lower()
    try: bet = int(parts[2])
    except: bot.reply_to(m, "❌ Cược phải là số.", parse_mode="HTML"); return
    if choice not in ['tai', 'xiu']: bot.reply_to(m, "❌ Chọn 'tai' hoặc 'xiu'.", parse_mode="HTML"); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "taixiu": GAME_SESSIONS[uid] = init_game_state(uid, "taixiu")
    g = GAME_SESSIONS[uid]
    if bet > g["balance"] or bet < 1: bot.reply_to(m, f"❌ Số dư game không đủ ({g['balance']} xu).", parse_mode="HTML"); return
    
    dice = [random.randint(1, 6) for _ in range(3)]; total = sum(dice); result = "tai" if total >= 11 else "xiu"
    dice_str = " ".join([["⚀","⚁","⚂","⚃","⚄","⚅"][d-1] for d in dice])
    if choice == result: g["balance"] += bet; g["wins"] += 1; outcome = f"✅ THẮNG +{bet} xu"
    else: g["balance"] -= bet; g["losses"] += 1; outcome = f"❌ THUA -{bet} xu"
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"🎲 <b>TÀI XỈU</b>\n🎲 {dice_str} = <b>{total}</b> → <b>{result.upper()}</b>\n🎯 Bạn: <b>{choice.upper()}</b>\n💰 {outcome} | Số dư: <b>{g['balance']}</b> xu\n📊 W:{g['wins']} L:{g['losses']}", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(commands=['kbb', 'keobuabao'])
def kbb_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid = m.from_user.id; users[str(uid)] = m.from_user.first_name; save_users(users); parts = m.text.split()
    choices = {"keo": "✌️ Kéo", "kéo": "✌️ Kéo", "bua": "🔨 Búa", "búa": "🔨 Búa", "bao": "📄 Bao"}
    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "keobuabao": GAME_SESSIONS[uid] = init_game_state(uid, "keobuabao")
        g = GAME_SESSIONS.get(uid, {})
        msg = bot.reply_to(m, f"✌️ <b>KÉO BÚA BAO</b>\n/kbb [keo/bua/bao]\n👤 {g.get('score',0)} | 🤖 {g.get('bot_score',0)} | 🤝 {g.get('draws',0)}", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 15); return
    choice = parts[1].lower()
    if choice not in choices: bot.reply_to(m, "❌ Chọn: keo/bua/bao", parse_mode="HTML"); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "keobuabao": GAME_SESSIONS[uid] = init_game_state(uid, "keobuabao")
    g = GAME_SESSIONS[uid]
    user_choice = choices[choice]; bot_choice = random.choice(list(choices.values()))
    ui, bi = list(choices.values()).index(user_choice), list(choices.values()).index(bot_choice)
    if ui == bi: result = "🤝 HÒA"; g["draws"] += 1
    elif (ui == 0 and bi == 2) or (ui == 1 and bi == 0) or (ui == 2 and bi == 1): result = "✅ THẮNG"; g["score"] += 1
    else: result = "❌ THUA"; g["bot_score"] += 1
    brain.stats["games_played"] += 1
    msg = bot.reply_to(m, f"✌️ <b>KÉO BÚA BAO</b>\n👤 {user_choice} vs 🤖 {bot_choice}\n📊 {result}\n🏆 Bạn: <b>{g['score']}</b> | Bot: <b>{g['bot_score']}</b> | Hòa: <b>{g['draws']}</b>", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 25)

@bot.message_handler(commands=['doanso'])
def doanso_cmd(m):
    if not is_grp(m) or antispam(m): return
    uid = m.from_user.id; users[str(uid)] = m.from_user.first_name; save_users(users); parts = m.text.split()
    if len(parts) < 2:
        GAME_SESSIONS[uid] = init_game_state(uid, "doanso")
        msg = bot.reply_to(m, "🔢 <b>ĐOÁN SỐ</b> (1-100)\n/doanso [số]\nBạn có <b>7</b> lần đoán!", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 15); return
    try: guess = int(parts[1])
    except: bot.reply_to(m, "❌ Nhập số 1-100.", parse_mode="HTML"); return
    if guess < 1 or guess > 100: bot.reply_to(m, "❌ Số 1-100.", parse_mode="HTML"); return
    if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "doanso": GAME_SESSIONS[uid] = init_game_state(uid, "doanso")
    g = GAME_SESSIONS[uid]; g["attempts"] += 1; secret = g["secret"]
    brain.stats["games_played"] += 1
    if guess == secret:
        reward = (8 - g["attempts"]) * 500; add_balance(uid, reward)
        msg = bot.reply_to(m, f"🎉 <b>CHÍNH XÁC!</b> Số <b>{secret}</b> sau {g['attempts']} lần!\n💰 +{reward:,} xu", parse_mode="HTML"); del GAME_SESSIONS[uid]
    elif g["attempts"] >= g["max_attempts"]:
        msg = bot.reply_to(m, f"💀 <b>HẾT LƯỢT!</b> Số là <b>{secret}</b>.", parse_mode="HTML"); del GAME_SESSIONS[uid]
    elif guess < secret: msg = bot.reply_to(m, f"🔢 <b>{guess}</b> → ⬆️ CAO HƠN ({g['max_attempts'] - g['attempts']} lần)", parse_mode="HTML")
    else: msg = bot.reply_to(m, f"🔢 <b>{guess}</b> → ⬇️ THẤP HƠN ({g['max_attempts'] - g['attempts']} lần)", parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 30)

# ─── AI + ANTI-SPAM ────────────────────────────────────────────────────
def antispam(m) -> bool:
    if is_admin(m.chat.id, m.from_user.id): return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid,[]) if now-t<4] + [now]
    if len(spam[uid]) > 5:
        warn_counts[uid] = warn_counts.get(uid,0) + 1; brain.stats["spam_blocked"] += 1
        try:
            bot.delete_message(m.chat.id, m.message_id)
            if warn_counts[uid] >= 3:
                try: bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time())+3600)
                except: pass
                bot.send_message(m.chat.id, f"🚫 <b>{html.escape(m.from_user.first_name)}</b> bị ban 1h vì spam.", parse_mode="HTML"); del warn_counts[uid]
            else:
                w = bot.send_message(m.chat.id, f"⚠️ Spam {warn_counts[uid]}/3 <b>{html.escape(m.from_user.first_name)}</b>", parse_mode="HTML"); del_msg(m.chat.id, w.message_id, 15)
        except: pass
        return True
    return False

def ask_ai(prompt: str, uid: Optional[int] = None) -> str:
    global ck_idx
    if brain.state == "sleep": return random.choice(get_kho())
    if len(mem) >= 2 and mem[-2] == prompt: return mem[-1]
    sys_msg = "Bạn là kẻ cọc cằn, chửi khịa. Xưng 'tao' gọi 'mày'. Dưới 12 từ."
    msgs = [{"role":"system","content":sys_msg}]
    for txt in list(mem)[-8:]: msgs.append({"role":"user","content":txt})
    msgs.append({"role":"user","content":prompt})
    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL: ck_idx = (ck_idx + 1) % len(AI_KEYS); continue
            try:
                resp = ses.post(k["url"], json={"model":k["model"],"messages":msgs,"max_tokens":40,"temperature":0.9}, headers={"Authorization":f"Bearer {k['key']}","Content-Type":"application/json"}, timeout=8)
                if resp.status_code == 200:
                    result = resp.json()['choices'][0]['message']['content'].strip(); result = re.sub(r'[_*`\[\]()]','',result)
                    k["fail"] = 0; k["last_used"] = time.time(); mem.append(prompt); mem.append(result); brain.stats["ai_calls"] += 1; return result
                else: k["fail"] += 1
            except: k["fail"] += 1; brain.stats["errors"] += 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
    if not any(k["status"] for k in AI_KEYS):
        for k in AI_KEYS: k["status"], k["fail"] = True, 0
        brain.stats["errors"] = 0; brain.state = "repair"; return "[Não tự sửa] AI đã reset."
    return random.choice(get_kho())

# ─── HANDLERS ──────────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m) or antispam(m): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users); brain.trusted_users.add(m.from_user.id)
    help_text = ("<b>🧠 Não Robot - AI RAM Manager</b>\n"
                 "💎 /daily - Điểm danh | /balance - Xem xu\n"
                 "🎰 /nohu - Nổ Hũ | /taixiu /kbb /doanso - Games\n"
                 "🎙️ /voice - Text to Speech\n"
                 "🧠 /ramstatus - Xem RAM | /clearcache - Dọn RAM\n"
                 "🛠️ /ban /mute /unmute /warn - Quản lí\n"
                 "Tag/reply bot = chat AI")
    msg = bot.reply_to(m, help_text, parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 60)

@bot.message_handler(commands=['brain'])
def brain_cmd(m):
    if not is_grp(m): return
    if not is_admin(m.chat.id, m.from_user.id): msg = bot.reply_to(m, "⛔ Không đủ quyền.", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 10); return
    uptime = int(time.time() - brain.stats["uptime_start"]); jackpot = load_jackpot()
    text = (f"🧠 State: <code>{brain.state}</code> | Mood: <code>{brain.mood}</code>\n"
            f"Msgs: <code>{brain.stats['msg_processed']}</code> | AI: <code>{brain.stats['ai_calls']}</code>\n"
            f"Voice: <code>{brain.stats['voice_generated']}</code> | Games: <code>{brain.stats['games_played']}</code>\n"
            f"Nổ Hũ: <code>{brain.stats['nohu_spins']}</code> | Jackpot: <code>{jackpot:,}</code> xu\n"
            f"RAM: <code>{ram_manager.get_memory_mb():.1f}MB</code> | Dọn: <code>{ram_manager.clean_count}</code> lần\n"
            f"Freed: <code>{ram_manager.total_cleaned_bytes/1024/1024:.1f}MB</code> | Cache: <code>{len(ram_manager.smart_cache)}</code>\n"
            f"Errors: <code>{brain.stats['errors']}</code> | Uptime: <code>{uptime//3600}h{(uptime%3600)//60}m</code>")
    msg = bot.reply_to(m, text, parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def handle_text(m):
    if antispam(m) or m.text.startswith('/'): return
    users[str(m.from_user.id)] = m.from_user.first_name; save_users(users)
    brain.think({"uid": m.from_user.id, "txt": m.text, "cmd": False})
    uid = m.from_user.id
    if not brain.should_reply(uid, m.text): return
    if uid in ai_cd and time.time() - ai_cd[uid] < 2: msg = bot.reply_to(m, "Đợi 2s.", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 3); return
    ai_cd[uid] = time.time()
    def _ai():
        reply = ask_ai(m.text, uid)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id): bot.reply_to(m, html.escape(reply), parse_mode="HTML")
        else: msg_reply = bot.reply_to(m, html.escape(reply), parse_mode="HTML"); del_msg(m.chat.id, msg_reply.message_id)
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    today = date.today().isoformat()
    for u in m.new_chat_members:
        if u.id == bot.get_me().id: continue
        users[str(u.id)] = u.first_name
        if str(u.id) not in member_stats.get("join_dates", {}): member_stats["join_dates"][str(u.id)] = today; member_stats["total_joined"] += 1
        member_stats["daily_join"][today] += 1; member_stats["current_members"] += 1
        save_users(users); save_member_stats()
        msg = bot.send_message(m.chat.id, f"🔥 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào. {random.choice(get_kho())}", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m):
    if not is_grp(m): return
    today = date.today().isoformat(); u = m.left_chat_member
    if u.id == bot.get_me().id: return
    member_stats["daily_leave"][today] += 1; member_stats["total_left"] += 1
    member_stats["current_members"] = max(0, member_stats["current_members"] - 1); save_member_stats()
    msg = bot.send_message(m.chat.id, f"🍂 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> cút. {random.choice(get_kho())}", parse_mode="HTML"); del_msg(m.chat.id, msg.message_id, 30)

# ╔══════════════════════════════════════════════════════════════╗
# ║  BACKGROUND TASKS                                          ║
# ╚══════════════════════════════════════════════════════════════╝
def scheduler_task():
    last_hour = -1; last_midnight = date.today()
    while True:
        try:
            now = datetime.now(tz); brain.health_check()
            if brain.state == "repair": brain.state = "normal"; brain.repair_mode = False
            today = date.today()
            if today != last_midnight: last_midnight = today
            if now.minute == 0 and now.hour != last_hour and users:
                uid, uname = random.choice(list(users.items()))
                msg = bot.send_message(GROUP_ID, f"🔔 <b>{now.strftime('%H:%M')}</b> | <a href='tg://user?id={uid}'>{html.escape(uname)}</a>... {random.choice(get_kho())}", parse_mode="HTML"); del_msg(GROUP_ID, msg.message_id, 15); last_hour = now.hour
            if now.minute != 0: last_hour = -1
            to_remove = []
            for uid, until in mutes.items():
                if time.time() > until:
                    try: bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True); to_remove.append(uid)
                    except: pass
            for uid in to_remove: del mutes[uid]
            if len(spam) > 100:
                oldest = sorted(spam.items(), key=lambda x: x[1][-1] if x[1] else 0)[:10]
                for uid, _ in oldest: del spam[uid]
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
    global user_balance, daily_checkin, nohu_jackpot, member_stats
    
    loaded_users = load_users()
    if isinstance(loaded_users, dict): users.update(loaded_users)
    user_balance = load_balances()
    daily_checkin = load_daily_checkins()
    nohu_jackpot = load_jackpot()
    
    loaded_stats = load_member_stats()
    member_stats.update(loaded_stats)
    if not isinstance(member_stats.get("daily_join"), defaultdict): member_stats["daily_join"] = defaultdict(int, member_stats.get("daily_join", {}))
    if not isinstance(member_stats.get("daily_leave"), defaultdict): member_stats["daily_leave"] = defaultdict(int, member_stats.get("daily_leave", {}))
    
    try: member_stats["current_members"] = bot.get_chat_member_count(GROUP_ID)
    except: member_stats["current_members"] = len(users)
    
    # Khởi động AI RAM Manager
    ram_manager.start_monitoring()
    
    logger.info(f"🚀 Khởi động: {len(users)} users, Jackpot: {nohu_jackpot:,} xu")
    logger.info(f"🧠 AI RAM Manager: Max {ram_manager.max_ram_bytes/1024/1024:.0f}MB, Auto-clean at 90%")
    logger.info(f"📄 PDF={HAS_PYPDF2} DOCX={HAS_DOCX} BS4={HAS_BS4}")
    
    Thread(target=scheduler_task, daemon=True).start()
    Thread(target=auto_save_task, daemon=True).start()
    
    try: bot.infinity_polling(timeout=30, none_stop=True, interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng: {e}")
        brain.stats["errors"] += 1; brain.save_state(); save_balances(user_balance); save_daily_checkins(daily_checkin); save_jackpot(load_jackpot()); save_member_stats()

if __name__ == "__main__":
    main()
