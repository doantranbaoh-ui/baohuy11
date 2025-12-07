#!/usr/bin/env python3
import telebot
from telebot import types

from database import Database
from admin import register_admin_handlers
from shop import register_shop_handlers
from giftcode import register_giftcode_handlers
from history import register_history_handlers
from keep_alive import keep_alive

# ================= CONFIG =================
TOKEN = "6367532329:AAE7uL4iMtoRBkM-Y8GIHOYDD-04XBzaAWM"
OWNER_ID = 5736655322

# ================= INIT ===================
bot = telebot.TeleBot(TOKEN)
db = Database("data.db")

# Load module handlers
admin = register_admin_handlers(bot, db, OWNER_ID)
shop = register_shop_handlers(bot, db)
giftcode = register_giftcode_handlers(bot, db)
history = register_history_handlers(bot, db)


# ================= MAIN MENU ==============
def main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎮 Mua Acc", callback_data="shop"))
    kb.add(
        types.InlineKeyboardButton("💳 Nạp Tiền", callback_data="nap"),
        types.InlineKeyboardButton("🎁 Giftcode", callback_data="gift"),
    )
    kb.add(types.InlineKeyboardButton("🧾 Lịch Sử", callback_data="history"))
    return kb


# ================= ADMIN MENU =============
def admin_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📥 Thêm Acc", callback_data="admin_addacc"))
    kb.add(types.InlineKeyboardButton("📋 List Acc", callback_data="admin_listacc"))
    kb.add(types.InlineKeyboardButton("❌ Xóa Acc", callback_data="admin_delacc"))
    kb.add(types.InlineKeyboardButton("🎁 Giftcode", callback_data="admin_giftcode"))
    return kb


# ================== /START =================
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    uid = msg.from_user.id
    db.add_user(uid)
    bot.send_message(
        msg.chat.id,
        f"🤖 Xin chào *{msg.from_user.first_name}*!\n"
        f"Chào mừng đến shop bán Acc Liên Quân.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )


# ================== /ADMIN =================
@bot.message_handler(commands=["admin"])
def admin_cmd(msg):
    if msg.from_user.id != OWNER_ID:
        return bot.reply_to(msg, "❌ Bạn không phải admin!")
    bot.send_message(msg.chat.id, "🔧 MENU ADMIN", reply_markup=admin_menu())


# =============== CALLBACK ==================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    cid = call.message.chat.id
    data = call.data

    # ----- SHOP -----
    if data == "shop":
        shop.open_shop(call)
        return

    # ----- NẠP TIỀN -----
    if data == "nap":
        bot.answer_callback_query(call.id)
        bot.send_message(
            cid,
            "💳 *Hướng dẫn nạp tiền*\n"
            "• STK: 0971487462\n"
            "• Ngân hàng: MB Bank\n"
            "• Nội dung: 5736655322\n"
            "• Số tiền: 10.000đ\n\n"
            "📸 Gửi ảnh bill vào đây để admin duyệt.",
            parse_mode="Markdown"
        )
        return

    # ----- GIFTCODE -----
    if data == "gift":
        giftcode.open_giftcode(call)
        return

    # ----- HISTORY -----
    if data == "history":
        history.open_history(call)
        return

    # ============= ADMIN CALLBACK ============
    if data.startswith("admin_"):
        if call.from_user.id != OWNER_ID:
            return bot.answer_callback_query(call.id, "Không phải admin!")
        # callback xử lý nằm trong admin.py
        return


# ============= KEEP ALIVE ==================
keep_alive()

# ============= RUN BOT =====================
print("Bot is running...")
bot.infinity_polling()
