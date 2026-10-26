import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from kotak_auth import router as kotak_router


app = FastAPI(
    title="TradeRakshak API",
    version="1.3.0"
)

app.include_router(kotak_router)

trades = {}
trade_lock = Lock()


class PaperTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    side: Literal["BUY", "SELL"]
    entry_price: float = Field(gt=0)
    quantity: int = Field(gt=0, le=100000)
    stop_loss: float = Field(gt=0)
    target: float = Field(gt=0)


class PriceUpdate(BaseModel):
    price: float = Field(gt=0)


def calculate_pnl(trade, price):
    if trade["side"] == "BUY":
        return round(
            (price - trade["entry_price"]) * trade["quantity"], 2
        )

    return round(
        (trade["entry_price"] - price) * trade["quantity"], 2
    )


def check_exit(trade, price):
    if trade["side"] == "BUY":
        if price <= trade["stop_loss"]:
            return "STOP_LOSS"
        if price >= trade["target"]:
            return "TARGET"

    else:
        if price >= trade["stop_loss"]:
            return "STOP_LOSS"
        if price <= trade["target"]:
            return "TARGET"

    return None


@app.get("/")
def home():
    return {
        "app": "TradeRakshak",
        "message": "Backend is running",
        "mode": "paper",
        "live_trading": False
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/broker/status")
def broker_status():
    return {
        "broker": "Kotak Neo",
        "token_configured": bool(os.getenv("KOTAK_API_TOKEN")),
        "connected": False,
        "mode": "test",
        "live_orders_enabled": False,
        "automatic_exit_enabled": False
    }


@app.post("/paper/trades")
def create_paper_trade(data: PaperTradeRequest):
    if data.side == "BUY":
        if not data.stop_loss < data.entry_price < data.target:
            raise HTTPException(
                status_code=400,
                detail="BUY ke liye Stop-loss < Entry < Target hona chahiye"
            )
    else:
        if not data.target < data.entry_price < data.stop_loss:
            raise HTTPException(
                status_code=400,
                detail="SELL ke liye Target < Entry < Stop-loss hona chahiye"
            )

    trade_id = str(uuid.uuid4())[:8]

    with trade_lock:
        trades[trade_id] = {
            "trade_id": trade_id,
            "symbol": data.symbol.upper(),
            "side": data.side,
            "entry_price": data.entry_price,
            "quantity": data.quantity,
            "stop_loss": data.stop_loss,
            "target": data.target,
            "current_price": data.entry_price,
            "pnl": 0.0,
            "status": "OPEN",
            "exit_reason": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        return {
            "message": "Paper trade created",
            "trade": trades[trade_id],
            "real_order_placed": False
        }


@app.get("/paper/trades")
def list_paper_trades():
    with trade_lock:
        return {
            "mode": "PAPER_ONLY",
            "trades": list(trades.values())
        }


@app.get("/paper/trades/{trade_id}")
def get_paper_trade(trade_id: str):
    with trade_lock:
        trade = trades.get(trade_id)

        if not trade:
            raise HTTPException(
                status_code=404,
                detail="Paper trade nahi mila"
            )

        return trade


@app.post("/paper/trades/{trade_id}/price")
def update_paper_price(trade_id: str, data: PriceUpdate):
    with trade_lock:
        trade = trades.get(trade_id)

        if not trade:
            raise HTTPException(
                status_code=404,
                detail="Paper trade nahi mila"
            )

        if trade["status"] != "OPEN":
            raise HTTPException(
                status_code=409,
                detail="Trade pehle hi exit ho chuka hai"
            )

        trade["current_price"] = data.price
        trade["pnl"] = calculate_pnl(trade, data.price)

        exit_reason = check_exit(trade, data.price)

        if exit_reason:
            trade["status"] = "CLOSED"
            trade["exit_reason"] = exit_reason
            trade["exit_price"] = data.price
            trade["closed_at"] = datetime.now(timezone.utc).isoformat()

        return {
            "trade": trade,
            "automatic_exit_signal": exit_reason,
            "real_order_placed": False
        }
