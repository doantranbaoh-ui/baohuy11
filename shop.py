# shop.py
from telebot import types

def register_shop(bot, db, OWNER_ID):
    # main menu handler (start/menu may be in main)
    @bot.callback_query_handler(func=lambda c: c.data == "menu_games")
    def _menu_games(cq):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⚔️ Liên Quân", callback_data="buy_game:LQ"))
        kb.add(types.InlineKeyboardButton("⬅️ Quay về", callback_data="menu_back"))
        bot.edit_message_text("Chọn game:", cq.message.chat.id, cq.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "menu_back")
    def _menu_back(cq):
        bot.edit_message_text("Menu chính:", cq.message.chat.id, cq.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🎮 Danh mục", callback_data="menu_games"),
            types.InlineKeyboardButton("💳 Nạp tiền", callback_data="menu_topup")
        ))

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("buy_game:"))
    def _buy_game(cq):
        _, game = cq.data.split(":",1)
        rows = db.list_accounts(only_available=True, game=game)
        if not rows:
            return bot.send_message(cq.from_user.id, "Hiện không có acc cho game này.")
        kb = types.InlineKeyboardMarkup(row_width=1)
        for r in rows:
            aid, g, title, info, price, sold = r
            kb.add(types.InlineKeyboardButton(f"{title} — {price}đ", callback_data=f"viewacc:{aid}"))
        kb.add(types.InlineKeyboardButton("⬅️ Quay lại", callback_data="menu_back"))
        bot.edit_message_text(f"📂 Acc {game}:", cq.message.chat.id, cq.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("viewacc:"))
    def _view_acc(cq):
        aid = int(cq.data.split(":",1)[1])
        a = db.get_account(aid)
        if not a:
            return bot.answer_callback_query(cq.id, "Acc không tồn tại.")
        aid, game, title, info, price, sold = a
        kb = types.InlineKeyboardMarkup()
        if sold == 0:
            kb.add(types.InlineKeyboardButton("🛒 Mua ngay", callback_data=f"buyacc:{aid}"))
        kb.add(types.InlineKeyboardButton("⬅️ Quay lại", callback_data="menu_back"))
        bot.edit_message_text(f"<b>{title}</b>\nGame: {game}\nGiá: <b>{price}đ</b>\n\n{info}", cq.message.chat.id, cq.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("buyacc:"))
    def _buyacc(cq):
        uid = cq.from_user.id
        a_id = int(cq.data.split(":",1)[1])
        acc = db.get_account(a_id)
        if not acc:
            return bot.answer_callback_query(cq.id, "Acc không tồn tại.")
        aid, game, title, info, price, sold = acc
        if sold:
            return bot.answer_callback_query(cq.id, "Acc đã bán.")
        bal = db.get_balance(uid)
        if bal < price:
            return bot.answer_callback_query(cq.id, "Số dư không đủ. Vui lòng nạp thêm.", show_alert=True)
        # trừ tiền & mark sold
        db.add_balance(uid, -price)  # implement negative topup by passing negative
        db.mark_account_sold(aid, uid)
        db.add_history(uid, "buy", f"Bought acc {aid} {title}", -price)
        # gửi info
        bot.send_message(uid, f"🎉 Mua thành công: <b>{title}</b>\n\n<pre>{info}</pre>")
        bot.answer_callback_query(cq.id, "Mua thành công!")

    # photo handler for topup (create request)
    @bot.message_handler(content_types=['photo'])
    def _photo_topup(m):
        uid = m.from_user.id
        caption = (m.caption or "").strip()
        amt = int(caption) if caption.isdigit() else 0
        file_id = m.photo[-1].file_id
        reqid = db.create_topup_request(uid, amt, file_id)
        bot.reply_to(m, "📨 Bill đã gửi. Admin sẽ duyệt.")
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Duyệt (set số tiền)", callback_data=f"topup_approve:{reqid}"),
               types.InlineKeyboardButton("❌ Từ chối", callback_data=f"topup_reject:{reqid}"))
        try:
            bot.send_photo(OWNER_ID, file_id, caption=f"Yêu cầu nạp #{reqid}\nUser: {uid}\nSố tiền (caption): {amt if amt>0 else '(chưa có)'}", reply_markup=kb)
        except:
            pass
