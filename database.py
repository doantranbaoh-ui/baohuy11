import os
import json
from config import USER_FILE, DATA_FOLDER

# ==========================
# TẠO THƯ MỤC & FILE NẾU CHƯA CÓ
# ==========================
os.makedirs(DATA_FOLDER, exist_ok=True)

# Nếu users.json chưa tồn tại → tạo mới
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        f.write("{}")


# ==========================
# LOAD & SAVE USER DATA
# ==========================
def load_users():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        # Nếu file lỗi → reset lại file sạch
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write("{}")
        return {}


def save_users(data: dict):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ==========================
# KHỞI TẠO DATABASE VÀO BIẾN
# ==========================
users = load_users()


# ==========================
# HANDLE SỐ DƯ
# ==========================
def get_balance(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}
        save_users(users)
    return users[uid]["balance"]


def add_balance(uid, amount: int):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}
    users[uid]["balance"] += amount
    save_users(users)


# ==========================
# TRỪ TIỀN
# ==========================
def reduce_balance(uid, amount: int):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"balance": 0}
    if users[uid]["balance"] >= amount:
        users[uid]["balance"] -= amount
        save_users(users)
        return True
    return False


# ==========================
# LẤY TOÀN BỘ USER
# ==========================
def all_users():
    return users
