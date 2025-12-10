from fastapi import FastAPI
import uvicorn
import threading

app = FastAPI()

@app.get("/")
def home():
    return {"status": "bảo huy dang online nè"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=10000)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()
