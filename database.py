import sqlite3
import time

class Database:
    def __init__(self, path="data.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
        """)
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            info TEXT,
            price INTEGER,
            sold INTEGER DEFAULT 0,
            buyer_id INTEGER
        )
        """)
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS giftcodes (
            code TEXT PRIMARY KEY,
            amount INTEGER,
            used INTEGER DEFAULT 0,
            used_by INTEGER
        )
        """)
        self.cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            time INTEGER
        )
        """)

        self.conn.commit()

    # USERS
    def add_user(self, uid):
        self.cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
        self.conn.commit()

    def get_balance(self, uid):
        r = self.cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        return r[0] if r else 0

    def add_balance(self, uid, amount):
        self.cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
        self.conn.commit()

    # ACCOUNTS
    def add_acc(self, info, price):
        self.cur.execute("INSERT INTO accounts (info, price) VALUES (?, ?)", (info, price))
        self.conn.commit()

    def list_acc(self):
        return self.cur.execute("SELECT * FROM accounts WHERE sold = 0").fetchall()

    def get_acc(self, acc_id):
        return self.cur.execute("SELECT * FROM accounts WHERE id=? AND sold=0", (acc_id,)).fetchone()

    def del_acc(self, acc_id):
        self.cur.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
        self.conn.commit()

    def buy_acc(self, acc_id, user_id):
        self.cur.execute("UPDATE accounts SET sold=1, buyer_id=? WHERE id=?", (user_id, acc_id))
        self.conn.commit()

    # GIFTCODE
    def add_giftcode(self, code, amount):
        self.cur.execute("INSERT OR REPLACE INTO giftcodes (code, amount) VALUES (?, ?)", (code, amount))
        self.conn.commit()

    def use_giftcode(self, uid, code):
        gc = self.cur.execute("SELECT amount, used FROM giftcodes WHERE code=?", (code,)).fetchone()
        if not gc or gc[1] == 1:
            return None
        self.cur.execute("UPDATE giftcodes SET used=1, used_by=? WHERE code=?", (uid, code))
        self.conn.commit()
        return gc[0]

    # HISTORY
    def add_history(self, uid, text):
        self.cur.execute("INSERT INTO history (user_id, action, time) VALUES (?, ?, ?)",
                         (uid, text, int(time.time())))
        self.conn.commit()

    def get_history(self, uid):
        return self.cur.execute("SELECT action, time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 20",
                                (uid,)).fetchall()
