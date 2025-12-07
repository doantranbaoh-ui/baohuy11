import sqlite3

DB = "accounts.db"

def db():
    return sqlite3.connect(DB, check_same_thread=False)

# =============================
# TẠO DATABASE
# =============================
def setup_database():
    conn = db()
    c = conn.cursor()

    # Bảng user
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)

    # Bảng acc
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT,
            info TEXT,
            price INTEGER,
            sold INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

# =============================
# USER FUNCTIONS
# =============================
def add_user(user_id):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(user_id, amount):
    add_user(user_id)
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

# =============================
# ACC MANAGER
# =============================
def add_acc(game, info, price):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO accounts (game, info, price) VALUES (?,?,?)", 
              (game, info, price))
    conn.commit()
    conn.close()

def list_acc():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, game, price FROM accounts WHERE sold=0")
    rows = c.fetchall()
    conn.close()
    return rows

def get_acc(acc_id):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, game, info, price FROM accounts WHERE id=? AND sold=0", (acc_id,))
    row = c.fetchone()
    conn.close()
    return row

def mark_sold(acc_id):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE accounts SET sold=1 WHERE id=?", (acc_id,))
    conn.commit()
    conn.close()

def delete_acc(acc_id):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM accounts WHERE id=?", (acc_id,))
    conn.commit()
    conn.close()
