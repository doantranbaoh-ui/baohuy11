import telebot
from db import init_db
from handlers import register_handlers
from keep_alive import keep_alive

TOKEN="6367532329:AAEyb8Uyot8Zj-wBbAyy-ZjJpt4JIeIKGvY"    # thay token vào

bot=telebot.TeleBot(TOKEN)

init_db()
register_handlers(bot)
keep_alive()

print("Bot running...")
bot.infinity_polling()
