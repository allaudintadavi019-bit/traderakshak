import os from kotak_auth import router as kotak_router
from fastapi import FastAPI

app = FastAPI(
    app.include_router(kotak_router)
    title="TradeRakshak API",
    version="1.2.1"
)


@app.get("/")
def home():
    return {
        "app": "TradeRakshak",
        "message": "Backend is running",
        "mode": "test",
        "live_trading": False
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/broker/status")
def broker_status():
    token = os.getenv("KOTAK_API_TOKEN")
    return {
        "broker": "Kotak Neo",
        "token_configured": bool(token),
        "connected": False,
        "mode": "test",
        "live_orders_enabled": False,
        "automatic_exit_enabled": False
    }
