# keep_alive.py
def keep_alive():
    try:
        from fastapi import FastAPI
        import uvicorn
        from threading import Thread
    except Exception:
        return

    app = FastAPI()

    @app.get("/")
    def home():
        return {"status": "baohuy day"}

    def _run():
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")

    t = Thread(target=_run, daemon=True)
    t.start()
