from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
title="TradeRakshak API",
version="1.1.0"
)

# Test-mode settings

PROFIT_TARGET = 1000
PROFIT_GIVEBACK_PERCENT = 30
DAILY_LOSS_LIMIT = 500

class TradeUpdate(BaseModel):
current_pnl: float
peak_pnl: float = 0
daily_pnl: float = 0

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
return {
"broker": "Kotak Neo",
"connected": False,
"mode": "test",
"live_orders_enabled": False,
"automatic_exit_enabled": False
}

@app.get("/settings")
def get_settings():
return {
"profit_target": PROFIT_TARGET,
"profit_giveback_percent": PROFIT_GIVEBACK_PERCENT,
"daily_loss_limit": DAILY_LOSS_LIMIT,
"mode": "test"
}

@app.post("/simulate")
def simulate_exit(trade: TradeUpdate):
current_pnl = trade.current_pnl
peak_pnl = max(trade.peak_pnl, current_pnl)

giveback_amount = peak_pnl * PROFIT_GIVEBACK_PERCENT / 100
exit_reason = None

if trade.daily_pnl <= -DAILY_LOSS_LIMIT:
    exit_reason = "DAILY_LOSS_LIMIT_REACHED"
elif peak_pnl >= PROFIT_TARGET and current_pnl <= peak_pnl - giveback_amount:
    exit_reason = "PROFIT_GIVEBACK_REACHED"

return {
    "mode": "test",
    "current_pnl": current_pnl,
    "peak_pnl": peak_pnl,
    "exit_simulation": exit_reason is not None,
    "reason": exit_reason,
    "real_order_sent": False
}
