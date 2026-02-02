from sqlalchemy import Column, Integer, String, Float, DateTime, Index, UniqueConstraint, Text, JSON
from .connection import Base
from datetime import datetime

class StockBar(Base):
    __tablename__ = "stock_bars"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    period = Column(String, index=True, nullable=False)  # 1m, 5m, 30m, 1d
    dt = Column(DateTime, index=True, nullable=False)
    
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)  # 成交额
    
    # 唯一约束，避免重复数据
    __table_args__ = (
        UniqueConstraint('symbol', 'period', 'dt', name='uix_symbol_period_dt'),
    )

class ChanSignal(Base):
    __tablename__ = "chan_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    period = Column(String)
    dt = Column(DateTime)
    
    signal_type = Column(String) # 1B, 2B, 3B, 1S, 2S, 3S
    price = Column(Float)
    desc = Column(String)        # 描述，例如 "底分型停顿", "中枢背驰"
    
    created_at = Column(DateTime, default=datetime.now)

class TradeRecord(Base):
    """
    实盘/模拟交易记录
    """
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False)  # BUY, SELL
    status = Column(String, default="OPEN")     # OPEN, CLOSED
    
    # Entry
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    entry_signal_id = Column(String)            # Reference to signal ID
    
    # Risk
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    # Exit
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_reason = Column(String, nullable=True) # TP, SL, MANUAL, SIGNAL
    
    # Result
    pnl = Column(Float, nullable=True)          # Absolute PnL
    roi = Column(Float, nullable=True)          # Percentage
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    period = Column(String)
    days = Column(Integer)
    filter_period = Column(String)
    
    start_dt = Column(DateTime)
    end_dt = Column(DateTime)
    
    initial_capital = Column(Float)
    final_equity = Column(Float)
    pnl = Column(Float)
    roi = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    
    trades = Column(JSON) # Store trades list as JSON
    logs = Column(JSON)   # Store logs list as JSON
    positions = Column(JSON) # Store final positions
    
    created_at = Column(DateTime, default=datetime.now)
