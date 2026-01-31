
import argparse
import sys
import os
from collections import defaultdict
from typing import List, Dict

# Add project root to path (Insert at 0 to prefer local modules over stdlib)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from main import ema, atr
from datafeed import get_bars
from signals.zone import detect_zone, MarketZone

def run_attribution_analysis(args):
    # Fetch Data
    count = max(args.tq_count, 2000) # Fetch more for backtest
    print(f"Fetching {count} bars for {args.symbol} ({args.period})...")
    
    bars, _ = get_bars(
        source=args.source,
        symbol=args.symbol,
        period=args.period,
        count=count,
        csv_dir=args.csv_dir,
        csv_path=args.csv_path,
        csv_path_daily=args.csv_path_daily,
        csv_path_60=args.csv_path_60,
        tdx_symbol=args.tdx_symbol,
        tdx_host=args.tdx_host,
        tdx_port=args.tdx_port,
        tdx_market=args.tdx_market,
        tdx_auto_main=args.tdx_auto_main,
        tq_symbol=args.tq_symbol,
        username=args.tq_username or os.getenv("TQ_USERNAME"),
        password=args.tq_password or os.getenv("TQ_PASSWORD"),
        timeout=args.tq_timeout,
        wait_update_once=True,
        required=max(args.slow, args.atr) + 50, # Buffer for lookback
        debug=args.debug,
    )

    if not bars:
        print("Error: No bars found.")
        return

    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    
    # Compute Indicators
    fast_line = ema(closes, args.fast)
    slow_line = ema(closes, args.slow)
    atr_line = atr(highs, lows, closes, args.atr)
    
    # State tracking
    active_trade = None 
    trades_history = []
    
    # Logic State
    trend_entries = 0
    last_trend_state = None
    
    # Start loop (ensure enough data for indicators + slope lookback)
    start_idx = max(args.slow, args.atr, args.trend_period) + 1
    
    print("Running Backtest Simulation...")
    
    for i in range(start_idx, len(bars)):
        c = closes[i]
        h = highs[i]
        l = lows[i]
        f = fast_line[i]
        s = slow_line[i]
        a = atr_line[i]
        date = bars[i].date
        
        # --- 1. Signal Generation (Enhanced Logic from generate_chart.py) ---
        
        # Slope
        if i < args.trend_period:
            slope_val = 0
        else:
            prev_s = slow_line[i - args.trend_period]
            slope_val = (s - prev_s) / a if a > 0 else 0
            
        is_uptrend = slope_val > args.trend_slope
        is_downtrend = slope_val < -args.trend_slope
        
        curr_trend_state = "Up" if is_uptrend else ("Down" if is_downtrend else "Flat")
        if curr_trend_state != last_trend_state:
            trend_entries = 0
            last_trend_state = curr_trend_state
            
        struct_long = f > s
        struct_short = f < s
        
        # Triggers
        n_period = args.filter_pullback_n if hasattr(args, "filter_pullback_n") else 5
        m_period = args.filter_breakout_m if hasattr(args, "filter_breakout_m") else 20
        atr_factor = args.filter_atr_factor if hasattr(args, "filter_atr_factor") else 0.5
        
        # Pullback Check
        has_pullback_long = False
        has_pullback_short = False
        start_lookback = max(0, i - n_period + 1)
        for k in range(start_lookback, i + 1):
            kf = fast_line[k]
            ka = atr_line[k]
            kl = lows[k]
            kh = highs[k]
            if kl <= kf + atr_factor * ka:
                has_pullback_long = True
            if kh >= kf - atr_factor * ka:
                has_pullback_short = True
        
        # Breakout Check
        # Struct High/Low (M bars before current)
        if i >= m_period:
            sh = max(highs[i - m_period : i])
            sl = min(lows[i - m_period : i])
        else:
            sh = h
            sl = l
            
        breakout_long = (c > sh)
        breakout_short = (c < sl)
        
        trigger_long = False
        trigger_short = False
        signal_type = "None"
        
        if struct_long and is_uptrend:
            if has_pullback_long:
                trigger_long = True
                signal_type = "Pullback"
            elif breakout_long:
                trigger_long = True
                signal_type = "Breakout"
                
        if struct_short and is_downtrend:
            if has_pullback_short:
                trigger_short = True
                signal_type = "Pullback"
            elif breakout_short:
                trigger_short = True
                signal_type = "Breakout"
        
        # --- 2. Trade Management ---
        
        # Check Active Trade Exit First
        if active_trade:
            closed_info = None
            if active_trade["direction"] == "Long":
                if l <= active_trade["stop"]:
                    closed_info = {"price": active_trade["stop"], "reason": "StopLoss"}
                elif h >= active_trade["tp"]:
                    closed_info = {"price": active_trade["tp"], "reason": "TakeProfit"}
            else: # Short
                if h >= active_trade["stop"]:
                    closed_info = {"price": active_trade["stop"], "reason": "StopLoss"}
                elif l <= active_trade["tp"]:
                    closed_info = {"price": active_trade["tp"], "reason": "TakeProfit"}
            
            if closed_info:
                entry_price = active_trade["entry"]
                exit_price = closed_info["price"]
                if active_trade["direction"] == "Long":
                    pnl = exit_price - entry_price
                else:
                    pnl = entry_price - exit_price
                
                trades_history.append({
                    "zone": active_trade["zone"],
                    "signal_type": active_trade["signal_type"],
                    "direction": active_trade["direction"],
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "entry_date": active_trade["entry_date"],
                    "exit_date": date
                })
                active_trade = None

        # Check Entry
        if not active_trade:
            # Check limits
            allowed = True
            max_entries = args.max_entries if hasattr(args, "max_entries") else 2
            if trend_entries >= max_entries:
                allowed = False
                
            if allowed and (trigger_long or trigger_short):
                # *** DETECT ZONE AT ENTRY MOMENT ***
                # We need historical lists up to current index i
                # Slicing ends at i+1 to include current bar
                zone_res, _ = detect_zone(
                    closes[:i+1],
                    fast_line[:i+1], # Note: detect_zone expects ema20/ema60
                    slow_line[:i+1], # Assume fast=20, slow=60 for zone calc logic? 
                                     # Wait, user said "Based on EMA20/EMA60/ATR".
                                     # Our args.fast might be 20, args.slow might be 60.
                                     # Let's pass the computed lines.
                    a
                )
                
                direction = "Long" if trigger_long else "Short"
                entry_price = c
                
                # Stop/TP
                if direction == "Long":
                    stop = c - a * args.stop_mult
                    tp = c + abs(c - stop) * args.tp_mult
                else:
                    stop = c + a * args.stop_mult
                    tp = c - abs(c - stop) * args.tp_mult
                    
                active_trade = {
                    "direction": direction,
                    "entry": entry_price,
                    "stop": stop,
                    "tp": tp,
                    "zone": zone_res.value,
                    "signal_type": signal_type,
                    "entry_date": date
                }
                trend_entries += 1

    # --- 3. Attribution Analysis ---
    
    # Structure: Zone -> Signal -> Stats
    attribution = defaultdict(lambda: defaultdict(list))
    
    for t in trades_history:
        attribution[t["zone"]][t["signal_type"]].append(t)
        
    print("\n" + "="*60)
    print(f"ZONE x OUTCOME ATTRIBUTION REPORT: {args.symbol}")
    print("="*60 + "\n")
    
    # Expected Zones order
    zones_order = ["TREND_START", "TREND_EXTEND", "RANGE_NOISE", "TREND_EXHAUST"]
    
    for zone in zones_order:
        print(f"ZONE={zone}")
        signals_data = attribution.get(zone, {})
        
        if not signals_data:
            print("  (No trades recorded)")
            print("")
            continue
            
        for sig_type, trades in signals_data.items():
            count = len(trades)
            if count == 0: continue
            
            wins = [t for t in trades if t["pnl"] > 0]
            losses = [t for t in trades if t["pnl"] <= 0]
            
            win_rate = len(wins) / count
            avg_pnl = sum(t["pnl"] for t in trades) / count
            
            # Expectancy Calculation
            # Exp = (Win% * AvgWin) - (Loss% * AvgLoss)
            # This is mathematically equal to Avg PnL per trade.
            # But let's show components if needed.
            # Let's just use Avg PnL as Expectancy (Expectation per trade).
            expectancy = avg_pnl 
            
            # Formatting
            win_rate_str = f"{win_rate*100:.1f}%"
            exp_str = f"{expectancy:+.2f}"
            
            print(f"  - {sig_type:<10} : trade={count:<4}, win_rate={win_rate_str:<6}, expectancy={exp_str}")
            
        print("")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Attribution Analysis")
    
    # Basic args
    parser.add_argument("--symbol", type=str, required=True)
    parser.add_argument("--period", type=str, default="30m")
    parser.add_argument("--source", type=str, default="tq")
    parser.add_argument("--tq_count", type=int, default=5000)
    
    # Strategy Params (Defaults for Rebar)
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=60)
    parser.add_argument("--atr", type=int, default=14)
    parser.add_argument("--stop_mult", type=float, default=2.0)
    parser.add_argument("--tp_mult", type=float, default=3.0)
    
    # Enhanced Params
    parser.add_argument("--trend_period", type=int, default=5)
    parser.add_argument("--trend_slope", type=float, default=0.1)
    parser.add_argument("--filter_pullback_n", type=int, default=5)
    parser.add_argument("--filter_breakout_m", type=int, default=20)
    parser.add_argument("--filter_atr_factor", type=float, default=0.5)
    parser.add_argument("--max_entries", type=int, default=2)
    
    # Datafeed args (boilerplate)
    parser.add_argument("--csv_dir", type=str, default="data/csv")
    parser.add_argument("--csv_path", type=str, default="")
    parser.add_argument("--csv_path_daily", type=str, default="")
    parser.add_argument("--csv_path_60", type=str, default="")
    parser.add_argument("--tdx_symbol", type=str, default="")
    parser.add_argument("--tdx_host", type=str, default="119.147.212.81")
    parser.add_argument("--tdx_port", type=int, default=7709)
    parser.add_argument("--tdx_market", type=int, default=1)
    parser.add_argument("--tdx_auto_main", action="store_true")
    parser.add_argument("--tq_symbol", type=str, default="")
    parser.add_argument("--tq_username", type=str, default="")
    parser.add_argument("--tq_password", type=str, default="")
    parser.add_argument("--tq_timeout", type=int, default=30)
    parser.add_argument("--increment", action="store_true")
    parser.add_argument("--cache_file", type=str, default="")
    parser.add_argument("--increment_count", type=int, default=1)
    parser.add_argument("--increment_overlap", type=int, default=0)
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    run_attribution_analysis(args)
