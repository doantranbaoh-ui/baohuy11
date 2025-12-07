# giftcode.py
from telebot import types
import secrets, string

def _gen_code(n=8):
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def register_giftcode(bot, db, OWNER_ID):
    @bot.callback_query_handler(func=lambda c: c.data == "menu_gift")
    def _menu_gift(cq):
        msg = bot.send_message(cq.from_user.id, "Nhập giftcode của bạn:")
        bot.register_next_step_handler(msg, _handle_redeem)

    def _handle_redeem(m):
        code = (m.text or "").strip().upper()
        if not code:
            return bot.reply_to(m, "Nhập mã hợp lệ.")
        val = db.use_giftcode(code)
        if not val:
            return bot.reply_to(m, "Mã không tồn tại hoặc đã hết lượt.")
        db.add_balance(m.from_user.id, val)
        db.add_history(m.from_user.id, "redeem", f"Redeemed {code}", val)
        bot.reply_to(m, f"🎉 Nhận +{val}đ từ {code}!")

    @bot.message_handler(commands=["autogift"])
    def _autogift(m):
        # admin helper: /autogift VALUE COUNT -> create COUNT codes
        if m.from_user.id != OWNER_ID:
            return bot.reply_to(m, "❌ Bạn không có quyền.")
        parts = m.text.split()
        if len(parts) < 3:
            return bot.reply_to(m, "Dùng: /autogift VALUE COUNT")
        try:
            val = int(parts[1]); cnt = int(parts[2])
        except:
            return bot.reply_to(m, "VALUE và COUNT phải là số.")
        codes = []
        for _ in range(cnt):
            code = _gen_code(8)
            db.create_giftcode(code, val, 1)
            codes.append(code)
        bot.reply_to(m, "Đã tạo:\n" + "\n".join(codes))
