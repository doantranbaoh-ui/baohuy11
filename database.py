# database.py
import os
import json
from typing import Dict, Any
from config import USERS_FILE, DATA_FOLDER

os.makedirs(DATA_FOLDER, exist_ok=True)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.write("{}")

def _load() -> Dict[str, Any]:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            f.write("{}")
        return {}

def _save(data: Dict[str, Any]):
    os.makedirs(DATA_FOLDER, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Public API
def ensure_user(uid: int):
    users = _load()
    k = str(uid)
    if k not in users:
        users[k] = {"balance": 0, "history": []}
        _save(users)

def get_balance(uid: int) -> int:
    users = _load()
    return users.get(str(uid), {}).get("balance", 0)

def add_balance(uid: int, amount: int, reason: str = ""):
    users = _load()
    k = str(uid)
    if k not in users:
        users[k] = {"balance": 0, "history": []}
    users[k]["balance"] = users[k].get("balance", 0) + int(amount)
    if reason:
        users[k].setdefault("history", []).append({"action": "add", "amount": int(amount), "reason": reason})
    _save(users)

def reduce_balance(uid: int, amount: int, reason: str = "") -> bool:
    users = _load()
    k = str(uid)
    if k not in users:
        users[k] = {"balance": 0, "history": []}
    if users[k].get("balance", 0) >= int(amount):
        users[k]["balance"] -= int(amount)
        if reason:
            users[k].setdefault("history", []).append({"action": "reduce", "amount": int(amount), "reason": reason})
        _save(users)
        return True
    return False

def add_history(uid: int, item: dict):
    users = _load()
    k = str(uid)
    if k not in users:
        users[k] = {"balance": 0, "history": []}
    users[k].setdefault("history", []).append(item)
    _save(users)

def get_history(uid: int):
    users = _load()
    return users.get(str(uid), {}).get("history", [])
