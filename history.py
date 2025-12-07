import time

def register_history_handlers(bot, db):

    def open_history(call):
        uid = call.from_user.id
        data = db.get_history(uid)

        if not data:
            return bot.send_message(call.message.chat.id, "📭 Chưa có lịch sử.")

        text = "🧾 *Lịch sử giao dịch:*\n\n"
        for action, t in data:
            text += f"- {action}\n⏱ {time.strftime('%d/%m %H:%M', time.localtime(t))}\n\n"

        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

    return type("Obj", (), {"open_history": open_history})
