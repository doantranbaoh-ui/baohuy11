import os, json
from config import USER_FILE

def load_users():
    if not os.path.exists(USER_FILE):
        save_users({})
    try:
        return json.load(open(USER_FILE,"r",encoding="utf-8"))
    except:
        save_users({})
        return {}

def save_users(data):
    json.dump(data, open(USER_FILE,"w",encoding="utf-8"), indent=4, ensure_ascii=False)

users = load_users()

def get_balance(uid):
    uid=str(uid)
    if uid not in users:
        users[uid]={"balance":0}
        save_users(users)
    return users[uid]["balance"]

def add_balance(uid,amount):
    uid=str(uid)
    if uid not in users:
        users[uid]={"balance":0}
    users[uid]["balance"]+=amount
    save_users(users)
