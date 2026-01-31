import sys
import os
from sqlalchemy.orm import Session
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import engine
from database.models import StockBar
from datafeed.base import PriceBar
from chan.k_merge import merge_klines
from chan.fractal import find_fractals
from chan.bi import find_bi
from chan.center import find_zhongshu
from chan.indicators import calculate_macd
from chan.common import Trend
from strategy.chan_strategy import ChanStrategy

def debug_run(symbol, period, count=2000):
    print(f"--- Debugging {symbol} {period} ---")
    session = Session(bind=engine)
    db_bars = session.query(StockBar).filter(
        StockBar.symbol == symbol,
        StockBar.period == period
    ).order_by(StockBar.dt.asc()).limit(count).all()
    session.close()
    
    print(f"Loaded {len(db_bars)} bars from DB")
    if not db_bars:
        return

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

    # 1. Calc MACD
    macd_df = calculate_macd(bars)
    
    # 2. Chan Processing
    chan_bars = merge_klines(bars)
    print(f"Merged K-lines: {len(chan_bars)}")
    
    fractals = find_fractals(chan_bars)
    print(f"Fractals found: {len(fractals)}")
    
    bis = find_bi(chan_bars, fractals)
    print(f"Bi found: {len(bis)}")
    
    if not bis:
        print("No Bi found. Exiting.")
        return

    # 3. Compute Dynamics
    strat = ChanStrategy(symbol, period)
    bis = strat.compute_bi_dynamics(bis, chan_bars, macd_df)
    
    # 4. Find Centers
    centers = find_zhongshu(bis)
    print(f"Centers found: {len(centers)}")
    
    # Run full strategy to see past signals
    signals = strat.run(bars)
    print(f"\nTotal Signals Generated: {len(signals)}")
    for s in signals:
        print(f"Signal: {s['type']} at {s['dt']} - {s['desc']}")
    
    # Check last few bis
    print("\n--- Last 3 Bis ---")
    for i in range(max(0, len(bis)-3), len(bis)):
        bi = bis[i]
        print(f"Bi[{i}]: Dir={bi.direction}, Start={bi.start_fx.date}, End={bi.end_fx.date}, Low={bi.low}, High={bi.high}, MACD_Area={bi.macd_area}")

    # Check last center
    if centers:
        lc = centers[-1]
        print(f"\n--- Last Center ---")
        print(f"ZG={lc.zg}, ZD={lc.zd}, Start={lc.start_bi_index}, End={lc.end_bi_index}")
        
        # Check 3B condition manually
        last_bi = bis[-1]
        if last_bi.direction == Trend.DOWN:
             print(f"Checking 3B: Last Bi Low ({last_bi.low}) > ZG ({lc.zg})? {last_bi.low > lc.zg}")
             if len(bis) >= 2:
                 prev_up = bis[-2]
                 print(f"Checking 3B: Prev Up High ({prev_up.high}) > ZG ({lc.zg})? {prev_up.high > lc.zg}")

        # Check 3S condition manually
        if last_bi.direction == Trend.UP:
             print(f"Checking 3S: Last Bi High ({last_bi.high}) < ZD ({lc.zd})? {last_bi.high < lc.zd}")
             if len(bis) >= 2:
                 prev_down = bis[-2]
                 print(f"Checking 3S: Prev Down Low ({prev_down.low}) < ZD ({lc.zd})? {prev_down.low < lc.zd}")

    # Check Divergence manually
    if len(bis) >= 3:
        last_bi = bis[-1]
        prev_bi = bis[-3]
        if last_bi.direction == prev_bi.direction:
            print(f"\n--- Checking Divergence ---")
            print(f"Last Area: {last_bi.macd_area}, Prev Area: {prev_bi.macd_area}")
            print(f"Area smaller? {last_bi.macd_area < prev_bi.macd_area}")
            if last_bi.direction == Trend.DOWN:
                print(f"New Low? {last_bi.low} < {prev_bi.low} = {last_bi.low < prev_bi.low}")
            if last_bi.direction == Trend.UP:
                print(f"New High? {last_bi.high} > {prev_bi.high} = {last_bi.high > prev_bi.high}")

if __name__ == "__main__":
    debug_run("KQ.m@SHFE.rb", "5m")
    debug_run("KQ.m@SHFE.rb", "30m")
