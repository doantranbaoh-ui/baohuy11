from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'NAO ROBOT ONLINE', 200

@app.route('/health')
def health():
    return 'OK', 200

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run, daemon=True).start()
