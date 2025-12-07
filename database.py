# database.py
import sqlite3
import time
import threading

DB_PATH = "data.db"
_lock = threading.Lock()

def _connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# tạo kết nối chia sẻ
_conn = _connect()
_cur = _conn.cursor()

def init_db():
    global _conn, _cur
    with _lock:
        _cur.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT,
            title TEXT,
            info TEXT,
            price INTEGER,
            sold INTEGER DEFAULT 0,
            buyer_id INTEGER,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS topup_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            photo_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS giftcodes(
            code TEXT PRIMARY KEY,
            value INTEGER,
            uses_left INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            detail TEXT,
            amount INTEGER,
            ts INTEGER
        );
        """)
        _conn.commit()

# utils
def now_ts():
    return int(time.time())

# user helpers
def ensure_user(user_id, username=""):
    with _lock:
        _cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if not _cur.fetchone():
            _cur.execute("INSERT INTO users(user_id, username, balance) VALUES (?,?,0)", (user_id, username or ""))
            _conn.commit()

def get_balance(user_id):
    ensure_user(user_id)
    with _lock:
        _cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        r = _cur.fetchone()
        return r[0] if r else 0

def add_balance(user_id, amount):
    ensure_user(user_id)
    with _lock:
        _cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        _cur.execute("INSERT INTO history(user_id,type,detail,amount,ts) VALUES (?,?,?,?,?)",
                     (user_id, "topup", f"Topup +{amount}", amount, now_ts()))
        _conn.commit()

# account helpers
def add_account(game, title, info, price):
    with _lock:
        _cur.execute("INSERT INTO accounts (game,title,info,price,created_at) VALUES (?,?,?,?,?)",
                     (game.upper(), title, info, price, now_ts()))
        _conn.commit()
        return _cur.lastrowid

def list_accounts(only_available=True, game=None, limit=100):
    sql = "SELECT id,game,title,info,price,sold FROM accounts"
    cond = []
    params = []
    if only_available:
        cond.append("sold=0")
    if game:
        cond.append("game=?")
        params.append(game.upper())
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _lock:
        _cur.execute(sql, tuple(params))
        return _cur.fetchall()

def get_account(aid):
    with _lock:
        _cur.execute("SELECT id,game,title,info,price,sold FROM accounts WHERE id=?", (aid,))
        return _cur.fetchone()

def mark_account_sold(aid, buyer_id):
    with _lock:
        _cur.execute("UPDATE accounts SET sold=1, buyer_id=? WHERE id=?", (buyer_id, aid))
        _cur.execute("INSERT INTO history(user_id,type,detail,amount,ts) VALUES (?,?,?,?,?)",
                     (buyer_id, "buy", f"Bought acc {aid}", 0, now_ts()))
        _conn.commit()

def delete_account(aid):
    with _lock:
        _cur.execute("DELETE FROM accounts WHERE id=?", (aid,))
        _conn.commit()

# topup helpers
def create_topup_request(user_id, amount, photo_file_id):
    with _lock:
        _cur.execute("INSERT INTO topup_requests (user_id,amount,photo_file_id,created_at) VALUES (?,?,?,?)",
                     (user_id, amount, photo_file_id, now_ts()))
        _conn.commit()
        return _cur.lastrowid

def get_topup(reqid):
    with _lock:
        _cur.execute("SELECT id,user_id,amount,photo_file_id,status FROM topup_requests WHERE id=?", (reqid,))
        return _cur.fetchone()

def set_topup_status(reqid, status, amount=None):
    with _lock:
        if amount is not None:
            _cur.execute("UPDATE topup_requests SET status=?, amount=? WHERE id=?", (status, amount, reqid))
        else:
            _cur.execute("UPDATE topup_requests SET status=? WHERE id=?", (status, reqid))
        _conn.commit()

# giftcode helpers
def create_giftcode(code, value, uses=1):
    with _lock:
        _cur.execute("INSERT OR REPLACE INTO giftcodes (code,value,uses_left) VALUES (?,?,?)", (code.upper(), value, uses))
        _conn.commit()

def use_giftcode(code):
    with _lock:
        _cur.execute("SELECT value, uses_left FROM giftcodes WHERE code=?", (code.upper(),))
        r = _cur.fetchone()
        if not r: return None
        value, uses = r
        if uses <= 0: return None
        _cur.execute("UPDATE giftcodes SET uses_left = uses_left - 1 WHERE code=?", (code.upper(),))
        _conn.commit()
        return value

# history helpers
def add_history(user_id, typ, detail, amount):
    with _lock:
        _cur.execute("INSERT INTO history (user_id,type,detail,amount,ts) VALUES (?,?,?,?,?)",
                     (user_id, typ, detail, amount, now_ts()))
        _conn.commit()

def get_history(user_id, limit=50):
    with _lock:
        _cur.execute("SELECT type,detail,amount,ts FROM history WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return _cur.fetchall()

# init on import
init_db()
