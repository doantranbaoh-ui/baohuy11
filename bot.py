import telebot
import requests
import time
import os
import urllib.parse
from keep_alive import keep_alive

# Lấy token từ Render Environment
TOKEN = os.getenv("8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE")

if not TOKEN:
    raise Exception(
        "❌ Chưa thêm BOT_TOKEN trong Render Environment"
    )

bot = telebot.TeleBot(TOKEN)

keep_alive()

print("✅ Bot đang hoạt động...")


@bot.message_handler(commands=['start'])
def start(message):

    text = """
✨ BOT BUFF TYM TIKTOK ✨

📌 Cách dùng:

/like link_tiktok

Ví dụ:
/like https://vt.tiktok.com/xxxxx
"""

    bot.reply_to(message, text)


@bot.message_handler(commands=['like'])
def like(message):

    try:

        start_time = time.time()

        args = message.text.split(maxsplit=1)

        if len(args) < 2:

            bot.reply_to(
                message,
                "❌ Thiếu link TikTok"
            )
            return

        url = args[1].strip()

        if "tiktok" not in url:

            bot.reply_to(
                message,
                "❌ Link TikTok không hợp lệ"
            )
            return

        loading = bot.reply_to(
            message,
            "⏳ Đang xử lý..."
        )

        encoded_url = urllib.parse.quote(url)

        api = (
            "https://tiktokvm.vercel.app"
            f"/api/likes?url={encoded_url}"
        )

        response = requests.get(
            api,
            timeout=30
        )

        if response.status_code != 200:

            raise Exception(
                f"API lỗi: {response.status_code}"
            )

        data = response.json()

        username = data.get(
            "username",
            "Không rõ"
        )

        uid = data.get(
            "uid",
            "Không rõ"
        )

        nickname = data.get(
            "nickname",
            "Không rõ"
        )

        before = int(
            data.get(
                "before",
                0
            )
        )

        added = int(
            data.get(
                "added",
                0
            )
        )

        after = int(
            data.get(
                "after",
                before + added
            )
        )

        speed = round(
            time.time()-start_time,
            2
        )

        result = f"""
╔══════════════════╗
   ✨ BUFF TYM THÀNH CÔNG ✨
╚══════════════════╝

👤 Tài khoản: {username}
🆔 UID: {uid}
🎭 Nickname: {nickname}

━━━━━━━━━━━━━━

📈 Tym trước: {before:,}
➕ Tăng: +{added:,}
🔥 Hiện tại: {after:,}

━━━━━━━━━━━━━━

⚡ Tốc độ: {speed}s
🕒 Time:
{time.strftime("%H:%M:%S | %d/%m/%Y")}

📡 Trạng thái: Hoạt động

✅️ Video đã được buff thành công!
🚀 Cảm ơn đã sử dụng bot
"""

        bot.edit_message_text(
            result,
            chat_id=message.chat.id,
            message_id=loading.message_id
        )

    except Exception as e:

        bot.send_message(
            message.chat.id,
            f"❌ Lỗi:\n{e}"
        )

        print(e)


bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60,
    none_stop=True
)
