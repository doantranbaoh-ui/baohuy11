# admin.py
from telebot import types

def register_admin(bot, db, OWNER_ID):
    @bot.message_handler(commands=["addacc"])
    def _addacc(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        # cú pháp: /addacc GAME|Title|Info|price
        text = m.text.partition(" ")[2].strip()
        if not text:
            return bot.reply_to(m, "Cú pháp:\n/addacc GAME|Title|Info|price")
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            return bot.reply_to(m, "Sai định dạng. VD: /addacc LQ|Acc xịn|email...|15000")
        try:
            game, title, info, price = parts[0], parts[1], parts[2], int(parts[3])
        except:
            return bot.reply_to(m, "Giá phải là số nguyên.")
        aid = db.add_account(game, title, info, price)
        bot.reply_to(m, f"✅ Đã thêm acc ID {aid} | {game} | {price}đ")

    @bot.message_handler(commands=["listacc"])
    def _listacc(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        rows = db.list_accounts(only_available=False)
        if not rows:
            return bot.reply_to(m, "📭 Kho trống.")
        text = "📋 DANH SÁCH ACC:\n\n"
        for r in rows:
            sid, game, title, info, price, sold = r
            text += f"ID:{sid} | {game} | {title} | {price}đ | {'SOLD' if sold else 'AVAIL'}\n"
        bot.reply_to(m, text)

    @bot.message_handler(commands=["delacc"])
    def _delacc(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        try:
            aid = int(m.text.split()[1])
        except:
            return bot.reply_to(m, "Dùng: /delacc ID")
        db.delete_account(aid)
        bot.reply_to(m, f"✅ Đã xóa acc ID {aid}")

    @bot.message_handler(commands=["creategift"])
    def _creategift(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        parts = m.text.split()
        if len(parts) < 3:
            return bot.reply_to(m, "Dùng: /creategift CODE VALUE [USES]")
        code = parts[1].upper()
        try:
            val = int(parts[2])
            uses = int(parts[3]) if len(parts) >= 4 else 1
        except:
            return bot.reply_to(m, "Giá trị phải là số.")
        db.create_giftcode(code, val, uses)
        bot.reply_to(m, f"🎁 Tạo giftcode {code} +{val}đ x{uses}")

    @bot.message_handler(commands=["broadcast"])
    def _broadcast(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        text = m.text.partition(" ")[2].strip()
        if not text:
            return bot.reply_to(m, "Dùng: /broadcast NỘI_DUNG")
        users = db._cur.execute("SELECT user_id FROM users").fetchall()
        sent = 0
        for u in users:
            try:
                bot.send_message(u[0], f"📣 Broadcast:\n\n{text}")
                sent += 1
            except:
                pass
        bot.reply_to(m, f"Đã gửi tới {sent} người.")

    @bot.message_handler(commands=["admin_history"])
    def _admin_history(m):
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        rows = db._cur.execute("SELECT id,user_id,type,detail,amount,ts FROM history ORDER BY id DESC LIMIT 200").fetchall()
        text = "📜 Lịch sử (200 gần nhất):\n\n"
        for r in rows:
            text += f"{r}\n"
        bot.reply_to(m, text)
