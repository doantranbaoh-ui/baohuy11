import os
from threading import Thread
from flask import Flask

flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Hệ thống Shop Liên Quân đang hoạt động ổn định 24/7!", 200

def run_flask():
    # Render tự động cấp cổng qua biến môi trường PORT, mặc định là 8080 nếu chạy local
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
