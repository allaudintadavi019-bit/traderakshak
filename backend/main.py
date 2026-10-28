import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from kotak_auth import router as kotak_router


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./traderakshak.db"
)

connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


class Trade(Base):
    __tablename__ = "paper_trades"

    trade_id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    pnl = Column(Float, default=0.0)
    status = Column(String, default="OPEN")
    exit_reason = Column(String, nullable=True)
    exit_price = Column(Float, nullable=True)
    created_at = Column(String, nullable=False)
    closed_at = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TradeRakshak API",
    version="1.5.0"
)

app.include_router(kotak_router)

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


def trade_to_dict(trade):
    return {
        "trade_id": trade.trade_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "entry_price": trade.entry_price,
        "quantity": trade.quantity,
        "stop_loss": trade.stop_loss,
        "target": trade.target,
        "current_price": trade.current_price,
        "pnl": trade.pnl,
        "status": trade.status,
        "exit_reason": trade.exit_reason,
        "exit_price": trade.exit_price,
        "created_at": trade.created_at,
        "closed_at": trade.closed_at,
    }


def calculate_pnl(trade, price):
    if trade.side == "BUY":
        pnl = (
            price - trade.entry_price
        ) * trade.quantity
    else:
        pnl = (
            trade.entry_price - price
        ) * trade.quantity

    return round(pnl, 2)


def check_exit(trade, price):
    if trade.side == "BUY":
        if price <= trade.stop_loss:
            return "STOP_LOSS"
        if price >= trade.target:
            return "TARGET"
    else:
        if price >= trade.stop_loss:
            return "STOP_LOSS"
        if price <= trade.target:
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
        "token_configured": bool(
            os.getenv("KOTAK_API_TOKEN")
        ),
        "connected": False,
        "mode": "test",
        "live_orders_enabled": False,
        "automatic_exit_enabled": False
    }


@app.post("/paper/trades")
def create_paper_trade(data: PaperTradeRequest):
    if data.side == "BUY":
        valid_prices = (
            data.stop_loss
            < data.entry_price
            < data.target
        )
    else:
        valid_prices = (
            data.target
            < data.entry_price
            < data.stop_loss
        )

    if not valid_prices:
        raise HTTPException(
            status_code=400,
            detail="Entry, Stop-loss aur Target ki prices galat hain"
        )

    trade = Trade(
        trade_id=str(uuid.uuid4())[:8],
        symbol=data.symbol.upper(),
        side=data.side,
        entry_price=data.entry_price,
        quantity=data.quantity,
        stop_loss=data.stop_loss,
        target=data.target,
        current_price=data.entry_price,
        pnl=0.0,
        status="OPEN",
        created_at=datetime.now(
            timezone.utc
        ).isoformat()
    )

    db = SessionLocal()
    try:
        db.add(trade)
        db.commit()
        db.refresh(trade)

        return {
            "message": "Paper trade created",
            "trade": trade_to_dict(trade),
            "real_order_placed": False
        }
    finally:
        db.close()


@app.get("/paper/trades")
def list_paper_trades():
    db = SessionLocal()
    try:
        items = db.query(Trade).order_by(
            Trade.created_at.desc()
        ).all()

        return {
            "mode": "PAPER_ONLY",
            "trades": [
                trade_to_dict(t) for t in items
            ]
        }
    finally:
        db.close()


@app.get("/paper/trades/{trade_id}")
def get_paper_trade(trade_id: str):
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(
            Trade.trade_id == trade_id
        ).first()

        if not trade:
            raise HTTPException(
                status_code=404,
                detail="Paper trade nahi mila"
            )

        return trade_to_dict(trade)
    finally:
        db.close()


@app.post("/paper/trades/{trade_id}/price")
def update_paper_price(
    trade_id: str,
    data: PriceUpdate
):
    db = SessionLocal()
    try:
        with trade_lock:
            trade = db.query(Trade).filter(
                Trade.trade_id == trade_id
            ).first()

            if not trade:
                raise HTTPException(
                    status_code=404,
                    detail="Paper trade nahi mila"
                )

            if trade.status != "OPEN":
                raise HTTPException(
                    status_code=409,
                    detail="Trade pehle hi exit ho chuka hai"
                )

            trade.current_price = data.price
            trade.pnl = calculate_pnl(
                trade,
                data.price
            )

            exit_reason = check_exit(
                trade,
                data.price
            )

            if exit_reason:
                trade.status = "CLOSED"
                trade.exit_reason = exit_reason
                trade.exit_price = data.price
                trade.closed_at = datetime.now(
                    timezone.utc
                ).isoformat()

            db.commit()
            db.refresh(trade)

            return {
                "trade": trade_to_dict(trade),
                "automatic_exit_signal": exit_reason,
                "real_order_placed": False
            }
    finally:
        db.close()


@app.get("/paper/dashboard")
def paper_dashboard():
    db = SessionLocal()
    try:
        all_trades = db.query(Trade).all()

        open_trades = [
            t for t in all_trades
            if t.status == "OPEN"
        ]

        closed_trades = [
            t for t in all_trades
            if t.status == "CLOSED"
        ]

        open_pnl = round(
            sum(t.pnl for t in open_trades),
            2
        )

        closed_pnl = round(
            sum(t.pnl for t in closed_trades),
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
            "trades": [
                trade_to_dict(t) for t in all_trades
            ]
        }
    finally:
        db.close()
