import sqlite3

DB_FILE = "db.sqlite"
con = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = con.cursor()

def init_db():
    cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, total_topup INTEGER DEFAULT 0)")
    cur.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,account TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS topup_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount INTEGER,img_id TEXT,status TEXT DEFAULT 'pending')")
    con.commit()

def create_user(uid):
    cur.execute("INSERT OR IGNORE INTO users(id,balance,total_topup) VALUES(?,?,?)",(uid,0,0))
    con.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?",(uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_money(uid,amount):
    create_user(uid)
    cur.execute("UPDATE users SET balance=balance+?, total_topup=total_topup+? WHERE id=?",(amount,amount,uid))
    con.commit()

def minus(uid,amount):
    cur.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount,uid))
    con.commit()

def history_save(uid,acc):
    cur.execute("INSERT INTO history(user_id,account) VALUES(?,?)",(uid,acc))
    con.commit()

def get_top():
    cur.execute("SELECT id,total_topup FROM users ORDER BY total_topup DESC LIMIT 10")
    return cur.fetchall()

def get_history(uid):
    cur.execute("SELECT account FROM history WHERE user_id=?",(uid,))
    return cur.fetchall()

def add_request(uid,amount,img):
    cur.execute("INSERT INTO topup_requests(user_id,amount,img_id) VALUES(?,?,?)",(uid,amount,img))
    con.commit()

def remove_request(img):
    cur.execute("DELETE FROM topup_requests WHERE img_id=?",(img,))
    con.commit()
