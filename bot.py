#!/usr/bin/env python3
import telebot
from telebot import types

# ================= CONFIG =================
TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 5736655322

# =============== IMPORT MODULE ===============
from keep_alive import keep_alive
from database import setup_database
from admin import register_admin_handlers
from shop import register_shop_handlers
from giftcode import register_giftcode_handlers
from history import register_history_handlers, setup_history

# =============== START BOT ===============
bot = telebot.TeleBot(TOKEN)

# =============== MENU CHÍNH ===============
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    markup = types.InlineKeyboardMarkup()

    btn1 = types.InlineKeyboardButton("🛒 Shop Acc", callback_data="shop_menu")
    btn2 = types.InlineKeyboardButton("💳 Nạp Tiền", callback_data="nap_tien")
    btn3 = types.InlineKeyboardButton("🎁 Giftcode", callback_data="gift_menu")
    btn4 = types.InlineKeyboardButton("📜 Lịch Sử", callback_data="history_menu")

    markup.add(btn1)
    markup.add(btn2, btn3)
    markup.add(btn4)

    if user_id == OWNER_ID:
        btn_admin = types.InlineKeyboardButton("👑 Admin Menu", callback_data="admin_menu")
        markup.add(btn_admin)

    bot.reply_to(
        message,
        "🎉 *Chào mừng bạn đến Shop Acc Liên Quân!* 🎉\n\n"
        "Vui lòng chọn chức năng bên dưới:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# =============== CALLBACK MENU ===============
@bot.callback_query_handler(func=lambda call: True)
def callback_menu(call):
    if call.data == "shop_menu":
        register_shop_handlers.send_shop_menu(bot, call.message)

    elif call.data == "nap_tien":
        bot.send_message(
            call.message.chat.id,
            "💳 *Hướng dẫn nạp tiền:*\n"
            "• STK: 0971487462\n"
            "• Ngân hàng: MB\n"
            "• Nội dung: baohuy\n"
            "• Số tiền: 10000đ\n\n"
            "📸 Gửi ảnh bill trực tiếp vào chat để admin duyệt!",
            parse_mode="Markdown"
        )

    elif call.data == "gift_menu":
        register_giftcode_handlers.gift_menu(bot, call.message)

    elif call.data == "history_menu":
        bot.send_message(call.message.chat.id, "/history")

    elif call.data == "admin_menu":
        register_admin_handlers.send_admin_menu(bot, call.message)

# =============== BILL NẠP TIỀN ===============
@bot.message_handler(content_types=['photo'])
def handle_bill(message):
    user_id = message.from_user.id
    caption = f"📩 Bill nạp tiền từ user {user_id}\nDuyệt hoặc từ chối?"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Duyệt", callback_data=f"duyet_{user_id}"),
        types.InlineKeyboardButton("❌ Từ chối", callback_data=f"huy_{user_id}")
    )

    bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    bot.reply_to(message, "📤 Bill đã gửi admin duyệt!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("duyet_") or call.data.startswith("huy_"))
def duyet_nap(call):
    from database import add_balance

    user_id = int(call.data.split("_")[1])

    if call.data.startswith("duyet_"):
        amount = 10000  # fix cứng hoặc sửa tùy bạn
        add_balance(user_id, amount)
        bot.send_message(user_id, f"💰 Nạp thành công +{amount}đ!")
        bot.send_message(call.message.chat.id, "✅ Đã duyệt thành công!")
    else:
        bot.send_message(user_id, "❌ Admin đã từ chối bill.")
        bot.send_message(call.message.chat.id, "⛔ Đã từ chối!")

# =============== KHỞI TẠO DATABASE ===============
setup_database()
setup_history()

# =============== ĐĂNG KÝ MODULE ===============
register_admin_handlers(bot)
register_shop_handlers(bot)
register_giftcode_handlers(bot)
register_history_handlers(bot)

# =============== KEEP ALIVE ===============
keep_alive()

# =============== RUN BOT ===============
print("Bot is running...")
bot.infinity_polling()
