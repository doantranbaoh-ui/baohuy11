import time
import urllib.parse
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from keep_alive import keep_alive

TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
bot = telebot.TeleBot(TOKEN)

keep_alive()
print("✅ Hệ thống Keep-Alive độc lập đã khởi động!")
print("✅ Bot Telegram đang hoạt động...")

user_cooldowns = {}
COOLDOWN_TIME = 15  # Thời gian chờ giữa các lần dùng lệnh của user


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
    user_id = message.from_user.id
    current_time = time.time()

    # --- CHỐNG SPAM ---
    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ Vui lòng đợi {remaining} giây để tiếp tục.")
            return

    start_time = time.time()
    loading = None

    try:
        args = message.text.split(maxsplit=1)

        if len(args) < 2:
            bot.reply_to(message, "❌ Vui lòng nhập link TikTok")
            return

        url = args[1].strip()

        if "tiktok" not in url.lower():
            bot.reply_to(message, "❌ Link TikTok không hợp lệ")
            return

        # 1. Gửi tin nhắn trạng thái đầu tiên
        loading = bot.reply_to(message, "⏳ Đang kết nối tới máy chủ tương tác...")
        user_cooldowns[user_id] = current_time

        # ========================================================
        # 2. CƠ CHẾ LOAD CHẬM API (DELAY NHÂN TẠO)
        # Bạn có thể đổi số 3 thành số giây bạn muốn bot đợi (ví dụ: 5, 10)
        # ========================================================
        DELAY_SECONDS = 3 
        time.sleep(DELAY_SECONDS) 
        
        # Cập nhật tin nhắn để người dùng biết bot vẫn đang chạy chứ không bị đơ
        bot.edit_message_text(
            "⏳ Đang xếp hàng xử lý dữ liệu video...", 
            chat_id=message.chat.id, 
            message_id=loading.message_id
        )
        time.sleep(2) # Đợi thêm 2 giây nữa trước khi gọi API thật
        # ========================================================

        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"

        # 3. Gọi API thật sự sau khi đã delay xong
        response = requests.get(api, timeout=40)

        if response.status_code != 200:
            raise Exception(f"Hệ thống API bảo trì hoặc bận (Mã lỗi: {response.status_code})")

        data = response.json()

        def safe_int(value, default=0):
            try:
                return int(value) if value is not None and str(value).isdigit() else default
            except:
                return default

        username = data.get("username") or "Không rõ"
        uid = data.get("uid") or "Không rõ"
        nickname = data.get("nickname") or "Không rõ"
        
        before = safe_int(data.get("before"))
        added = safe_int(data.get("added"))
        after = safe_int(data.get("after"), before + added)

        # Tính tổng tốc độ bao gồm cả thời gian đã delay
        speed = round(time.time() - start_time, 2)

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

⚡ Tổng thời gian xử lý: {speed}s
🕒 {time.strftime("%H:%M:%S | %d/%m/%Y")}

📡 Trạng thái: Hoạt động ổn định

✅ Video đã được xử lý thành công!
🚀 Cảm ơn bạn đã sử dụng bot.
"""
        bot.edit_message_text(
            result,
            chat_id=message.chat.id,
            message_id=loading.message_id
        )

    except Timeout:
        handle_error(message, loading, "❌ Máy chủ API phản hồi quá chậm. Vui lòng thử lại sau!")
        
    except RequestException:
        handle_error(message, loading, "❌ Lỗi kết nối đến máy chủ tăng tương tác!")
        
    except Exception as e:
        handle_error(message, loading, f"❌ Có lỗi xảy ra trong quá trình xử lý:\n`{str(e)}`")


def handle_error(message, loading_msg, error_text):
    print(f" LOG LỖI: {error_text}")
    if loading_msg:
        try:
            bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, error_text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, error_text, parse_mode="Markdown")


bot.infinity_polling(
    timeout=60,
    long_polling_timeout=30,
    none_stop=True
)
