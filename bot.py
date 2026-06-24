# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - AUDIO VOICE ĐÃ FIX                       │
# │  Phiên bản sửa lỗi TTS: hỗ trợ edge-tts, gTTS, pyttsx3 (offline)      │
# │  Tác giả: palofsc (palo)  |  Ngày: 2026-06-24                          │
# └────────────────────────────────────────────────────────────────────────┘
import sys
import io
import os
import json
import time
import random
import re
import html
import hashlib
import subprocess
import socket
import signal
import logging
import base64
import tempfile
import asyncio
import traceback
from threading import Thread, Lock, Event, Timer
from datetime import datetime, timedelta
from collections import deque, defaultdict, OrderedDict
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, PriorityQueue
from dataclasses import dataclass, field

# ─── LOGGING ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("NaoRobot")

# ─── ENCODING ──────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ─── KEEP ALIVE ────────────────────────────────────────────────────────────
try:
    from keep_alive import keep_alive
    keep_alive()
    logger.info("Keep-alive đã kích hoạt.")
except ImportError:
    logger.warning("Module keep_alive không tìm thấy, bỏ qua.")

# ─── THƯ VIỆN NGOÀI ───────────────────────────────────────────────────────
import telebot
from telebot import types, util
import requests
import pytz

# ╔══════════════════════════════════════════════════════════════╗
# ║  PHÁT HIỆN & KHỞI TẠO THƯ VIỆN TTS                         ║
# ╚══════════════════════════════════════════════════════════════╝

# --- edge-tts (giọng Việt online, tốt nhất) ---
HAS_EDGE_TTS = False
try:
    import edge_tts
    # Kiểm tra thử xem có import được không
    test_voices = asyncio.run(edge_tts.list_voices())
    vi_voices = [v for v in test_voices if v["Locale"] == "vi-VN"]
    if vi_voices:
        HAS_EDGE_TTS = True
        logger.info(f"edge-tts đã sẵn sàng ({len(vi_voices)} giọng vi-VN).")
    else:
        logger.warning("edge-tts không có giọng vi-VN.")
except Exception as e:
    logger.warning(f"edge-tts không khả dụng: {e}")

# --- gTTS (Google Text-to-Speech online) ---
HAS_GTTS = False
try:
    from gtts import gTTS
    # Kiểm tra nhanh
    test_tts = gTTS(text="test", lang="vi")
    HAS_GTTS = True
    logger.info("gTTS đã sẵn sàng.")
except Exception as e:
    logger.warning(f"gTTS không khả dụng: {e}")

# --- pyttsx3 (offline, không cần mạng) ---
HAS_PYTTSX3 = False
try:
    import pyttsx3
    # Khởi tạo engine để kiểm tra
    test_engine = pyttsx3.init()
    voices = test_engine.getProperty('voices')
    if voices:
        HAS_PYTTSX3 = True
        logger.info(f"pyttsx3 đã sẵn sàng ({len(voices)} giọng).")
    else:
        logger.warning("pyttsx3 không có giọng nào.")
    test_engine.stop()
except Exception as e:
    logger.warning(f"pyttsx3 không khả dụng: {e}")

# Nếu không có cái nào thì cảnh báo
if not HAS_EDGE_TTS and not HAS_GTTS and not HAS_PYTTSX3:
    logger.critical("KHÔNG CÓ THƯ VIỆN TTS NÀO! Cài: pip install edge-tts gtts pyttsx3")

# ╔══════════════════════════════════════════════════════════════╗
# ║  NÃO (BRAIN) - LỚP ĐIỀU KHIỂN TRUNG TÂM                    ║
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
            "msg_processed": 0,
            "spam_blocked": 0,
            "ai_calls": 0,
            "errors": 0,
            "votes_created": 0,
            "voice_generated": 0,
            "uptime_start": time.time(),
            "last_save": time.time()
        }
        self.decision_log: deque = deque(maxlen=200)
        self.last_health_check: float = time.time()
        self.repair_mode: bool = False
        self.file_lock = Lock()
        self.load_state()

    def load_state(self) -> None:
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
                logger.info(f"Não đã tải: mood={self.mood}, state={self.state}.")
            except Exception as e:
                logger.error(f"Lỗi tải não: {e}")

    def save_state(self) -> None:
        with self.file_lock:
            self.stats["last_save"] = time.time()
            try:
                data = {
                    "learned": dict(self.learned),
                    "banned": list(self.banned_words),
                    "trusted": list(self.trusted_users),
                    "stats": self.stats,
                    "state": self.state,
                    "mood": self.mood
                }
                with open(self.save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Lỗi lưu não: {e}")

    def think(self, context: Dict[str, Any]) -> str:
        uid = context.get("uid")
        txt = context.get("txt", "")
        self.stats["msg_processed"] += 1
        words = re.findall(r'\b\w{3,}\b', txt.lower())
        for w in words:
            self.learned[w] += 1
        neg = ["bot ngu", "bot dở", "bot lỗi", "mày ngu", "bot chậm"]
        pos = ["bot hay", "bot pro", "cảm ơn bot", "bot tốt", "bot giỏi"]
        if any(p in txt.lower() for p in neg):
            self.mood -= 2
        elif any(p in txt.lower() for p in pos):
            self.mood += 1
        self.mood = max(-10, min(10, self.mood))
        if self.mood < -5:
            self.state = "aggressive"
        elif self.mood > 5:
            self.state = "normal"
        else:
            self.state = "normal"
        self.decision_log.append({
            "time": datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S"),
            "uid": uid,
            "decision": self.state,
            "mood": self.mood
        })
        if len(self.decision_log) % 5 == 0:
            self.save_state()
        return self.state

    def should_reply(self, uid: int, msg_text: str) -> bool:
        if uid in self.trusted_users:
            return True
        if self.learned.get(msg_text.lower(), 0) > 5:
            return random.random() > 0.3
        return random.random() > 0.1

    def get_insult_level(self) -> str:
        if self.state == "aggressive":
            return "extreme"
        elif self.mood < 0:
            return "high"
        return "normal"

    def health_check(self) -> str:
        now = time.time()
        if now - self.last_health_check > 300:
            self.last_health_check = now
            if self.stats["errors"] > 20:
                self.repair_mode = True
                self.state = "repair"
                self.stats["errors"] = 0
                logger.warning("NÃO chuyển sang chế độ sửa chữa.")
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

# ─── HTTP SESSION ─────────────────────────────────────────────────────────
ses = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=200,
    pool_maxsize=500,
    max_retries=3,
    pool_block=False
)
ses.mount('https://', adapter)
ses.mount('http://', adapter)

# ─── THREAD POOL ──────────────────────────────────────────────────────────
ai_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="AI")
voice_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Voice")
download_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="Download")

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI KEYS (TỰ SỬA)                                          ║
# ╚══════════════════════════════════════════════════════════════╝
AI_KEYS: List[Dict[str, Any]] = [
    {
        "key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",
        "url": "https://api.byesu.com/v1/chat/completions",
        "model": "gpt-4o",
        "status": True,
        "fail": 0,
        "last_used": 0
    },
    {
        "key": "sk-d1c9defa13eaa7386af8f711f38e9e8dd7a4754c9eebfe7f5642a391db82c2c3",
        "url": "https://api.byesu.com/v1/chat/completions",
        "model": "gpt-4o",
        "status": True,
        "fail": 0,
        "last_used": 0
    },
    {
        "key": "fe_oa_7bd49f79bc22bda1bc0c9b89f37741aa0a3086e87cfba034",
        "url": "https://api.freemodel.dev/v1/chat/completions",
        "model": "gpt-4o",
        "status": True,
        "fail": 0,
        "last_used": 0
    }
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════╗
# ║  KHO CHỬI                                                  ║
# ╚══════════════════════════════════════════════════════════════╝
KHO_NORMAL = [
    "Mồm thối, câm đi.", "Não bã đậu, im lặng.", "Thùng rỗng kêu to.",
    "Cào phím nhanh, não chậm.", "Ảo tưởng sức mạnh.", "Về nhà rửa bát.",
    "IQ âm, đừng nói.", "Không ai cần mày.", "Mày là gì? Không là gì.", "Câm mồm, đỡ nhục."
]
KHO_HIGH = [
    "Nứt mắt đòi làm anh hùng.", "Đầu rỗng, mồm thối.", "Mạng xã hội nuôi mày à?",
    "Ra đời người ta vả cho.", "Mẹ gọi, về nhà đi.", "Tưởng mình ngầu? Hề vãi.",
    "Học không lo, cào phím giỏi.", "Tương lai mù mịt như chị Dậu.", "Đời vả mặt, mày cười ngây.",
    "Không có gì để nói với mày."
]
KHO_EXTREME = [
    "Mày đáng giá bằng cái nút block.", "Tồn tại để làm gì? Để tao chửi à?",
    "Não mày như ổ đĩa format nhầm.", "Mày là lỗi của tự nhiên, bug của xã hội.",
    "Tao chửi mày còn thấy phí thời gian.", "Mày không đáng để tao nhớ tên.",
    "Cút về lỗ mà mày chui ra.", "Mày là minh chứng cho thất bại của tiến hóa.",
    "Tao nhìn mày mà tưởng đang xem phim hài.", "Mày sống làm gì? Để tổn thương người khác à?"
]

def get_kho() -> List[str]:
    lvl = brain.get_insult_level()
    if lvl == "extreme":
        return KHO_EXTREME
    elif lvl == "high":
        return KHO_HIGH
    return KHO_NORMAL

# ╔══════════════════════════════════════════════════════════════╗
# ║  BIẾN TOÀN CỤC                                             ║
# ╚══════════════════════════════════════════════════════════════╝
lock = Lock()
mem = deque(maxlen=50)
users: Dict[str, str] = {}
spam: Dict[int, List[float]] = {}
warn_counts: Dict[int, int] = {}
mutes: Dict[int, float] = {}
ai_cd: Dict[int, float] = {}
vote_active: Dict[int, Dict] = {}
USR_FILE = "usr.json"
RULES_FILE = "rules.txt"

TIKTOK_LINK = re.compile(r'https?://(?:vm|vt|www|m)\.tiktok\.com/\S+', re.I)
TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}|@[a-zA-Z0-9_]{5,}', re.I)

# ╔══════════════════════════════════════════════════════════════╗
# ║  TIỆN ÍCH CHUNG                                            ║
# ╚══════════════════════════════════════════════════════════════╝
def load_users() -> Dict[str, str]:
    if os.path.exists(USR_FILE):
        try:
            with open(USR_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_users(data: Dict[str, str]) -> None:
    with lock:
        try:
            with open(USR_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Lỗi save users: {e}")

def del_msg(chat_id: int, msg_id: int, delay: int = 60) -> None:
    def _del():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
    Thread(target=_del, daemon=True).start()

def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in admins)
    except:
        return False

def is_grp(m: telebot.types.Message) -> bool:
    return m.chat.id == GROUP_ID

def extract_user_and_reason(message: telebot.types.Message, bot_username: str) -> Tuple[Optional[int], str]:
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
                mention_match = re.match(r'@(\w+)', arg)
                if mention_match:
                    try:
                        target = bot.get_chat_member(message.chat.id, mention_match.group(0)).user.id
                        reason = arg[mention_match.end():].strip()
                    except:
                        pass
                else:
                    num_match = re.search(r'\d+', arg)
                    if num_match:
                        target = int(num_match.group())
                        reason = arg[num_match.end():].strip()
    return target, reason

def parse_duration(reason: str) -> int:
    time_match = re.search(r'(\d+)\s*(h|m|s|p)', reason.lower())
    if time_match:
        num = int(time_match.group(1))
        unit = time_match.group(2)
        if unit == 's':
            return num
        elif unit == 'm':
            return num * 60
        elif unit == 'h':
            return num * 3600
        elif unit == 'p':
            return num * 60
    return 3600

# ╔══════════════════════════════════════════════════════════════╗
# ║  VOICE GENERATION (TTS) - ĐÃ SỬA LỖI                        ║
# ║  Thứ tự ưu tiên: edge-tts -> gTTS -> pyttsx3               ║
# ║  Nếu lỗi ở bước nào thì fallback xuống bước dưới           ║
# ╚══════════════════════════════════════════════════════════════╝

# Danh sách giọng vi-VN cho edge-tts
EDGE_VOICES_VI = [
    "vi-VN-NamNeural",      # Nam
    "vi-VN-HoaiMyNeural",   # Nữ (Hoài My)
    "vi-VN-AnNeural",       # Nữ (An)
    "vi-VN-LanNeural",      # Nữ (Lan)
    "vi-VN-LinhNeural",     # Nữ (Linh)
    "vi-VN-QuanNeural",     # Nam (Quân)
    "vi-VN-KienNeural",     # Nam (Kiên)
]

@dataclass
class VoiceRequest:
    chat_id: int
    reply_id: int
    text: str
    user_name: str
    lang: str = "vi"
    created_at: float = field(default_factory=time.time)

voice_queue: Queue = Queue(maxsize=30)

def generate_voice_edge(text: str) -> Optional[io.BytesIO]:
    """
    Tạo voice bằng edge-tts.
    Trả về BytesIO chứa file mp3, hoặc None nếu lỗi.
    """
    if not HAS_EDGE_TTS:
        logger.debug("edge-tts không khả dụng, bỏ qua.")
        return None
    
    # Chọn giọng ngẫu nhiên để đa dạng
    voice_name = random.choice(EDGE_VOICES_VI)
    logger.info(f"edge-tts: dùng giọng {voice_name}, text={text[:50]}...")
    
    temp_path = None
    try:
        # Tạo file tạm
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(temp_fd)
        
        # Chạy edge-tts async trong thread
        async def _gen():
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_path)
        
        # Tạo event loop mới cho thread này
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_gen())
        loop.close()
        
        # Đọc file tạm
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
        
        # Kiểm tra audio có hợp lệ không
        if len(audio_data) < 100:
            logger.warning(f"edge-tts: file audio quá nhỏ ({len(audio_data)} bytes).")
            return None
        
        logger.info(f"edge-tts: thành công, {len(audio_data)} bytes.")
        return io.BytesIO(audio_data)
        
    except Exception as e:
        logger.error(f"edge-tts lỗi: {e}\n{traceback.format_exc()}")
        return None
    finally:
        # Dọn dẹp file tạm
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

def generate_voice_gtts(text: str) -> Optional[io.BytesIO]:
    """
    Tạo voice bằng gTTS (Google Text-to-Speech).
    Trả về BytesIO chứa file mp3, hoặc None nếu lỗi.
    """
    if not HAS_GTTS:
        logger.debug("gTTS không khả dụng, bỏ qua.")
        return None
    
    logger.info(f"gTTS: text={text[:50]}...")
    try:
        buf = io.BytesIO()
        tts = gTTS(text=text, lang="vi", slow=False)
        tts.write_to_fp(buf)
        buf.seek(0)
        
        # Kiểm tra kích thước
        audio_data = buf.getvalue()
        if len(audio_data) < 100:
            logger.warning(f"gTTS: file audio quá nhỏ ({len(audio_data)} bytes).")
            return None
        
        logger.info(f"gTTS: thành công, {len(audio_data)} bytes.")
        return buf
    except Exception as e:
        logger.error(f"gTTS lỗi: {e}\n{traceback.format_exc()}")
        return None

def generate_voice_pyttsx3(text: str) -> Optional[io.BytesIO]:
    """
    Tạo voice bằng pyttsx3 (offline, không cần mạng).
    Trả về BytesIO chứa file wav, hoặc None nếu lỗi.
    """
    if not HAS_PYTTSX3:
        logger.debug("pyttsx3 không khả dụng, bỏ qua.")
        return None
    
    logger.info(f"pyttsx3: text={text[:50]}...")
    temp_path = None
    try:
        # Tạo file tạm
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        
        # Khởi tạo engine
        engine = pyttsx3.init()
        
        # Thử đặt giọng tiếng Việt nếu có
        voices = engine.getProperty('voices')
        vi_voice = None
        for voice in voices:
            if 'viet' in voice.name.lower() or 'vi' in voice.id.lower():
                vi_voice = voice.id
                break
        if vi_voice:
            engine.setProperty('voice', vi_voice)
        
        # Cấu hình tốc độ
        engine.setProperty('rate', 150)  # Tốc độ mặc định
        
        # Lưu ra file
        engine.save_to_file(text, temp_path)
        engine.runAndWait()
        engine.stop()
        
        # Đọc file
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
        
        if len(audio_data) < 100:
            logger.warning(f"pyttsx3: file audio quá nhỏ ({len(audio_data)} bytes).")
            return None
        
        logger.info(f"pyttsx3: thành công, {len(audio_data)} bytes.")
        return io.BytesIO(audio_data)
        
    except Exception as e:
        logger.error(f"pyttsx3 lỗi: {e}\n{traceback.format_exc()}")
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

def generate_voice(text: str) -> Tuple[Optional[io.BytesIO], str]:
    """
    Tạo voice, thử lần lượt edge-tts -> gTTS -> pyttsx3.
    Trả về (BytesIO, engine_name) hoặc (None, error_msg).
    """
    # Bước 1: Thử edge-tts (tốt nhất)
    logger.info("Thử edge-tts...")
    audio = generate_voice_edge(text)
    if audio:
        return audio, "edge-tts"
    
    # Bước 2: Fallback gTTS
    logger.info("edge-tts thất bại, thử gTTS...")
    audio = generate_voice_gtts(text)
    if audio:
        return audio, "gTTS"
    
    # Bước 3: Fallback pyttsx3 (offline)
    logger.info("gTTS thất bại, thử pyttsx3 (offline)...")
    audio = generate_voice_pyttsx3(text)
    if audio:
        return audio, "pyttsx3"
    
    # Tất cả đều thất bại
    logger.error("TẤT CẢ CÁC ENGINE TTS ĐỀU THẤT BẠI!")
    return None, "all_failed"

def voice_worker() -> None:
    """Worker xử lý hàng đợi voice liên tục."""
    while True:
        try:
            req: VoiceRequest = voice_queue.get(block=True, timeout=1)
            if req is None:
                continue
            
            # Giới hạn độ dài text (tối đa 400 ký tự để tránh lỗi)
            voice_text = req.text[:400].strip()
            
            # Nếu text rỗng sau khi strip thì báo lỗi
            if not voice_text:
                bot.send_message(
                    req.chat_id,
                    f"❌ {html.escape(req.user_name)}, text rỗng sau khi xử lý.",
                    parse_mode="HTML"
                )
                voice_queue.task_done()
                continue
            
            logger.info(f"Đang tạo voice cho '{req.user_name}': {voice_text[:50]}...")
            
            # Gửi tin nhắn đang xử lý
            status_msg = bot.send_message(
                req.chat_id,
                f"🎙️ Đang tạo giọng nói cho <b>{html.escape(req.user_name)}</b>...",
                parse_mode="HTML"
            )
            
            # Tạo voice
            audio, engine = generate_voice(voice_text)
            
            # Xóa tin nhắn trạng thái
            try:
                bot.delete_message(req.chat_id, status_msg.message_id)
            except:
                pass
            
            if audio and engine != "all_failed":
                # Gửi file audio
                ext = "mp3" if engine != "pyttsx3" else "wav"
                audio.name = f"voice_{req.user_name}_{int(time.time())}.{ext}"
                
                caption = (
                    f"🎙️ <b>{html.escape(req.user_name)}</b> nói:\n"
                    f"<i>{html.escape(voice_text[:200])}</i>\n"
                    f"<code>Engine: {engine}</code>"
                )
                
                bot.send_voice(
                    req.chat_id,
                    audio,
                    reply_to_message_id=req.reply_id,
                    caption=caption,
                    parse_mode="HTML"
                )
                brain.stats["voice_generated"] += 1
                logger.info(f"Voice đã gửi thành công ({engine}).")
            else:
                # Tất cả engine đều thất bại
                error_msg = (
                    f"❌ <b>{html.escape(req.user_name)}</b>, không thể tạo giọng nói.\n"
                    f"<i>Lý do: Tất cả engine TTS (edge-tts, gTTS, pyttsx3) đều thất bại.</i>\n"
                    f"<i>Text của bạn: {html.escape(voice_text[:100])}...</i>"
                )
                bot.send_message(
                    req.chat_id,
                    error_msg,
                    reply_to_message_id=req.reply_id,
                    parse_mode="HTML"
                )
                logger.error(f"Voice thất bại hoàn toàn cho user {req.user_name}.")
            
            voice_queue.task_done()
        except Exception as e:
            logger.error(f"Voice worker lỗi: {e}\n{traceback.format_exc()}")
            # Đánh dấu task done để không bị kẹt queue
            try:
                voice_queue.task_done()
            except:
                pass

# Khởi động voice workers
for _ in range(4):
    Thread(target=voice_worker, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI GỌI (TỰ SỬA)                                          ║
# ╚══════════════════════════════════════════════════════════════╝
def ask_ai(prompt: str, uid: Optional[int] = None) -> str:
    global ck_idx
    if brain.state == "sleep":
        return random.choice(get_kho())

    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]

    system_msg = "Bạn là kẻ cọc cằn, chửi khịa trẻ trâu. Xưng 'tao' gọi 'mày'. Trả lời dưới 12 từ, không emoji."
    messages = [{"role": "system", "content": system_msg}]
    for txt in list(mem)[-8:]:
        messages.append({"role": "user", "content": txt})
    messages.append({"role": "user", "content": prompt})

    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                resp = ses.post(
                    k["url"],
                    json={
                        "model": k["model"],
                        "messages": messages,
                        "max_tokens": 40,
                        "temperature": 0.9
                    },
                    headers={
                        "Authorization": f"Bearer {k['key']}",
                        "Content-Type": "application/json"
                    },
                    timeout=8
                )
                if resp.status_code == 200:
                    result = resp.json()['choices'][0]['message']['content'].strip()
                    result = re.sub(r'[_*`\[\]()]', '', result)
                    k["fail"] = 0
                    k["last_used"] = time.time()
                    mem.append(prompt)
                    mem.append(result)
                    brain.stats["ai_calls"] += 1
                    return result
                else:
                    k["fail"] += 1
                    if k["fail"] >= MAX_FAIL:
                        k["status"] = False
            except Exception as e:
                k["fail"] += 1
                if k["fail"] >= MAX_FAIL:
                    k["status"] = False
                brain.stats["errors"] += 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)

    if not any(k["status"] for k in AI_KEYS):
        for k in AI_KEYS:
            k["status"], k["fail"] = True, 0
        brain.stats["errors"] = 0
        brain.state = "repair"
        return "[Não tự sửa] AI đã reset. Thử lại sau 5s."
    return random.choice(get_kho())

# ╔══════════════════════════════════════════════════════════════╗
# ║  CHỐNG SPAM & LINK BẨN                                    ║
# ╚══════════════════════════════════════════════════════════════╝
def antispam(m: telebot.types.Message) -> bool:
    if is_admin(m.chat.id, m.from_user.id):
        return False
    uid, now = m.from_user.id, time.time()
    spam[uid] = [t for t in spam.get(uid, []) if now - t < 4] + [now]
    if len(spam[uid]) > 5:
        warn_counts[uid] = warn_counts.get(uid, 0) + 1
        brain.stats["spam_blocked"] += 1
        try:
            bot.delete_message(m.chat.id, m.message_id)
            if warn_counts[uid] >= 3:
                try:
                    bot.ban_chat_member(m.chat.id, uid, until_date=int(time.time())+3600)
                except:
                    pass
                bot.send_message(
                    m.chat.id,
                    f"🚫 <b>{html.escape(m.from_user.first_name)}</b> bị ban 1h vì spam.",
                    parse_mode="HTML"
                )
                del warn_counts[uid]
            else:
                w = bot.send_message(
                    m.chat.id,
                    f"⚠️ Spam {warn_counts[uid]}/3 <b>{html.escape(m.from_user.first_name)}</b>",
                    parse_mode="HTML"
                )
                del_msg(m.chat.id, w.message_id, 15)
        except:
            pass
        return True
    return False

def antilink(m: telebot.types.Message) -> bool:
    if is_admin(m.chat.id, m.from_user.id):
        return False
    text = (m.text or "") + (m.caption or "")
    if TELEGRAM_LINK.search(text):
        try:
            bot.delete_message(m.chat.id, m.message_id)
            w = bot.send_message(
                m.chat.id,
                f"⚠️ Link bẩn. {random.choice(get_kho())}",
                parse_mode="HTML"
            )
            del_msg(m.chat.id, w.message_id, 30)
        except:
            pass
        return True
    return False

# ╔══════════════════════════════════════════════════════════════╗
# ║  TẢI VIDEO TIKTOK                                          ║
# ╚══════════════════════════════════════════════════════════════╝
def download_tiktok(url: str, chat_id: int, reply_id: int) -> None:
    try:
        api_resp = ses.get(
            f"https://api.tikwm.com/api/?url={requests.utils.quote(url)}",
            timeout=10
        ).json()
        if api_resp.get("code") == 0:
            video_data = ses.get(api_resp["data"]["play"], timeout=20).content
            msg = bot.send_video(
                chat_id,
                io.BytesIO(video_data),
                reply_to_message_id=reply_id,
                caption="🎬 Của mày. <i>(Xóa 60s)</i>",
                parse_mode="HTML"
            )
            del_msg(chat_id, msg.message_id, 60)
    except Exception as e:
        brain.stats["errors"] += 1
        logger.error(f"Lỗi tải TikTok: {e}")

# ╔══════════════════════════════════════════════════════════════╗
# ║  LỆNH /voice (ĐÃ FIX) - TEXT TO SPEECH                     ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['voice'])
def voice_cmd(m: telebot.types.Message) -> None:
    """
    Lệnh /voice [text] - Chuyển văn bản thành giọng nói.
    Hỗ trợ reply để lấy text từ tin nhắn được reply.
    Tự động fallback qua edge-tts -> gTTS -> pyttsx3.
    """
    if not is_grp(m) or antispam(m) or antilink(m):
        return
    
    users[str(m.from_user.id)] = m.from_user.first_name
    save_users(users)

    # Lấy text: ưu tiên reply, sau đó là text sau lệnh
    voice_text = ""
    if m.reply_to_message and m.reply_to_message.text:
        voice_text = m.reply_to_message.text.strip()
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1:
            voice_text = parts[1].strip()
    
    if not voice_text:
        msg = bot.reply_to(m, "❌ Dùng: /voice [text] hoặc reply tin nhắn có text.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return

    # Kiểm tra độ dài (giới hạn 400 ký tự)
    if len(voice_text) > 400:
        voice_text = voice_text[:400]
        bot.reply_to(m, "⚠️ Text quá dài, đã cắt còn 400 ký tự.", parse_mode="HTML")
    
    # Kiểm tra text không chỉ toàn ký tự đặc biệt
    if not re.search(r'[a-zA-ZÀ-ỹà-ỹ0-9]', voice_text):
        msg = bot.reply_to(m, "❌ Text không chứa ký tự đọc được.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return

    # Đưa vào hàng đợi voice
    try:
        voice_queue.put_nowait(VoiceRequest(
            chat_id=m.chat.id,
            reply_id=m.message_id,
            text=voice_text,
            user_name=m.from_user.first_name
        ))
        msg = bot.reply_to(
            m,
            f"🎙️ <b>{html.escape(m.from_user.first_name)}</b>, yêu cầu voice đã được xếp hàng.\n"
            f"<i>Text: {html.escape(voice_text[:100])}...</i>",
            parse_mode="HTML"
        )
        del_msg(m.chat.id, msg.message_id, 8)
    except Exception as e:
        logger.error(f"Lỗi đưa vào queue voice: {e}")
        bot.reply_to(m, "⚠️ Hàng đợi voice đầy, thử lại sau.", parse_mode="HTML")

# ╔══════════════════════════════════════════════════════════════╗
# ║  LỆNH QUẢN LÍ NHÓM                                        ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.message_handler(commands=['ban'])
def ban_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần reply hoặc mention/ID để ban.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    try:
        bot.ban_chat_member(m.chat.id, target)
        bot.delete_message(m.chat.id, m.message_id)
        txt = f"🚫 <b>{html.escape(m.from_user.first_name)}</b> đã ban <code>{target}</code>"
        if reason:
            txt += f"\nLý do: {reason}"
        w = bot.send_message(m.chat.id, txt, parse_mode="HTML")
        del_msg(m.chat.id, w.message_id, 30)
    except Exception as e:
        bot.reply_to(m, f"⚠️ Lỗi: {str(e)[:100]}", parse_mode="HTML")

@bot.message_handler(commands=['unban'])
def unban_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần ID user cần unban.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    try:
        bot.unban_chat_member(m.chat.id, target)
        bot.delete_message(m.chat.id, m.message_id)
        w = bot.send_message(m.chat.id, f"✅ Đã unban <code>{target}</code>", parse_mode="HTML")
        del_msg(m.chat.id, w.message_id, 20)
    except Exception as e:
        bot.reply_to(m, f"⚠️ Lỗi: {str(e)[:100]}", parse_mode="HTML")

@bot.message_handler(commands=['mute'])
def mute_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần reply hoặc mention/ID để mute.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    duration = parse_duration(reason) if reason else 3600
    try:
        until_date = int(time.time()) + duration
        bot.restrict_chat_member(
            m.chat.id, target,
            until_date=until_date,
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        bot.delete_message(m.chat.id, m.message_id)
        dur_str = f"{duration//3600}h{(duration%3600)//60}m" if duration>=3600 else f"{duration//60}m{duration%60}s"
        w = bot.send_message(
            m.chat.id,
            f"🔇 <b>{html.escape(m.from_user.first_name)}</b> đã mute <code>{target}</code> trong {dur_str}",
            parse_mode="HTML"
        )
        del_msg(m.chat.id, w.message_id, 30)
        mutes[target] = until_date
    except Exception as e:
        bot.reply_to(m, f"⚠️ Lỗi: {str(e)[:100]}", parse_mode="HTML")

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, _ = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần reply hoặc mention/ID để unmute.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    try:
        bot.restrict_chat_member(
            m.chat.id, target,
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        bot.delete_message(m.chat.id, m.message_id)
        w = bot.send_message(m.chat.id, f"🔊 Đã unmute <code>{target}</code>", parse_mode="HTML")
        del_msg(m.chat.id, w.message_id, 20)
        if target in mutes:
            del mutes[target]
    except Exception as e:
        bot.reply_to(m, f"⚠️ Lỗi: {str(e)[:100]}", parse_mode="HTML")

@bot.message_handler(commands=['warn'])
def warn_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần reply hoặc mention/ID để warn.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    warn_counts[target] = warn_counts.get(target, 0) + 1
    cnt = warn_counts[target]
    bot.delete_message(m.chat.id, m.message_id)
    w = bot.send_message(
        m.chat.id,
        f"⚠️ <b>{html.escape(m.from_user.first_name)}</b> warn <code>{target}</code> [{cnt}/3]\nLý do: {reason if reason else 'Không'}",
        parse_mode="HTML"
    )
    del_msg(m.chat.id, w.message_id, 25)
    if cnt >= 3:
        try:
            bot.ban_chat_member(m.chat.id, target, until_date=int(time.time())+3600)
            bot.send_message(m.chat.id, f"🚫 <code>{target}</code> bị ban do đủ 3 warn.", parse_mode="HTML")
            del warn_counts[target]
        except Exception as e:
            logger.error(f"Warn ban error: {e}")

@bot.message_handler(commands=['del'])
def del_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    if m.reply_to_message:
        try:
            bot.delete_message(m.chat.id, m.reply_to_message.message_id)
            bot.delete_message(m.chat.id, m.message_id)
        except:
            pass
    else:
        msg = bot.reply_to(m, "❌ Phải reply tin nhắn cần xóa.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)

@bot.message_handler(commands=['rule'])
def rule_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m):
        return
    if m.text.strip() == '/rule':
        rules = ""
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                rules = f.read()
        if not rules:
            rules = "Chưa có nội quy."
        bot.reply_to(m, f"📜 Nội quy:\n{rules}", parse_mode="HTML")
    else:
        if not is_admin(m.chat.id, m.from_user.id):
            return
        new_rules = m.text.split(maxsplit=1)[1].strip()
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            f.write(new_rules)
        msg = bot.reply_to(m, "✅ Đã cập nhật nội quy.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)

@bot.message_handler(commands=['admin'])
def admin_list_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m):
        return
    try:
        admins = bot.get_chat_administrators(m.chat.id)
        text = "👑 <b>Quản trị viên:</b>\n"
        for admin in admins:
            if admin.user.is_bot:
                continue
            text += f"- <a href='tg://user?id={admin.user.id}'>{html.escape(admin.user.first_name)}</a>\n"
        msg = bot.reply_to(m, text, parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 20)
    except Exception as e:
        bot.reply_to(m, f"Lỗi: {e}", parse_mode="HTML")

@bot.message_handler(commands=['vote'])
def vote_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        msg = bot.reply_to(m, "❌ Dùng: /vote Tiêu đề | Lựa chọn 1 | Lựa chọn 2 ...", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return
    parts = [p.strip() for p in args[1].split('|')]
    if len(parts) < 3:
        msg = bot.reply_to(m, "❌ Cần ít nhất 2 lựa chọn.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return
    title = parts[0]
    options = parts[1:]
    if len(options) > 10:
        msg = bot.reply_to(m, "❌ Tối đa 10 lựa chọn.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, opt in enumerate(options):
        callback_data = f"vote_{m.message_id}_{idx}"
        markup.add(types.InlineKeyboardButton(f"{idx+1}. {opt} (0)", callback_data=callback_data))
    vote_msg = bot.send_message(
        m.chat.id,
        f"📊 <b>VOTE:</b> {html.escape(title)}\n<i>Ấn vào lựa chọn để bầu.</i>",
        reply_markup=markup,
        parse_mode="HTML"
    )
    vote_active[vote_msg.message_id] = {
        "title": title,
        "options": options,
        "votes": {str(i): set() for i in range(len(options))},
        "creator": m.from_user.id
    }
    brain.stats["votes_created"] += 1
    bot.delete_message(m.chat.id, m.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('vote_'))
def vote_callback(call: types.CallbackQuery) -> None:
    _, msg_id, opt_idx = call.data.split('_')
    msg_id = int(msg_id)
    opt_idx = str(opt_idx)
    uid = call.from_user.id
    if msg_id not in vote_active:
        bot.answer_callback_query(call.id, "Cuộc vote này đã kết thúc hoặc không tồn tại.")
        return
    data = vote_active[msg_id]
    for idx, voters in data["votes"].items():
        if uid in voters:
            bot.answer_callback_query(call.id, "Bạn đã vote rồi!")
            return
    data["votes"][opt_idx].add(uid)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, opt in enumerate(data["options"]):
        count = len(data["votes"][str(idx)])
        btn_text = f"{idx+1}. {opt} ({count})"
        callback_data = f"vote_{msg_id}_{idx}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=msg_id,
            reply_markup=markup
        )
    except:
        pass
    bot.answer_callback_query(call.id, "Đã ghi nhận phiếu của bạn.")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(m: telebot.types.Message) -> None:
    if m.from_user.id != ADMIN_ID:
        return
    text = m.text.split(maxsplit=1)
    if len(text) < 2:
        bot.reply_to(m, "Cần nội dung broadcast.")
        return
    broadcast_msg = text[1]
    sent = 0
    for uid in list(users.keys()):
        try:
            bot.send_message(int(uid), f"📢 Thông báo từ Admin:\n{broadcast_msg}")
            sent += 1
        except:
            pass
    bot.reply_to(m, f"Đã gửi broadcast đến {sent}/{len(users)} người.")

@bot.message_handler(commands=['kick'])
def kick_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    target, reason = extract_user_and_reason(m, bot.get_me().username)
    if not target:
        msg = bot.reply_to(m, "❌ Cần reply hoặc mention/ID để kick.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 15)
        return
    try:
        bot.ban_chat_member(m.chat.id, target, until_date=int(time.time())+35)
        bot.delete_message(m.chat.id, m.message_id)
        txt = f"👢 <b>{html.escape(m.from_user.first_name)}</b> đã kick <code>{target}</code>"
        if reason:
            txt += f"\nLý do: {reason}"
        w = bot.send_message(m.chat.id, txt, parse_mode="HTML")
        del_msg(m.chat.id, w.message_id, 30)
    except Exception as e:
        bot.reply_to(m, f"⚠️ Lỗi: {str(e)[:100]}", parse_mode="HTML")

@bot.message_handler(commands=['listmuted'])
def list_muted_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m) or not is_admin(m.chat.id, m.from_user.id):
        return
    if not mutes:
        msg = bot.reply_to(m, "Không ai bị mute hiện tại.")
        del_msg(m.chat.id, msg.message_id, 10)
        return
    text = "🔇 <b>Danh sách mute:</b>\n"
    for uid, until in mutes.items():
        remaining = int(until - time.time())
        if remaining > 0:
            text += f"- <code>{uid}</code> (còn {remaining//60}m{remaining%60}s)\n"
    bot.reply_to(m, text, parse_mode="HTML")

@bot.message_handler(commands=['ttsstatus'])
def tts_status_cmd(m: telebot.types.Message) -> None:
    """Lệnh kiểm tra trạng thái các engine TTS."""
    if not is_grp(m):
        return
    status = (
        f"🔊 <b>Trạng thái TTS:</b>\n"
        f"edge-tts: {'✅' if HAS_EDGE_TTS else '❌'}\n"
        f"gTTS: {'✅' if HAS_GTTS else '❌'}\n"
        f"pyttsx3 (offline): {'✅' if HAS_PYTTSX3 else '❌'}\n"
        f"Voice queue: {voice_queue.qsize()}\n"
        f"Voice generated: {brain.stats['voice_generated']}"
    )
    msg = bot.reply_to(m, status, parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 20)

# ╔══════════════════════════════════════════════════════════════╗
# ║  HANDLERS CƠ BẢN                                           ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m: telebot.types.Message) -> None:
    if not is_grp(m) or antispam(m) or antilink(m):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_users(users)
    brain.trusted_users.add(m.from_user.id)
    help_text = (
        "<b>🧠 Não Robot - Audio Voice (Đã Fix)</b>\n"
        "/ban /unban /mute /unmute /warn /kick /del\n"
        "/rule /admin /vote /listmuted /brain\n"
        "<b>/voice [text]</b> - Chuyển text thành giọng nói 🎙️\n"
        "<b>/ttsstatus</b> - Kiểm tra engine TTS\n"
        "TikTok link = tải video\n"
        "Tag/reply bot = chat AI\n"
        "<i>(Xóa sau 60s)</i>"
    )
    msg = bot.reply_to(m, help_text, parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 60)

@bot.message_handler(commands=['brain'])
def brain_cmd(m: telebot.types.Message) -> None:
    if not is_grp(m):
        return
    if not is_admin(m.chat.id, m.from_user.id):
        msg = bot.reply_to(m, "⛔ Mày không đủ quyền xem não tao.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return
    uptime = int(time.time() - brain.stats["uptime_start"])
    status_text = (
        f"🧠 <b>TRẠNG THÁI NÃO</b>\n"
        f"State: <code>{brain.state}</code>\n"
        f"Mood: <code>{brain.mood}</code>\n"
        f"Msgs: <code>{brain.stats['msg_processed']}</code>\n"
        f"Spam blocked: <code>{brain.stats['spam_blocked']}</code>\n"
        f"AI calls: <code>{brain.stats['ai_calls']}</code>\n"
        f"Voice generated: <code>{brain.stats['voice_generated']}</code>\n"
        f"Errors: <code>{brain.stats['errors']}</code>\n"
        f"Uptime: <code>{uptime//3600}h{(uptime%3600)//60}m</code>\n"
        f"Trusted: <code>{len(brain.trusted_users)}</code>\n"
        f"Learned: <code>{len(brain.learned)}</code>\n"
        f"Voice queue: <code>{voice_queue.qsize()}</code>\n"
        f"TTS: edge-tts={'✅' if HAS_EDGE_TTS else '❌'} gTTS={'✅' if HAS_GTTS else '❌'} pyttsx3={'✅' if HAS_PYTTSX3 else '❌'}"
    )
    msg = bot.reply_to(m, status_text, parse_mode="HTML")
    del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def handle_text(m: telebot.types.Message) -> None:
    if antispam(m) or antilink(m) or m.text.startswith('/'):
        return
    users[str(m.from_user.id)] = m.from_user.first_name
    save_users(users)

    brain.think({"uid": m.from_user.id, "txt": m.text, "cmd": False})

    match = TIKTOK_LINK.search(m.text)
    if match:
        download_executor.submit(download_tiktok, match.group(0), m.chat.id, m.message_id)
        return

    uid = m.from_user.id
    if not brain.should_reply(uid, m.text):
        return

    if uid in ai_cd and time.time() - ai_cd[uid] < 2:
        msg = bot.reply_to(m, "Đợi 2s.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 3)
        return
    ai_cd[uid] = time.time()

    try:
        bot.send_chat_action(m.chat.id, 'typing')
    except:
        pass

    def _ai_response():
        reply = ask_ai(m.text, uid)
        if f"@{bot.get_me().username}" in m.text or (m.reply_to_message and m.reply_to_message.from_user.id == bot.get_me().id):
            bot.reply_to(m, html.escape(reply), parse_mode="HTML")
        else:
            msg_reply = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
            del_msg(m.chat.id, msg_reply.message_id)

    ai_executor.submit(_ai_response)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m: telebot.types.Message) -> None:
    if not is_grp(m):
        return
    for u in m.new_chat_members:
        if u.id == bot.get_me().id:
            continue
        users[str(u.id)] = u.first_name
        save_users(users)
        msg = bot.send_message(
            m.chat.id,
            f"🔥 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> vừa vào. {random.choice(get_kho())}",
            parse_mode="HTML"
        )
        del_msg(m.chat.id, msg.message_id, 30)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye(m: telebot.types.Message) -> None:
    if not is_grp(m):
        return
    u = m.left_chat_member
    if u.id == bot.get_me().id:
        return
    msg = bot.send_message(
        m.chat.id,
        f"🍂 <a href='tg://user?id={u.id}'>{html.escape(u.first_name)}</a> cút. {random.choice(get_kho())}",
        parse_mode="HTML"
    )
    del_msg(m.chat.id, msg.message_id, 30)

# ╔══════════════════════════════════════════════════════════════╗
# ║  TÁC VỤ NỀN                                                ║
# ╚══════════════════════════════════════════════════════════════╝
def scheduler_task() -> None:
    last_hour = -1
    while True:
        try:
            now = datetime.now(tz)
            brain.health_check()
            if brain.state == "repair":
                brain.state = "normal"
                brain.repair_mode = False

            if now.minute == 0 and now.hour != last_hour and users:
                uid, uname = random.choice(list(users.items()))
                msg = bot.send_message(
                    GROUP_ID,
                    f"🔔 <b>{now.strftime('%H:%M')}</b> | <a href='tg://user?id={uid}'>{html.escape(uname)}</a>... {random.choice(get_kho())}",
                    parse_mode="HTML"
                )
                del_msg(GROUP_ID, msg.message_id, 15)
                last_hour = now.hour
            if now.minute != 0:
                last_hour = -1

            to_remove = []
            for uid, until in mutes.items():
                if time.time() > until:
                    try:
                        bot.restrict_chat_member(
                            GROUP_ID, uid,
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True
                        )
                        to_remove.append(uid)
                    except:
                        pass
            for uid in to_remove:
                del mutes[uid]

            if len(spam) > 100:
                oldest = sorted(spam.items(), key=lambda x: x[1][-1] if x[1] else 0)[:10]
                for uid, _ in oldest:
                    del spam[uid]
        except Exception as e:
            logger.error(f"Lỗi scheduler: {e}")
        time.sleep(15)

def auto_save_task() -> None:
    while True:
        time.sleep(600)
        try:
            save_users(users)
            brain.save_state()
        except Exception as e:
            logger.error(f"Lỗi auto save: {e}")

# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN                                                      ║
# ╚══════════════════════════════════════════════════════════════╝
def main() -> None:
    loaded_users = load_users()
    if isinstance(loaded_users, dict):
        users.update(loaded_users)
    
    logger.info(f"Khởi động với {len(users)} người dùng, mood={brain.mood}")
    logger.info(f"TTS engines: edge-tts={HAS_EDGE_TTS}, gTTS={HAS_GTTS}, pyttsx3={HAS_PYTTSX3}")
    
    if not HAS_EDGE_TTS and not HAS_GTTS and not HAS_PYTTSX3:
        logger.critical("KHÔNG CÓ ENGINE TTS NÀO! Cài đặt: pip install edge-tts gtts pyttsx3")
        logger.critical("Trên Termux/Android: pkg install python && pip install gtts pyttsx3")
        logger.critical("Trên Windows/Linux: pip install edge-tts gtts pyttsx3")

    Thread(target=scheduler_task, daemon=True).start()
    Thread(target=auto_save_task, daemon=True).start()

    logger.info("Bot bắt đầu polling...")
    try:
        bot.infinity_polling(timeout=30, none_stop=True, interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng đột ngột: {e}")
        brain.stats["errors"] += 1
        brain.save_state()

if __name__ == "__main__":
    main()
