from telebot import types

def register_admin_handlers(bot, db, OWNER_ID):

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
    def admin_callback(call):
        if call.from_user.id != OWNER_ID:
            return bot.answer_callback_query(call.id, "Không phải admin!")

        cid = call.message.chat.id

        # ADD ACC
        if call.data == "admin_addacc":
            msg = bot.send_message(cid, "Nhập dạng: info|giá")
            bot.register_next_step_handler(msg, addacc_step)
            return

        # LIST ACC
        if call.data == "admin_listacc":
            data = db.list_acc()
            if not data:
                return bot.send_message(cid, "📭 Không có acc nào.")

            text = "📋 *Danh sách acc chưa bán:*\n\n"
            for x in data:
                text += f"ID: {x[0]}\nInfo: `{x[1]}`\nGiá: {x[2]}\n\n"

            return bot.send_message(cid, text, parse_mode="Markdown")

        # DELETE ACC
        if call.data == "admin_delacc":
            msg = bot.send_message(cid, "Nhập ID acc muốn xóa:")
            bot.register_next_step_handler(msg, delacc_step)
            return

    def addacc_step(msg):
        try:
            info, price = msg.text.split("|")
            db.add_acc(info.strip(), int(price))
            bot.send_message(msg.chat.id, "✅ Đã thêm acc!")
        except:
            bot.send_message(msg.chat.id, "❌ Sai định dạng!")

    def delacc_step(msg):
        try:
            acc_id = int(msg.text)
            db.del_acc(acc_id)
            bot.send_message(msg.chat.id, "✅ Đã xóa acc!")
        except:
            bot.send_message(msg.chat.id, "❌ Lỗi!")
