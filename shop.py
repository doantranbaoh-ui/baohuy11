from telebot import types

def register_shop_handlers(bot, db):

    def open_shop(call):
        cid = call.message.chat.id
        data = db.list_acc()

        if not data:
            return bot.send_message(cid, "📭 Không có acc nào bán.")

        for acc in data:
            btn = types.InlineKeyboardMarkup()
            btn.add(types.InlineKeyboardButton(f"Mua {acc[2]}đ", callback_data=f"buy_{acc[0]}"))

            bot.send_message(
                cid,
                f"🎮 *ACC LIÊN QUÂN*\n\n"
                f"ID: `{acc[0]}`\n"
                f"Thông tin: `{acc[1]}`\n"
                f"Giá: *{acc[2]}đ*",
                reply_markup=btn,
                parse_mode="Markdown"
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
    def buy_acc(call):
        uid = call.from_user.id
        acc_id = int(call.data.split("_")[1])

        acc = db.get_acc(acc_id)
        if not acc:
            return bot.answer_callback_query(call.id, "Acc không tồn tại!")

        balance = db.get_balance(uid)
        if balance < acc[2]:
            return bot.send_message(call.message.chat.id, "❌ Không đủ tiền!")

        db.add_balance(uid, -acc[2])
        db.buy_acc(acc_id, uid)
        db.add_history(uid, f"Mua acc ID {acc_id} giá {acc[2]}đ")

        bot.send_message(uid, f"✅ Mua thành công!\nThông tin acc:\n`{acc[1]}`", parse_mode="Markdown")

    # return để dùng trong Bot.py
    return type("Obj", (), {"open_shop": open_shop})
