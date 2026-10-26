from fastapi import FastAPI

app = FastAPI(
    title="TradeRakshak API",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "app": "TradeRakshak",
        "message": "Backend is running",
        "live_trading": False
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/broker/status")
def broker_status():
    return {
        "broker": "Kotak Neo",
        "connected": False,
        "mode": "test",
        "live_orders_enabled": False,
        "automatic_exit_enabled": False
    }
