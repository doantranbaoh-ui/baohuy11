from telebot import types
from database import add_balance
from history import log_history

GIFT = {
    "LQ50": 5000,
    "LQ100": 10000,
    "VIP": 20000
}

def register_giftcode_handlers(bot):

    @bot.message_handler(commands=['gift'])
    def gift_cmd(message):
        gift_menu(bot, message)

    @bot.message_handler(commands=['redeem'])
    def redeem_gift(message):
        code = message.text.replace("/redeem", "").strip().upper()
        user_id = message.from_user.id

        if code in GIFT:
            amount = GIFT[code]
            add_balance(user_id, amount)
            log_history(user_id, "Giftcode", amount, code)

            return bot.reply_to(message, f"🎁 Bạn đã nhận: +{amount}đ!")

        bot.reply_to(message, "❌ Giftcode không tồn tại hoặc đã dùng.")

def gift_menu(bot, message):
    text = "🎁 *Giftcode có sẵn:*\n\n"
    for code, amount in GIFT.items():
        text += f"🔹 `{code}` — {amount}đ\n"

    bot.reply_to(message, text, parse_mode="Markdown")
