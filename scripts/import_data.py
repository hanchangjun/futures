import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db, engine
from database.models import StockBar
from datafeed.tq_feed import fetch_tq_bars, resolve_tq_symbol
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

def save_bars_to_db(bars, symbol, period):
    if not bars:
        print("No bars to save.")
        return

    # Use a session context
    session = Session(bind=engine)
    
    # Construct list of dicts
    data_to_insert = []
    for bar in bars:
        data_to_insert.append({
            "symbol": symbol,
            "period": period,
            "dt": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "amount": 0.0 # TQSDK bar doesn't have amount in PriceBar wrapper currently
        })
    
    # Bulk upsert using PostgreSQL specific syntax
    stmt = insert(StockBar).values(data_to_insert)
    
    # On conflict, update the columns that might change (though history shouldn't change much)
    do_update_stmt = stmt.on_conflict_do_update(
        constraint='uix_symbol_period_dt', # Use the constraint name defined in models.py
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        }
    )
    
    try:
        result = session.execute(do_update_stmt)
        session.commit()
        print(f"Successfully saved/updated {len(data_to_insert)} bars for {symbol} {period}")
    except Exception as e:
        print(f"Error saving bars: {e}")
        session.rollback()
    finally:
        session.close()

def run_import(symbol, period="1d", count=1000, tq_user=None, tq_pass=None):
    """
    Programmatic entry point for data import
    """
    tq_symbol = resolve_tq_symbol(symbol)
    print(f"Fetching {count} bars for {tq_symbol} ({period})...")
    
    # Try getting credentials from env if not provided
    user = tq_user or os.getenv("TQ_USERNAME")
    password = tq_pass or os.getenv("TQ_PASSWORD")
    
    if not user or not password:
        print("Error: TQSDK credentials required.")
        return False

    bars = fetch_tq_bars(
        symbol=tq_symbol,
        period=period,
        count=count,
        username=user,
        password=password,
        timeout=30,
        wait_update_once=False,
        debug=True
    )
    
    if bars:
        save_bars_to_db(bars, tq_symbol, period)
        return True
    else:
        print("Failed to fetch bars.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Import TQSDK data to PostgreSQL")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol (e.g. KQ.m@SHFE.rb)")
    parser.add_argument("--period", type=str, default="1d", help="Period (e.g. 1d, 30m)")
    parser.add_argument("--count", type=int, default=1000, help="Number of bars to fetch")
    parser.add_argument("--tq-user", type=str, help="TQSDK Username")
    parser.add_argument("--tq-pass", type=str, help="TQSDK Password")
    
    args = parser.parse_args()
    run_import(args.symbol, args.period, args.count, args.tq_user, args.tq_pass)

if __name__ == "__main__":
    main()
