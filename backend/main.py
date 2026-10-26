import os
import uuid@app.get("/paper/dashboard")
def paper_dashboard():
    with trade_lock:
        all_trades = list(trades.values())

        open_trades = [
            trade for trade in all_trades
            if trade["status"] == "OPEN"
        ]

        closed_trades = [
            trade for trade in all_trades
            if trade["status"] == "CLOSED"
        ]

        open_pnl = round(
            sum(trade["pnl"] for trade in open_trades), 2
        )

        closed_pnl = round(
            sum(trade["pnl"] for trade in closed_trades), 2
        )

        return {
            "mode": "PAPER_ONLY",
            "live_trading": False,
            "total_trades": len(all_trades),
            "open_positions": len(open_trades),
            "closed_positions": len(closed_trades),
            "open_pnl": open_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": round(open_pnl + closed_pnl, 2),
            "trades": all_trades
        }
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
    version="1.4.0"
)

app.include_router(kotak_router)

trades = {}
trade_lock = Lock()


# =========================
# REQUEST MODELS
# =========================

class PaperTradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    side: Literal["BUY", "SELL"]
    entry_price: float = Field(gt=0)
    quantity: int = Field(gt=0, le=100000)
    stop_loss: float = Field(gt=0)
    target: float = Field(gt=0)


class PriceUpdate(BaseModel):
    price: float = Field(gt=0)


# =========================
# P&L CALCULATION
# =========================

def calculate_pnl(trade, price):
    if trade["side"] == "BUY":
        pnl = (
            price - trade["entry_price"]
        ) * trade["quantity"]
    else:
        pnl = (
            trade["entry_price"] - price
        ) * trade["quantity"]

    return round(pnl, 2)


# =========================
# STOP-LOSS / TARGET CHECK
# =========================

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


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {
        "app": "TradeRakshak",
        "message": "Backend is running",
        "mode": "paper",
        "live_trading": False
    }


# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# =========================
# BROKER STATUS
# =========================

@app.get("/broker/status")
def broker_status():
    return {
        "broker": "Kotak Neo",
        "token_configured": bool(
            os.getenv("KOTAK_API_TOKEN")
        ),
        "connected": False,
        "mode": "test",
        "live_orders_enabled": False,
        "automatic_exit_enabled": False
    }


# =========================
# CREATE PAPER TRADE
# =========================

@app.post("/paper/trades")
def create_paper_trade(data: PaperTradeRequest):

    if data.side == "BUY":
        if not (
            data.stop_loss
            < data.entry_price
            < data.target
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "BUY ke liye Stop-loss < Entry < Target "
                    "hona chahiye"
                )
            )

    else:
        if not (
            data.target
            < data.entry_price
            < data.stop_loss
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "SELL ke liye Target < Entry < Stop-loss "
                    "hona chahiye"
                )
            )

    trade_id = str(uuid.uuid4())[:8]

    trade = {
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
        "created_at": datetime.now(
            timezone.utc
        ).isoformat()
    }

    with trade_lock:
        trades[trade_id] = trade

    return {
        "message": "Paper trade created",
        "trade": trade,
        "real_order_placed": False
    }


# =========================
# LIST ALL PAPER TRADES
# =========================

@app.get("/paper/trades")
def list_paper_trades():
    with trade_lock:
        return {
            "mode": "PAPER_ONLY",
            "trades": list(trades.values())
        }


# =========================
# GET ONE PAPER TRADE
# =========================

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


# =========================
# UPDATE PRICE AND CHECK EXIT
# =========================

@app.post("/paper/trades/{trade_id}/price")
def update_paper_price(
    trade_id: str,
    data: PriceUpdate
):

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

        trade["pnl"] = calculate_pnl(
            trade,
            data.price
        )

        exit_reason = check_exit(
            trade,
            data.price
        )

        if exit_reason:
            trade["status"] = "CLOSED"
            trade["exit_reason"] = exit_reason
            trade["exit_price"] = data.price
            trade["closed_at"] = datetime.now(
                timezone.utc
            ).isoformat()

        return {
            "trade": trade,
            "automatic_exit_signal": exit_reason,
            "real_order_placed": False
        }


# =========================
# PAPER MONITORING DASHBOARD
# =========================

@app.get("/paper/dashboard")
def paper_dashboard():

    with trade_lock:
        all_trades = list(trades.values())

        open_trades = [
            trade
            for trade in all_trades
            if trade["status"] == "OPEN"
        ]

        closed_trades = [
            trade
            for trade in all_trades
            if trade["status"] == "CLOSED"
        ]

        open_pnl = round(
            sum(
                trade["pnl"]
                for trade in open_trades
            ),
            2
        )

        closed_pnl = round(
            sum(
                trade["pnl"]
                for trade in closed_trades
            ),
            2
        )

        return {
            "mode": "PAPER_ONLY",
            "live_trading": False,
            "total_trades": len(all_trades),
            "open_positions": len(open_trades),
            "closed_positions": len(closed_trades),
            "open_pnl": open_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": round(
                open_pnl + closed_pnl,
                2
            ),
            "trades": all_trades
        }
