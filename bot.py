# -*- coding: utf-8 -*-
# NAO ROBOT V11.0 - Bot quản lý nhóm Telegram đầy đủ
# Tính năng: Quản lý nhóm, AI Chat, Filter (text/file/media), Từ cấm, Auto-Mod
# Tác giả: baohuydev

import sys, io, os, json, time, random, re, html, logging, traceback, hashlib
import urllib.parse, gc, psutil, weakref, signal, base64, tempfile
import math, statistics, itertools, threading, subprocess, shutil, zipfile
from threading import Thread, Lock, Timer, Event, Semaphore
from datetime import datetime, timedelta, date
from collections import deque, defaultdict, OrderedDict, Counter
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# ─── KEEP ALIVE (cho Replit) ───
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
# ║                    CONFIG                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
AUTO_DELETE = 60
TOKEN = os.getenv("BOT_TOKEN", "8080338995:AAEL2qb-TMjjUmoSvG1bWuY5M1QFST_zdJ4")
MASTER_ADMIN = int(os.getenv("MASTER_ADMIN", "5736655322"))

# ─── QUẢN LÝ NHIỀU NHÓM ───
groups_db = {}
groups_lock = Lock()
GROUPS_FILE = "groups.json"

def load_groups():
    global groups_db
    try:
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                groups_db = json.load(f)
            logger.info(f"Loaded {len(groups_db)} groups")
    except:
        groups_db = {}

def save_groups():
    with groups_lock:
        try:
            with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(groups_db, f, ensure_ascii=False, indent=2)
        except:
            pass

def get_group(gid: int) -> Dict:
    gid_str = str(gid)
    if gid_str not in groups_db:
        groups_db[gid_str] = {
            "name": "",
            "admins": [MASTER_ADMIN],
            "settings": {
                "warn_limit": 3,
                "warn_ban_duration": 3600,
                "spam_limit": 5,
                "spam_window": 4,
                "auto_mute_spam": True,
                "auto_mute_duration": 1800,
                "delete_bad_words": True,
                "delete_links": True,
                "delete_telegram_links": True,
                "max_message_length": 500,
                "allow_media": True,
                "allow_stickers": True,
                "allow_gifs": True,
                "ai_chat": True,
                "filter_enabled": True,
                "bad_words_enabled": True
            }
        }
        save_groups()
    return groups_db[gid_str]

def is_admin(uid: int, gid: int) -> bool:
    if uid == MASTER_ADMIN:
        return True
    g = get_group(gid)
    return uid in g.get("admins", [])

def add_group_admin(gid: int, uid: int):
    g = get_group(gid)
    if uid not in g["admins"]:
        g["admins"].append(uid)
        save_groups()

def remove_group_admin(gid: int, uid: int):
    g = get_group(gid)
    if uid in g["admins"] and uid != MASTER_ADMIN:
        g["admins"].remove(uid)
        save_groups()

def get_group_setting(gid: int, key: str, default=None):
    g = get_group(gid)
    return g["settings"].get(key, default)

def set_group_setting(gid: int, key: str, value):
    g = get_group(gid)
    g["settings"][key] = value
    save_groups()

load_groups()

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
    }
]
MAX_FAIL = 3
ck_idx = 0
ck_lock = Lock()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    BAD WORDS                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
BAD_WORDS_DEFAULT = [
    "lồn", "cặc", "địt", "đụ", "chịch", "vãi lồn", "đmm", "clmm",
    "dit", "lon", "cac", "dcm", "vcl", "vl", "dm", "cc", "đéo", "đcm"
]

bad_words_db: Dict[str, List[str]] = defaultdict(list)
BAD_WORDS_FILE = "bad_words.json"

def load_bad_words():
    global bad_words_db
    try:
        if os.path.exists(BAD_WORDS_FILE):
            with open(BAD_WORDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for gid_str, words in data.items():
                    bad_words_db[gid_str] = words
            logger.info(f"Loaded bad words for {len(bad_words_db)} groups")
    except Exception as e:
        logger.error(f"Lỗi load bad words: {e}")
        bad_words_db = defaultdict(list)

def save_bad_words():
    try:
        with open(BAD_WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(bad_words_db), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi save bad words: {e}")

def get_bad_words(gid: int) -> List[str]:
    gk_str = str(gid)
    if gk_str in bad_words_db and bad_words_db[gk_str]:
        return bad_words_db[gk_str]
    return BAD_WORDS_DEFAULT.copy()

def get_bad_words_pattern(gid: int):
    words = get_bad_words(gid)
    if not words:
        return None
    return re.compile(r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b', re.IGNORECASE)

load_bad_words()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    FILTERS                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
filters_db: Dict[str, Dict[str, Dict]] = defaultdict(dict)
FILTERS_FILE = "filters.json"

def load_filters():
    global filters_db
    try:
        if os.path.exists(FILTERS_FILE):
            with open(FILTERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for gid_str, filters in data.items():
                    filters_db[gid_str] = filters
            logger.info(f"Loaded filters for {len(filters_db)} groups")
    except Exception as e:
        logger.error(f"Lỗi load filters: {e}")
        filters_db = defaultdict(dict)

def save_filters():
    try:
        with open(FILTERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(filters_db), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi save filters: {e}")

load_filters()

# Link patterns
TELEGRAM_LINK = re.compile(r'(https?://)?(www\.)?(t\.me|telegram\.me|telegram\.org|tg\.me)/[a-zA-Z0-9_]{5,}', re.I)
ALL_LINKS = re.compile(r'https?://\S+', re.I)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI RESPONSES                                             ║
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
# ║                    QUẢN LÝ DỮ LIỆU NGƯỜI DÙNG                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
warns: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
mutes: Dict[str, Dict[int, float]] = defaultdict(dict)
spam_counter: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
ban_history: Dict[str, List[Dict]] = defaultdict(list)
user_names: Dict[int, str] = {}
user_names_lock = Lock()

def get_user_name(uid: int) -> str:
    with user_names_lock:
        return user_names.get(uid, str(uid))

def set_user_name(uid: int, name: str):
    with user_names_lock:
        user_names[uid] = name

def gk(gid: int) -> str:
    return str(gid)

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

def parse_duration(text: str) -> int:
    m = re.search(r'(\d+)\s*(d|h|m|s|p)', text.lower())
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == 's': return num
        elif unit in ['m', 'p']: return num * 60
        elif unit == 'h': return num * 3600
        elif unit == 'd': return num * 86400
    return 3600

def extract_target(message) -> Tuple[Optional[int], str]:
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
            if arg.startswith('@'):
                try:
                    target = bot.get_chat_member(message.chat.id, arg).user.id
                    reason = ""
                except:
                    pass
            elif arg.isdigit():
                target = int(arg)
            else:
                m = re.match(r'(\d+)', arg)
                if m:
                    target = int(m.group(1))
                    reason = arg[m.end():].strip()
    return target, reason

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    LỆNH QUẢN LÝ NHÓM                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['addgroup'])
def add_group_cmd(m):
    if m.from_user.id != MASTER_ADMIN:
        m2 = bot.reply_to(m, "❌ Chỉ Master Admin mới có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split()
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /addgroup [group_id]")
        del_both(m, m2.message_id)
        return
    try:
        gid = int(parts[1])
    except:
        m2 = bot.reply_to(m, "❌ ID nhóm không hợp lệ!")
        del_both(m, m2.message_id)
        return
    try:
        chat_info = bot.get_chat(gid)
        g = get_group(gid)
        g["name"] = chat_info.title
        try:
            admins = bot.get_chat_administrators(gid)
            for a in admins:
                if a.user.id != bot.get_me().id and a.user.id not in g["admins"]:
                    g["admins"].append(a.user.id)
        except:
            pass
        save_groups()
        m2 = bot.reply_to(m,
            f"✅ ĐÃ THÊM NHÓM\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📛 Tên: {html.escape(chat_info.title)}\n"
            f"🆔 ID: <code>{gid}</code>",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        try:
            bot.send_message(gid, "🤖 Bot đã được thêm vào nhóm!\nDùng /start để xem lệnh.")
        except:
            pass
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['removegroup'])
def remove_group_cmd(m):
    if m.from_user.id != MASTER_ADMIN:
        m2 = bot.reply_to(m, "❌ Chỉ Master Admin mới có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split()
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /removegroup [group_id]")
        del_both(m, m2.message_id)
        return
    try:
        gid = str(int(parts[1]))
        if gid in groups_db:
            del groups_db[gid]
            save_groups()
            m2 = bot.reply_to(m, f"✅ Đã xóa nhóm: {gid}")
        else:
            m2 = bot.reply_to(m, "❌ Nhóm không tồn tại!")
        del_both(m, m2.message_id)
    except:
        pass

@bot.message_handler(commands=['groups'])
def list_groups_cmd(m):
    if m.from_user.id != MASTER_ADMIN:
        m2 = bot.reply_to(m, "❌ Chỉ Master Admin mới có quyền!")
        del_both(m, m2.message_id)
        return
    if not groups_db:
        m2 = bot.reply_to(m, "❌ Chưa có nhóm nào!")
        del_both(m, m2.message_id)
        return
    text = "📋 DANH SÁCH NHÓM\n━━━━━━━━━━━━━━━━━━━━\n"
    for gid_str, g in groups_db.items():
        text += f"📛 {html.escape(g.get('name', '?'))}\n"
        text += f"🆔 <code>{gid_str}</code>\n\n"
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── QUẢN LÝ ADMIN NHÓM ───
@bot.message_handler(commands=['addadmin'])
def add_admin_cmd(m):
    gid = m.chat.id
    if m.from_user.id != MASTER_ADMIN and not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    target, _ = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /addadmin [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    add_group_admin(gid, target)
    m2 = bot.reply_to(m, f"✅ Đã thêm admin: <code>{target}</code>", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['removeadmin'])
def remove_admin_cmd(m):
    gid = m.chat.id
    if m.from_user.id != MASTER_ADMIN:
        m2 = bot.reply_to(m, "❌ Chỉ Master Admin mới có quyền!")
        del_both(m, m2.message_id)
        return
    target, _ = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /removeadmin [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    remove_group_admin(gid, target)
    m2 = bot.reply_to(m, f"✅ Đã xóa admin: <code>{target}</code>", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['admins'])
def list_admins_cmd(m):
    gid = m.chat.id
    g = get_group(gid)
    text = "👑 DANH SÁCH ADMIN\n━━━━━━━━━━━━━━━━━━━━\n"
    for uid in g.get("admins", []):
        name = get_user_name(uid)
        if uid == MASTER_ADMIN:
            text += f"⭐ {html.escape(name)} - <code>{uid}</code> (Master)\n"
        else:
            text += f"👤 {html.escape(name)} - <code>{uid}</code>\n"
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

# ─── LỆNH MUTE/BAN/KICK/WARN ───
@bot.message_handler(commands=['mute'])
def mute_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền mute!")
        del_both(m, m2.message_id)
        return
    target, reason = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /mute [user] [thời_gian] [lý_do]")
        del_both(m, m2.message_id)
        return
    if is_admin(target, gid):
        m2 = bot.reply_to(m, "❌ Không thể mute admin!")
        del_both(m, m2.message_id)
        return
    duration = parse_duration(reason) if reason else 3600
    until_time = int(time.time()) + duration
    try:
        bot.restrict_chat_member(gid, target, until_date=until_time, can_send_messages=False)
        mutes[gk(gid)][target] = time.time() + duration
        time_str = f"{duration // 86400}d" if duration >= 86400 else f"{duration // 3600}h" if duration >= 3600 else f"{duration // 60}m" if duration >= 60 else f"{duration}s"
        m2 = bot.reply_to(m,
            f"🔇 MUTE\n"
            f"👤 {html.escape(get_user_name(target))}\n"
            f"⏰ {time_str}\n"
            f"📝 {reason or 'Không có lý do'}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unmute'])
def unmute_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    target, _ = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /unmute [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    try:
        bot.restrict_chat_member(gid, target, can_send_messages=True, can_send_media_messages=True,
                                can_send_other_messages=True, can_add_web_page_previews=True)
        if target in mutes[gk(gid)]:
            del mutes[gk(gid)][target]
        m2 = bot.reply_to(m, f"🔊 Đã unmute: {html.escape(get_user_name(target))}", parse_mode="HTML")
        del_both(m, m2.message_id)
    except:
        pass

@bot.message_handler(commands=['ban'])
def ban_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền ban!")
        del_both(m, m2.message_id)
        return
    target, reason = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /ban [user] [thời_gian] [lý_do]")
        del_both(m, m2.message_id)
        return
    if is_admin(target, gid):
        m2 = bot.reply_to(m, "❌ Không thể ban admin!")
        del_both(m, m2.message_id)
        return
    duration = parse_duration(reason) if reason else 86400
    until_time = int(time.time()) + duration
    try:
        bot.ban_chat_member(gid, target, until_date=until_time)
        ban_history[gk(gid)].append({
            "uid": target, "name": get_user_name(target),
            "by": m.from_user.id, "by_name": m.from_user.first_name,
            "time": time.time(), "duration": duration, "reason": reason
        })
        warns[gk(gid)][target] = 0
        time_str = f"{duration // 86400}d" if duration >= 86400 else f"{duration // 3600}h" if duration >= 3600 else f"{duration // 60}m"
        m2 = bot.reply_to(m,
            f"🚫 BAN\n"
            f"👤 {html.escape(get_user_name(target))}\n"
            f"⏰ {time_str}\n"
            f"📝 {reason or 'Không có lý do'}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
    except Exception as e:
        m2 = bot.reply_to(m, f"❌ Lỗi: {str(e)[:100]}")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['unban'])
def unban_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split()
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /unban [user_id]")
        del_both(m, m2.message_id)
        return
    try:
        target = int(parts[1])
        bot.unban_chat_member(gid, target)
        m2 = bot.reply_to(m, f"✅ Đã unban: <code>{target}</code>", parse_mode="HTML")
        del_both(m, m2.message_id)
    except:
        pass

@bot.message_handler(commands=['warn'])
def warn_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    target, reason = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /warn [user] [lý_do]")
        del_both(m, m2.message_id)
        return
    if is_admin(target, gid):
        m2 = bot.reply_to(m, "❌ Không thể warn admin!")
        del_both(m, m2.message_id)
        return
    warn_limit = get_group_setting(gid, "warn_limit", 3)
    warns[gk(gid)][target] += 1
    current_warns = warns[gk(gid)][target]
    action_text = ""
    if current_warns >= warn_limit:
        warn_ban_duration = get_group_setting(gid, "warn_ban_duration", 3600)
        try:
            bot.ban_chat_member(gid, target, until_date=int(time.time()) + warn_ban_duration)
            action_text = f"\n🚫 AUTO-BAN {warn_ban_duration // 3600}h"
            warns[gk(gid)][target] = 0
        except:
            action_text = "\n⚠️ Không thể auto-ban"
    m2 = bot.reply_to(m,
        f"⚠️ WARN\n"
        f"👤 {html.escape(get_user_name(target))}\n"
        f"📊 {current_warns}/{warn_limit}\n"
        f"📝 {reason or 'Không có lý do'}{action_text}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['unwarn'])
def unwarn_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    target, _ = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /unwarn [user] hoặc reply")
        del_both(m, m2.message_id)
        return
    warns[gk(gid)][target] = max(0, warns[gk(gid)][target] - 1)
    m2 = bot.reply_to(m, f"✅ Còn {warns[gk(gid)][target]}/3 warn", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['warns'])
def check_warns_cmd(m):
    gid = m.chat.id
    target = m.reply_to_message.from_user.id if m.reply_to_message else m.from_user.id
    count = warns[gk(gid)].get(target, 0)
    m2 = bot.reply_to(m, f"📊 {html.escape(get_user_name(target))}: {count}/3 warn", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['kick'])
def kick_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    target, reason = extract_target(m)
    if not target:
        m2 = bot.reply_to(m, "❌ /kick [user] [lý_do]")
        del_both(m, m2.message_id)
        return
    if is_admin(target, gid):
        m2 = bot.reply_to(m, "❌ Không thể kick admin!")
        del_both(m, m2.message_id)
        return
    try:
        bot.ban_chat_member(gid, target)
        time.sleep(1)
        bot.unban_chat_member(gid, target)
        m2 = bot.reply_to(m, f"👢 Đã kick: {html.escape(get_user_name(target))}", parse_mode="HTML")
        del_both(m, m2.message_id)
    except:
        pass

# ─── LỆNH QUẢN LÝ TIN NHẮN ───
@bot.message_handler(commands=['del'])
def del_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    if m.reply_to_message:
        try:
            bot.delete_message(gid, m.reply_to_message.message_id)
            m2 = bot.reply_to(m, "✅ Đã xóa!")
            del_both(m, m2.message_id)
        except:
            pass
    else:
        m2 = bot.reply_to(m, "❌ Reply tin nhắn cần xóa!")
        del_both(m, m2.message_id)

@bot.message_handler(commands=['purge'])
def purge_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    if not m.reply_to_message:
        m2 = bot.reply_to(m, "❌ Reply tin nhắn đầu tiên cần xóa!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split()
    count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
    count = min(count, 500)
    try:
        msg_ids = [m.reply_to_message.message_id + i for i in range(count)]
        bot.delete_messages(gid, msg_ids)
        m2 = bot.reply_to(m, f"✅ Đã xóa {count} tin nhắn!")
        del_both(m, m2.message_id)
    except:
        pass

@bot.message_handler(commands=['pin'])
def pin_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    if m.reply_to_message:
        try:
            bot.pin_chat_message(gid, m.reply_to_message.message_id)
            m2 = bot.reply_to(m, "📌 Đã ghim!")
            del_both(m, m2.message_id)
        except:
            pass

@bot.message_handler(commands=['unpin'])
def unpin_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    try:
        bot.unpin_chat_message(gid)
        m2 = bot.reply_to(m, "✅ Đã bỏ ghim!")
        del_both(m, m2.message_id)
    except:
        pass

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    LỆNH FILTER - HỖ TRỢ TEXT VÀ FILE/MEDIA                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['filter'])
def filter_cmd(m):
    """Quản lý filter - hỗ trợ lưu text và file/media"""
    gid = m.chat.id
    gk_str = gk(gid)
    
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền quản lý filter!")
        del_both(m, m2.message_id)
        return
    
    parts = m.text.split(maxsplit=2)
    
    # /filter - liệt kê tất cả filter
    if len(parts) == 1:
        if not filters_db.get(gk_str):
            m2 = bot.reply_to(m, 
                "📋 Chưa có filter nào!\n\n"
                "Cách dùng:\n"
                "• Text: /filter add [từ_khóa] [nội_dung]\n"
                "• File: Reply file + /filter add [từ_khóa]\n"
                "• Ảnh: Reply ảnh + /filter add [từ_khóa]\n"
                "• Video: Reply video + /filter add [từ_khóa]\n"
                "• Sticker: Reply sticker + /filter add [từ_khóa]"
            )
            del_both(m, m2.message_id)
            return
        
        text = "📋 DANH SÁCH FILTER\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, (kw, data) in enumerate(filters_db[gk_str].items(), 1):
            filter_type = data.get('type', 'text')
            if filter_type == 'text':
                preview = data.get('reply', '')[:50]
                icon = "💬"
            elif filter_type == 'photo':
                preview = "🖼️ Ảnh"
                icon = "🖼️"
            elif filter_type == 'video':
                preview = "🎬 Video"
                icon = "🎬"
            elif filter_type == 'audio':
                preview = "🎵 Audio"
                icon = "🎵"
            elif filter_type == 'document':
                preview = f"📄 {data.get('file_name', 'File')}"
                icon = "📄"
            elif filter_type == 'sticker':
                preview = "🏷️ Sticker"
                icon = "🏷️"
            elif filter_type == 'animation':
                preview = "🎞️ GIF"
                icon = "🎞️"
            elif filter_type == 'voice':
                preview = "🎤 Voice"
                icon = "🎤"
            elif filter_type == 'video_note':
                preview = "🎬 Video Note"
                icon = "🎬"
            else:
                preview = data.get('reply', '')[:50]
                icon = "📦"
            
            hit = data.get('hit_count', 0)
            text += f"{i}. {icon} <code>{html.escape(kw)}</code> → {html.escape(preview)}\n"
            text += f"   🎯 {hit} lượt kích hoạt\n"
        
        text += f"\n📊 Tổng: {len(filters_db[gk_str])} filter"
        m2 = bot.reply_to(m, text, parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    action = parts[1].lower() if len(parts) > 1 else ""
    
    # ─── /filter add - THÊM FILTER ───
    if action in ["add", "them", "thêm"]:
        args = parts[2].split(maxsplit=1) if len(parts) > 2 else [""]
        keyword = args[0].lower().strip() if args else ""
        
        if not keyword:
            m2 = bot.reply_to(m, 
                "❌ Thiếu từ khóa!\n"
                "• Text: /filter add [từ_khóa] [nội_dung]\n"
                "• File: Reply file + /filter add [từ_khóa]"
            )
            del_both(m, m2.message_id)
            return
        
        if len(keyword) < 2:
            m2 = bot.reply_to(m, "❌ Từ khóa quá ngắn (tối thiểu 2 ký tự)!")
            del_both(m, m2.message_id)
            return
        
        # Kiểm tra nếu có reply tin nhắn chứa file/media
        if m.reply_to_message:
            rmsg = m.reply_to_message
            
            # LƯU ẢNH
            if rmsg.photo:
                file_id = rmsg.photo[-1].file_id
                caption = rmsg.caption or (args[1] if len(args) > 1 else "")
                filters_db[gk_str][keyword] = {
                    "type": "photo", "file_id": file_id,
                    "caption": caption, "reply": caption or "",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER ẢNH\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🖼️ Loại: Ảnh\n"
                    f"💬 Caption: {html.escape(caption or 'Không có')}",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU VIDEO
            elif rmsg.video:
                file_id = rmsg.video.file_id
                caption = rmsg.caption or (args[1] if len(args) > 1 else "")
                filters_db[gk_str][keyword] = {
                    "type": "video", "file_id": file_id,
                    "caption": caption, "reply": caption or "",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER VIDEO\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🎬 Loại: Video",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU AUDIO
            elif rmsg.audio:
                file_id = rmsg.audio.file_id
                caption = rmsg.caption or (args[1] if len(args) > 1 else "")
                filters_db[gk_str][keyword] = {
                    "type": "audio", "file_id": file_id,
                    "caption": caption, "reply": caption or "",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER AUDIO\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🎵 Loại: Audio",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU DOCUMENT
            elif rmsg.document:
                file_id = rmsg.document.file_id
                file_name = rmsg.document.file_name or "file"
                caption = rmsg.caption or (args[1] if len(args) > 1 else "")
                filters_db[gk_str][keyword] = {
                    "type": "document", "file_id": file_id,
                    "file_name": file_name, "caption": caption,
                    "reply": caption or f"📄 {file_name}",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER DOCUMENT\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"📄 File: {html.escape(file_name)}",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU STICKER
            elif rmsg.sticker:
                file_id = rmsg.sticker.file_id
                filters_db[gk_str][keyword] = {
                    "type": "sticker", "file_id": file_id,
                    "reply": "🏷️ Sticker",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER STICKER\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🏷️ Loại: Sticker",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU GIF/ANIMATION
            elif rmsg.animation:
                file_id = rmsg.animation.file_id
                caption = rmsg.caption or (args[1] if len(args) > 1 else "")
                filters_db[gk_str][keyword] = {
                    "type": "animation", "file_id": file_id,
                    "caption": caption, "reply": caption or "",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER GIF\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🎞️ Loại: GIF/Animation",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU VOICE
            elif rmsg.voice:
                file_id = rmsg.voice.file_id
                filters_db[gk_str][keyword] = {
                    "type": "voice", "file_id": file_id,
                    "reply": "🎤 Voice",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER VOICE\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🎤 Loại: Voice",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU VIDEO NOTE
            elif rmsg.video_note:
                file_id = rmsg.video_note.file_id
                filters_db[gk_str][keyword] = {
                    "type": "video_note", "file_id": file_id,
                    "reply": "🎬 Video Note",
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER VIDEO NOTE\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"🎬 Loại: Video Note",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
            
            # LƯU TEXT (reply tin nhắn text)
            elif rmsg.text:
                reply_text = rmsg.text
                filters_db[gk_str][keyword] = {
                    "type": "text", "reply": reply_text,
                    "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
                    "added_time": time.time(), "hit_count": 0
                }
                save_filters()
                m2 = bot.reply_to(m,
                    f"✅ ĐÃ LƯU FILTER TEXT\n"
                    f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
                    f"💬 Nội dung: {html.escape(reply_text[:100])}",
                    parse_mode="HTML"
                )
                del_both(m, m2.message_id)
                return
        
        # KHÔNG REPLY - CHỈ LƯU TEXT
        if len(args) < 2 or not args[1].strip():
            m2 = bot.reply_to(m, 
                "❌ Thiếu nội dung!\n"
                "• Text: /filter add [từ_khóa] [nội_dung]\n"
                "• File: Reply file + /filter add [từ_khóa]"
            )
            del_both(m, m2.message_id)
            return
        
        reply_text = args[1].strip()
        filters_db[gk_str][keyword] = {
            "type": "text", "reply": reply_text,
            "added_by": m.from_user.id, "added_by_name": m.from_user.first_name,
            "added_time": time.time(), "hit_count": 0
        }
        save_filters()
        m2 = bot.reply_to(m,
            f"✅ ĐÃ LƯU 1 BỘ LỌC\n"
            f"🔑 Từ khóa: <code>{html.escape(keyword)}</code>\n"
            f"💬 Nội dung: {html.escape(reply_text[:100])}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    # ─── /filter del - XÓA FILTER ───
    elif action in ["del", "delete", "xoa", "xóa", "rm", "remove"]:
        if len(parts) < 3:
            m2 = bot.reply_to(m, "❌ /filter del [từ_khóa]")
            del_both(m, m2.message_id)
            return
        keyword = parts[2].lower().strip()
        if keyword in filters_db.get(gk_str, {}):
            del filters_db[gk_str][keyword]
            save_filters()
            m2 = bot.reply_to(m, f"✅ Đã xóa filter: <code>{html.escape(keyword)}</code>", parse_mode="HTML")
        else:
            m2 = bot.reply_to(m, f"❌ Không tìm thấy: <code>{html.escape(keyword)}</code>", parse_mode="HTML")
        del_both(m, m2.message_id)
        return
    
    # ─── /filter clear - XÓA TẤT CẢ ───
    elif action in ["clear", "reset"]:
        count = len(filters_db.get(gk_str, {}))
        filters_db[gk_str] = {}
        save_filters()
        m2 = bot.reply_to(m, f"✅ Đã xóa {count} filter!")
        del_both(m, m2.message_id)
        return
    
    # ─── /filter stats - THỐNG KÊ ───
    elif action in ["stats", "info"]:
        total_hits = sum(f.get("hit_count", 0) for f in filters_db.get(gk_str, {}).values())
        total_filters = len(filters_db.get(gk_str, {}))
        
        # Đếm theo loại
        type_counts = Counter(f.get("type", "text") for f in filters_db.get(gk_str, {}).values())
        type_text = ""
        type_names = {
            "text": "💬 Text", "photo": "🖼️ Ảnh", "video": "🎬 Video",
            "audio": "🎵 Audio", "document": "📄 Document", "sticker": "🏷️ Sticker",
            "animation": "🎞️ GIF", "voice": "🎤 Voice", "video_note": "🎬 Video Note"
        }
        for t, c in type_counts.most_common():
            type_text += f"{type_names.get(t, '📦 ' + t)}: {c}\n"
        
        m2 = bot.reply_to(m,
            f"📊 FILTER STATS\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Số filter: {total_filters}\n"
            f"🎯 Tổng lượt kích hoạt: {total_hits}\n\n"
            f"📋 Theo loại:\n{type_text}",
            parse_mode="HTML"
        )
        del_both(m, m2.message_id)
        return
    
    else:
        m2 = bot.reply_to(m,
            "❌ Cú pháp:\n"
            "/filter - Liệt kê filter\n"
            "/filter add [từ] [nội_dung] - Thêm text filter\n"
            "/filter add [từ] (reply file) - Thêm file filter\n"
            "/filter del [từ] - Xóa filter\n"
            "/filter clear - Xóa tất cả\n"
            "/filter stats - Thống kê"
        )
        del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    LỆNH QUẢN LÝ TỪ CẤM (BLOCK CHỬI)                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['addbad'])
def add_bad_word_cmd(m):
    """Thêm từ cấm vào danh sách"""
    gid = m.chat.id
    gk_str = gk(gid)
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /addbad [từ_cấm]")
        del_both(m, m2.message_id)
        return
    word = parts[1].strip().lower()
    if len(word) < 2:
        m2 = bot.reply_to(m, "❌ Từ quá ngắn!")
        del_both(m, m2.message_id)
        return
    if gk_str not in bad_words_db:
        bad_words_db[gk_str] = BAD_WORDS_DEFAULT.copy()
    if word in bad_words_db[gk_str]:
        m2 = bot.reply_to(m, f"❌ Từ <code>{html.escape(word)}</code> đã tồn tại!", parse_mode="HTML")
    else:
        bad_words_db[gk_str].append(word)
        save_bad_words()
        m2 = bot.reply_to(m,
            f"✅ ĐÃ THÊM TỪ CẤM\n"
            f"🔑 Từ: <code>{html.escape(word)}</code>\n"
            f"📊 Tổng: {len(bad_words_db[gk_str])} từ",
            parse_mode="HTML"
        )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['delbad'])
def del_bad_word_cmd(m):
    """Xóa từ cấm khỏi danh sách"""
    gid = m.chat.id
    gk_str = gk(gid)
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        m2 = bot.reply_to(m, "❌ /delbad [từ_cấm]")
        del_both(m, m2.message_id)
        return
    word = parts[1].strip().lower()
    if gk_str in bad_words_db and word in bad_words_db[gk_str]:
        bad_words_db[gk_str].remove(word)
        save_bad_words()
        m2 = bot.reply_to(m, f"✅ Đã xóa từ cấm: <code>{html.escape(word)}</code>", parse_mode="HTML")
    else:
        m2 = bot.reply_to(m, f"❌ Không tìm thấy: <code>{html.escape(word)}</code>", parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['listbad'])
def list_bad_words_cmd(m):
    """Liệt kê tất cả từ cấm"""
    gid = m.chat.id
    words = get_bad_words(gid)
    if not words:
        m2 = bot.reply_to(m, "📋 Chưa có từ cấm nào!")
    else:
        text = "🚫 DANH SÁCH TỪ CẤM\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, w in enumerate(words, 1):
            text += f"{i}. <code>{html.escape(w)}</code>\n"
        text += f"\n📊 Tổng: {len(words)} từ"
        m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['clearbad'])
def clear_bad_words_cmd(m):
    """Xóa tất cả từ cấm của nhóm"""
    gid = m.chat.id
    gk_str = gk(gid)
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    bad_words_db[gk_str] = []
    save_bad_words()
    m2 = bot.reply_to(m, "✅ Đã xóa tất cả từ cấm!")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    CÀI ĐẶT NHÓM                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['settings'])
def settings_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    s = get_group(gid)["settings"]
    text = (
        f"⚙️ CÀI ĐẶT NHÓM\n━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Warn limit: {s['warn_limit']}\n"
        f"🚫 Warn ban: {s['warn_ban_duration'] // 3600}h\n"
        f"📊 Spam limit: {s['spam_limit']} tin/{s['spam_window']}s\n"
        f"🔇 Auto mute spam: {'Bật' if s['auto_mute_spam'] else 'Tắt'}\n"
        f"⏰ Auto mute: {s['auto_mute_duration'] // 60}phút\n"
        f"🗑️ Xóa từ cấm: {'Bật' if s['delete_bad_words'] else 'Tắt'}\n"
        f"🔗 Xóa link: {'Bật' if s['delete_links'] else 'Tắt'}\n"
        f"🔗 Xóa link TG: {'Bật' if s['delete_telegram_links'] else 'Tắt'}\n"
        f"💬 AI Chat: {'Bật' if s['ai_chat'] else 'Tắt'}\n"
        f"🔍 Filter: {'Bật' if s.get('filter_enabled', True) else 'Tắt'}\n"
        f"🚫 Từ cấm: {'Bật' if s.get('bad_words_enabled', True) else 'Tắt'}"
    )
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['set'])
def set_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    parts = m.text.split()
    if len(parts) < 3:
        m2 = bot.reply_to(m,
            "❌ /set [key] [value]\n"
            "Keys: warn_limit, warn_ban_duration, spam_limit, spam_window,\n"
            "      auto_mute_spam, auto_mute_duration, delete_bad_words,\n"
            "      delete_links, delete_telegram_links, ai_chat,\n"
            "      filter_enabled, bad_words_enabled"
        )
        del_both(m, m2.message_id)
        return
    key = parts[1].lower()
    value = parts[2].lower()
    valid_keys = ["warn_limit", "warn_ban_duration", "spam_limit", "spam_window",
                  "auto_mute_spam", "auto_mute_duration", "delete_bad_words",
                  "delete_links", "delete_telegram_links", "ai_chat",
                  "filter_enabled", "bad_words_enabled"]
    if key not in valid_keys:
        m2 = bot.reply_to(m, "❌ Key không hợp lệ!")
        del_both(m, m2.message_id)
        return
    if key in ["auto_mute_spam", "delete_bad_words", "delete_links", 
               "delete_telegram_links", "ai_chat", "filter_enabled", "bad_words_enabled"]:
        value = value in ["true", "1", "on", "yes", "bật"]
    else:
        try:
            value = int(value)
        except:
            m2 = bot.reply_to(m, "❌ Value phải là số!")
            del_both(m, m2.message_id)
            return
    set_group_setting(gid, key, value)
    m2 = bot.reply_to(m, f"✅ Đã đặt {key} = {value}")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    LỆNH TIỆN ÍCH                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(commands=['id'])
def id_cmd(m):
    gid = m.chat.id
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        m2 = bot.reply_to(m,
            f"🆔 {html.escape(target.first_name)}\n"
            f"👤 <code>{target.id}</code>\n"
            f"💬 <code>{gid}</code>",
            parse_mode="HTML"
        )
    else:
        user = m.from_user
        m2 = bot.reply_to(m,
            f"🆔 {html.escape(user.first_name)}\n"
            f"👤 <code>{user.id}</code>\n"
            f"💬 <code>{gid}</code>",
            parse_mode="HTML"
        )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['info'])
def info_cmd(m):
    gid = m.chat.id
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    gk_str = gk(gid)
    text = (
        f"📋 THÔNG TIN\n"
        f"👤 {html.escape(target.first_name)}\n"
        f"🆔 <code>{target.id}</code>\n"
        f"⚠️ Warns: {warns[gk_str].get(target.id, 0)}/3\n"
        f"🔇 Muted: {'Có' if target.id in mutes[gk_str] else 'Không'}\n"
        f"👑 Admin: {'Có' if is_admin(target.id, gid) else 'Không'}"
    )
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['banlist'])
def banlist_cmd(m):
    gid = m.chat.id
    if not is_admin(m.from_user.id, gid):
        m2 = bot.reply_to(m, "❌ Bạn không có quyền!")
        del_both(m, m2.message_id)
        return
    history = ban_history[gk(gid)]
    if not history:
        m2 = bot.reply_to(m, "📋 Chưa có ai bị ban!")
        del_both(m, m2.message_id)
        return
    text = "📋 LỊCH SỬ BAN\n━━━━━━━━━━━━━━━━━━━━\n"
    for h in history[-10:]:
        text += f"👤 {html.escape(h['name'])} - <code>{h['uid']}</code>\n"
        text += f"👮 {html.escape(h['by_name'])} - {datetime.fromtimestamp(h['time']).strftime('%d/%m %H:%M')}\n\n"
    m2 = bot.reply_to(m, text, parse_mode="HTML")
    del_both(m, m2.message_id)

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    gid = m.chat.id
    try:
        rc = bot.get_chat_member_count(gid)
    except:
        rc = 0
    gk_str = gk(gid)
    m2 = bot.reply_to(m,
        f"📊 THỐNG KÊ\n"
        f"👥 Members: {rc}\n"
        f"🔇 Muted: {len(mutes[gk_str])}\n"
        f"⚠️ Warned: {len(warns[gk_str])}\n"
        f"🔍 Filters: {len(filters_db.get(gk_str, {}))}\n"
        f"🚫 Từ cấm: {len(get_bad_words(gid))}\n"
        f"📋 Nhóm: {len(groups_db)}",
        parse_mode="HTML"
    )
    del_both(m, m2.message_id)

@bot.message_handler(commands=['start', 'help'])
def start_cmd(m):
    gid = m.chat.id
    set_user_name(m.from_user.id, m.from_user.first_name)
    help_text = (
        f"🤖 NAO ROBOT V11.0\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ QUẢN LÝ:\n"
        f"/mute [user] [time] - Khóa mõm\n"
        f"/unmute [user] - Mở khóa\n"
        f"/ban [user] [time] - Cấm\n"
        f"/unban [user_id] - Bỏ cấm\n"
        f"/warn [user] - Cảnh cáo\n"
        f"/unwarn [user] - Gỡ cảnh cáo\n"
        f"/warns - Xem cảnh cáo\n"
        f"/kick [user] - Đuổi\n"
        f"/del - Xóa tin (reply)\n"
        f"/purge [số] - Xóa nhiều tin\n"
        f"/pin - Ghim (reply)\n"
        f"/unpin - Bỏ ghim\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 FILTER:\n"
        f"/filter - Liệt kê filter\n"
        f"/filter add [từ] [nội_dung] - Thêm text filter\n"
        f"/filter add [từ] (reply file) - Thêm file filter\n"
        f"/filter del [từ] - Xóa filter\n"
        f"/filter clear - Xóa tất cả\n"
        f"/filter stats - Thống kê\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚫 TỪ CẤM:\n"
        f"/addbad [từ] - Thêm từ cấm\n"
        f"/delbad [từ] - Xóa từ cấm\n"
        f"/listbad - Danh sách từ cấm\n"
        f"/clearbad - Xóa tất cả từ cấm\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 THÔNG TIN:\n"
        f"/id - Lấy ID\n"
        f"/info - Thông tin user\n"
        f"/admins - Danh sách admin\n"
        f"/banlist - Lịch sử ban\n"
        f"/settings - Cài đặt nhóm\n"
        f"/stats - Thống kê\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 MASTER:\n"
        f"/addgroup [id] - Thêm nhóm\n"
        f"/groups - Danh sách nhóm\n"
        f"/addadmin [user] - Thêm admin\n"
        f"/removeadmin [user] - Xóa admin\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Chat để AI trả lời!"
    )
    m2 = bot.reply_to(m, help_text, parse_mode="HTML")
    del_both(m, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    KIỂM TRA FILTER                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def check_filters(m) -> bool:
    """Kiểm tra tin nhắn có khớp filter không, trả về True nếu khớp"""
    gid = m.chat.id
    gk_str = gk(gid)
    if not get_group_setting(gid, "filter_enabled", True):
        return False
    
    text = m.text.lower()
    
    # Sắp xếp filter theo độ dài từ khóa giảm dần (ưu tiên từ khóa dài hơn)
    sorted_filters = sorted(filters_db.get(gk_str, {}).items(), 
                           key=lambda x: len(x[0]), reverse=True)
    
    for keyword, data in sorted_filters:
        if keyword in text:
            data["hit_count"] = data.get("hit_count", 0) + 1
            save_filters()
            
            filter_type = data.get("type", "text")
            
            try:
                if filter_type == "text":
                    reply_text = data.get("reply", "")
                    m2 = bot.reply_to(m, html.escape(reply_text), parse_mode="HTML")
                    auto_del(gid, m2.message_id, 30)
                    
                elif filter_type == "photo":
                    m2 = bot.reply_to(m, "🖼️", parse_mode="HTML")
                    bot.send_photo(gid, data["file_id"], caption=data.get("caption", ""))
                    bot.delete_message(gid, m2.message_id)
                    
                elif filter_type == "video":
                    m2 = bot.reply_to(m, "🎬", parse_mode="HTML")
                    bot.send_video(gid, data["file_id"], caption=data.get("caption", ""))
                    bot.delete_message(gid, m2.message_id)
                    
                elif filter_type == "audio":
                    m2 = bot.reply_to(m, "🎵", parse_mode="HTML")
                    bot.send_audio(gid, data["file_id"], caption=data.get("caption", ""))
                    bot.delete_message(gid, m2.message_id)
                    
                elif filter_type == "document":
                    bot.send_document(gid, data["file_id"], caption=data.get("caption", ""))
                    
                elif filter_type == "sticker":
                    bot.send_sticker(gid, data["file_id"])
                    
                elif filter_type == "animation":
                    bot.send_animation(gid, data["file_id"], caption=data.get("caption", ""))
                    
                elif filter_type == "voice":
                    bot.send_voice(gid, data["file_id"])
                    
                elif filter_type == "video_note":
                    bot.send_video_note(gid, data["file_id"])
                    
            except Exception as e:
                logger.error(f"Lỗi gửi filter: {e}")
                try:
                    reply_text = data.get("reply", "")
                    if reply_text:
                        bot.reply_to(m, html.escape(reply_text), parse_mode="HTML")
                except:
                    pass
            
            return True
    
    return False

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AUTO-MOD                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def auto_mod(m):
    gid = m.chat.id
    uid = m.from_user.id
    gk_str = gk(gid)
    
    set_user_name(uid, m.from_user.first_name)
    
    # Kiểm tra filter trước
    if check_filters(m):
        return
    
    # Bỏ qua admin
    if is_admin(uid, gid):
        return
    
    s = get_group(gid)["settings"]
    
    # Kiểm tra từ cấm
    if s.get("bad_words_enabled", True) and s.get("delete_bad_words", True):
        pattern = get_bad_words_pattern(gid)
        if pattern and pattern.search(m.text):
            try:
                bot.delete_message(gid, m.message_id)
            except:
                pass
            warns[gk_str][uid] += 1
            if warns[gk_str][uid] >= s.get("warn_limit", 3):
                try:
                    bot.ban_chat_member(gid, uid, until_date=int(time.time()) + s.get("warn_ban_duration", 3600))
                    bot.send_message(gid, f"🚫 {html.escape(m.from_user.first_name)} bị auto-ban vì vi phạm từ cấm!")
                except:
                    pass
                warns[gk_str][uid] = 0
            else:
                m2 = bot.send_message(gid, f"⚠️ {html.escape(m.from_user.first_name)} - Cảnh cáo ({warns[gk_str][uid]}/{s.get('warn_limit', 3)}): Không dùng từ cấm!")
                auto_del(gid, m2.message_id, 5)
            return
    
    # Kiểm tra link Telegram
    if s.get("delete_telegram_links", True) and TELEGRAM_LINK.search(m.text):
        try:
            bot.delete_message(gid, m.message_id)
        except:
            pass
        m2 = bot.send_message(gid, f"⚠️ {html.escape(m.from_user.first_name)} - Không gửi link Telegram!")
        auto_del(gid, m2.message_id, 5)
        return
    
    # Kiểm tra link khác
    if s.get("delete_links", True) and ALL_LINKS.search(m.text) and not TELEGRAM_LINK.search(m.text):
        try:
            bot.delete_message(gid, m.message_id)
        except:
            pass
        m2 = bot.send_message(gid, f"⚠️ {html.escape(m.from_user.first_name)} - Không gửi link!")
        auto_del(gid, m2.message_id, 5)
        return
    
    # Kiểm tra spam
    now = time.time()
    spam_counter[gk_str][uid] = [t for t in spam_counter[gk_str].get(uid, []) if now - t < s.get("spam_window", 4)] + [now]
    
    if len(spam_counter[gk_str][uid]) > s.get("spam_limit", 5):
        if s.get("auto_mute_spam", True):
            duration = s.get("auto_mute_duration", 1800)
            try:
                bot.restrict_chat_member(gid, uid, until_date=int(now) + duration, can_send_messages=False)
                mutes[gk_str][uid] = now + duration
            except:
                pass
        warns[gk_str][uid] += 1
        if warns[gk_str][uid] >= s.get("warn_limit", 3):
            try:
                bot.ban_chat_member(gid, uid, until_date=int(now) + s.get("warn_ban_duration", 3600))
                bot.send_message(gid, f"🚫 {html.escape(m.from_user.first_name)} bị auto-ban vì spam!")
            except:
                pass
            warns[gk_str][uid] = 0
        else:
            m2 = bot.send_message(gid, f"⚠️ {html.escape(m.from_user.first_name)} - Cảnh cáo spam ({warns[gk_str][uid]}/{s.get('warn_limit', 3)})")
            auto_del(gid, m2.message_id, 5)
        return

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    AI CHAT                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
mem = deque(maxlen=30)
ai_cd = {}

def ask_ai(prompt, gid):
    global ck_idx
    if not get_group_setting(gid, "ai_chat", True):
        return None
    if len(mem) >= 2 and mem[-2] == prompt:
        return mem[-1]
    loai = phan_loai_tin_nhan(prompt)
    fallback = random.choice(AI_RESPONSES[loai])
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

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def ai_chat_handler(m):
    gid = m.chat.id
    uid = m.from_user.id
    if not get_group_setting(gid, "ai_chat", True):
        return
    if is_admin(uid, gid):
        return
    if uid in ai_cd and time.time() - ai_cd[uid] < 2:
        return
    ai_cd[uid] = time.time()
    acquired = ai_semaphore.acquire(timeout=5)
    if not acquired:
        return
    def _ai():
        try:
            reply = ask_ai(m.text, gid)
            if reply:
                m2 = bot.reply_to(m, html.escape(reply), parse_mode="HTML")
                auto_del(gid, m2.message_id)
        except Exception as e:
            logger.error(f"AI error: {e}")
        finally:
            ai_semaphore.release()
    ai_executor.submit(_ai)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    WELCOME                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    gid = m.chat.id
    for u in m.new_chat_members:
        if u.id == bot.get_me().id:
            g = get_group(gid)
            g["name"] = m.chat.title
            save_groups()
            m2 = bot.send_message(gid, "🤖 Bot đã sẵn sàng!\n/start để xem lệnh")
            auto_del(gid, m2.message_id, 30)
        else:
            set_user_name(u.id, u.first_name)
            m2 = bot.send_message(gid, f"👋 {html.escape(u.first_name)}! Chào mừng đến với {html.escape(m.chat.title)}!\n🤖 /start để xem lệnh")
            auto_del(gid, m2.message_id)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    SCHEDULER                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def cleanup_spam():
    while True:
        time.sleep(60)
        try:
            now = time.time()
            for gk_str in list(spam_counter.keys()):
                for uid in list(spam_counter[gk_str].keys()):
                    spam_counter[gk_str][uid] = [t for t in spam_counter[gk_str][uid] if now - t < 10]
                    if not spam_counter[gk_str][uid]:
                        del spam_counter[gk_str][uid]
        except:
            pass

def auto_unmute():
    while True:
        time.sleep(15)
        try:
            now = time.time()
            for gk_str in list(mutes.keys()):
                for uid in list(mutes[gk_str].keys()):
                    if now > mutes[gk_str][uid]:
                        try:
                            gid = int(gk_str)
                            bot.restrict_chat_member(gid, uid, can_send_messages=True)
                        except:
                            pass
                        del mutes[gk_str][uid]
        except:
            pass

def save_data_periodically():
    while True:
        time.sleep(300)
        save_groups()
        save_bad_words()
        save_filters()

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    MAIN                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
def main():
    logger.info("="*60)
    logger.info("NAO ROBOT V11.0 - FULL COMPLETE")
    logger.info(f"Master Admin: {MASTER_ADMIN}")
    logger.info(f"Nhom: {len(groups_db)}")
    logger.info(f"Filters: {sum(len(f) for f in filters_db.values())}")
    logger.info(f"Bad words: {sum(len(w) for w in bad_words_db.values())}")
    logger.info("="*60)
    
    Thread(target=cleanup_spam, daemon=True, name="SpamCleanup").start()
    Thread(target=auto_unmute, daemon=True, name="AutoUnmute").start()
    Thread(target=save_data_periodically, daemon=True, name="SaveData").start()
    
    logger.info("Bot dang khoi dong...")
    bot.infinity_polling(timeout=30, none_stop=True)

if __name__ == "__main__":
    main()
