import sqlite3
from telebot import types

DB = "accounts.db"

def db():
    return sqlite3.connect(DB, check_same_thread=False)

def setup_history():
    conn = db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            amount INTEGER,
            note TEXT,
            time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_history(user_id, action, amount=0, note=""):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, action, amount, note) VALUES (?,?,?,?)",
              (user_id, action, amount, note))
    conn.commit()
    conn.close()

def register_history_handlers(bot):
    @bot.message_handler(commands=['history'])
    def view_my_history(message):
        user_id = message.from_user.id
        conn = db()
        c = conn.cursor()
        c.execute("SELECT action, amount, note, time FROM history WHERE user_id=? ORDER BY id DESC LIMIT 20", 
                  (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            bot.reply_to(message, "📭 Bạn chưa có giao dịch nào.")
            return

        text = "📜 *Lịch sử giao dịch gần đây:*\n\n"
        for action, amount, note, time in rows:
            text += f"🔹 *{action}* — {amount}đ\n📝 {note}\n⏰ {time}\n\n"

        bot.reply_to(message, text, parse_mode="Markdown")
