from telebot import types
from database import add_acc, delete_acc, list_acc
from history import log_history

OWNER_ID = 5736655322

def register_admin_handlers(bot):

    @bot.message_handler(commands=['admin'])
    def admin_cmd(message):
        if message.from_user.id != OWNER_ID:
            return bot.reply_to(message, "⛔ Bạn không phải admin!")

        send_admin_menu(bot, message)

    @bot.message_handler(commands=['addacc'])
    def addacc_cmd(message):
        if message.from_user.id != OWNER_ID:
            return

        msg = bot.reply_to(message,
            "📌 Nhập thông tin acc theo dạng:\n\n"
            "`game | info | price`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_addacc)

    def process_addacc(message):
        try:
            game, info, price = message.text.split("|")
            game = game.strip()
            info = info.strip()
            price = int(price.strip())

            add_acc(game, info, price)
            log_history(message.from_user.id, "Thêm acc", price, f"{game}")

            bot.reply_to(message, "✅ Đã thêm acc thành công!")

        except:
            bot.reply_to(message, "❌ Sai định dạng! Hãy nhập:\n`game | info | price`")

    @bot.message_handler(commands=['delacc'])
    def delacc_cmd(message):
        if message.from_user.id != OWNER_ID:
            return

        msg = bot.reply_to(message, "📌 Nhập ID acc muốn xóa:")
        bot.register_next_step_handler(msg, process_del)

    def process_del(message):
        try:
            acc_id = int(message.text)
            delete_acc(acc_id)
            log_history(message.from_user.id, "Xóa acc", 0, f"ID {acc_id}")

            bot.reply_to(message, "🗑️ Đã xóa acc!")
        except:
            bot.reply_to(message, "❌ ID không hợp lệ!")

    @bot.message_handler(commands=['listacc'])
    def listacc_cmd(message):
        if message.from_user.id != OWNER_ID:
            return

        data = list_acc()
        if not data:
            return bot.reply_to(message, "📭 Không có acc nào!")

        text = "📋 *Danh sách acc chưa bán:*\n\n"
        for acc in data:
            text += f"🔹 ID: {acc[0]} — {acc[1]} — {acc[2]}đ\n"

        bot.reply_to(message, text, parse_mode="Markdown")

def send_admin_menu(bot, message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Thêm acc", callback_data="admin_addacc"),
        types.InlineKeyboardButton("🗑 Xóa acc", callback_data="admin_delacc")
    )
    markup.add(types.InlineKeyboardButton("📋 Danh sách acc", callback_data="admin_listacc"))
    bot.reply_to(message, "👑 *Admin Menu*", parse_mode="Markdown", reply_markup=markup)
