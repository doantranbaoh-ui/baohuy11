import time
import urllib.parse
import telebot
import requests
from requests.exceptions import RequestException, Timeout
# Gọi hệ thống keep_alive từ file kế bên sang
from keep_alive import keep_alive

# Token cấu hình trực tiếp của bạn
TOKEN = "8080338995:AAEXOZr1duwHWqmBBciXvmeHFHaiuOTvayE"
bot = telebot.TeleBot(TOKEN)

# Kích hoạt tính năng giữ sống Web Server trước khi chạy Bot chính
keep_alive()
print("✅ Bot Telegram đang hoạt động...")

# Từ điển lưu trữ thời gian bấm lệnh của người dùng để chống spam
user_cooldowns = {}
COOLDOWN_TIME = 10  # Thời gian chờ giữa các lần dùng lệnh (giây)


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

    # --- CƠ CHẾ CHỐNG SPAM (COOLDOWN) ---
    if user_id in user_cooldowns:
        elapsed_time = current_time - user_cooldowns[user_id]
        if elapsed_time < COOLDOWN_TIME:
            remaining = round(COOLDOWN_TIME - elapsed_time, 1)
            bot.reply_to(message, f"⏳ Bạn đang thao tác quá nhanh! Vui lòng đợi {remaining} giây để tiếp tục.")
            return

    start_time = time.time()
    loading = None

    try:
        # Tách lệnh và link
        args = message.text.split(maxsplit=1)

        if len(args) < 2:
            bot.reply_to(message, "❌ Vui lòng nhập kèm link TikTok.\nVí dụ: `/like https://vt.tiktok.com/xxx`", parse_mode="Markdown")
            return

        url = args[1].strip()

        if "tiktok" not in url.lower():
            bot.reply_to(message, "❌ Link gửi lên không phải link TikTok hợp lệ!")
            return

        # Gửi tin nhắn chờ xử lý và lưu trạng thái cooldown của người dùng
        loading = bot.reply_to(message, "⏳ Đang kết nối tới máy chủ API và xếp hàng xử lý dữ liệu...")
        user_cooldowns[user_id] = current_time

        # Mã hóa URL và chuẩn bị endpoint API
        encoded = urllib.parse.quote(url)
        api = f"https://tiktokvm.vercel.app/api/likes?url={encoded}"

        # Thực hiện gọi API (Đặt thời gian chờ timeout là 30 giây phòng khi server bận)
        response = requests.get(api, timeout=56)

        if response.status_code != 200:
            raise Exception(f"Máy chủ tương tác đang bảo trì (Mã lỗi HTTP: {response.status_code})")

        # Đọc dữ liệu JSON trả về
        try:
            data = response.json()
            # In log ra màn hình console để theo dõi dữ liệu thực tế nếu cần debug
            print(f" LOG API [{time.strftime('%H:%M:%S')}]: {data}")
        except ValueError:
            raise Exception("API không trả về cấu trúc định dạng JSON hợp lệ.")

        # --- PHÂN TÍCH DỮ LIỆU AN TOÀN CHỐNG CRASH BOT ---
        # Tìm kiếm linh hoạt theo nhiều tên trường dữ liệu khác nhau phòng khi API thay đổi cấu trúc cấu hình
        username = data.get("username") or data.get("user") or data.get("author") or "Không rõ"
        uid = data.get("uid") or data.get("user_id") or data.get("id") or "Không rõ"
        nickname = data.get("nickname") or data.get("name") or "Không rõ"
        
        # Hàm ép số an toàn, tránh lỗi khi trường dữ liệu bị rỗng hoặc trả về null
        def safe_int(keys, default_val=0):
            for key in keys:
                val = data.get(key)
                if val is not None and str(val).isdigit():
                    return int(val)
            return default_val

        before = safe_int(["before", "original_likes", "old_likes"], 0)
        added = safe_int(["added", "added_likes", "count"], 0)
        after = safe_int(["after", "new_likes", "current_likes"], before + added)

        # Kiểm tra xem API có trả về thông báo từ chối / lỗi ẩn bên trong JSON không
        if username == "Không rõ" and before == 0 and added == 0:
            api_error = data.get("message") or data.get("error") or data.get("msg")
            if api_error:
                raise Exception(f"Phía API từ chối xử lý với lý do: {api_error}")

        # Tính toán tốc độ xử lý thực tế
        speed = round(time.time() - start_time, 2)

        result_text = f"""
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

⚡ Tốc độ phản hồi: {speed}s
🕒 {time.strftime("%H:%M:%S | %d/%m/%Y")}

📡 Trạng thái: Hoạt động ổn định

✅ Video đã được xử lý thành công!
🚀 Cảm ơn bạn đã sử dụng bot.
"""
        # Cập nhật trực tiếp vào tin nhắn đang chờ trước đó
        bot.edit_message_text(
            result_text,
            chat_id=message.chat.id,
            message_id=loading.message_id
        )

    except Timeout:
        handle_error(message, loading, "❌ Máy chủ API phản hồi quá chậm (Timeout). Vui lòng thử lại sau ít phút khi máy chủ bớt nghẽn!")
        
    except RequestException:
        handle_error(message, loading, "❌ Lỗi kết nối vật lý không thể chạm tới máy chủ tăng tương tác!")
        
    except Exception as e:
        handle_error(message, loading, f"❌ Bot không thể lấy được kết quả từ API!\n\n**Chi tiết lỗi:** `{str(e)}`")


def handle_error(message, loading_msg, error_text):
    """Hàm trung gian quản lý việc hiển thị thông báo lỗi mượt mà trên UI Telegram"""
    print(f" LOG LỖI: {error_text}")
    if loading_msg:
        try:
            bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, error_text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, error_text, parse_mode="Markdown")


# Khởi chạy bot liên tục
bot.infinity_polling(
    timeout=60,
    long_polling_timeout=40,
    none_stop=True
)
