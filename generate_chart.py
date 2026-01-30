
import argparse
import json
import os
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List

from main import build_parser, ema, atr
from datafeed import get_bars
from signal.zone import detect_zone, MarketZone

def calc_adx(highs, lows, closes, period=14):
    if len(highs) < period * 2:
        return [0] * len(highs)
        
    plus_dm = []
    minus_dm = []
    trs = []
    
    for i in range(1, len(highs)):
        h_diff = highs[i] - highs[i-1]
        l_diff = lows[i-1] - lows[i]
        
        if h_diff > l_diff and h_diff > 0:
            plus_dm.append(h_diff)
        else:
            plus_dm.append(0)
            
        if l_diff > h_diff and l_diff > 0:
            minus_dm.append(l_diff)
        else:
            minus_dm.append(0)
            
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
        
    # Smoothed stats
    smooth_pdm = [sum(plus_dm[:period])]
    smooth_mdm = [sum(minus_dm[:period])]
    smooth_tr = [sum(trs[:period])]
    
    for i in range(period, len(plus_dm)):
        smooth_pdm.append(smooth_pdm[-1] * (period - 1) / period + plus_dm[i])
        smooth_mdm.append(smooth_mdm[-1] * (period - 1) / period + minus_dm[i])
        smooth_tr.append(smooth_tr[-1] * (period - 1) / period + trs[i])
        
    dx_list = []
    for i in range(len(smooth_tr)):
        pdi = 100 * smooth_pdm[i] / smooth_tr[i] if smooth_tr[i] != 0 else 0
        mdi = 100 * smooth_mdm[i] / smooth_tr[i] if smooth_tr[i] != 0 else 0
        di_sum = pdi + mdi
        dx = 100 * abs(pdi - mdi) / di_sum if di_sum != 0 else 0
        dx_list.append(dx)
        
    # ADX is smoothed DX
    adx_list = [sum(dx_list[:period]) / period]
    for i in range(period, len(dx_list)):
        adx_list.append((adx_list[-1] * (period - 1) + dx_list[i]) / period)
        
    # Padding
    padding_len = len(highs) - len(adx_list)
    return [0] * padding_len + adx_list

def calc_rsi(closes, period=14):
    if len(closes) < period:
        return [50] * len(closes)
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(0, d) for d in deltas]
    losses = [abs(min(0, d)) for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi_list = []
    
    # First RSI
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    rsi = 100 - (100 / (1 + rs))
    rsi_list.append(rsi)
    
    # Smoothed
    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi = 100 - (100 / (1 + rs))
        rsi_list.append(rsi)
        
    padding = [50] * (len(closes) - len(rsi_list))
    return padding + rsi_list

def generate_chart(args):
    # Force count to 800 if not specified larger
    count = max(args.tq_count, 800)
    
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
        increment=args.increment,
        cache_file=args.cache_file,
        increment_count=args.increment_count,
        increment_overlap=args.increment_overlap,
        required=max(args.slow, args.atr) + 5,
        debug=args.debug,
    )

    if not bars:
        print("Error: No bars found.")
        return

    # Keep only last 800 bars for display if we fetched more
    if len(bars) > 800:
        display_bars = bars[-800:]
        # But we need full history for indicators?
        # ema/atr functions take the whole list.
        # So we compute on full list, then slice for display.
    else:
        display_bars = bars

    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [b.volume for b in bars]
    
    # Feature 2: HTF Filter (Daily Trend)
    print("Fetching Daily bars for HTF filter...")
    bars_daily, _ = get_bars(
        source=args.source,
        symbol=args.symbol,
        period="1d", # Force daily
        count=300, # Enough for EMA60
        csv_dir=args.csv_dir,
        csv_path=args.csv_path_daily, # Use daily CSV if provided
        # Pass other necessary auth args...
        tdx_symbol=args.tdx_symbol,
        tdx_host=args.tdx_host,
        tdx_port=args.tdx_port,
        tdx_market=args.tdx_market,
        tq_symbol=args.tq_symbol,
        username=args.tq_username or os.getenv("TQ_USERNAME"),
        password=args.tq_password or os.getenv("TQ_PASSWORD"),
        timeout=args.tq_timeout,
        wait_update_once=True,
        required=65
    )
    
    daily_trend_map = {} # date_str (YYYY-MM-DD) -> "Bull" or "Bear"
    if bars_daily:
        d_closes = [b.close for b in bars_daily]
        d_fast = ema(d_closes, 20)
        d_slow = ema(d_closes, 60)
        for i, b in enumerate(bars_daily):
            if not b.date: continue
            date_key = b.date.strftime("%Y-%m-%d")
            # Determine trend: Bull if EMA20 > EMA60
            # Note: For strict backtest, we should use *previous day's* trend to avoid lookahead.
            # But in daily trading, we know the trend 'today' as it develops, or use yesterday's close.
            # Let's use current bar's EMA values for simplicity, assuming we check "Daily Trend" as "Today's EMA20 vs EMA60"
            is_bull = d_fast[i] > d_slow[i]
            daily_trend_map[date_key] = "Bull" if is_bull else "Bear"
    else:
        print("Warning: Could not fetch Daily bars. HTF Filter disabled.")

    print("Calculating indicators...")
    fast_line = ema(closes, args.fast)
    slow_line = ema(closes, args.slow)
    atr_line = atr(highs, lows, closes, args.atr)
    adx_line = calc_adx(highs, lows, closes, period=14)
    rsi_line = calc_rsi(closes, period=14)
    
    # Volume MA (20)
    vol_ma = []
    for i in range(len(volumes)):
        if i < 20:
            vol_ma.append(sum(volumes[:i+1]) / (i+1))
        else:
            vol_ma.append(sum(volumes[i-19:i+1]) / 20)
    
    # Align data for the display window
    start_offset = len(bars) - len(display_bars)
    
    dates = [b.date.strftime("%Y-%m-%d %H:%M") if b.date else str(i) for i, b in enumerate(display_bars)]
    kline_data = [[b.open, b.close, b.low, b.high] for b in display_bars]
    
    disp_fast = fast_line[start_offset:]
    disp_slow = slow_line[start_offset:]
    disp_atr = atr_line[start_offset:]
    disp_adx = adx_line[start_offset:] # Add ADX display if needed
    
    # Logic simulation
    annotations = []
    table_rows = []
    
    # Track state for enhanced logic
    active_trade = None # {type, entry, stop, tp, entry_date}
    trades_history = []
    trend_entries = 0
    last_trend_state = None # "Up", "Down", "Flat"

    # Structure lines (M-period High/Low)
    struct_highs = []
    struct_lows = []
    m_period = args.filter_breakout_m if hasattr(args, "filter_breakout_m") else 20
    
    # Feature 1: Circuit Breaker State
    consecutive_losses = 0
    circuit_breaker_active = False
    cb_cooldown_bars = 0
    
    print("Simulating strategy logic...")
    for i in range(len(display_bars)):
        idx_full = start_offset + i
        date = dates[i]
        c = closes[idx_full]
        h = highs[idx_full]
        l = lows[idx_full]
        f = fast_line[idx_full]
        s = slow_line[idx_full]
        a = atr_line[idx_full]
        
        # Calculate Structure (High/Low of last M bars, exclusive of current)
        # Using [idx_full - M : idx_full]
        if idx_full >= m_period:
            sh = max(highs[idx_full - m_period : idx_full])
            sl = min(lows[idx_full - m_period : idx_full])
        else:
            sh = h
            sl = l
        struct_highs.append(sh)
        struct_lows.append(sl)

        # Determine Logic Type
        if args.enhanced:
            # --- Enhanced Logic (Replication of main.py + Entry Filter) ---
            
            # Update Circuit Breaker Cooldown
            if circuit_breaker_active:
                cb_cooldown_bars -= 1
                if cb_cooldown_bars <= 0:
                    circuit_breaker_active = False
                    consecutive_losses = 0 # Reset after cooldown? Or keep counting? Usually reset or require manual.
                    # Let's say reset to allow trying again.
                    entry_reason = "CircuitBreaker Reset" 
            
            # 0. Detect Zone
            # Need history up to current index for zone detection
            # Pass data up to idx_full + 1 to include current bar
            current_closes = closes[:idx_full+1]
            current_fast = fast_line[:idx_full+1]
            current_slow = slow_line[:idx_full+1]
            zone_res, _ = detect_zone(current_closes, current_fast, current_slow, a)
            current_zone = zone_res.value

            # 1. Slope
            if idx_full < args.trend_period:
                slope_val = 0
            else:
                prev_s = slow_line[idx_full - args.trend_period]
                slope_val = (s - prev_s) / a if a > 0 else 0
                
            is_uptrend = slope_val > args.trend_slope
            is_downtrend = slope_val < -args.trend_slope
            
            # Update Trend State & Reset Counter
            curr_trend_state = "Up" if is_uptrend else ("Down" if is_downtrend else "Flat")
            if curr_trend_state != last_trend_state:
                trend_entries = 0
                last_trend_state = curr_trend_state
            
            # 2. Structure
            struct_long = f > s
            struct_short = f < s
            
            # 3. Trigger (Pullback OR Breakout)
            n_period = args.filter_pullback_n if hasattr(args, "filter_pullback_n") else 5
            atr_factor = args.filter_atr_factor if hasattr(args, "filter_atr_factor") else 0.5
            
            # Check Pullback in last N bars (Rule A)
            has_pullback_long = False
            has_pullback_short = False
            start_lookback = max(0, idx_full - n_period + 1)
            
            for k in range(start_lookback, idx_full + 1):
                kf = fast_line[k]
                ka = atr_line[k]
                kl = lows[k]
                kh = highs[k]
                if kl <= kf + atr_factor * ka:
                    has_pullback_long = True
                if kh >= kf - atr_factor * ka:
                    has_pullback_short = True
            
            pullback_long = has_pullback_long
            pullback_short = has_pullback_short
            
            # Breakout Rule (Rule B) - Using computed sh/sl
            # Feature 3: Entry Confirmation (Close > Level)
            # This is naturally handled here since 'c' is the close price.
            # So breakout_long = (c > sh) means "Close is higher than previous M-bar High".
            breakout_long = (c > sh)
            breakout_short = (c < sl)
            
            # Combine Triggers
            trigger_long = False
            trigger_short = False
            
            entry_reason = ""
            
            if struct_long and is_uptrend:
                if pullback_long: 
                    # trigger_long = True # FILTER: Pullback disabled by attribution
                    entry_reason = "Pullback(Blocked)"
                elif breakout_long:
                    trigger_long = True
                    entry_reason = "Breakout"
                
            if struct_short and is_downtrend:
                if pullback_short: 
                    # trigger_short = True # FILTER: Pullback disabled by attribution
                    entry_reason = "Pullback(Blocked)"
                elif breakout_short:
                    trigger_short = True
                    entry_reason = "Breakout"
            
            # --- ATTRIBUTION FILTERING ---
            # Block if Zone is RANGE_NOISE or TREND_EXTEND
            # Only allow Breakout in START or EXHAUST
            
            is_blocked = False
            block_reason = ""
            
            # Feature 2: HTF Filter Check
            if trigger_long or trigger_short:
                # Get Daily Trend
                current_date_str = display_bars[i].date.strftime("%Y-%m-%d") if display_bars[i].date else ""
                daily_trend = daily_trend_map.get(current_date_str, "Unknown")
                
                if trigger_long and daily_trend == "Bear":
                    is_blocked = True
                    block_reason = f"Daily:Bear"
                elif trigger_short and daily_trend == "Bull":
                    is_blocked = True
                    block_reason = f"Daily:Bull"
            
            if trigger_long or trigger_short:
                if current_zone in ["RANGE_NOISE", "TREND_EXTEND", "TREND_EXHAUST"]:
                    is_blocked = True
                    block_reason = f"Zone:{current_zone}"
                
                # Double check Pullback is definitely blocked (already done above but explicit here)
                if "Pullback" in entry_reason and "Blocked" not in entry_reason:
                     is_blocked = True
                     block_reason = "Pullback Bad Expectancy"
                
                # Feature 4: ADX Filter
                curr_adx = adx_line[idx_full]
                if curr_adx < 25:
                     is_blocked = True
                     block_reason = f"ADX<25({curr_adx:.1f})"
                
                # Feature 6: RSI Filter
                curr_rsi = rsi_line[idx_full]
                if trigger_long and curr_rsi > 70:
                     is_blocked = True
                     block_reason = f"RSI>70({curr_rsi:.0f})"
                if trigger_short and curr_rsi < 30:
                     is_blocked = True
                     block_reason = f"RSI<30({curr_rsi:.0f})"

                # Feature 5: Volume Filter (For Breakout only)
                if "Breakout" in entry_reason:
                     curr_vol = volumes[idx_full]
                     curr_vol_ma = vol_ma[idx_full]
                     if curr_vol < curr_vol_ma * 1.0: # At least average volume
                          is_blocked = True
                          block_reason = f"LowVol({curr_vol}<{curr_vol_ma:.0f})"
                
                # Feature 1: Circuit Breaker Check
                if circuit_breaker_active:
                    is_blocked = True
                    block_reason = f"CircuitBreaker(Losses={consecutive_losses})"
                     
                if is_blocked:
                    trigger_long = False
                    trigger_short = False
                    entry_reason = f"{entry_reason} [{block_reason}]"
            
            # Signal Gen
            signal_dir = "观望"
            
            # Check Active Trade (Stop/TP)
            if active_trade:
                closed_info = None

                if active_trade["type"] == "多":
                    if l <= active_trade["stop"]:
                        # Stop Hit
                        closed_info = {"price": active_trade["stop"], "reason": "止损"}
                        annotations.append({
                            "coord": [date, l],
                            "value": "止损",
                            "itemStyle": {"color": "black"},
                            "symbol": "pin"
                        })
                    elif h >= active_trade["tp"]:
                        # TP Hit
                        closed_info = {"price": active_trade["tp"], "reason": "止盈"}
                        annotations.append({
                            "coord": [date, h],
                            "value": "止盈",
                            "itemStyle": {"color": "gold"},
                            "symbol": "pin"
                        })
                elif active_trade["type"] == "空":
                    if h >= active_trade["stop"]:
                        # Stop Hit
                        closed_info = {"price": active_trade["stop"], "reason": "止损"}
                        annotations.append({
                            "coord": [date, h],
                            "value": "止损",
                            "itemStyle": {"color": "black"},
                            "symbol": "pin"
                        })
                    elif l <= active_trade["tp"]:
                        # TP Hit
                        closed_info = {"price": active_trade["tp"], "reason": "止盈"}
                        annotations.append({
                            "coord": [date, l],
                            "value": "止盈",
                            "itemStyle": {"color": "gold"},
                            "symbol": "pin"
                        })
                
                if closed_info:
                    entry_price = active_trade["entry"]
                    exit_price = closed_info["price"]
                    if active_trade["type"] == "多":
                        pnl = exit_price - entry_price
                    else:
                        pnl = entry_price - exit_price
                    
                    trades_history.append({
                        "entry_date": active_trade["entry_date"],
                        "type": active_trade["type"],
                        "entry_price": entry_price,
                        "exit_date": date,
                        "exit_price": exit_price,
                        "reason": closed_info["reason"],
                        "pnl": pnl,
                        "zone": active_trade.get("zone", "N/A")
                    })
                    
                    # Update Consecutive Losses / Circuit Breaker
                    if pnl < 0:
                        consecutive_losses += 1
                        if consecutive_losses >= 3: # Circuit Breaker Threshold
                            circuit_breaker_active = True
                            cb_cooldown_bars = 48 # e.g. 24 hours (48 * 30m)
                    else:
                        consecutive_losses = 0
                        circuit_breaker_active = False # Reset on win? Or require manual? Let's say win resets.

                    active_trade = None
            
            # Check Entry (Only if no active trade AND entry count limit not reached)
            if not active_trade:
                allowed = True
                max_entries = args.max_entries if hasattr(args, "max_entries") else 2
                if trend_entries >= max_entries: # Limit to max entries per trend leg
                    allowed = False
                
                if allowed:
                    if trigger_long:
                        signal_dir = "多"
                    elif trigger_short:
                        signal_dir = "空"
                        
                    if signal_dir == "多":
                        stop = c - a * args.stop_mult
                        tp = c + abs(c - stop) * args.tp_mult
                        active_trade = {
                            "type": "多", 
                            "entry": c, 
                            "stop": stop, 
                            "tp": tp, 
                            "entry_date": date,
                            "zone": current_zone # Track Zone
                        }
                        trend_entries += 1
                        annotations.append({
                            "coord": [date, l * 0.995],
                            "value": f"开多\n{entry_reason}",
                            "itemStyle": {"color": "#ff0000"},
                            "symbol": "arrow",
                            "symbolRotate": 0
                        })
                    elif signal_dir == "空":
                        stop = c + a * args.stop_mult
                        tp = c - abs(c - stop) * args.tp_mult
                        active_trade = {
                            "type": "空", 
                            "entry": c, 
                            "stop": stop, 
                            "tp": tp, 
                            "entry_date": date,
                            "zone": current_zone # Track Zone
                        }
                        trend_entries += 1
                        annotations.append({
                            "coord": [date, h * 1.005],
                            "value": f"开空\n{entry_reason}",
                            "itemStyle": {"color": "#00ff00"},
                            "symbol": "arrow",
                            "symbolRotate": 180
                        })
            else:
                # If holding, we can display "Hold"
                signal_dir = active_trade["type"] + "(持)"

            direction = signal_dir
            stop = active_trade["stop"] if active_trade else 0
            tp = active_trade["tp"] if active_trade else 0
            
            # Logic string
            logic_parts = []
            if is_uptrend: logic_parts.append(f"Slope>0")
            elif is_downtrend: logic_parts.append(f"Slope<0")
            
            logic_parts.append(f"[{current_zone}]") # Add Zone info
            
            if trigger_long: logic_parts.append(f"Trig:L({entry_reason})")
            if trigger_short: logic_parts.append(f"Trig:S({entry_reason})")
            
            if trend_entries >= max_entries: logic_parts.append("MaxEntries")
            
            logic_str = " ".join(logic_parts)

        else:
            # --- Original Logic ---
            direction = "观望"
            is_buy = (f > s and c > s)
            is_sell = (f < s and c < s)
            
            if is_buy:
                direction = "多"
            elif is_sell:
                direction = "空"
                
            # Detect entry (change from non-buy to buy, or non-sell to sell)
            # Check previous bar
            prev_idx = idx_full - 1
            if prev_idx >= 0:
                pf = fast_line[prev_idx]
                ps = slow_line[prev_idx]
                pc = closes[prev_idx]
                prev_buy = (pf > ps and pc > ps)
                prev_sell = (pf < ps and pc < ps)
            else:
                prev_buy = False
                prev_sell = False
                
            if is_buy and not prev_buy:
                annotations.append({
                    "coord": [date, display_bars[i].low * 0.995],
                    "value": "开多",
                    "itemStyle": {"color": "#ff0000"},
                    "symbol": "arrow",
                    "symbolRotate": 0
                })
            elif is_sell and not prev_sell:
                annotations.append({
                    "coord": [date, display_bars[i].high * 1.005],
                    "value": "开空",
                    "itemStyle": {"color": "#00ff00"},
                    "symbol": "arrow",
                    "symbolRotate": 180
                })
                
            # Stop/TP
            if direction == "多":
                stop = c - a * args.stop_mult
                tp = c + (c - stop) * args.tp_mult
            elif direction == "空":
                stop = c + a * args.stop_mult
                tp = c - (stop - c) * args.tp_mult
            else:
                stop = 0
                tp = 0
            
            logic_str = "Classic"
            
        row = {
            "date": date,
            "close": c,
            "fast": round(f, 2),
            "slow": round(s, 2),
            "atr": round(a, 2),
            "adx": round(adx_line[idx_full], 1) if args.enhanced else "-",
            "direction": direction,
            "stop": round(stop, 2) if stop else "-",
            "tp": round(tp, 2) if tp else "-",
            "logic": logic_str
        }
        table_rows.append(row)

    disp_struct_h = struct_highs
    disp_struct_l = struct_lows

    # Calculate stats
    total_trades = len(trades_history)
    total_pnl = sum(t["pnl"] for t in trades_history)
    winning_trades = [t for t in trades_history if t["pnl"] > 0]
    losing_trades = [t for t in trades_history if t["pnl"] <= 0]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0

    print("\n" + "="*50)
    print("RECENT TRADES (Last 10)")
    print("="*50)
    for t in trades_history[-10:]:
        # Handle cases where 'zone' might not be in dict (if using old logic path, though here we use enhanced)
        zone_info = t.get("zone", "N/A")
        print(f"[{t['entry_date']}] {t['type']} ({zone_info}) @ {t['entry_price']:.1f} -> {t['exit_price']:.1f} ({t['reason']}) PnL: {t['pnl']:.1f}")
    
    print("-" * 50)
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total PnL: {total_pnl:.1f}")
    print("="*50 + "\n")

    stats_html = f"""
    <h3>策略表现统计</h3>
    <table>
        <tr>
            <th>总交易数</th>
            <th>总盈亏</th>
            <th>平均盈亏</th>
            <th>胜率</th>
            <th>盈利单</th>
            <th>亏损单</th>
        </tr>
        <tr>
            <td>{total_trades}</td>
            <td style="color: {'red' if total_pnl > 0 else 'green'}">{total_pnl:.2f}</td>
            <td>{avg_pnl:.2f}</td>
            <td>{win_rate:.1f}%</td>
            <td>{len(winning_trades)}</td>
            <td>{len(losing_trades)}</td>
        </tr>
    </table>
    """

    trades_html = """
    <h3>交易操作列表</h3>
    <div class="table-container" style="max-height: 300px;">
        <table>
            <thead>
                <tr>
                    <th>开仓时间</th>
                    <th>方向</th>
                    <th>开仓价</th>
                    <th>平仓时间</th>
                    <th>平仓价</th>
                    <th>平仓类型</th>
                    <th>盈亏</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for t in trades_history:
        pnl_color = "red" if t["pnl"] > 0 else "green"
        type_color = "red" if t["type"] == "多" else "green"
        trades_html += f"""
                <tr>
                    <td>{t['entry_date']}</td>
                    <td style="color: {type_color}">{t['type']}</td>
                    <td>{t['entry_price']:.2f}</td>
                    <td>{t['exit_date']}</td>
                    <td>{t['exit_price']:.2f}</td>
                    <td>{t['reason']}</td>
                    <td style="color: {pnl_color}">{t['pnl']:.2f}</td>
                </tr>
        """
    trades_html += """
            </tbody>
        </table>
    </div>
    <hr>
    """

    # Generate HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{args.symbol} 策略逻辑示意图</title>
    <script src="echarts.min.js"></script>
    <style>
        body {{ font-family: sans-serif; margin: 0; padding: 20px; }}
        #chart {{ width: 100%; height: 600px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 12px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
        th {{ background-color: #f2f2f2; position: sticky; top: 0; }}
        .container {{ display: flex; flex-direction: column; }}
        .table-container {{ max-height: 500px; overflow-y: auto; }}
        .buy {{ color: red; font-weight: bold; }}
        .sell {{ color: green; font-weight: bold; }}
    </style>
</head>
<body>
    <h2>{args.symbol} ({args.period}) - 最近 {len(display_bars)} K线买卖逻辑示意</h2>
    <div id="chart"></div>
    {stats_html}
    {trades_html}
    <h3>逐K线解释 (倒序)</h3>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>时间</th>
                    <th>收盘价</th>
                    <th>EMA{args.fast}</th>
                    <th>EMA{args.slow}</th>
                    <th>ATR{args.atr}</th>
                    <th>信号方向</th>
                    <th>理论止损</th>
                    <th>理论止盈</th>
                    <th>逻辑判断</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Reverse order for table
    for row in reversed(table_rows):
        direction_class = ""
        if row["direction"] == "多":
            direction_class = "buy"
        elif row["direction"] == "空":
            direction_class = "sell"
            
        html += f"""
                <tr>
                    <td>{row['date']}</td>
                    <td>{row['close']}</td>
                    <td>{row['fast']}</td>
                    <td>{row['slow']}</td>
                    <td>{row['atr']}</td>
                    <td class="{direction_class}">{row['direction']}</td>
                    <td>{row['stop']}</td>
                    <td>{row['tp']}</td>
                    <td>{row['logic']}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>

    <script type="text/javascript">
        var chartDom = document.getElementById('chart');
        var myChart = echarts.init(chartDom);
        var option;

        var dates = """ + json.dumps(dates) + """;
        var data = """ + json.dumps(kline_data) + """;
        var fast = """ + json.dumps(disp_fast) + """;
        var slow = """ + json.dumps(disp_slow) + """;
        var struct_h = """ + json.dumps(disp_struct_h) + """;
        var struct_l = """ + json.dumps(disp_struct_l) + """;
        var annotations = """ + json.dumps(annotations) + """;

        option = {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' }
            },
            legend: {
                data: ['K线', 'EMA""" + str(args.fast) + """', 'EMA""" + str(args.slow) + """', 'StructH', 'StructL']
            },
            grid: {
                left: '3%',
                right: '3%',
                bottom: '10%'
            },
            xAxis: {
                type: 'category',
                data: dates,
                boundaryGap: false
            },
            yAxis: {
                scale: true,
                splitArea: {
                    show: true
                }
            },
            dataZoom: [
                {
                    type: 'inside',
                    start: 80,
                    end: 100
                },
                {
                    show: true,
                    type: 'slider',
                    top: '90%',
                    start: 80,
                    end: 100
                }
            ],
            series: [
                {
                    name: 'K线',
                    type: 'candlestick',
                    data: data,
                    itemStyle: {
                        color: '#ef232a',
                        color0: '#14b143',
                        borderColor: '#ef232a',
                        borderColor0: '#14b143'
                    },
                    markPoint: {
                        data: annotations,
                        label: {
                            formatter: function(param) {
                                return param.value;
                            }
                        }
                    }
                },
                {
                    name: 'EMA""" + str(args.fast) + """',
                    type: 'line',
                    data: fast,
                    smooth: true,
                    lineStyle: { opacity: 0.5, width: 1 }
                },
                {
                    name: 'EMA""" + str(args.slow) + """',
                    type: 'line',
                    data: slow,
                    smooth: true,
                    lineStyle: { opacity: 0.8, width: 2 }
                },
                {
                    name: 'StructH',
                    type: 'line',
                    data: struct_h,
                    step: 'end',
                    lineStyle: { opacity: 0.3, width: 1, type: 'dashed', color: '#666' },
                    symbol: 'none'
                },
                {
                    name: 'StructL',
                    type: 'line',
                    data: struct_l,
                    step: 'end',
                    lineStyle: { opacity: 0.3, width: 1, type: 'dashed', color: '#666' },
                    symbol: 'none'
                }
            ]
        };

        option && myChart.setOption(option);
    </script>
</body>
</html>
"""
    
    output_path = Path("strategy_chart.html").absolute()
    output_path.write_text(html, encoding="utf-8")
    print(f"Chart generated: {output_path}")
    
    # Try to open in browser
    # webbrowser.open(output_path.as_uri())

if __name__ == "__main__":
    parser = build_parser()
    # Override defaults if needed or just parse
    args = parser.parse_args()
    generate_chart(args)
