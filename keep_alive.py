# -*- coding: utf-8 -*-
# keep_alive.py - Dành cho Render.com
# Tạo web server ảo để Render không kill service

from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
    <head><title>Não Robot - Alive</title></head>
    <body style="background:#0a0a0a;color:#00ff00;font-family:monospace;text-align:center;padding-top:100px;">
        <h1>🧠 NÃO ROBOT</h1>
        <p>Status: <span style="color:#00ff00;">● ONLINE</span></p>
        <p>RAM: <span id="ram">...</span></p>
        <script>setInterval(()=>{document.getElementById('ram').textContent=(performance.memory?.usedJSHeapSize/1024/1024||0).toFixed(1)+' MB'},1000);</script>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/ping')
def ping():
    return 'PONG', 200

def run():
    """Chạy Flask server trên port từ biến môi trường PORT (mặc định 10000)."""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """Hàm chính để gọi từ bot.py."""
    t = Thread(target=run, daemon=True)
    t.start()
