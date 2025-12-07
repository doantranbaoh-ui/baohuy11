from telebot import types

def register_giftcode_handlers(bot, db):

    def open_giftcode(call):
        msg = bot.send_message(call.message.chat.id, "🎁 Nhập giftcode:")
        bot.register_next_step_handler(msg, gift_step)

    def gift_step(msg):
        uid = msg.from_user.id
        code = msg.text.strip()

        amount = db.use_giftcode(uid, code)
        if not amount:
            return bot.send_message(msg.chat.id, "❌ Giftcode không hợp lệ!")

        db.add_balance(uid, amount)
        db.add_history(uid, f"Dùng giftcode +{amount}")

        bot.send_message(msg.chat.id, f"🎉 Nhận thành công +{amount}đ")

    return type("Obj", (), {"open_giftcode": open_giftcode})
