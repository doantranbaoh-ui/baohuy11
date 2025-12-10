import json, os

DATA_FILE = "data/users.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def ensure_user(user_id):
    data = load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": 0, "history": []}
        save_users(data)

def get_balance(user_id):
    return load_users().get(str(user_id), {}).get("balance", 0)

def add_balance(user_id, amount):
    data = load_users()
    uid = str(user_id)
    data[uid]["balance"] += amount
    save_users(data)

def add_history(user_id, text):
    data = load_users()
    uid = str(user_id)
    data[uid]["history"].append(text)
    save_users(data)
