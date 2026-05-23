import time
import urllib.parse
import telebot
import requests
from requests.exceptions import RequestException, Timeout
from datetime import datetime
import pytz
from keep_alive import keep_alive

# Cấu hình Token và Múi giờ
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
bot = telebot.TeleBot(TOKEN)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

keep_alive()
print("✅ Bot Telegram đang hoạt động...")

user_cooldowns = {}
COOLDOWN_TIME = 7  # Thời gian giãn cách giữa các lần bấm lệnh (giây)


@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✨ *BOT BUFF TYM TIKTOK*\n\n📌 Cách dùng:\n`/like link_tiktok`", parse_mode="Markdown")


@bot.message_handler(commands=['like'])
def like(message):
    user_id = message.from_user.id
    current_time = time.time()

    # Kiểm tra Cooldown chống spam
    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ Vui lòng đợi {remaining} giây.")
            return

    loading = None
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok!")
            return

        url = args[1].strip()
        if "tiktok" not in url.lower():
            bot.reply_to(message, "❌ Link TikTok không hợp lệ!")
            return

        loading = bot.reply_to(message, "⏳ Đang gửi yêu cầu...")
        user_cooldowns[user_id] = current_time

        # Gọi API hệ thống
        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"
        
        response = requests.get(api, timeout=25)
        
        # Tạo sẵn thời gian định dạng chuẩn VN
        current_vn_time = datetime.now(VN_TZ).strftime("%H:%M | %d/%m/%Y")

        # --- XỬ LÝ KẾT QUẢ THEO HƯỚNG TỐI GIẢN & CHỐNG LỖI API ---
        if response.status_code == 200:
            try:
                data = response.json()
                # Thử lấy các trường dữ liệu linh hoạt, nếu trống thì để mặc định
                username = data.get("username") or data.get("user") or "TikTok User"
                added = data.get("added") or data.get("count") or "Đang chạy..."
            except:
                # Nếu API phản hồi 200 OK nhưng dữ liệu bên trong bị lỗi/rỗng
                username = "Liên kết gửi lên"
                added = "Hệ thống đang tăng"

            # Kết quả siêu ngắn gọn theo ý bạn
            result_text = f"""
🚀 **BUFF TYM THÀNH CÔNG**
━━━━━━━━━━━━━━━━━━
👤 **Tài khoản:** {username}
➕ **Trạng thái:** +{added}
🕒 **Thời gian:** {current_vn_time}
━━━━━━━━━━━━━━━━━━
✅ Hệ thống đã tiếp nhận video của bạn!
"""
            bot.edit_message_text(result_text, chat_id=message.chat.id, message_id=loading.message_id, parse_mode="Markdown")
        
        else:
            # Nếu Server API phản hồi các mã lỗi hệ thống như 404, 500, 502...
            bot.edit_message_text(f"❌ Máy chủ tăng tương tác đang bận hoặc bảo trì (Mã lỗi: {response.status_code}). Vui lòng thử lại sau!", chat_id=message.chat.id, message_id=loading.message_id)

    except Timeout:
        handle_error(message, loading, "❌ Kết nối quá hạn (Timeout). Vui lòng thử lại!")
    except RequestException:
        handle_error(message, loading, "❌ Lỗi kết nối đến máy chủ tăng tương tác!")
    except Exception as e:
        handle_error(message, loading, f"❌ Có lỗi xảy ra khi xử lý dữ liệu!")


def handle_error(message, loading_msg, error_text):
    if loading_msg:
        try:
            bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=loading_msg.message_id)
        except:
            bot.send_message(message.chat.id, error_text)
    else:
        bot.send_message(message.chat.id, error_text)


bot.infinity_polling(timeout=60, long_polling_timeout=30, none_stop=True)
