#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NAO ROBOT V8.0 - QUẢN LÝ NHÓM TOÀN DIỆN BẰNG AI
# AI: DeepSeek + GPT-4o + FreeModel.dev
# Tính năng: AI Chat, Quản lý nhóm, Chống spam, Tự động dọn RAM
# Đã xóa: Mini games, Coin system, Balance, Daily, Nohu, API client, Local storage

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
    logger.info("Keep-alive da khoi dong")
except ImportError:
    logger.warning("keep_alive.py khong tim thay")

import telebot
from telebot import types, util
import requests
import pytz

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI RANDOM ENGINE                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
class AIRandomEngine:
    def __init__(self):
        self.counter = 0
        self.twister_state = self._init_mt()
        self.entropy_pool = bytearray(64)
        self._refresh_entropy()

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

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CONFIG & TOKEN                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AUTO_DELETE = 60
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "5736655322").split(",")]
GROUP_ID = int(os.getenv("GROUP_ID", "-1003925717296"))

bot = telebot.TeleBot(TOKEN, num_threads=10)
tz = pytz.timezone('Asia/Ho_Chi_Minh')

adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=2, pool_block=False)
ses = requests.Session()
ses.mount('https://', adapter)
ses.mount('http://', adapter)

AI_MAX_CONCURRENT = 10
ai_semaphore = Semaphore(AI_MAX_CONCURRENT)
ai_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="AI")
del_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="Del")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI KEYS                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AI_KEYS = [
    {
        "key": "sk-b309cbab7920474b848e0336598fc3d6",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "status": True,
        "fail": 0
    },
    {
        "key": "sk-d92be6f49626610cee386cf85897fe353cd5fadc44f66a73e98a0cce3efdfd8d",
        "url": "https://api.byesu.com/v1/chat/completions",
        "model": "gpt-4o",
        "status": True,
        "fail": 0
    },
    {
        "key": "fe_oa_49470785c775bae446168ad37488a9997b7f2ffdcd74073d",
        "url": "https://api.freemodel.dev/v1/chat/completions",
        "model": "gpt-4o",
        "status": True,
        "fail": 0
    }
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI RESPONSES (NGẮN GỌN, KHÔNG THƠ)                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AI_RESPONSES = {
    "chao": ["Chào anh!", "Hi anh!", "Anh gọi em à?"],
    "hoi": ["Để em check...", "Em biết nè!", "Để em trả lời..."],
    "cam_on": ["Không có gì ạ!", "Rất vui được giúp anh!"],
    "xin_loi": ["Không sao đâu ạ!", "Em hiểu mà!"],
    "tam_biet": ["Bye anh!", "Gặp lại anh sau!"],
    "mac_dinh": ["Dạ có em đây!", "Anh cần gì ạ?", "Em nghe anh!"]
}

def phan_loai_tin_nhan(van_ban: str) -> str:
    van_ban_lower = van_ban.lower()
    if any(tu in van_ban_lower for tu in ["chào", "hello", "hi", "hey", "alo"]):
        return "chao"
    if any(tu in van_ban_lower for tu in ["cảm ơn", "thanks", "cám ơn"]):
        return "cam_on"
    if any(tu in van_ban_lower for tu in ["xin lỗi", "sorry"]):
        return "xin_loi"
    if any(tu in van_ban_lower for tu in ["bye", "tạm biệt", "pp", "bai"]):
        return "tam_biet"
    if any(tu in van_ban_lower for tu in ["sao", "gì", "nào", "đâu", "ai", "cách", "làm sao"]):
        return "hoi"
    return "mac_dinh"

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    BIẾN TOÀN CỤC                                           ║
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
    return m.from_user.id in ADMIN_IDS

def parse_duration(text: str) -> int:
    m = re.search(r'(\d+)\s*(h|m|s|p)', text.lower())
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == 's': return num
        elif unit in ['m', 'p']: return num * 60
        elif unit == 'h': return num * 3600
    return 3600

def extract_user_and_reason(message) -> Tuple[Optional[int], str]:
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
# ║                    QUẢN LÝ NHÓM - LỆNH QUẢN TRỊ                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền mute!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /mute [user] [thời_gian] [lý_do]\nHoặc reply + /mute [thời_gian]")
        del_both(m, m2.message_id)
        return
    
    duration = parse_duration(reason) if reason else 3600
    until_time = int(time.time()) + duration
    
    try:
        bot.restrict_chat_member(m.chat.id, target, until_date=until_time, can_send_messages=False)
        mutes[target] = until_time
        
        target_name = target
        try:
            target_name = bot.get_chat_member(m.chat.id, target).user.first_name
        except:
            pass
        
        if duration >= 3600:
            time_str = f"{duration // 3600}h"
        elif duration >= 60:
            time_str = f"{duration // 60}m"
        else:
            time_str = f"{duration}s"
        
        m2 = bot.reply_to(m,
            f"🔇 MUTE\n"
            f"👤 {html.escape(str(target_name))}\n"
            f"⏰ {time_str}\n"
            f"👮 {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền unmute!")
        del_both(m, m2.message_id)
        return
    
    target, _ = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /unmute [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    
    try:
        bot.restrict_chat_member(m.chat.id, target,
                                can_send_messages=True,
                                can_send_media_messages=True,
                                can_send_other_messages=True,
                                can_add_web_page_previews=True)
        if target in mutes:
            del mutes[target]
        
        target_name = target
        try:
            target_name = bot.get_chat_member(m.chat.id, target).user.first_name
        except:
            pass
        
        m2 = bot.reply_to(m,
            f"🔊 UNMUTE\n"
            f"👤 {html.escape(str(target_name))}\n"
            f"👮 {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền ban!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /ban [user] [thời_gian] [lý_do]\nHoặc reply + /ban [thời_gian]")
        del_both(m, m2.message_id)
        return
    
    duration = parse_duration(reason) if reason else 86400
    until_time = int(time.time()) + duration
    
    try:
        bot.ban_chat_member(m.chat.id, target, until_date=until_time)
        
        target_name = target
        try:
            target_name = bot.get_chat_member(m.chat.id, target).user.first_name
        except:
            pass
        
        if duration >= 86400:
            time_str = f"{duration // 86400}d"
        elif duration >= 3600:
            time_str = f"{duration // 3600}h"
        else:
            time_str = f"{duration // 60}m"
        
        m2 = bot.reply_to(m,
            f"🚫 BAN\n"
            f"👤 {html.escape(str(target_name))}\n"
            f"⏰ {time_str}\n"
            f"👮 {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
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
            f"✅ UNBAN\n"
            f"👤 ID: {target}\n"
            f"👮 {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    if not is_grp(m): return
    if not is_adm(m):
        m2 = bot.reply_to(m, "❌ Chỉ admin mới có quyền warn!")
        del_both(m, m2.message_id)
        return
    
    target, reason = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /warn [user] [lý_do] hoặc reply")
        del_both(m, m2.message_id)
        return
    
    warns[target] = warns.get(target, 0) + 1
    
    target_name = target
    try:
        target_name = bot.get_chat_member(m.chat.id, target).user.first_name
    except:
        pass
    
    action_text = ""
    if warns[target] >= 3:
        try:
            bot.ban_chat_member(m.chat.id, target, until_date=int(time.time()) + 3600)
            action_text = "\n🚫 Auto-ban 1h (đủ 3 warn)"
            del warns[target]
        except:
            action_text = "\n⚠️ Không thể auto-ban"
    
    m2 = bot.reply_to(m,
        f"⚠️ WARN\n"
        f"👤 {html.escape(str(target_name))}\n"
        f"📊 {warns.get(target, 3)}/3{action_text}\n"
        f"👮 {html.escape(m.from_user.first_name)}",
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
    
    target, _ = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /unwarn [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    
    if target in warns:
        warns[target] = max(0, warns[target] - 1)
        if warns[target] == 0:
            del warns[target]
    
    target_name = target
    try:
        target_name = bot.get_chat_member(m.chat.id, target).user.first_name
    except:
        pass
    
    m2 = bot.reply_to(m,
        f"✅ UNWARN\n"
        f"👤 {html.escape(str(target_name))}\n"
        f"📊 Còn: {warns.get(target, 0)}/3\n"
        f"👮 {html.escape(m.from_user.first_name)}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['warns'])
def warns_cmd(m):
    if not is_grp(m): return
    target = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    target_name = target
    try:
        target_name = bot.get_chat_member(m.chat.id, target).user.first_name
    except:
        pass
    count = warns.get(target, 0)
    
    m2 = bot.reply_to(m,
        f"📊 WARNS\n"
        f"👤 {html.escape(str(target_name))}\n"
        f"⚠️ {count}/3",
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
    
    target, reason = extract_user_and_reason(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /kick [user] [lý_do] hoặc reply")
        del_both(m, m2.message_id)
        return
    
    try:
        bot.ban_chat_member(m.chat.id, target)
        time.sleep(1)
        bot.unban_chat_member(m.chat.id, target)
        
        target_name = target
        try:
            target_name = bot.get_chat_member(m.chat.id, target).user.first_name
        except:
            pass
        
        m2 = bot.reply_to(m,
            f"👢 KICK\n"
            f"👤 {html.escape(str(target_name))}\n"
            f"👮 {html.escape(m.from_user.first_name)}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
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
            m2 = bot.reply_to(m, "✅ Đã xóa!")
            del_both(m, m2.message_id)
        except Exception as e:
            m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
            del_both(m, m2.message_id)
    else:
        m2 = bot.reply_to(m, "❌ Reply tin nhắn cần xóa!")
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
            m2 = bot.reply_to(m, "📌 Đã ghim!")
            del_both(m, m2.message_id)
        except Exception as e:
            m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
            del_both(m, m2.message_id)
    else:
        m2 = bot.reply_to(m, "❌ Reply tin nhắn cần ghim!")
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
        m2 = bot.reply_to(m, "✅ Đã bỏ ghim!")
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['id'])
def id_cmd(m):
    if not is_grp(m): return
    
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        m2 = bot.reply_to(m,
            f"🆔 ID\n"
            f"👤 {html.escape(target.first_name)}\n"
            f"🆔 <code>{target.id}</code>\n"
            f"💬 <code>{m.chat.id}</code>",
            parse_mode="HTML"
        )
    else:
        user = m.from_user
        m2 = bot.reply_to(m,
            f"🆔 ID\n"
            f"👤 {html.escape(user.first_name)}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💬 <code>{m.chat.id}</code>",
            parse_mode="HTML"
        )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['admins'])
def admins_cmd(m):
    if not is_grp(m): return
    try:
        admins = bot.get_chat_administrators(m.chat.id)
        text = "👑 DANH SÁCH ADMIN\n"
        for a in admins:
            name = a.user.first_name
            text += f"• {html.escape(name)} (<code>{a.user.id}</code>)\n"
        m2 = bot.reply_to(m, text, parse_mode="HTML")
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CHỐNG SPAM + LINK TELEGRAM                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(func=lambda m: is_grp(m) and m.text and TELEGRAM_LINK.search(m.text))
def delete_telegram_link(m):
    if is_adm(m): return
    try:
        bot.delete_message(m.chat.id, m.message_id)
        m2 = bot.send_message(m.chat.id, f"⚠️ {html.escape(m.from_user.first_name)}, không gửi link Telegram!")
        auto_del(m.chat.id, m2.message_id, 5)
    except:
        pass

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def ask_ai(prompt):
    global ck_idx
    
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]
    
    loai = phan_loai_tin_nhan(prompt)
    fallback = ai_random.choice(AI_RESPONSES[loai])
    
    system_prompt = (
        "Bạn là Nao, trợ lý ảo nữ 18 tuổi người Việt. "
        "Trả lời ngắn gọn dưới 20 từ, thêm 1 emoji. "
        "Gọi người dùng là 'anh'. Không thơ, không dài dòng."
    )
    
    msgs = [{"role": "system", "content": system_prompt}]
    for t in list(mem)[-6:]:
        idx = list(mem).index(t)
        role = "user" if idx % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": t})
    msgs.append({"role": "user", "content": prompt})
    
    acquired = ck_lock.acquire(timeout=5)
    if not acquired:
        return fallback
    
    try:
        for _ in range(len(AI_KEYS)):
            k = AI_KEYS[ck_idx]
            if not k.get("status", True) or k.get("fail", 0) >= MAX_FAIL:
                ck_idx = (ck_idx + 1) % len(AI_KEYS)
                continue
            try:
                r = ses.post(
                    k["url"],
                    json={"model": k["model"], "messages": msgs, "max_tokens": 60, "temperature": 0.9},
                    headers={"Authorization": f"Bearer {k['key']}", "Content-Type": "application/json"},
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
                    return txt
                else:
                    k["fail"] = k.get("fail", 0) + 1
            except:
                k["fail"] = k.get("fail", 0) + 1
            ck_idx = (ck_idx + 1) % len(AI_KEYS)
        
        for k in AI_KEYS:
            k["status"] = True
            k["fail"] = 0
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
# ║                    HANDLERS                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['start'])
def start(m):
    if not is_grp(m): return
    
    help_text = (
        f"🤖 NAO ROBOT V8.0\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ QUẢN LÝ NHÓM:\n"
        f"/mute [user] [time] - Khóa mõm\n"
        f"/unmute [user] - Mở khóa\n"
        f"/ban [user] [time] - Cấm\n"
        f"/unban [user_id] - Bỏ cấm\n"
        f"/warn [user] - Cảnh cáo (3=ban)\n"
        f"/unwarn [user] - Gỡ cảnh cáo\n"
        f"/warns - Xem cảnh cáo\n"
        f"/kick [user] - Đuổi\n"
        f"/del - Xóa tin nhắn (reply)\n"
        f"/pin - Ghim (reply)\n"
        f"/unpin - Bỏ ghim\n"
        f"/id - Lấy ID\n"
        f"/admins - Danh sách admin\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Chat để AI trả lời!\n"
        f"⏰ Time: 30m, 2h, 60s"
    )
    m2 = bot.reply_to(m, help_text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['stats'])
def stats(m):
    if not is_grp(m): return
    try:
        rc = bot.get_chat_member_count(GROUP_ID)
    except:
        rc = 0
    
    m2 = bot.reply_to(m,
        f"📊 THỐNG KÊ\n"
        f"👥 Members: {rc}\n"
        f"🔇 Muted: {len(mutes)}\n"
        f"⚠️ Warned: {len(warns)}\n"
        f"🧵 Threads: {threading.active_count()}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(func=lambda m: is_grp(m) and m.text)
def chat(m):
    if antispam(m) or m.text.startswith('/'):
        return
    uid = m.from_user.id
    
    if uid in ai_cd and time.time() - ai_cd[uid] < 2:
        return
    ai_cd[uid] = time.time()
    
    acquired = ai_semaphore.acquire(timeout=5)
    if not acquired:
        return
    
    def _ai():
        try:
            reply = ask_ai(m.text)
            m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
            auto_del(m.chat.id, m2.message_id)
        except Exception as e:
            logger.error(f"AI error: {e}")
        finally:
            ai_semaphore.release()
    
    ai_executor.submit(_ai)

@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    if not is_grp(m): return
    for u in m.new_chat_members:
        if u.id == bot.get_me().id:
            continue
        m2 = bot.send_message(m.chat.id,
            f"👋 {html.escape(u.first_name)}! Chào mừng!\n"
            f"🤖 /start để xem lệnh",
            parse_mode="HTML"
        )
        auto_del(m.chat.id, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    SCHEDULER                                                ║
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
        except:
            pass

def auto_unmute():
    while True:
        time.sleep(15)
        try:
            for uid in list(mutes.keys()):
                if time.time() > mutes[uid]:
                    try:
                        bot.restrict_chat_member(GROUP_ID, uid, can_send_messages=True)
                    except:
                        pass
                    del mutes[uid]
        except:
            pass

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    MAIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    logger.info("="*60)
    logger.info("NAO ROBOT V8.0 - QUAN LY NHOM BANG AI")
    logger.info(f"Group: {GROUP_ID}")
    logger.info(f"Admins: {ADMIN_IDS}")
    logger.info("="*60)
    
    Thread(target=cleanup_spam_dict, daemon=True, name="SpamCleanup").start()
    Thread(target=auto_unmute, daemon=True, name="AutoUnmute").start()
    
    logger.info("Starting bot...")
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
