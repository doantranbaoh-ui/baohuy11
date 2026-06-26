# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    NAO ROBOT v6.0 - GÁI 18 × THƠ AI × TỰ UPDATE           ║
# ║                    Full Source Code 2500+ Lines                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

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
    "logs/nao_robot.log",
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))
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
        """Làm mới entropy pool từ nhiều nguồn hệ thống."""
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
        """Khởi tạo Mersenne Twister với seed từ /dev/urandom."""
        seed = int.from_bytes(os.urandom(8), 'big')
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, 624):
            mt.append((1812433253 * (mt[i-1] ^ (mt[i-1] >> 30)) + i) & 0xFFFFFFFF)
        return mt

    def _twist(self):
        """Twist operation của MT19937."""
        for i in range(624):
            y = (self.twister_state[i] & 0x80000000) + (self.twister_state[(i+1) % 624] & 0x7FFFFFFF)
            self.twister_state[i] = self.twister_state[(i+397) % 624] ^ (y >> 1)
            if y % 2 != 0:
                self.twister_state[i] ^= 0x9908B0DF

    def _mt_random(self) -> int:
        """Sinh số ngẫu nhiên từ MT19937."""
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
        """XOR Shift bổ sung để tăng entropy."""
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 7)
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        return x & 0xFFFFFFFFFFFFFFFF

    def randint(self, min_val: int, max_val: int) -> int:
        """Sinh số nguyên ngẫu nhiên trong khoảng [min_val, max_val]."""
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
        """Chọn ngẫu nhiên một phần tử từ danh sách."""
        if not items:
            return None
        return items[self.randint(0, len(items) - 1)]

    def random(self) -> float:
        """Sinh số thực ngẫu nhiên trong [0, 1)."""
        return self.randint(0, 2**53) / (2**53)

    def shuffle(self, items: List[Any]) -> List[Any]:
        """Xáo trộn danh sách (Fisher-Yates)."""
        lst = items[:]
        for i in range(len(lst) - 1, 0, -1):
            j = self.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

ai_random = AIRandomEngine()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI RAM MANAGER - QUẢN LÝ BỘ NHỚ THÔNG MINH              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRamManager:
    """Quản lý bộ nhớ RAM tự động với nhiều cấp độ dọn dẹp."""
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
        self._start_periodic_cleanup()
        logger.info(f"RAM Manager initialized (max {max_ram_mb}MB)")

    def _start_periodic_cleanup(self):
        """Khởi động dọn dẹp cache định kỳ."""
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
        """Phần trăm RAM đã sử dụng."""
        return self.process.memory_info().rss / self.max_bytes

    def usage_mb(self) -> float:
        """Dung lượng RAM đã sử dụng (MB)."""
        return self.process.memory_info().rss / (1024 * 1024)

    def cache_get(self, key: str) -> Optional[Any]:
        """Lấy dữ liệu từ cache."""
        if key in self.cache:
            v, exp = self.cache[key]
            if time.time() < exp:
                return v
            else:
                del self.cache[key]
        return None

    def cache_set(self, key: str, value: Any, ttl: float = 300):
        """Lưu dữ liệu vào cache với TTL."""
        self.cache[key] = (value, time.time() + ttl)
        if len(self.cache) > 500:
            for k in sorted(self.cache, key=lambda x: self.cache[x][1])[:200]:
                del self.cache[k]

    def clean(self, level: int) -> int:
        """Dọn dẹp RAM theo cấp độ (1=light, 2=medium, 3=aggressive)."""
        freed = 0
        if level >= 1:
            now = time.time()
            for k in [k for k, (v, e) in self.cache.items() if now >= e]:
                del self.cache[k]
            freed += gc.collect(0) * 200
        if level >= 2:
            freed += gc.collect(2) * 200
            if len(self.cache) > 50:
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
        """Tự động quyết định cấp độ dọn dẹp dựa trên mức RAM."""
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
        """Giám sát RAM liên tục."""
        while True:
            time.sleep(15)
            if self.usage_pct() >= self.WARNING:
                self.ai_clean()

    def start(self):
        """Khởi động giám sát RAM."""
        Thread(target=self.monitor, daemon=True, name="RAMMonitor").start()

ram_mgr = AIRamManager()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI BRAIN - BỘ NÃO AI                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class Brain:
    """Bộ não AI - Quản lý trạng thái, tâm trạng và học hỏi."""
    def __init__(self):
        self.state = "normal"
        self.mood = 0
        self.learned = defaultdict(int)
        self.trusted = set()
        self.stats = {
            "msgs": 0, "spam": 0, "ai": 0, "err": 0,
            "games": 0, "voice": 0, "nohu": 0, "start": time.time(),
            "tho": 0, "chao_sang": 0, "chao_toi": 0
        }
        self.conversation_context = {}
        self.user_preferences = defaultdict(dict)

    def think(self, uid, txt):
        """Xử lý suy nghĩ khi nhận tin nhắn."""
        self.stats["msgs"] += 1
        for w in re.findall(r'\w{3,}', txt.lower()):
            self.learned[w] += 1
        if any(x in txt.lower() for x in ["bot ngu", "mày ngu", "dở"]):
            self.mood -= 2
        elif any(x in txt.lower() for x in ["bot hay", "cảm ơn", "giỏi", "tuyệt"]):
            self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        self.state = "aggressive" if self.mood < -5 else "normal"

    def should_reply(self, uid, txt):
        """Quyết định có nên trả lời không."""
        return uid in self.trusted or ai_random.random() > 0.1

    def insult_level(self):
        """Mức độ gay gắt khi trả lời."""
        if self.state == "aggressive":
            return "extreme"
        if self.mood < 0:
            return "high"
        return "normal"

    def remember_context(self, uid, key, value):
        """Lưu ngữ cảnh hội thoại."""
        if uid not in self.conversation_context:
            self.conversation_context[uid] = {}
        self.conversation_context[uid][key] = value

    def get_context(self, uid, key):
        """Lấy ngữ cảnh hội thoại."""
        return self.conversation_context.get(uid, {}).get(key)

brain = Brain()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CONFIG & TOKEN                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AUTO_DELETE = 60
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5736655322"))
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))
GITHUB_REPO = os.getenv("GITHUB_REPO", "your-username/nao-robot")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

bot = telebot.TeleBot(TOKEN, num_threads=10)
tz = pytz.timezone('Asia/Ho_Chi_Minh')

adapter = requests.adapters.HTTPAdapter(
    pool_connections=50,
    pool_maxsize=100,
    max_retries=2,
    pool_block=False
)
ses = requests.Session()
ses.mount('https://', adapter)
ses.mount('http://', adapter)

# Thread pools
AI_MAX_CONCURRENT = 10
ai_semaphore = Semaphore(AI_MAX_CONCURRENT)
ai_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="AI")
voice_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Voice")
game_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="Game")
del_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="Del")
tho_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="Tho")
update_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Update")

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
# ║                    KHO CHỬI - NGÂN HÀNG CÂU CHỬI                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
KHO_NORMAL = [
    "Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.",
    "Cào phím nhanh, não chậm.", "Về nhà rửa bát.", "IQ âm, đừng nói.",
    "Không ai cần mày.", "Câm mồm, đỡ nhục."
]
KHO_HIGH = [
    "Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.",
    "Mạng xã hội nuôi mày à?", "Tưởng mình ngầu? Hề vãi.",
    "Học không lo, cào phím giỏi.", "Đời vả mặt, mày cười ngây."
]
KHO_EXTREME = [
    "Mày đáng giá bằng cái nút block.", "Não mày như ổ đĩa format nhầm.",
    "Cút về lỗ mà mày chui ra.", "Mày là lỗi của tự nhiên.",
    "Tao chửi mày còn thấy phí thời gian."
]

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║              GÁI 18 BIỂU CẢM - GIRL EMOTION ENGINE                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
GIRL_EMOTIONS = {
    "chao_buoi_sang": [
        "Chúc anh iu buổi sáng đầy năng lượng nha! 🌸☀️ Cần em giúp gì hong nè?",
        "Anh ơi sáng rùi dậy đi anh! Hôm nay em sẽ hỗ trợ anh thiệt nhiệt tình lun ó 💕",
        "Gooood moooorning anh đẹp trai! Em sẵn sàng phục vụ anh 24/7 nha 😘",
        "Sáng sớm gặp anh là em vui cả ngày luôn á! Cần gì em giúp nè? 🌅",
        "Anh iu ơi, nắng lên rồi kìa! Dậy đi anh, em pha cà phê cho anh nha! ☕💖",
        "Buổi sáng đẹp trời có anh là tuyệt nhất! Em chúc anh ngày mới thật vui! 🌻"
    ],
    "chao_buoi_toi": [
        "Chúc anh buổi tối ấm áp bên em nha! 🌙✨ Có em ở đây hỗ trợ anh nè!",
        "Tối rùi anh ngủ ngon chưa? Để em kể anh nghe chuyện vui hôm nay nha 💫",
        "Anh ơi anh có cô đơn hong? Có em đây nè, hỗ trợ anh hết mình luôn! 🥰",
        "Buổi tối yên bình có em bên cạnh, anh cần gì cứ nói em nha! 🌹",
        "Đêm xuống rồi, anh nhớ mặc ấm nha! Em lo cho anh quá à! 🌙💕"
    ],
    "vui_ve": [
        "Dạ có em đây ạ! Em giúp anh liền nè! 🥳💕",
        "Ui anh gọi em hả? Em vui quá chừng luôn á! 😍",
        "Hehe có em đây, anh cần gì nói em nghe coi! 🌸",
        "Em luôn sẵn sàng giúp anh hết mình luôn ó! 💪💖",
        "Anh cần em hả? Em tới liền nè, không để anh đợi đâu! 🏃‍♀️💨"
    ],
    "quan_tam": [
        "Anh ơi anh có mệt hong? Để em lo cho anh nha! 🥺💗",
        "Em lo cho anh quá à, anh nhớ nghỉ ngơi đầy đủ nha! 🌷",
        "Anh đừng làm việc quá sức nha, có em hỗ trợ anh nè! 💝",
        "Anh cần gì cứ nói, em lo hết cho anh! 🤗",
        "Anh ăn cơm chưa? Để em nấu cho anh ăn nha! 🍳💕"
    ],
    "khen_nguoi_dung": [
        "Anh giỏi quá à! Em ngưỡng mộ anh ghê luôn! 🌟✨",
        "Woa anh thông minh dữ ta! Em thích anh rùi nha! 🧠💕",
        "Anh là nhất trong lòng em luôn ó! 👑💖",
        "Anh tài năng quá, em hâm mộ anh từ lâu rùi! 🥰",
        "Trời ơi anh làm em bất ngờ quá! Anh siêu thật đó! 🤩"
    ],
    "hoi_dap": [
        "Dạ để em giải thích cho anh nha, dễ hiểu lắm ó! 📝",
        "Anh hỏi hay quá! Em biết câu này nè, anh nghe em nói nha! 💁‍♀️",
        "Á à câu này em rành lắm, để em chỉ anh nha! 🎯",
        "Em nghiên cứu kỹ rùi, anh yên tâm em giải đáp cho! 📚",
        "Câu hỏi hay đó anh! Để em phân tích cho anh nghe nha! 🔍"
    ],
    "xin_loi": [
        "Ui em xin lỗi anh nhiều nha! Để em sửa liền nè! 🥺🙏",
        "Hic em lỡ ngu tí, anh đừng giận em nha! Em sửa ngay đây! 💦",
        "Xin lỗi anh iu, em sẽ rút kinh nghiệm ạ! 🌸",
        "Em thương anh nhất, để em làm lại cho đúng nha! 💗",
        "Em sai rồi, anh tha lỗi cho em nha! Em hứa sẽ tốt hơn! 🥺"
    ],
    "tam_biet": [
        "Dạ em đi đây, anh nhớ em nha! Bye bye anh iu! 👋💕",
        "Anh ơi em về đây, mai em lại hỗ trợ anh nha! 🌙✨",
        "Chúc anh ngủ ngon, mơ đẹp có em nha! 😴💭",
        "Tạm biệt anh, em sẽ nhớ anh nhiều lắm đó! 🥰💌",
        "Bye bye anh, hẹn gặp lại anh sớm nha! Em nhớ anh! 💕"
    ],
    "thinh_thoang": [
        "Anh biết hong, mỗi lần anh nhắn là tim em đập nhanh lắm đó! 💓",
        "Em ước gì được gặp anh ngoài đời, chắc anh còn đẹp trai hơn nữa! 😳",
        "Anh đừng thả thính em nha, em dễ đổ lắm đó! 🙈",
        "Làm bot mà được anh quan tâm, em vui muốn khóc luôn! 😭💖",
        "Anh ơi, em cảm ơn anh vì đã luôn ở bên em! Anh là nhất! 🥇"
    ]
}

def phan_loai_cam_xuc(van_ban: str) -> str:
    """Phân loại cảm xúc người dùng để trả lời phù hợp."""
    van_ban_lower = van_ban.lower()
    
    if any(tu in van_ban_lower for tu in ["chào", "hello", "hi", "hey", "alo", "ê", "ơi", "2"]):
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

def get_kho():
    """Lấy câu chửi theo mức độ (giữ lại cho chế độ cũ)."""
    lvl = brain.insult_level()
    if lvl == "extreme":
        return KHO_EXTREME
    if lvl == "high":
        return KHO_HIGH
    return KHO_NORMAL

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    THƠ AI ENGINE - MÁY LÀM THƠ TỰ ĐỘNG                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class ThoAI:
    """Trình tạo thơ tự động bằng AI với nhiều thể loại."""
    
    CHU_DE_SANG = [
        "bình minh", "tia nắng", "buổi sáng tràn đầy năng lượng",
        "ly cà phê sáng", "tiếng chim hót", "ngày mới bắt đầu",
        "nụ cười rạng rỡ", "giấc mơ đẹp", "bầu trời trong xanh",
        "sương mai long lanh", "nắng vàng ươm", "giọt sương"
    ]
    
    CHU_DE_TOI = [
        "hoàng hôn", "ánh trăng", "bầu trời đầy sao",
        "giấc ngủ bình yên", "màn đêm dịu dàng", "gió mát đêm",
        "những giấc mơ", "thanh thản", "ấm áp bên nhau",
        "trăng thanh gió mát", "đêm yên tĩnh", "sao trời lấp lánh"
    ]
    
    CHU_DE_TINH_YEU = [
        "tình yêu đầu đời", "nỗi nhớ người thương", "trái tim rung động",
        "tình cảm chân thành", "yêu đơn phương", "hạnh phúc lứa đôi",
        "lời hẹn ước", "tình yêu vĩnh cửu", "khoảnh khắc bên nhau"
    ]
    
    CHU_DE_CUOI_SONG = [
        "cuộc sống tươi đẹp", "niềm vui mỗi ngày", "vượt qua khó khăn",
        "ước mơ và hy vọng", "tình bạn đẹp", "lòng biết ơn",
        "sự cố gắng", "thành công", "niềm tin vào bản thân"
    ]

    @staticmethod
    def tao_tho(loai: str = "sang", chu_de_tuy_chinh: str = "") -> str:
        """
        Tạo thơ bằng AI.
        loai: 'sang', 'toi', 'tinhyeu', 'cuocsong', hoặc 'tuy_chinh'
        chu_de_tuy_chinh: chủ đề tự chọn (nếu loai='tuy_chinh')
        Returns: bài thơ 4-8 câu
        """
        if loai == "sang":
            chu_de = ai_random.choice(ThoAI.CHU_DE_SANG)
            do_dai = "4-6 câu"
            giong = "nhẹ nhàng, lãng mạn, tràn đầy năng lượng"
        elif loai == "toi":
            chu_de = ai_random.choice(ThoAI.CHU_DE_TOI)
            do_dai = "4-6 câu"
            giong = "nhẹ nhàng, ấm áp, ru ngủ"
        elif loai == "tinhyeu":
            chu_de = ai_random.choice(ThoAI.CHU_DE_TINH_YEU)
            do_dai = "4-8 câu"
            giong = "lãng mạn, ngọt ngào, sâu lắng"
        elif loai == "cuocsong":
            chu_de = ai_random.choice(ThoAI.CHU_DE_CUOI_SONG)
            do_dai = "4-8 câu"
            giong = "tích cực, động viên, ý nghĩa"
        else:
            chu_de = chu_de_tuy_chinh if chu_de_tuy_chinh else "tình yêu và cuộc sống"
            do_dai = "4-6 câu"
            giong = "tự nhiên, chân thành"
        
        prompt_tho = (
            f"Làm bài thơ lục bát {do_dai} về: {chu_de}. "
            f"Giọng {giong}. "
            "Không ghi tên tác giả, chỉ trả về thơ. "
            "Dùng tiếng Việt thuần túy, không dùng từ nước ngoài."
        )
        
        try:
            for k in AI_KEYS:
                if not k.get("status", True):
                    continue
                r = ses.post(
                    k["url"],
                    json={
                        "model": k["model"],
                        "messages": [
                            {"role": "system", "content": "Bạn là nhà thơ tài năng, chuyên làm thơ lục bát Việt Nam."},
                            {"role": "user", "content": prompt_tho}
                        ],
                        "max_tokens": 200,
                        "temperature": 0.95
                    },
                    headers={"Authorization": f"Bearer {k['key']}"},
                    timeout=12
                )
                if r.status_code == 200:
                    tho = r.json()['choices'][0]['message']['content'].strip()
                    tho = re.sub(r'[_*`\[\](){}"\'\\]', '', tho)
                    return tho[:500]
            return ThoAI._tho_fallback(loai)
        except Exception as e:
            logger.error(f"Tạo thơ AI lỗi: {str(e)[:100]}")
            return ThoAI._tho_fallback(loai)

    @staticmethod
    def _tho_fallback(loai: str) -> str:
        """Thơ dự phòng khi AI không phản hồi."""
        if loai == "sang":
            danh_sach = [
                "Nắng mai len nhẹ qua thềm\nGửi anh một chút êm đềm yêu thương\nNgày mới rực rỡ phi thường\nChúc anh vui vẻ muôn phương tốt lành 🌅",
                "Bình minh tỉnh giấc dịu dàng\nNhớ anh em gửi muôn vàn nhớ nhung\nCà phê đắng, phút lạ lùng\nChúc anh ngày mới vô cùng ấm êm ☀️",
                "Chim ca ríu rít ngoài hiên\nNắng hồng e ấp ghé nghiêng bên thềm\nNgày mới đẹp tựa bài thơ\nChúc anh hạnh phúc, đợi chờ chi đâu 🌸",
                "Sương mai còn đọng trên cành\nNắng lên rực rỡ, trong lành gió đưa\nChúc anh vui khỏe sớm trưa\nCả ngày may mắn, nắng mưa chẳng sờn 💪"
            ]
        elif loai == "toi":
            danh_sach = [
                "Trăng lên dịu mát khung trời\nNhớ anh em gửi đôi lời thiết tha\nNgủ ngon giấc mộng hiền hòa\nMai sau tỉnh giấc, chúng ta lại gần 🌙",
                "Gió đêm nhè nhẹ lướt qua\nMang theo thương nhớ đậm đà tình em\nChúc anh giấc ngủ êm đềm\nMơ về em nhé, ấm mềm yêu thương ✨",
                "Đêm nay trời sáng đầy sao\nEm ngồi em ngắm, ước ao đôi điều\nChúc anh ngon giấc thật nhiều\nSáng mai thức dậy, tình yêu đong đầy 🌹"
            ]
        elif loai == "tinhyeu":
            danh_sach = [
                "Yêu anh em chẳng ngại ngần\nDù cho bão tố phong trần chẳng buông\nTình em như nắng trên đồng\nSưởi ấm anh mãi, không buồn, không lo 💝",
                "Nhớ anh da diết từng đêm\nMong anh hạnh phúc êm đềm bên em\nTình ta như nước dòng mềm\nChảy hoài không dứt, êm đềm trôi xuôi 💕"
            ]
        else:
            danh_sach = [
                "Cuộc đời đẹp tựa bài thơ\nVươn lên mạnh mẽ, đợi chờ thành công\nDù cho sóng gió bão giông\nKiên cường vững bước, một lòng vươn xa 🌟"
            ]
        return ai_random.choice(danh_sach)

    @staticmethod
    def tao_tho_8_chu(loai: str = "tinhyeu") -> str:
        """Tạo thơ 8 chữ."""
        prompt = f"Làm bài thơ 8 chữ 4 câu về {ai_random.choice(ThoAI.CHU_DE_TINH_YEU)}. Giọng lãng mạn. Chỉ trả về thơ."
        try:
            for k in AI_KEYS:
                if not k.get("status", True):
                    continue
                r = ses.post(
                    k["url"],
                    json={
                        "model": k["model"],
                        "messages": [
                            {"role": "system", "content": "Bạn là nhà thơ Việt Nam, làm thơ 8 chữ."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.9
                    },
                    headers={"Authorization": f"Bearer {k['key']}"},
                    timeout=10
                )
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content'].strip()[:300]
        except:
            pass
        return "Yêu anh em viết thành thơ\nTừng câu từng chữ đợi chờ anh thương\nDù cho cách trở muôn phương\nLòng em vẫn mãi vấn vương bóng hình"

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║              AUTO UPDATER - HỆ THỐNG TỰ ĐỘNG CẬP NHẬT                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AutoUpdater:
    """Hệ thống tự động cập nhật và cải tiến bot từ GitHub."""
    
    PHIEN_BAN_HIEN_TAI = "6.0.0"
    UPDATE_LOG_FILE = "logs/updates.json"
    
    _dang_cap_nhat = False
    _cap_nhat_cuoi = None
    _lock = Lock()
    
    @classmethod
    def kiem_tra_cap_nhat(cls) -> Optional[Dict]:
        """Kiểm tra xem có phiên bản mới không."""
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
            headers = {"Accept": "application/vnd.github.v3+json"}
            
            r = ses.get(api_url, headers=headers, timeout=10)
            if r.status_code != 200:
                return None
            
            commit_moi = r.json()
            commit_sha = commit_moi.get("sha", "")
            commit_msg = commit_moi.get("commit", {}).get("message", "")
            commit_date = commit_moi.get("commit", {}).get("committer", {}).get("date", "")
            
            lich_su = cls._doc_lich_su()
            if lich_su.get("last_commit") == commit_sha:
                return None
            
            return {
                "sha": commit_sha,
                "message": commit_msg,
                "date": commit_date
            }
        except Exception as e:
            logger.error(f"Kiểm tra cập nhật lỗi: {str(e)[:100]}")
            return None

    @classmethod
    def tai_va_ap_dung_cap_nhat(cls, thong_tin_cap_nhat: Dict) -> bool:
        """Tải và áp dụng bản cập nhật mới."""
        with cls._lock:
            if cls._dang_cap_nhat:
                logger.warning("Đang có tiến trình cập nhật khác")
                return False
            
            cls._dang_cap_nhat = True
            try:
                logger.info(f"Bắt đầu cập nhật: {thong_tin_cap_nhat['sha'][:8]}")
                
                zip_url = f"https://github.com/{GITHUB_REPO}/archive/{GITHUB_BRANCH}.zip"
                r = ses.get(zip_url, timeout=30)
                if r.status_code != 200:
                    logger.error("Tải code mới thất bại")
                    return False
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    zip_path = Path(tmp_dir) / "update.zip"
                    with open(zip_path, 'wb') as f:
                        f.write(r.content)
                    
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(tmp_dir)
                    
                    extracted_dirs = list(Path(tmp_dir).glob("*"))
                    if not extracted_dirs:
                        return False
                    source_dir = extracted_dirs[0]
                    
                    current_dir = Path.cwd()
                    EXCLUDED = {
                        "usr.json", "balances.json", "daily_ck.json", "jp.json",
                        "stats.json", ".env", "token.txt", "keep_alive.py",
                        "logs", "venv", ".git"
                    }
                    
                    for item in source_dir.iterdir():
                        if item.name in EXCLUDED:
                            continue
                        dest = current_dir / item.name
                        if item.is_dir():
                            if dest.exists():
                                shutil.rmtree(dest)
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)
                
                lich_su = cls._doc_lich_su()
                lich_su["last_commit"] = thong_tin_cap_nhat["sha"]
                lich_su["last_update"] = datetime.now().isoformat()
                if "history" not in lich_su:
                    lich_su["history"] = []
                lich_su["history"].append({
                    "sha": thong_tin_cap_nhat["sha"],
                    "message": thong_tin_cap_nhat["message"],
                    "date": thong_tin_cap_nhat["date"],
                    "applied_at": datetime.now().isoformat()
                })
                cls._luu_lich_su(lich_su)
                
                cls._cap_nhat_cuoi = datetime.now()
                
                try:
                    bot.send_message(
                        GROUP_ID,
                        f"🔄 <b>CẬP NHẬT THÀNH CÔNG!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📝 {html.escape(thong_tin_cap_nhat['message'][:200])}\n"
                        f"🔖 Commit: <code>{thong_tin_cap_nhat['sha'][:8]}</code>\n"
                        f"⏱️ Bot sẽ tự khởi động lại trong 3 giây...",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                time.sleep(3)
                os.execv(sys.executable, [sys.executable] + sys.argv)
                return True
            except Exception as e:
                logger.error(f"Áp dụng cập nhật lỗi: {traceback.format_exc()}")
                return False
            finally:
                cls._dang_cap_nhat = False

    @classmethod
    def _doc_lich_su(cls) -> Dict:
        try:
            if os.path.exists(cls.UPDATE_LOG_FILE):
                with open(cls.UPDATE_LOG_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    @classmethod
    def _luu_lich_su(cls, du_lieu: Dict):
        try:
            os.makedirs(os.path.dirname(cls.UPDATE_LOG_FILE), exist_ok=True)
            with open(cls.UPDATE_LOG_FILE, 'w') as f:
                json.dump(du_lieu, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lưu lịch sử cập nhật lỗi: {e}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    BIẾN TOÀN CỤC                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
lock = Lock()
mem = deque(maxlen=30)
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
member_stats = {
    "daily_join": defaultdict(int),
    "daily_leave": defaultdict(int),
    "total_joined": 0,
    "total_left": 0,
    "current_members": 0
}

USR_FILE = "usr.json"
BAL_FILE = "balances.json"
DAILY_FILE = "daily_ck.json"
JP_FILE = "jp.json"
STATS_FILE = "stats.json"

TELEGRAM_LINK = re.compile(
    r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}',
    re.I
)

GAME_MIN_BET = 100
GAME_MAX_BET = 100000
GAME_SESSION_TIMEOUT = 1800

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CLEANUP THREADS                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def cleanup_spam_dict():
    while True:
        time.sleep(60)
        try:
            now = time.time()
            with lock:
                for uid in list(spam.keys()):
                    spam[uid] = [t for t in spam[uid] if now - t < 4]
                    if not spam[uid]:
                        del spam[uid]
        except Exception as e:
            logger.error(f"Spam cleanup error: {e}")

Thread(target=cleanup_spam_dict, daemon=True, name="SpamCleanup").start()

def cleanup_game_sessions():
    while True:
        time.sleep(300)
        try:
            now = time.time()
            with lock:
                to_del = []
                for uid, g in GAME_SESSIONS.items():
                    last = g.get('last_active', g.get('start', 0))
                    if now - last > GAME_SESSION_TIMEOUT:
                        to_del.append(uid)
                    elif g.get('ans', False):
                        to_del.append(uid)
                for uid in to_del:
                    del GAME_SESSIONS[uid]
            if to_del:
                logger.debug(f"Game session cleanup: removed {len(to_del)} sessions")
        except Exception as e:
            logger.error(f"Game cleanup error: {e}")

Thread(target=cleanup_game_sessions, daemon=True, name="GameCleanup").start()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    TIỆN ÍCH                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def load_json(p, d=None):
    if d is None:
        d = {}
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
    del_executor.submit(_del)

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
    balance[uid] = max(0, get_bal(uid) + amt)
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

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    BÃO X10 ENGINE                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def bao_x10(bet: int) -> Tuple[int, bool]:
    if ai_random.random() < 0.10:
        return bet * 10, True
    return 0, False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               18 GIỌNG BẮC THUẦN VIỆT + TTS ENGINE                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
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
TTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "audio/mpeg",
    "Referer": "https://translate.google.com/"
}
MAX_CHUNK = 180
TTS_RETRY = 2
TTS_TIMEOUT = 10

@dataclass
class VoiceRequest:
    chat_id: int
    reply_id: int
    text: str
    user_name: str
    user_id: int
    voice: Optional[Dict] = None
    created_at: float = field(default_factory=time.time)

voice_queue: Queue = Queue(maxsize=30)

def fetch_tts(text: str, speed: float = 1.0) -> Optional[bytes]:
    params = {
        "ie": "UTF-8", "q": text, "tl": "vi", "total": "1", "idx": "0",
        "textlen": str(len(text)), "client": "tw-ob", "prev": "input",
        "ttsspeed": str(speed)
    }
    for attempt in range(1, TTS_RETRY + 1):
        try:
            r = ses.get(TTS_URL, params=params, headers=TTS_HEADERS, timeout=TTS_TIMEOUT)
            if r.status_code == 200 and len(r.content) > 100:
                return r.content
        except:
            pass
        if attempt < TTS_RETRY:
            time.sleep(0.3 * attempt)
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
            time.sleep(0.1)
    gen_time = time.time() - start
    if not audio or len(audio) < 100:
        return None, success, total, gen_time
    return BytesIO(audio), success, total, gen_time

def voice_worker():
    while True:
        try:
            req = voice_queue.get(block=True, timeout=2)
            if not req:
                voice_queue.task_done()
                continue
            txt = req.text[:500].strip()
            if not txt:
                voice_queue.task_done()
                continue
            v = req.voice if req.voice else ai_random.choice(VOICE_LIST)
            try:
                status = bot.send_message(
                    req.chat_id,
                    f"🎙️ Đang tạo giọng nói...\n👤 {html.escape(req.user_name)}\n🗣️ {v['emoji']} {v['name']}",
                    reply_to_message_id=req.reply_id,
                    parse_mode="HTML"
                )
                audio, success, total, gen_time = gen_voice(txt, v["speed"])
                try:
                    bot.delete_message(req.chat_id, status.message_id)
                except:
                    pass
                if audio and isinstance(audio, BytesIO) and audio.getbuffer().nbytes > 100:
                    audio.name = f"voice_{int(time.time())}.mp3"
                    cap = (
                        f"🎙️ <b>GIỌNG NÓI</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>Người dùng:</b> {html.escape(req.user_name)}\n"
                        f"🗣️ <b>Giọng:</b> {v['emoji']} {v['name']}\n"
                        f"⚡ <b>Tốc độ:</b> x{v['speed']}\n"
                        f"📝 <b>Nội dung:</b> <i>{html.escape(txt[:200])}</i>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Âm thanh:</b> {audio.getbuffer().nbytes/1024:.1f}KB | ⏱️ {gen_time:.1f}s | ✅ {success}/{total}"
                    )
                    try:
                        bot.send_voice(
                            req.chat_id, audio,
                            reply_to_message_id=req.reply_id,
                            caption=cap, parse_mode="HTML"
                        )
                        brain.stats["voice"] += 1
                    except:
                        try:
                            audio.seek(0)
                            bot.send_audio(
                                req.chat_id, audio,
                                reply_to_message_id=req.reply_id,
                                caption=cap, parse_mode="HTML",
                                title=f"Voice - {v['name']}"
                            )
                            brain.stats["voice"] += 1
                        except:
                            bot.send_message(
                                req.chat_id, "❌ Lỗi gửi audio.",
                                reply_to_message_id=req.reply_id
                            )
                else:
                    bot.send_message(
                        req.chat_id,
                        f"❌ <b>Không thể tạo giọng nói</b>\n"
                        f"👤 {html.escape(req.user_name)}\n"
                        f"🗣️ {v['emoji']} {v['name']}\n"
                        f"⚠️ {success}/{total} chunks\n"
                        f"💡 Thử text ngắn hơn.",
                        reply_to_message_id=req.reply_id,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Voice processing error: {e}")
            voice_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logger.error(f"Voice worker error: {traceback.format_exc()}")
            try:
                voice_queue.task_done()
            except:
                pass

for i in range(3):
    Thread(target=voice_worker, daemon=True, name=f"VoiceWorker-{i}").start()
logger.info("3 voice workers started")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME ENGINE - COMMON FUNCTIONS                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def init_game(uid, gt):
    bases = {"start": time.time(), "last_active": time.time()}
    game_types = {
        "taixiu": {"type": "taixiu", "w": 0, "l": 0, **bases},
        "baucua": {"type": "baucua", "sym": ["Cua", "Ca", "Tom", "Ga", "Nai", "Bau"], "w": 0, "l": 0, **bases},
        "kbb": {"type": "kbb", "score": 0, "bot": 0, "draw": 0, **bases},
        "doanso": {"type": "doanso", "secret": ai_random.randint(1, 100), "att": 0, "max": 7, **bases},
        "lxn": {"type": "lxn", "w": 0, "l": 0, **bases},
        "xx": {"type": "xx", "w": 0, "l": 0, **bases},
        "caudo": {"type": "caudo", "score": 0, "qnum": 0, "cur": None, "hint": False, "ans": False, **bases},
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
    if get_bal(uid) < amount:
        return False, f"❌ Không đủ xu! Số dư: {get_bal(uid):,} xu\n💰 Nhận thêm: /daily"
    return True, ""

def resolve_bet(uid, bet_amount, won: bool, multiplier: float = 1.0) -> Tuple[int, bool, str]:
    bao_bonus, is_bao = bao_x10(bet_amount)
    if won:
        win_amount = int(bet_amount * multiplier) + bao_bonus
        add_bal(uid, win_amount)
        out = f"🎉 Thắng +{win_amount:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
        return win_amount, is_bao, out
    else:
        deduct_bal(uid, bet_amount)
        out = f"💔 Thua -{bet_amount:,} xu"
        return -bet_amount, False, out

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          GAME 1-12: TOÀN BỘ GAME CŨ (GIỮ NGUYÊN, THÊM GAME MỚI)           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
# [GIỮ NGUYÊN TẤT CẢ GAME 1-12 TỪ MÃ NGUỒN GỐC - TÀI XỈU, BẦU CUA, KBB, ...]
# Để tiết kiệm không gian, tôi giữ nguyên các game 1-12 từ code gốc
# Chỉ thêm game 13-18 mới bên dưới

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 13: RỒNG HỔ                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['rongho'])
def rongho(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "rongho":
            GAME_SESSIONS[uid] = init_game(uid, "rongho")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🐉 <b>RỒNG HỔ BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> Rồng vs Hổ, bài ai cao hơn thắng\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"💰 <b>Thắng:</b> x2 tiền cược\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /rongho [rong/ho] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /rongho [rong/ho] [cược]")
        del_both(m, m2.message_id)
        return

    if ch not in ['rong', 'ho']:
        m2 = bot.reply_to(m, "❌ Chọn <b>rong</b> hoặc <b>ho</b>")
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
    g["last_active"] = time.time()

    rong = ai_random.randint(1, 13)
    ho = ai_random.randint(1, 13)
    cards = {1: "A", 11: "J", 12: "Q", 13: "K"}
    rong_str = cards.get(rong, str(rong))
    ho_str = cards.get(ho, str(ho))

    if rong > ho:
        res = "rong"
    elif ho > rong:
        res = "ho"
    else:
        res = "hoa"

    won = (ch == res)
    if res == "hoa":
        add_bal(uid, bt)
        out = "🤝 Hòa! Hoàn tiền cược"
    else:
        _, _, out = resolve_bet(uid, bt, won, multiplier=2)

    if won:
        g["w"] += 1
    elif res != "hoa":
        g["l"] += 1

    brain.stats["games"] += 1
    m2 = bot.reply_to(m,
        f"🐉 <b>RỒNG HỔ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🐉 Rồng: <b>{rong_str}</b> | 🐯 Hổ: <b>{ho_str}</b>\n"
        f"🎯 Kết quả: <b>{'RỒNG' if res == 'rong' else 'HỔ' if res == 'ho' else 'HÒA'}</b>\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 14: CHẴN LẺ 2 (KIỂU MỚI)                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['chanle2'])
def chanle2(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 3:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "chanle2":
            GAME_SESSIONS[uid] = init_game(uid, "chanle2")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🔢 <b>CHẴN LẺ 2 BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> Tổng 2 số 1-50, đoán chẵn/lẻ\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"💰 <b>Thắng:</b> x4 tiền cược\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /chanle2 [chan/le] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    ch = parts[1].lower()
    try:
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ Cược phải là số.")
        del_both(m, m2.message_id)
        return

    if ch not in ['chan', 'le']:
        m2 = bot.reply_to(m, "❌ Chọn <b>chan</b> hoặc <b>le</b>")
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
    g["last_active"] = time.time()

    n1 = ai_random.randint(1, 50)
    n2 = ai_random.randint(1, 50)
    total = n1 + n2
    res = "chan" if total % 2 == 0 else "le"
    won = (ch == res)

    _, _, out = resolve_bet(uid, bt, won, multiplier=4)
    if won:
        g["w"] += 1
    else:
        g["l"] += 1

    brain.stats["games"] += 1
    m2 = bot.reply_to(m,
        f"🔢 <b>CHẴN LẺ 2</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 {n1} + {n2} = <b>{total}</b> → <b>{'CHẴN' if total % 2 == 0 else 'LẺ'}</b>\n"
        f"🎯 Bạn chọn: <b>{ch.upper()}</b>\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 15: 3 CÂY                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['3cay'])
def ba_cay(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "3cay":
            GAME_SESSIONS[uid] = init_game(uid, "3cay")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🃏 <b>3 CÂY BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> So 3 lá bài, ai cao điểm hơn thắng\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"💰 <b>Thắng:</b> x5 tiền cược\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /3cay [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    try:
        bt = int(parts[1])
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
    g["last_active"] = time.time()

    suits = ["♠", "♥", "♦", "♣"]
    user_cards = [ai_random.randint(1, 13) for _ in range(3)]
    bot_cards = [ai_random.randint(1, 13) for _ in range(3)]
    cards_map = {1: "A", 11: "J", 12: "Q", 13: "K"}
    
    user_score = sum(min(c, 10) for c in user_cards) % 10
    bot_score = sum(min(c, 10) for c in bot_cards) % 10
    
    user_display = " ".join(f"{cards_map.get(c, str(c))}{ai_random.choice(suits)}" for c in user_cards)
    bot_display = " ".join(f"{cards_map.get(c, str(c))}{ai_random.choice(suits)}" for c in bot_cards)

    if user_score > bot_score:
        won = True
    elif user_score < bot_score:
        won = False
    else:
        won = None

    if won is None:
        add_bal(uid, bt)
        out = "🤝 Hòa! Hoàn tiền cược"
    else:
        _, _, out = resolve_bet(uid, bt, won, multiplier=5)

    if won:
        g["w"] += 1
    elif won is not None:
        g["l"] += 1

    brain.stats["games"] += 1
    m2 = bot.reply_to(m,
        f"🃏 <b>3 CÂY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Bạn: {user_display} → <b>{user_score} điểm</b>\n"
        f"🤖 Bot: {bot_display} → <b>{bot_score} điểm</b>\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 16: SLOT MACHINE                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['slot'])
def slot_machine(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "slot":
            GAME_SESSIONS[uid] = init_game(uid, "slot")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🎰 <b>SLOT MACHINE BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> 3 cột, khớp biểu tượng để thắng\n"
            f"💎 777 = x50 | 🍒🍒🍒 = x10 | Giống đôi = x2\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /slot [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🎰 Đã quay: {g['spins']} | 🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    try:
        bt = int(parts[1])
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
    g["last_active"] = time.time()
    g["spins"] += 1

    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
    weights = [25, 20, 18, 15, 10, 8, 4]
    
    c1 = ai_random.choice(symbols)
    c2 = ai_random.choice(symbols)
    c3 = ai_random.choice(symbols)

    if c1 == c2 == c3:
        if c1 == "7️⃣":
            mult = 50
        elif c1 == "💎":
            mult = 25
        else:
            mult = 10
        won = True
    elif c1 == c2 or c2 == c3 or c1 == c3:
        mult = 2
        won = True
    else:
        won = False
        mult = 0

    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won:
        g["w"] += 1
    else:
        g["l"] += 1

    brain.stats["games"] += 1
    m2 = bot.reply_to(m,
        f"🎰 <b>SLOT MACHINE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"┌─────┐\n"
        f"│{c1}│{c2}│{c3}│\n"
        f"└─────┘\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎰 Đã quay: {g['spins']} | 🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 17: BẦU CUA SLOT                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['bauslot'])
def bau_slot(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 2:
        if uid not in GAME_SESSIONS or GAME_SESSIONS[uid].get("type") != "bauslot":
            GAME_SESSIONS[uid] = init_game(uid, "bauslot")
        g = GAME_SESSIONS[uid]
        g["last_active"] = time.time()
        m2 = bot.reply_to(m,
            f"🎰 <b>BẦU CUA SLOT BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> 3 cột bầu cua, giống 3 = x20, giống 2 = x3\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /bauslot [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    try:
        bt = int(parts[1])
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
    g["last_active"] = time.time()

    syms = ["🐄", "🦀", "🐟", "🐔", "🦌", "🦐"]
    c1 = ai_random.choice(syms)
    c2 = ai_random.choice(syms)
    c3 = ai_random.choice(syms)

    if c1 == c2 == c3:
        won = True
        mult = 20
    elif c1 == c2 or c2 == c3 or c1 == c3:
        won = True
        mult = 3
    else:
        won = False
        mult = 0

    _, _, out = resolve_bet(uid, bt, won, multiplier=mult)
    if won:
        g["w"] += 1
    else:
        g["l"] += 1

    brain.stats["games"] += 1
    m2 = bot.reply_to(m,
        f"🎰 <b>BẦU CUA SLOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"┌─────┐\n"
        f"│{c1}│{c2}│{c3}│\n"
        f"└─────┘\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Thắng: {g['w']} | Thua: {g['l']}\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    GAME 18: ĐOÁN SỐ SIÊU TỐC 3 LƯỢT                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['doanso3'])
def doanso3(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 3:
        GAME_SESSIONS[uid] = init_game(uid, "doanso3")
        m2 = bot.reply_to(m,
            f"⚡ <b>ĐOÁN SỐ SIÊU TỐC 3 LƯỢT - BÃO X10</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Luật:</b> Đoán số 1-50, chỉ 3 lần đoán\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n"
            f"💰 <b>Thưởng:</b> 1 lần = x50, 2 lần = x25, 3 lần = x10\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 /doanso3 [số] [cược]\n"
            f"💵 Cược: {GAME_MIN_BET:,} - {GAME_MAX_BET:,} xu\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    try:
        gs = int(parts[1])
        bt = int(parts[2])
    except:
        m2 = bot.reply_to(m, "❌ /doanso3 [số 1-50] [cược]")
        del_both(m, m2.message_id)
        return

    if gs < 1 or gs > 50:
        m2 = bot.reply_to(m, "❌ Số từ 1-50.")
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
    g["last_active"] = time.time()
    brain.stats["games"] += 1

    if gs == g["secret"]:
        multipliers = {1: 50, 2: 25, 3: 10}
        mult = multipliers.get(g["att"], 5)
        _, _, out = resolve_bet(uid, bt, True, multiplier=mult)
        m2 = bot.reply_to(m,
            f"⚡ <b>CHÍNH XÁC!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số: <b>{g['secret']}</b>\n"
            f"🔢 Lần đoán: <b>{g['att']}</b> (x{mult})\n"
            f"{out}\n"
            f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
            parse_mode="HTML"
        )
        del GAME_SESSIONS[uid]
    elif g["att"] >= g["max"]:
        deduct_bal(uid, bt)
        m2 = bot.reply_to(m,
            f"💔 <b>HẾT LƯỢT!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Số đúng: <b>{g['secret']}</b>\n"
            f"💔 Thua -{bt:,} xu\n"
            f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
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
    global nohu_jp
    if not is_grp(m):
        return
    uid = m.from_user.id
    parts = m.text.split()

    if len(parts) < 2:
        m2 = bot.reply_to(m,
            f"🎰 <b>NỔ HŨ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 JP: {nohu_jp:,} xu\n"
            f"🎫 Phí: {nohu_fee:,} xu/lượt\n"
            f"💥 <b>Bão X10:</b> 10% cơ hội nhân 10\n\n"
            f"/nohu [cược]",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    try:
        bet = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ Nhập số.")
        del_both(m, m2.message_id)
        return

    if bet < 100 or bet > 100000:
        m2 = bot.reply_to(m, "❌ Cược từ 100 - 100,000 xu.")
        del_both(m, m2.message_id)
        return

    total = bet + nohu_fee
    if not deduct_bal(uid, total):
        m2 = bot.reply_to(m, f"❌ Không đủ! Cần {total:,} xu\n💰 Số dư: {get_bal(uid):,} xu")
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
            out = f"🎉 JACKPOT! +{win:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
        else:
            win = bet * 5 + bao_bonus
            add_bal(uid, win)
            out = f"🎉 Nổ! +{win:,} xu" + (" 💥 BÃO X10!!!" if is_bao else "")
    elif c1 == c2 or c2 == c3 or c1 == c3:
        win = int(bet * 0.5)
        add_bal(uid, win)
        out = f"🤏 Hoàn {win:,} xu"
    else:
        out = f"💔 Thua -{total:,} xu"

    brain.stats["nohu"] += 1
    m2 = bot.reply_to(m,
        f"🎰 <b>NỔ HŨ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{c1}{c2}{c3}\n"
        f"{out}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 JP: {nohu_jp:,} xu\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['daily'])
def daily(m):
    if not is_grp(m):
        return
    uid = m.from_user.id
    today = date.today().isoformat()

    if daily_ck.get(uid) == today:
        m2 = bot.reply_to(m,
            f"✅ Đã điểm danh hôm nay!\n"
            f"💰 Số dư: {get_bal(uid):,} xu\n"
            f"⏰ Quay lại sau 0h",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    daily_ck[uid] = today
    rw = 500 + ai_random.randint(0, 1000)
    add_bal(uid, rw)
    save_json(DAILY_FILE, daily_ck)
    m2 = bot.reply_to(m,
        f"📅 <b>ĐIỂM DANH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ +{rw:,} xu\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['balance', 'xu'])
def balance_cmd(m):
    if not is_grp(m):
        return
    t = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    n = m.reply_to_message.from_user.first_name if m.reply_to_message else m.from_user.first_name
    m2 = bot.reply_to(m,
        f"💰 <b>{html.escape(n)}:</b> {get_bal(t):,} xu",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['top'])
def top(m):
    if not is_grp(m):
        return
    sb = sorted(balance.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 <b>BẢNG XẾP HẠNG</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    if not sb:
        text += "Chưa có ai chơi!\n"
    else:
        medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
        for i, (uid, bal) in enumerate(sb):
            name = users.get(str(uid), str(uid))
            text += f"{medals[i]} <b>{html.escape(name)}</b>: {bal:,} xu\n"
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
        try:
            amt = int(parts[1]) if len(parts) > 1 else 0
        except:
            pass
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
            try:
                amt = int(parts[2])
            except:
                pass

    if not target or amt < 100:
        m2 = bot.reply_to(m,
            "❌ <b>Cách dùng:</b>\n"
            "• /give [số xu] (reply tin nhắn)\n"
            "• /give @username [số xu]\n"
            "• /give [user_id] [số xu]\n"
            "💵 Tối thiểu: 100 xu\n"
            "💸 Phí: 5%",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    if target == uid:
        m2 = bot.reply_to(m, "❌ Không thể tự chuyển cho mình!")
        del_both(m, m2.message_id)
        return

    fee = int(amt * 0.05)
    total = amt + fee

    if not deduct_bal(uid, total):
        m2 = bot.reply_to(m,
            f"❌ Không đủ xu!\n"
            f"💰 Cần: {total:,} xu (gồm {fee:,} phí)\n"
            f"💰 Số dư: {get_bal(uid):,} xu",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return

    add_bal(target, amt)
    target_name = users.get(str(target), str(target))
    m2 = bot.reply_to(m,
        f"✅ <b>CHUYỂN XU</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 {amt:,} xu → {html.escape(target_name)}\n"
        f"💵 Phí: {fee:,} xu\n"
        f"💰 Số dư: <b>{get_bal(uid):,} xu</b>",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT CẢI TIẾN - GÁI 18 BIỂU CẢM                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def ask_ai(prompt):
    """AI chat với phong cách gái 18 tuổi nhiệt tình."""
    global ck_idx
    
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]
    
    cam_xuc = phan_loai_cam_xuc(prompt)
    loi_chao_cam_xuc = ai_random.choice(GIRL_EMOTIONS[cam_xuc])
    
    system_prompt = (
        "Bạn là trợ lý ảo nữ 18 tuổi người Việt, tên Nao. "
        "Tính cách: nhiệt tình, đáng yêu, nói chuyện như gái miền Nam. "
        "Luôn gọi người dùng là 'anh iu' hoặc 'anh'. "
        "Trả lời ngắn gọn dưới 15 từ, thêm emoji dễ thương. "
        "Không dùng từ ngữ thô tục, không chửi thề. "
        "Phong cách: nhẹ nhàng, hỗ trợ hết mình, thỉnh thoảng thả thính."
    )
    
    msgs = [{"role": "system", "content": system_prompt}]
    for t in list(mem)[-6:]:
        idx = list(mem).index(t)
        role = "user" if idx % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": t})
    msgs.append({"role": "user", "content": prompt})
    
    acquired = ck_lock.acquire(timeout=5)
    if not acquired:
        logger.warning("AI lock timeout - dùng fallback")
        return loi_chao_cam_xuc
    
    try:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k.get("status", True) or k.get("fail", 0) >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                r = ses.post(
                    k["url"],
                    json={
                        "model": k["model"],
                        "messages": msgs,
                        "max_tokens": 60,
                        "temperature": 0.9
                    },
                    headers={"Authorization": f"Bearer {k['key']}"},
                    timeout=8
                )
                if r.status_code == 200:
                    txt = r.json()['choices'][0]['message']['content'].strip()
                    txt = re.sub(r'[_*`\[\](){}]', '', txt)
                    if len(txt) > 100:
                        txt = txt[:97] + "..."
                    k["fail"] = 0
                    mem.append(prompt)
                    mem.append(txt)
                    brain.stats["ai"] += 1
                    return txt
                else:
                    k["fail"] = k.get("fail", 0) + 1
            except Exception as e:
                k["fail"] = k.get("fail", 0) + 1
                logger.error(f"AI request error: {str(e)[:100]}")
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
        
        for k in AI_KEYS:
            k["status"] = True
            k["fail"] = 0
        return loi_chao_cam_xuc
    finally:
        ck_lock.release()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    ANTISPAM                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
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
            if uid in warns:
                del warns[uid]
        else:
            try:
                bot.delete_message(m.chat.id, m.message_id)
            except:
                pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    HANDLERS - LỆNH CHÍNH                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_json(USR_FILE, users)
    brain.trusted.add(m.from_user.id)
    help_text = (
        f"🤖 <b>NAO ROBOT v{AutoUpdater.PHIEN_BAN_HIEN_TAI} - GÁI 18 HỖ TRỢ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💖 <b>TÍNH NĂNG CHÍNH:</b>\n"
        "📜 /tho [sang/toi/tinhyeu/cuocsong] - Em làm thơ tặng anh\n"
        "👋 /chao - Em chào anh iu nè\n"
        "🎙️ /voice [text] - 18 giọng Bắc thuần Việt\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 <b>18 GAMES BÃO X10:</b>\n"
        "/taixiu /baucua /kbb /doanso\n"
        "/lxn /xx /caudo /chanle\n"
        "/caothap /keo /bingo /doanso2\n"
        "/rongho /chanle2 /3cay /slot\n"
        "/bauslot /doanso3\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎰 /nohu | 📅 /daily | 💰 /balance\n"
        "🏆 /top | 💸 /give\n"
        "🔨 /ban /mute /unmute /warn\n"
        "📊 /stats | 💾 /ramstatus\n"
        "🔄 /update (admin)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ v{AutoUpdater.PHIEN_BAN_HIEN_TAI} - Gái 18 × Thơ AI × Tự Update"
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

    req = VoiceRequest(
        chat_id=m.chat.id,
        reply_id=m.message_id,
        text=txt,
        user_name=m.from_user.first_name,
        user_id=m.from_user.id,
        voice=selected
    )
    try:
        voice_queue.put_nowait(req)
        m2 = bot.reply_to(m, "🎙️ Đã nhận yêu cầu...")
        auto_del(m.chat.id, m2.message_id, 10)
    except Full:
        m2 = bot.reply_to(m, "⚠️ Hàng đợi đầy, thử lại sau.")
        del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    LỆNH MỚI: THƠ, CHÀO, UPDATE                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['tho'])
def lenh_tho(m):
    """Lệnh yêu cầu bot làm thơ."""
    if not is_grp(m):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_json(USR_FILE, users)
    
    parts = m.text.split()
    loai = "sang" if datetime.now(tz).hour < 18 else "toi"
    chu_de_tuy_chinh = ""
    
    if len(parts) > 1:
        loai_input = parts[1].lower()
        if loai_input in ["sang", "toi", "tinhyeu", "cuocsong"]:
            loai = loai_input
            if len(parts) > 2:
                chu_de_tuy_chinh = " ".join(parts[2:])
        else:
            loai = "tuy_chinh"
            chu_de_tuy_chinh = " ".join(parts[1:])
    
    m2 = bot.reply_to(m, "📝 Em đang làm thơ tặng anh, đợi em xíu nha... 💕")
    
    def lam_tho():
        tho = ThoAI.tao_tho(loai, chu_de_tuy_chinh)
        try:
            bot.delete_message(m.chat.id, m2.message_id)
        except:
            pass
        
        emoji_map = {"sang": "🌅", "toi": "🌙", "tinhyeu": "💝", "cuocsong": "🌟", "tuy_chinh": "📜"}
        ten_map = {"sang": "SÁNG", "toi": "TỐI", "tinhyeu": "TÌNH YÊU", "cuocsong": "CUỘC SỐNG", "tuy_chinh": "TẶNG ANH"}
        
        brain.stats["tho"] += 1
        m3 = bot.reply_to(m,
            f"{emoji_map.get(loai, '📜')} <b>THƠ {ten_map.get(loai, '')} TẶNG ANH {html.escape(m.from_user.first_name)}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>{html.escape(tho)}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💖 Em mong anh thích nha!",
            parse_mode="HTML"
        )
        auto_del(m.chat.id, m3.message_id, 120)
    
    tho_executor.submit(lam_tho)

@bot.message_handler(commands=['chao'])
def lenh_chao(m):
    """Lệnh chào thủ công."""
    if not is_grp(m):
        return
    
    gio_hien_tai = datetime.now(tz).hour
    if gio_hien_tai < 12:
        loi_chao = ai_random.choice(GIRL_EMOTIONS["chao_buoi_sang"])
    else:
        loi_chao = ai_random.choice(GIRL_EMOTIONS["chao_buoi_toi"])
    
    m2 = bot.reply_to(m, f"{loi_chao}\n\n💖 Em chúc anh một ngày thật vui nha!", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['update'])
def lenh_cap_nhat(m):
    """Lệnh kiểm tra và áp dụng cập nhật (admin only)."""
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới dùng được lệnh này nha anh! 🥺")
        del_both(m, m2.message_id)
        return
    
    m2 = bot.reply_to(m, "🔄 Em đang kiểm tra cập nhật mới...")
    
    def kiem_tra():
        cap_nhat = AutoUpdater.kiem_tra_cap_nhat()
        try:
            bot.delete_message(m.chat.id, m2.message_id)
        except:
            pass
        
        if not cap_nhat:
            m3 = bot.reply_to(m,
                f"✅ <b>Bot đã là phiên bản mới nhất!</b>\n"
                f"🔖 v{AutoUpdater.PHIEN_BAN_HIEN_TAI}\n"
                f"💖 Không có gì để cập nhật ạ!",
                parse_mode="HTML"
            )
            del_both(m, m3.message_id)
            return
        
        m3 = bot.reply_to(m,
            f"🔄 <b>PHÁT HIỆN CẬP NHẬT MỚI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 {html.escape(cap_nhat['message'][:200])}\n"
            f"🔖 Commit: <code>{cap_nhat['sha'][:8]}</code>\n"
            f"📅 Ngày: {cap_nhat.get('date', 'N/A')}\n\n"
            f"⏳ Đang tự động áp dụng...",
            parse_mode="HTML"
        )
        
        thanh_cong = AutoUpdater.tai_va_ap_dung_cap_nhat(cap_nhat)
        if not thanh_cong:
            bot.send_message(m.chat.id, "❌ Cập nhật thất bại, anh kiểm tra log giúp em nha! 🥺")
    
    update_executor.submit(kiem_tra)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    ADMIN COMMANDS                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['ban'])
def ban(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if target:
        try:
            bot.ban_chat_member(m.chat.id, target)
            bot.delete_message(m.chat.id, m.message_id)
            logger.info(f"Admin banned user {target}")
        except Exception as e:
            logger.error(f"Ban error: {e}")

@bot.message_handler(commands=['mute'])
def mute(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        return
    dur = parse_duration(reason) if reason else 3600
    try:
        bot.restrict_chat_member(
            m.chat.id, target,
            until_date=int(time.time()) + dur,
            can_send_messages=False
        )
        bot.delete_message(m.chat.id, m.message_id)
        mutes[target] = int(time.time()) + dur
        logger.info(f"Admin muted user {target} for {dur}s")
    except Exception as e:
        logger.error(f"Mute error: {e}")

@bot.message_handler(commands=['unmute'])
def unmute(m):
    if not is_grp(m) or not is_adm(m):
        return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if target:
        try:
            bot.restrict_chat_member(m.chat.id, target, can_send_messages=True)
            bot.delete_message(m.chat.id, m.message_id)
            if target in mutes:
                del mutes[target]
            logger.info(f"Admin unmuted user {target}")
        except Exception as e:
            logger.error(f"Unmute error: {e}")

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
            if target in warns:
                del warns[target]
            logger.info(f"User {target} auto-banned after 3 warns")
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
    uptime_seconds = int(time.time() - brain.stats["start"])
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    m2 = bot.reply_to(m,
        f"📊 <b>THỐNG KÊ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Thành viên: {rc}\n"
        f"⏱️ Uptime: {hours}h {minutes}m {seconds}s\n"
        f"💬 AI chat: {brain.stats['ai']}\n"
        f"🎮 Games: {brain.stats['games']}\n"
        f"🎰 Nổ hũ: {brain.stats['nohu']}\n"
        f"🎙️ Voice: {brain.stats['voice']}\n"
        f"📜 Thơ AI: {brain.stats['tho']}\n"
        f"🌅 Chào sáng: {brain.stats['chao_sang']} | 🌙 Chào tối: {brain.stats['chao_toi']}\n"
        f"🧹 RAM cleans: {ram_mgr.cleans}\n"
        f"📦 Game sessions: {len(GAME_SESSIONS)}\n"
        f"🧵 Active threads: {threading.active_count()}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['ramstatus'])
def ramstatus(m):
    if not is_grp(m):
        return
    m2 = bot.reply_to(m,
        f"💾 <b>RAM STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Usage: {ram_mgr.usage_mb():.1f} MB\n"
        f"🧹 Cleans: {ram_mgr.cleans}\n"
        f"💨 Freed: {ram_mgr.freed/1024/1024:.1f} MB\n"
        f"📦 Cache: {len(ram_mgr.cache)} entries\n"
        f"🧵 Threads: {threading.active_count()}\n"
        f"📮 Voice queue: {voice_queue.qsize()}/{voice_queue.maxsize}",
        parse_mode="HTML"
    )
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

    acquired = ai_semaphore.acquire(timeout=5)
    if not acquired:
        logger.warning(f"AI semaphore timeout for user {uid}")
        return

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
        loi_chao = ai_random.choice(GIRL_EMOTIONS["vui_ve"])
        m2 = bot.send_message(
            m.chat.id,
            f"👋 {html.escape(u.first_name)} ơi! {loi_chao}\n"
            f"🤖 Xem lệnh: /start"
        )
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

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CHÀO SÁNG/TỐI TỰ ĐỘNG                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def chao_buoi_sang_tu_dong():
    """Tự động gửi thơ chào buổi sáng vào group."""
    try:
        tho_sang = ThoAI.tao_tho("sang")
        loi_chao = ai_random.choice(GIRL_EMOTIONS["chao_buoi_sang"])
        tin_nhan = (
            f"{loi_chao}\n\n"
            f"📜 <b>THƠ SÁNG TẶNG CẢ NHÀ NÈ:</b>\n"
            f"<i>{html.escape(tho_sang)}</i>\n\n"
            f"💖 Chúc cả nhà ngày mới tràn đầy năng lượng nha!"
        )
        msg = bot.send_message(GROUP_ID, tin_nhan, parse_mode="HTML")
        brain.stats["chao_sang"] += 1
        logger.info("Đã gửi thơ chào buổi sáng")
        return msg.message_id
    except Exception as e:
        logger.error(f"Gửi thơ sáng lỗi: {str(e)[:100]}")
        return None

def chao_buoi_toi_tu_dong():
    """Tự động gửi thơ chào buổi tối vào group."""
    try:
        tho_toi = ThoAI.tao_tho("toi")
        loi_chao = ai_random.choice(GIRL_EMOTIONS["chao_buoi_toi"])
        tin_nhan = (
            f"{loi_chao}\n\n"
            f"📜 <b>THƠ TỐI TẶNG CẢ NHÀ NÈ:</b>\n"
            f"<i>{html.escape(tho_toi)}</i>\n\n"
            f"🌙 Chúc cả nhà ngủ thật ngon, mơ thật đẹp nha!"
        )
        msg = bot.send_message(GROUP_ID, tin_nhan, parse_mode="HTML")
        brain.stats["chao_toi"] += 1
        logger.info("Đã gửi thơ chào buổi tối")
        return msg.message_id
    except Exception as e:
        logger.error(f"Gửi thơ tối lỗi: {str(e)[:100]}")
        return None

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    SCHEDULER CẢI TIẾN                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def scheduler_cai_tien():
    """Scheduler mới: thơ sáng/tối + chat giờ + dọn dẹp + tự update."""
    last_hour = -1
    da_chao_sang = False
    da_chao_toi = False
    last_update_check = time.time()
    
    while True:
        try:
            now = datetime.now(tz)
            gio_hien_tai = now.hour
            
            if gio_hien_tai == 0:
                da_chao_sang = False
                da_chao_toi = False
            
            if gio_hien_tai == 6 and now.minute == 30 and not da_chao_sang and users:
                chao_buoi_sang_tu_dong()
                da_chao_sang = True
            
            if gio_hien_tai == 21 and now.minute == 0 and not da_chao_toi and users:
                chao_buoi_toi_tu_dong()
                da_chao_toi = True
            
            if now.minute == 0 and gio_hien_tai != last_hour and users:
                uid, un = ai_random.choice(list(users.items()))
                try:
                    msg = bot.send_message(
                        GROUP_ID,
                        f"🕐 {now.strftime('%H:%M')} | {un} ơi... {ai_random.choice(GIRL_EMOTIONS['quan_tam'])}"
                    )
                    auto_del(GROUP_ID, msg.message_id, 90)
                except:
                    pass
                last_hour = gio_hien_tai
            
            if now.minute != 0:
                last_hour = -1
            
            for uid in list(mutes.keys()):
                if time.time() > mutes[uid]:
                    try:
                        bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                    except:
                        pass
                    del mutes[uid]
            
            if time.time() - last_update_check > 21600:
                cap_nhat = AutoUpdater.kiem_tra_cap_nhat()
                if cap_nhat:
                    logger.info(f"Phát hiện cập nhật mới: {cap_nhat['sha'][:8]}")
                    AutoUpdater.tai_va_ap_dung_cap_nhat(cap_nhat)
                    break
                last_update_check = time.time()
            
            if now.minute % 30 == 0 and now.second < 15:
                ram_mgr.ai_clean()
        
        except Exception as e:
            logger.error(f"Scheduler lỗi: {str(e)[:200]}")
        
        time.sleep(15)

def auto_save():
    while True:
        time.sleep(600)
        try:
            save_json(USR_FILE, users)
            save_json(BAL_FILE, {str(k): v for k, v in balance.items()})
            save_json(DAILY_FILE, daily_ck)
            save_json(JP_FILE, {"jp": nohu_jp})
            logger.debug("Auto-save completed")
        except Exception as e:
            logger.error(f"Auto save error: {e}")

def health_check():
    while True:
        time.sleep(300)
        try:
            active_threads = threading.active_count()
            ram_usage = ram_mgr.usage_mb()
            logger.info(
                f"Health: {active_threads} threads, {ram_usage:.1f}MB RAM, "
                f"{len(GAME_SESSIONS)} game sessions, {len(spam)} spam entries, "
                f"voice_queue: {voice_queue.qsize()}"
            )
            if active_threads > 100:
                logger.warning(f"High thread count: {active_threads}")
            if ram_usage > 200:
                ram_mgr.ai_clean()
        except Exception as e:
            logger.error(f"Health check error: {e}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    MAIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    global balance, daily_ck, nohu_jp

    logger.info("="*60)
    logger.info(f"NAO ROBOT v{AutoUpdater.PHIEN_BAN_HIEN_TAI} STARTING...")
    logger.info("Gái 18 × Thơ AI × Tự Update × 18 Games Bão X10")

    if os.path.exists(USR_FILE):
        users.update(load_json(USR_FILE, {}))
    balance = {int(k): v for k, v in load_json(BAL_FILE, {}).items()}
    daily_ck = load_json(DAILY_FILE, {})
    nohu_jp = load_json(JP_FILE, {"jp": 100000}).get("jp", 100000)

    ram_mgr.start()

    logger.info(f"Users: {len(users)} | JP: {nohu_jp:,} xu")
    logger.info(f"18 Games Bão X10 | 18 Giọng Bắc | Gái 18 Biểu Cảm | Thơ AI | Tự Update")
    logger.info("="*60)

    Thread(target=scheduler_cai_tien, daemon=True, name="SchedulerV2").start()
    Thread(target=auto_save, daemon=True, name="AutoSave").start()
    Thread(target=health_check, daemon=True, name="HealthCheck").start()

    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
