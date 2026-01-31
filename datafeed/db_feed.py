from typing import List, Tuple
from sqlalchemy.orm import Session
from database.connection import engine as db_engine
from database.models import StockBar
from .base import PriceBar, log_debug

def get_bars_db(
    symbol: str,
    period: str,
    count: int = 2000,
    **kwargs
) -> Tuple[List[PriceBar], str]:
    log_debug(kwargs.get("debug", False), f"Querying DB for {symbol} {period}...")
    
    session = Session(bind=db_engine)
    try:
        # Resolve symbol if needed (for now assume exact match or simple mapping)
        # TQ symbols often have "KQ.m@" prefix, DB might store them differently?
        # Assuming DB stores exact symbol passed.
        
        query = session.query(StockBar).filter(
            StockBar.symbol == symbol,
            StockBar.period == period
        ).order_by(StockBar.dt.asc())
        
        # If count is specified, maybe take last N?
        # Usually for backtest we want all available, or specific range.
        # But get_bars semantics usually implies "recent N" or "all".
        # Let's take all for now, or respect count if provided.
        # Actually backtest usually needs ALL history.
        
        db_bars = query.all()
        
        # If we need to limit to count, take from end
        if count and len(db_bars) > count:
            db_bars = db_bars[-count:]
            
        bars = []
        for b in db_bars:
            bars.append(PriceBar(
                date=b.dt,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume
            ))
            
        return bars, symbol
        
    except Exception as e:
        log_debug(kwargs.get("debug", False), f"DB Error: {e}")
        return [], symbol
    finally:
        session.close()
