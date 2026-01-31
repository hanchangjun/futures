from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List
import uvicorn
import os

from database.connection import get_db, engine, Base
from database.models import StockBar

# 自动创建表 (生产环境建议用 Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChanQuant API")

@app.get("/")
def read_root():
    return {"message": "Welcome to ChanQuant System"}

@app.get("/api/bars/{symbol}/{period}")
def read_bars(symbol: str, period: str, limit: int = 1000, db: Session = Depends(get_db)):
    bars = db.query(StockBar).filter(
        StockBar.symbol == symbol,
        StockBar.period == period
    ).order_by(StockBar.dt.desc()).limit(limit).all()
    
    # Reverse to return chronological order
    return bars[::-1]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
