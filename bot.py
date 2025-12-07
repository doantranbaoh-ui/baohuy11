#!/usr/bin/env python3
# bot.py - Shop bot (legal products), safe, optimized for Render/Replit
# FEATURES:
# - /start, /help, inline menu
# - Catalog: /catalog, /product <id>
# - Buy flow: /buy <id> -> creates order pending -> admin approves
# - User orders: /myorders
# - Admin commands: /addproduct, /listproducts, /delproduct, /export, /createcoupon, /couponlist, /approveorder <id> <approve|reject>
# - Giftcode/coupon system: /redeem <code>
# - SQLite with WAL, thread-safe locking, commit after each write
# - Handles image uploads (order proof)
# - keep_alive import optional (for Replit)
# - TOKEN from env TELEGRAM_TOKEN (secure)

import os
import sys
import time
import csv
import logging
import sqlite3
import threading
import traceback
from datetime import datetime
from io import BytesIO

import telebot
from telebot import types

# ---------- CONFIG ----------
TOKEN = os.getenv("6367532329:AAE7uL4iMtoRBkM-Y8GIHOYDD-04XBzaAWM")
if not TOKEN:
    print("ERROR: Set TELEGRAM_TOKEN environment variable.", file=sys.stderr)
    sys.exit(1)

OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # your telegram id (optional). set to 0 if unused
PRICE_PLACEHOLDER = 10000  # default price if missing
DB_FILE = os.getenv("BOT_DB", "shop.db")
USE_KEEP_ALIVE = os.getenv("USE_KEEP_ALIVE", "false").lower() in ("1", "true", "yes")

# ---------- logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopbot")

# ---------- bot init ----------
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# optional keep alive import
if USE_KEEP_ALIVE:
    try:
        from keep_alive import keep_alive
        keep_alive()
        logger.info("keep_alive started")
    except Exception:
        logger.exception("keep_alive import failed")

# ---------- DB ----------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.commit()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            quantity INTEGER DEFAULT 0,
            created_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            product_title TEXT,
            price INTEGER,
            quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            proof_file_id TEXT,
            created_at TEXT,
            updated_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            discount INTEGER, -- amount subtracted
            used_by TEXT DEFAULT ''
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 1
        )""")
        # ensure owner as highest admin if provided
        if OWNER_ID:
            conn.execute("INSERT OR IGNORE INTO admins(user_id, level) VALUES(?,?)", (OWNER_ID, 3))
        conn.commit()
    logger.info("DB initialized (WAL)")

init_db()

# ---------- helpers ----------
def db_exec(sql, params=(), fetch=False):
    try:
        with db_lock:
            cur = conn.execute(sql, params)
            conn.commit()
            if fetch:
                return cur.fetchall()
    except Exception:
        logger.error("DB error: %s", traceback.format_exc())
        return None

def is_admin(uid):
    row = db_exec("SELECT level FROM admins WHERE user_id=?", (int(uid),), fetch=True)
    return bool(row and int(row[0]["level"]) >= 1)

def is_owner(uid):
    row = db_exec("SELECT level FROM admins WHERE user_id=?", (int(uid),), fetch=True)
    return bool(row and int(row[0]["level"]) == 3)

def format_currency(v):
    try:
        return f"{int(v):,}đ"
    except:
        return str(v)

# ---------- UI ----------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛍️ Catalog", "🧾 My Orders")
    kb.row("➕ Add Note (temp)", "ℹ️ Help")
    return kb

# ---------- Commands: user ----------
@bot.message_handler(commands=["start", "help"])
def cmd_start(m):
    try:
        uid = m.from_user.id
        bot.reply_to(m,
            f"👋 Chào {m.from_user.first_name}!\n"
            "Mình là shop bot mẫu.\n\n"
            "Dùng /catalog để xem sản phẩm,\n/buy <id> để đặt hàng,\n/myorders để xem đơn hàng của bạn.\nAdmin dùng /addproduct, /listproducts, /approveorder, v.v.",
            parse_mode="Markdown")
        bot.send_message(m.chat.id, "Menu nhanh:", reply_markup=main_menu())
    except Exception:
        logger.exception("start")

@bot.message_handler(commands=["catalog"])
def cmd_catalog(m):
    try:
        rows = db_exec("SELECT id, title, price, quantity FROM products ORDER BY id DESC", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có sản phẩm nào.")
            return
        msgs = []
        for r in rows:
            msgs.append(f"*{r['id']}* | {r['title']}\nGiá: {format_currency(r['price'])} | Tồn: {r['quantity']}")
        # send in chunks if many
        chunk = "\n\n".join(msgs)
        bot.reply_to(m, chunk, parse_mode="Markdown")
    except Exception:
        logger.exception("catalog")

@bot.message_handler(commands=["product"])
def cmd_product(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 Dùng: /product <id>")
            return
        pid = int(parts[1])
        r = db_exec("SELECT * FROM products WHERE id=?", (pid,), fetch=True)
        if not r:
            bot.reply_to(m, "❌ Sản phẩm không tồn tại.")
            return
        p = r[0]
        txt = f"*{p['title']}*\n\n{p['description'] or ''}\n\nGiá: {format_currency(p['price'])}\nTồn: {p['quantity']}\nID: {p['id']}"
        bot.reply_to(m, txt, parse_mode="Markdown")
    except Exception:
        logger.exception("product")

@bot.message_handler(commands=["buy"])
def cmd_buy(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 Dùng: /buy <product_id> [số lượng]")
            return
        pid = int(parts[1])
        qty = int(parts[2]) if len(parts) >= 3 else 1
        # fetch product
        pr = db_exec("SELECT id, title, price, quantity FROM products WHERE id=?", (pid,), fetch=True)
        if not pr:
            bot.reply_to(m, "❌ Sản phẩm không tồn tại.")
            return
        p = pr[0]
        if p["quantity"] < qty:
            bot.reply_to(m, f"⚠ Số lượng trong kho chỉ còn {p['quantity']}.")
            return
        # create order pending
        created = datetime.utcnow().isoformat()
        db_exec("""INSERT INTO orders(user_id, product_id, product_title, price, quantity, status, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)""", (m.from_user.id, p["id"], p["title"], p["price"], qty, "pending", created, created))
        # decrement stock tentatively? We'll decrement only on approve to avoid stock race (alternative approach: reserve)
        bot.reply_to(m, f"✅ Đã tạo đơn hàng cho *{p['title']}* x{qty}. Trạng thái: pending. Admin sẽ duyệt.\nGửi ảnh bằng cách reply vào đơn nếu cần.", parse_mode="Markdown")
        # notify admins
        admins = db_exec("SELECT user_id FROM admins", (), fetch=True) or []
        if admins:
            for a in admins:
                try:
                    bot.send_message(int(a[0]["user_id"]), f"📥 Đơn hàng mới từ {m.from_user.id} — dùng /orders để xem.")
                except Exception:
                    pass
    except Exception:
        logger.exception("buy")

@bot.message_handler(commands=["myorders"])
def cmd_myorders(m):
    try:
        rows = db_exec("SELECT id, product_title, price, quantity, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC", (m.from_user.id,), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Bạn chưa có đơn hàng.")
            return
        lines = []
        for r in rows:
            lines.append(f"*{r['id']}* | {r['product_title']} x{r['quantity']} | {format_currency(r['price'])} | {r['status']} | {r['created_at']}")
        bot.reply_to(m, "\n\n".join(lines), parse_mode="Markdown")
    except Exception:
        logger.exception("myorders")

@bot.message_handler(commands=["redeem"])
def cmd_redeem(m):
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /redeem <code>")
            return
        code = parts[1].upper()
        row = db_exec("SELECT discount, used_by FROM coupons WHERE code=?", (code,), fetch=True)
        if not row:
            bot.reply_to(m, "❌ Mã giảm giá không tồn tại.")
            return
        discount, used_by = row[0]["discount"], row[0]["used_by"]
        used_list = used_by.split(",") if used_by else []
        if str(m.from_user.id) in used_list:
            bot.reply_to(m, "⚠ Bạn đã dùng mã này trước đó.")
            return
        # mark used
        new_used = ",".join(used_list + [str(m.from_user.id)]) if used_by else str(m.from_user.id)
        db_exec("UPDATE coupons SET used_by=? WHERE code=?", (new_used, code))
        bot.reply_to(m, f"✅ Mã {code} áp dụng, bạn được giảm {format_currency(discount)} (lưu ý: bạn cần áp dụng mã khi thanh toán manual).")
    except Exception:
        logger.exception("redeem")

# ---------- upload image handling (proof) ----------
@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    try:
        # If user replies with "order:<id>" in caption or reply_to message, we attach proof to that order
        caption = (m.caption or "").strip()
        target_order_id = None
        # try parse "order:123" or "order 123" in caption
        import re
        if caption:
            found = re.search(r"order[:\s#]*([0-9]+)", caption, re.IGNORECASE)
            if found:
                target_order_id = int(found.group(1))
        # if replying to a bot message that mentions order id, try parse
        if not target_order_id and m.reply_to_message and m.reply_to_message.text:
            found = re.search(r"\*([0-9]+)\*", m.reply_to_message.text)  # sometimes id shown as *123*
            if found:
                target_order_id = int(found.group(1))
        # fallback: attach to latest pending order of user
        if not target_order_id:
            row = db_exec("SELECT id FROM orders WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (m.from_user.id,), fetch=True)
            if row:
                target_order_id = row[0]["id"]
        if not target_order_id:
            bot.reply_to(m, "❗ Không tìm thấy đơn hàng để đính kèm. Vui lòng gửi caption 'order:<id>' hoặc reply vào tin nhắn chứa ID đơn.")
            return
        file_id = m.photo[-1].file_id
        db_exec("UPDATE orders SET proof_file_id=?, updated_at=? WHERE id=?", (file_id, datetime.utcnow().isoformat(), target_order_id))
        bot.reply_to(m, f"✅ Đính kèm ảnh proof cho đơn #{target_order_id}. Admin sẽ kiểm tra.")
        # notify admins
        admins = db_exec("SELECT user_id FROM admins", (), fetch=True) or []
        for a in admins:
            try:
                bot.send_message(int(a[0]["user_id"]), f"📸 Proof đính kèm cho đơn #{target_order_id}")
            except Exception:
                pass
    except Exception:
        logger.exception("handle_photo")

# ---------- Admin commands ----------
@bot.message_handler(commands=["addproduct"])
def cmd_addproduct(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "📌 /addproduct title | price | qty | description")
            return
        # format: title | price | qty | description
        raw = parts[1]
        pparts = [x.strip() for x in raw.split("|")]
        if len(pparts) < 3:
            bot.reply_to(m, "📌 Format: title | price | qty | description (description optional)")
            return
        title = pparts[0]
        price = int(pparts[1].replace(",", "").replace("đ", "").strip())
        qty = int(pparts[2])
        desc = pparts[3] if len(pparts) >= 4 else ""
        db_exec("INSERT INTO products(title, description, price, quantity, created_at) VALUES(?,?,?,?,?)",
                (title, desc, price, qty, datetime.utcnow().isoformat()))
        bot.reply_to(m, f"✅ Đã thêm sản phẩm *{title}* (giá {format_currency(price)}, qty {qty})", parse_mode="Markdown")
    except Exception:
        logger.exception("addproduct")
        bot.reply_to(m, "⚠️ Lỗi khi thêm sản phẩm.")

@bot.message_handler(commands=["listproducts"])
def cmd_listproducts(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_exec("SELECT id, title, price, quantity FROM products ORDER BY id DESC", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có sản phẩm.")
            return
        lines = [f"*{r['id']}* | {r['title']} | {format_currency(r['price'])} | qty: {r['quantity']}" for r in rows]
        bot.reply_to(m, "\n".join(lines), parse_mode="Markdown")
    except Exception:
        logger.exception("listproducts")

@bot.message_handler(commands=["delproduct"])
def cmd_delproduct(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "📌 /delproduct <id>")
            return
        pid = int(parts[1])
        db_exec("DELETE FROM products WHERE id=?", (pid,))
        bot.reply_to(m, f"✅ Đã xóa product {pid}")
    except Exception:
        logger.exception("delproduct")

@bot.message_handler(commands=["export"])
def cmd_export(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_exec("SELECT id,title,description,price,quantity,created_at FROM products ORDER BY id", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có sản phẩm.")
            return
        output = "id,title,description,price,quantity,created_at\n"
        for r in rows:
            # escape csv simple
            line = [str(r["id"]), r["title"].replace("\n", " "), (r["description"] or "").replace("\n", " "), str(r["price"]), str(r["quantity"]), r["created_at"] or ""]
            output += ",".join('"%s"' % s.replace('"', '""') for s in line) + "\n"
        bio = BytesIO(output.encode("utf-8"))
        bio.name = "products_export.csv"
        bot.send_document(m.chat.id, bio)
    except Exception:
        logger.exception("export")

@bot.message_handler(commands=["orders"])
def cmd_orders(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_exec("SELECT id, user_id, product_title, price, quantity, status, created_at FROM orders ORDER BY id DESC", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có đơn.")
            return
        lines = []
        for r in rows:
            lines.append(f"*{r['id']}* | user:{r['user_id']} | {r['product_title']} x{r['quantity']} | {format_currency(r['price'])} | {r['status']} | {r['created_at']}")
        bot.reply_to(m, "\n\n".join(lines), parse_mode="Markdown")
    except Exception:
        logger.exception("orders")

@bot.message_handler(commands=["approveorder"])
def cmd_approveorder(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "📌 /approveorder <order_id> <approve|reject>")
            return
        oid = int(parts[1])
        action = parts[2].lower()
        row = db_exec("SELECT id, user_id, product_id, quantity, status FROM orders WHERE id=?", (oid,), fetch=True)
        if not row:
            bot.reply_to(m, "❌ Đơn không tồn tại.")
            return
        o = row[0]
        if o["status"] != "pending":
            bot.reply_to(m, f"⚠ Trạng thái đơn hiện là {o['status']}")
            return
        if action == "approve":
            # decrement product quantity
            prod = db_exec("SELECT quantity FROM products WHERE id=?", (o["product_id"],), fetch=True)
            if not prod:
                bot.reply_to(m, "❌ Sản phẩm liên kết không tồn tại.")
                return
            available = int(prod[0]["quantity"])
            if available < o["quantity"]:
                bot.reply_to(m, f"⚠ Kho không đủ (tồn: {available}). Hãy cập nhật kho trước khi duyệt.")
                return
            db_exec("UPDATE products SET quantity = quantity - ? WHERE id=?", (o["quantity"], o["product_id"]))
            db_exec("UPDATE orders SET status=?, updated_at=? WHERE id=?", ("approved", datetime.utcnow().isoformat(), oid))
            bot.reply_to(m, f"✅ Đã duyệt đơn #{oid}")
            # inform user
            try:
                bot.send_message(int(o["user_id"]), f"✅ Đơn hàng #{oid} của bạn đã được duyệt. Sản phẩm: {o['product_title']}.")
            except Exception:
                pass
        elif action == "reject":
            db_exec("UPDATE orders SET status=?, updated_at=? WHERE id=?", ("rejected", datetime.utcnow().isoformat(), oid))
            bot.reply_to(m, f"❌ Đã từ chối đơn #{oid}")
            try:
                bot.send_message(int(o["user_id"]), f"❌ Đơn hàng #{oid} của bạn đã bị từ chối. Liên hệ admin để biết lý do.")
            except Exception:
                pass
        else:
            bot.reply_to(m, "📌 Hành động phải là approve hoặc reject")
    except Exception:
        logger.exception("approveorder")

@bot.message_handler(commands=["createcoupon"])
def cmd_createcoupon(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "📌 /createcoupon <code> <discount_amount>")
            return
        code = parts[1].upper()
        discount = int(parts[2])
        db_exec("INSERT OR REPLACE INTO coupons(code, discount, used_by) VALUES(?,?,?)", (code, discount, ""))
        bot.reply_to(m, f"✅ Tạo coupon {code} (-{format_currency(discount)})")
    except Exception:
        logger.exception("createcoupon")

@bot.message_handler(commands=["couponlist"])
def cmd_couponlist(m):
    try:
        if not is_admin(m.from_user.id):
            bot.reply_to(m, "⛔ Bạn không có quyền.")
            return
        rows = db_exec("SELECT code, discount, used_by FROM coupons ORDER BY code", (), fetch=True)
        if not rows:
            bot.reply_to(m, "📭 Không có coupon.")
            return
        lines = [f"{r['code']} | -{format_currency(r['discount'])} | used_by: {r['used_by']}" for r in rows]
        bot.reply_to(m, "\n".join(lines))
    except Exception:
        logger.exception("couponlist")

# ---------- fallback handlers (quick menu mapping) ----------
@bot.message_handler(func=lambda msg: msg.text == "🛍️ Catalog")
def quick_catalog(m):
    cmd_catalog(m)

@bot.message_handler(func=lambda msg: msg.text == "🧾 My Orders")
def quick_orders(m):
    cmd_myorders(m)

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ Help")
def quick_help(m):
    bot.reply_to(m, "Dùng /help hoặc /start để xem hướng dẫn.")

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def fallback(m):
    text = m.text.strip().lower()
    if text.startswith("/"):
        bot.reply_to(m, "Lệnh không hợp lệ hoặc chưa hỗ trợ. Dùng /help để xem lệnh.")
    else:
        bot.reply_to(m, "Mình chưa hiểu — dùng menu hoặc /help.")

# ---------- polling loop ----------
def run_polling():
    logger.info("Starting bot polling (skip_pending=True)")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            logger.error("Polling crashed: %s\n%s", e, traceback.format_exc())
            time.sleep(3)

if __name__ == "__main__":
    run_polling()
