# -*- coding: utf-8 -*-
# ┌────────────────────────────────────────────────────────────────────────┐
# │                    NÃO ROBOT - AUDIO VOICE + SIÊU TỐC                   │
# │  Phiên bản 2000 dòng  |  Tác giả: palofsc (palo)                       │
# │  Ngày: 2026-06-24     |  Python 3.9+ | pyTelegramBotAPI | gTTS | Edge  │
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

# Thư viện voice (ưu tiên edge-tts vì nhẹ hơn gTTS)
try:
    import edge_tts
    HAS_EDGE_TTS = True
    logger.info("edge-tts đã sẵn sàng (giọng vi-VN).")
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts không có, thử dùng gTTS.")

try:
    from gtts import gTTS
    HAS_GTTS = True
    logger.info("gTTS đã sẵn sàng.")
except ImportError:
    HAS_GTTS = False
    logger.warning("gTTS không có, voice bị vô hiệu hóa.")

# ╔══════════════════════════════════════════════════════════════╗
# ║  NÃO (BRAIN) - LỚP ĐIỀU KHIỂN TRUNG TÂM                    ║
# ╚══════════════════════════════════════════════════════════════╝
class Brain:
    """
    Não điều khiển bot: tự học, tự điều chỉnh mood, tự sửa lỗi.
    Quyết định mức độ chửi và chế độ hoạt động.
    """
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

bot = telebot.TeleBot(TOKEN, num_threads=50)  # Tăng thread lên 50
tz = pytz.timezone('Asia/Ho_Chi_Minh')

# ─── HTTP SESSION TỐI ƯU ─────────────────────────────────────────────────
ses = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=200,      # Tăng pool kết nối
    pool_maxsize=500,         # Tăng pool tối đa
    max_retries=3,
    pool_block=False          # Không block khi pool đầy
)
ses.mount('https://', adapter)
ses.mount('http://', adapter)

# ╔══════════════════════════════════════════════════════════════╗
# ║  THREAD POOL CHO CÁC TÁC VỤ NẶNG                           ║
# ╚══════════════════════════════════════════════════════════════╝
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
message_queue: Queue = Queue(maxsize=500)  # Hàng đợi xử lý tin nhắn
USR_FILE = "usr.json"
RULES_FILE = "rules.txt"

# Regex
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
# ║  VOICE GENERATION (TEXT-TO-SPEECH)                         ║
# ║  Hỗ trợ: edge-tts (giọng vi-VN mượt) hoặc gTTS            ║
# ╚══════════════════════════════════════════════════════════════╝
@dataclass
class VoiceRequest:
    """Đối tượng yêu cầu tạo voice."""
    chat_id: int
    reply_id: int
    text: str
    user_name: str
    lang: str = "vi"
    created_at: float = field(default_factory=time.time)

voice_queue: Queue = Queue(maxsize=30)  # Hàng đợi voice riêng biệt

def generate_voice_edge(text: str, lang: str = "vi") -> Optional[io.BytesIO]:
    """
    Tạo voice bằng edge-tts (giọng vi-VN-NamNeural hoặc vi-VN-HoaiMyNeural).
    Trả về BytesIO chứa file mp3, hoặc None nếu lỗi.
    """
    if not HAS_EDGE_TTS:
        return None
    try:
        voice_name = "vi-VN-NamNeural" if random.random() > 0.5 else "vi-VN-HoaiMyNeural"
        # Tạo file tạm
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()

        async def _gen():
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_path)

        # Chạy async trong thread
        asyncio.run(_gen())

        with open(temp_path, 'rb') as f:
            audio_data = f.read()
        os.unlink(temp_path)  # Xóa file tạm
        return io.BytesIO(audio_data)
    except Exception as e:
        logger.error(f"Edge-TTS lỗi: {e}")
        return None

def generate_voice_gtts(text: str, lang: str = "vi") -> Optional[io.BytesIO]:
    """Tạo voice bằng gTTS (Google Text-to-Speech)."""
    if not HAS_GTTS:
        return None
    try:
        buf = io.BytesIO()
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.error(f"gTTS lỗi: {e}")
        return None

def generate_voice(text: str, lang: str = "vi") -> Optional[io.BytesIO]:
    """Tạo voice, ưu tiên edge-tts rồi gTTS."""
    # Thử edge-tts trước
    audio = generate_voice_edge(text, lang)
    if audio:
        return audio
    # Fallback gTTS
    return generate_voice_gtts(text, lang)

def voice_worker() -> None:
    """Worker xử lý hàng đợi voice liên tục."""
    while True:
        try:
            req: VoiceRequest = voice_queue.get(block=True)
            if req is None:
                continue
            # Giới hạn độ dài text cho voice (tối đa 500 ký tự)
            voice_text = req.text[:500]
            logger.info(f"Đang tạo voice cho: {voice_text[:50]}...")
            audio = generate_voice(voice_text, req.lang)
            if audio:
                audio.name = f"voice_{req.user_name}.mp3"
                bot.send_voice(
                    req.chat_id,
                    audio,
                    reply_to_message_id=req.reply_id,
                    caption=f"🎙️ {html.escape(req.user_name)} nói: {html.escape(voice_text[:100])}...",
                    parse_mode="HTML"
                )
                brain.stats["voice_generated"] += 1
                logger.info(f"Voice đã gửi cho {req.user_name}.")
            else:
                bot.send_message(
                    req.chat_id,
                    f"❌ {html.escape(req.user_name)}, không thể tạo giọng nói (có thể do text dài hoặc lỗi TTS).",
                    parse_mode="HTML"
                )
            voice_queue.task_done()
        except Exception as e:
            logger.error(f"Voice worker lỗi: {e}")

# Khởi động voice workers (nhiều worker xử lý song song)
for _ in range(4):
    Thread(target=voice_worker, daemon=True).start()

# ╔══════════════════════════════════════════════════════════════╗
# ║  AI GỌI (TỰ SỬA) - TỐI ƯU TỐC ĐỘ                          ║
# ╚══════════════════════════════════════════════════════════════╝
def ask_ai(prompt: str, uid: Optional[int] = None) -> str:
    """
    Gửi prompt đến AI với cơ chế xoay vòng key và cache.
    """
    global ck_idx
    if brain.state == "sleep":
        return random.choice(get_kho())

    # Cache đơn giản: nếu prompt đã có trong mem gần đây thì trả lại ngay
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]

    system_msg = "Bạn là kẻ cọc cằn, chửi khịa trẻ trâu. Xưng 'tao' gọi 'mày'. Trả lời dưới 12 từ, không emoji."
    messages = [{"role": "system", "content": system_msg}]
    for txt in list(mem)[-8:]:  # Giảm context xuống 8 để nhanh hơn
        messages.append({"role": "user", "content": txt})
    messages.append({"role": "user", "content": prompt})

    with ck_lock:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k["status"] or k["fail"] >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                # Timeout giảm xuống 8 giây để nhanh hơn
                resp = ses.post(
                    k["url"],
                    json={
                        "model": k["model"],
                        "messages": messages,
                        "max_tokens": 40,      # Giảm tokens
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
                logger.error(f"AI fail key {ck_idx}: {e}")
            ck_idx = (ck_idx + 1) % len(AI_KEYS)

    if not any(k["status"] for k in AI_KEYS):
        for k in AI_KEYS:
            k["status"], k["fail"] = True, 0
        brain.stats["errors"] = 0
        brain.state = "repair"
        logger.critical("Tất cả AI key đã reset tự động.")
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
# ║  LỆNH /voice (MỚI) - TEXT TO SPEECH                        ║
# ╚══════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['voice'])
def voice_cmd(m: telebot.types.Message) -> None:
    """
    Lệnh /voice [text] - Chuyển văn bản thành giọng nói.
    Hỗ trợ reply để lấy text từ tin nhắn được reply.
    """
    if not is_grp(m) or antispam(m) or antilink(m):
        return
    
    users[str(m.from_user.id)] = m.from_user.first_name
    save_users(users)

    # Lấy text: ưu tiên reply, sau đó là text sau lệnh
    voice_text = ""
    if m.reply_to_message and m.reply_to_message.text:
        voice_text = m.reply_to_message.text
    elif m.text.strip() != '/voice':
        parts = m.text.split(maxsplit=1)
        if len(parts) > 1:
            voice_text = parts[1].strip()
    
    if not voice_text:
        msg = bot.reply_to(m, "❌ Dùng: /voice [text] hoặc reply tin nhắn có text.", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 10)
        return

    # Kiểm tra độ dài
    if len(voice_text) > 500:
        voice_text = voice_text[:500]
        bot.reply_to(m, "⚠️ Text quá dài, đã cắt còn 500 ký tự.", parse_mode="HTML")

    # Đưa vào hàng đợi voice
    try:
        voice_queue.put_nowait(VoiceRequest(
            chat_id=m.chat.id,
            reply_id=m.message_id,
            text=voice_text,
            user_name=m.from_user.first_name
        ))
        msg = bot.reply_to(m, f"🎙️ Đang tạo giọng nói cho <b>{html.escape(m.from_user.first_name)}</b>... (có thể mất vài giây)", parse_mode="HTML")
        del_msg(m.chat.id, msg.message_id, 8)
    except Exception:
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
        "<b>🧠 Não Robot - Audio Voice</b>\n"
        "/ban /unban /mute /unmute /warn /kick /del\n"
        "/rule /admin /vote /listmuted /brain\n"
        "<b>/voice [text]</b> - Chuyển text thành giọng nói 🎙️\n"
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
        f"Voice queue: <code>{voice_queue.qsize()}</code>"
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

    # Tải video TikTok nếu có (chạy trong thread pool)
    match = TIKTOK_LINK.search(m.text)
    if match:
        download_executor.submit(download_tiktok, match.group(0), m.chat.id, m.message_id)
        return

    uid = m.from_user.id
    if not brain.should_reply(uid, m.text):
        return

    # Cooldown AI 2 giây (giảm từ 3s)
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

    # Sử dụng thread pool thay vì tạo thread mới mỗi lần
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
        time.sleep(15)  # Giảm từ 20s xuống 15s để phản hồi nhanh hơn

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

    # Khởi động thread nền
    Thread(target=scheduler_task, daemon=True).start()
    Thread(target=auto_save_task, daemon=True).start()

    # Tối ưu: tăng timeout và giảm thời gian chờ giữa các lần poll
    logger.info("Bot bắt đầu polling (tối ưu tốc độ)...")
    try:
        bot.infinity_polling(timeout=30, none_stop=True, interval=0.5)
    except Exception as e:
        logger.critical(f"Bot dừng đột ngột: {e}")
        brain.stats["errors"] += 1
        brain.save_state()

if __name__ == "__main__":
    main()
