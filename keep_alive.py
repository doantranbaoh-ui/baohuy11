from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot đang chạy ngon lành! 🚀"

def run_web_server():
    # Khởi chạy Flask ở cổng 8080
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Hàm khởi chạy Web Server trên một luồng phụ tách biệt với Bot"""
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()
