# Bot.py
import telebot
from database import *        # exports functions and conn
import database as db
from admin import register_admin
from shop import register_shop
from giftcode import register_giftcode
from history import register_history_handlers
from keep_alive import keep_alive
import os

TOKEN = os.getenv("BOT_TOKEN","6367532329:AAE7uL4iMtoRBkM-Y8GIHOYDD-04XBzaAWM")
OWNER_ID = int(os.getenv("OWNER_ID","5736655322"))

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# register modules
register_admin(bot, db, OWNER_ID)
register_shop(bot, db, OWNER_ID)
register_giftcode(bot, db, OWNER_ID)
register_history_handlers(bot, db, OWNER_ID)

# simple start handler + main menu
@bot.message_handler(commands=["start","menu"])
def _start(m):
    db.ensure_user(m.from_user.id, m.from_user.username)
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(telebot.types.InlineKeyboardButton("🎮 Danh mục", callback_data="menu_games"))
    kb.add(telebot.types.InlineKeyboardButton("💳 Nạp tiền", callback_data="menu_topup"))
    kb.add(telebot.types.InlineKeyboardButton("🎁 Giftcode", callback_data="menu_gift"))
    kb.add(telebot.types.InlineKeyboardButton("👤 Thông tin", callback_data="menu_info"))
    bot.send_message(m.chat.id, "Chọn chức năng:", reply_markup=kb)

# start keep alive and polling
if __name__ == "__main__":
    keep_alive()
    print("Bot starting...")
    bot.infinity_polling()
