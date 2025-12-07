from telebot import types
from database import list_acc, get_acc, mark_sold, get_balance, add_balance
from history import log_history

def register_shop_handlers(bot):

    @bot.message_handler(commands=['shop'])
    def shop_cmd(message):
        send_shop_menu(bot, message)

def send_shop_menu(bot, message):
    data = list_acc()

    if not data:
        return bot.reply_to(message, "📭 Hiện không có acc nào!")

    text = "🛒 *Danh sách Acc Liên Quân*\n\n"
    markup = types.InlineKeyboardMarkup()

    for acc in data:
        acc_id, game, price = acc
        markup.add(
            types.InlineKeyboardButton(f"{game} - {price}đ", callback_data=f"buy_{acc_id}")
        )

    bot.reply_to(message, text, parse_mode="Markdown", reply_markup=markup)


def register_shop_handlers(bot):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
    def buy_acc(call):
        acc_id = int(call.data.split("_")[1])
        acc = get_acc(acc_id)

        if not acc:
            return bot.answer_callback_query(call.id, "Acc đã bán hoặc không tồn tại!")

        acc_id, game, info, price = acc
        user_id = call.from_user.id

        balance = get_balance(user_id)
        if balance < price:
            return bot.answer_callback_query(call.id, "❌ Bạn không đủ tiền!")

        add_balance(user_id, -price)
        mark_sold(acc_id)

        bot.send_message(user_id, f"🎉 Bạn đã mua *{game}* với giá {price}đ!\n\n🔑 Thông tin acc:\n`{info}`",
                         parse_mode="Markdown")

        log_history(user_id, "Mua acc", price, f"ID {acc_id} - {game}")
        bot.answer_callback_query(call.id, "Mua thành công!")
