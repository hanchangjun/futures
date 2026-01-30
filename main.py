import argparse
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from datafeed import PriceBar, get_bars, log_debug
from notify import notify as notify_message


@dataclass
class Signal:
    direction: str
    entry: float
    stop: float
    take_profit: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    hands: int
    risk: float
    reason: str
    strength: str = "normal"


def ema(values: List[float], period: int) -> List[float]:
    if not values or period <= 0:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def atr(highs: List[float], lows: List[float], closes: List[float], period: int) -> List[float]:
    if len(highs) < 2 or period <= 0:
        return []
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return []
    result = []
    first = sum(trs[:period]) / period
    result.append(first)
    for v in trs[period:]:
        result.append((result[-1] * (period - 1) + v) / period)
    padding = [result[0]] * (len(highs) - len(result))
    return padding + result


def compute_signal(
    bars: List[PriceBar],
    fast_period: int,
    slow_period: int,
    atr_period: int,
    stop_atr_multiplier: float,
    take_profit_multiplier: float,
    sr_lookback: int,
    equity: float,
    risk_pct: float,
    contract_multiplier: float,
    use_enhanced: bool = False,
    trend_filter_period: int = 5,
    trend_slope_threshold: float = 0.1,
    pullback_dist_atr: float = 1.0,
    filter_pullback_n: int = 5,
    filter_breakout_m: int = 20,
    filter_atr_factor: float = 0.5,
    max_entries: int = 2,
    use_entry_filter: bool = False,
) -> Optional[Signal]:
    if len(bars) < max(slow_period, atr_period, trend_filter_period) + 2:
        return None
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    if not fast or not slow:
        return None
    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return None
    
    if use_enhanced:
        # --- Enhanced Logic (State Simulation) ---
        # 1. Find Trend Start (Scan Backwards)
        # We look for the point where Slope changed sign or became zero.
        # Max lookback: 200 bars
        current_idx = len(bars) - 1
        lookback_limit = min(len(bars), 200)
        
        trend_start_idx = current_idx - lookback_limit + 1
        if trend_start_idx < trend_filter_period:
            trend_start_idx = trend_filter_period
            
        # Simulate forward from `trend_start_idx`
        active_trade = None # {type, entry, stop, tp}
        entry_count = 0
        last_trend_state = "Flat" # Up, Down, Flat
        
        from types import SimpleNamespace
        # Mock args for entry_filter
        filter_args = SimpleNamespace(
            fast=fast_period, slow=slow_period, atr=atr_period,
            filter_pullback_n=filter_pullback_n,
            filter_breakout_m=filter_breakout_m,
            filter_atr_factor=filter_atr_factor
        )
        
        # We need to import check_entry_filter
        from entry_filter import check_entry_filter
        
        final_signal = None
        
        for i in range(trend_start_idx, current_idx + 1):
            # Calculate Indicators for bar i
            c = closes[i]
            h = highs[i]
            l = lows[i]
            f = fast[i]
            s = slow[i]
            a = atr_series[i]
            
            # 1. Trend Filter (Slope)
            prev_s_idx = i - trend_filter_period
            slope_val = (s - slow[prev_s_idx]) / a if a > 0 else 0
            
            is_uptrend = slope_val > trend_slope_threshold
            is_downtrend = slope_val < -trend_slope_threshold
            
            curr_trend_state = "Up" if is_uptrend else ("Down" if is_downtrend else "Flat")
            
            # Reset Entry Count if Trend Changes
            if curr_trend_state != last_trend_state:
                entry_count = 0
                last_trend_state = curr_trend_state
            
            # Manage Active Trade
            if active_trade:
                trade_closed = False
                if active_trade["type"] == "多":
                    if l <= active_trade["stop"]: # Stop Loss
                        active_trade = None
                        trade_closed = True
                    elif h >= active_trade["tp"]: # Take Profit
                        active_trade = None
                        trade_closed = True
                elif active_trade["type"] == "空":
                    if h >= active_trade["stop"]: # Stop Loss
                        active_trade = None
                        trade_closed = True
                    elif l <= active_trade["tp"]: # Take Profit
                        active_trade = None
                        trade_closed = True
            
            # Check for New Entry (if no active trade)
            if not active_trade:
                # Check Entry Count Limit
                if entry_count < max_entries:
                    # Check Signal Logic
                    temp_signal = None
                    if is_uptrend:
                        temp_signal = SimpleNamespace(direction="多", reason="SlopeUp")
                    elif is_downtrend:
                        temp_signal = SimpleNamespace(direction="空", reason="SlopeDown")
                    
                    if temp_signal:
                        # Slice bars up to i (inclusive)
                        current_bars_slice = bars[:i+1]
                        
                        allowed, reason = check_entry_filter(current_bars_slice, temp_signal, filter_args)
                        
                        if allowed:
                            # Valid Entry!
                            entry_dir = temp_signal.direction
                            entry_price = c
                            
                            if entry_dir == "多":
                                stop_price = entry_price - a * stop_atr_multiplier
                                tp_price = entry_price + abs(entry_price - stop_price) * take_profit_multiplier
                            else:
                                stop_price = entry_price + a * stop_atr_multiplier
                                tp_price = entry_price - abs(entry_price - stop_price) * take_profit_multiplier
                            
                            active_trade = {
                                "type": entry_dir,
                                "entry": entry_price,
                                "stop": stop_price,
                                "tp": tp_price,
                                "hands": 0,
                                "risk": 0,
                                "reason": reason
                            }
                            entry_count += 1
                            
                            # If this is the LAST bar (current_idx), this is our SIGNAL!
                            if i == current_idx:
                                # Calculate Hands/Risk
                                stop_dist = abs(entry_price - stop_price)
                                risk_per_contract = stop_dist * contract_multiplier
                                total_risk = equity * risk_pct
                                hands = max(int(math.floor(total_risk / risk_per_contract)), 0) if risk_per_contract > 0 else 0
                                risk = hands * risk_per_contract
                                
                                final_signal = Signal(
                                    direction=entry_dir,
                                    entry=entry_price,
                                    stop=stop_price,
                                    take_profit=tp_price,
                                    support=min(lows[i-sr_lookback:i]) if i>sr_lookback else None,
                                    resistance=max(highs[i-sr_lookback:i]) if i>sr_lookback else None,
                                    hands=hands,
                                    risk=risk,
                                    reason=f"Enhanced:{reason} (#{entry_count})",
                                    strength="strong"
                                )

        if final_signal:
            return final_signal
            
        if active_trade:
             return Signal(direction="观望", entry=closes[-1], stop=0, take_profit=None, support=None, resistance=None, hands=0, risk=0, reason="Holding")

        return Signal(direction="观望", entry=closes[-1], stop=0, take_profit=None, support=None, resistance=None, hands=0, risk=0, reason="No Signal")

    # --- Original Logic (Fallback) ---
    last_close = closes[-1]
    last_fast = fast[-1]
    last_slow = slow[-1]
    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return None
    last_atr = atr_series[-1]
    direction = "观望"
    if last_fast > last_slow and last_close > last_slow:
        direction = "多"
    elif last_fast < last_slow and last_close < last_slow:
        direction = "空"
    entry = last_close
    if direction == "多":
        stop = entry - last_atr * stop_atr_multiplier
    elif direction == "空":
        stop = entry + last_atr * stop_atr_multiplier
    else:
        return Signal(direction="观望", entry=entry, stop=entry, take_profit=None, support=None, resistance=None, hands=0, risk=0.0, reason="无趋势")
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return None
    if direction == "多":
        take_profit = entry + stop_distance * take_profit_multiplier
    else:
        take_profit = entry - stop_distance * take_profit_multiplier
    lookback = min(len(bars), max(sr_lookback, 2))
    recent = bars[-lookback:]
    support = min(b.low for b in recent) if recent else None
    resistance = max(b.high for b in recent) if recent else None
    risk_per_contract = stop_distance * contract_multiplier
    total_risk = equity * risk_pct
    hands = max(int(math.floor(total_risk / risk_per_contract)), 0)
    risk = hands * risk_per_contract
    reason = f"EMA{fast_period}/{slow_period}"
    return Signal(
        direction=direction,
        entry=entry,
        stop=stop,
        take_profit=take_profit,
        support=support,
        resistance=resistance,
        hands=hands,
        risk=risk,
        reason=reason,
    )


def resolve_contract_label(symbol: str) -> str:
    raw = symbol.strip()
    upper = raw.upper()
    lower = raw.lower()
    if lower == "kq.m@shfe.rb":
        return "螺纹钢主力合约"
    if lower == "kq.m@czce.fg":
        return "玻璃主力合约"
    if upper == "RB":
        return "螺纹钢主力合约"
    if upper == "FG":
        return "玻璃主力合约"
    def extract_suffix(code: str, prefix: str) -> Optional[str]:
        if code.startswith(prefix) and len(code) > len(prefix):
            suffix = code[len(prefix) :]
            if suffix.isdigit():
                return suffix
        return None
    for prefix, name in (("RB", "螺纹钢"), ("FG", "玻璃"), ("SHFE.RB", "螺纹钢"), ("CZCE.FG", "玻璃")):
        suffix = extract_suffix(upper, prefix)
        if suffix:
            return f"{name}{suffix}合约"
    return symbol


def format_signal(symbol: str, signal: Signal) -> str:
    risk_value = int(round(signal.risk))
    entry_value = int(round(signal.entry))
    stop_value = int(round(signal.stop))
    take_profit_value = int(round(signal.take_profit)) if signal.take_profit is not None else None
    support_value = int(round(signal.support)) if signal.support is not None else None
    resistance_value = int(round(signal.resistance)) if signal.resistance is not None else None
    extra_lines = ""
    if take_profit_value is not None:
        extra_lines += f"\n止盈：{take_profit_value}"
    if support_value is not None:
        extra_lines += f"\n支撑：{support_value}"
    if resistance_value is not None:
        extra_lines += f"\n压力：{resistance_value}"
    contract_label = resolve_contract_label(symbol)
    return (
        f"【{symbol} 波段信号】\n"
        f"合约：{contract_label}\n"
        f"方向：{signal.direction}\n"
        f"入场：{entry_value}\n"
        f"止损：{stop_value}\n"
        f"手数：{signal.hands}\n"
        f"风险：{risk_value}"
        f"{extra_lines}\n"
        f"依据：{signal.reason}"
    )


def signal_payload(symbol: str, signal: Signal, latest_date: Optional[datetime]) -> dict:
    return {
        "symbol": symbol,
        "direction": signal.direction,
        "entry": int(round(signal.entry)),
        "stop": int(round(signal.stop)),
        "take_profit": int(round(signal.take_profit)) if signal.take_profit is not None else None,
        "support": int(round(signal.support)) if signal.support is not None else None,
        "resistance": int(round(signal.resistance)) if signal.resistance is not None else None,
        "hands": signal.hands,
        "risk": int(round(signal.risk)),
        "reason": signal.reason,
        "date": latest_date.isoformat() if latest_date else None,
        "strength": signal.strength,
    }


def is_new_signal(signal: dict, state_file: Path) -> bool:
    if not state_file.exists():
        state_file.write_text(json.dumps(signal, ensure_ascii=False))
        return True
    try:
        last = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        last = None
    if signal != last:
        state_file.write_text(json.dumps(signal, ensure_ascii=False))
        return True
    return False


def notify(message: str, popup: bool, webhook: Optional[str], level: str = "INFO", **kwargs) -> None:
    print(message)
    if popup:
        try:
            import tkinter
            from tkinter import messagebox

            root = tkinter.Tk()
            root.withdraw()
            messagebox.showinfo("交易信号", message)
            root.destroy()
        except Exception:
            pass
    notify_message(message, level=level, webhook_url=webhook, **kwargs)


def compute_dual_signal(
    primary_bars: List[PriceBar],
    secondary_bars: Optional[List[PriceBar]],
    args: argparse.Namespace,
) -> Optional[Signal]:
    primary_signal = compute_signal(
        bars=primary_bars,
        fast_period=args.fast,
        slow_period=args.slow,
        atr_period=args.atr,
        stop_atr_multiplier=args.stop_mult,
        take_profit_multiplier=args.tp_mult,
        sr_lookback=args.sr_lookback,
        equity=args.equity,
        risk_pct=args.risk_pct,
        contract_multiplier=args.contract_multiplier,
        use_enhanced=args.enhanced,
        trend_filter_period=args.trend_period,
        trend_slope_threshold=args.trend_slope,
        pullback_dist_atr=args.pullback_dist,
        filter_pullback_n=args.filter_pullback_n,
        filter_breakout_m=args.filter_breakout_m,
        filter_atr_factor=args.filter_atr_factor,
        max_entries=args.max_entries,
        use_entry_filter=args.use_entry_filter,
    )
    if primary_signal is None:
        return None
    if secondary_bars is None:
        # Single period mode:
        # Valid signal (hands > 0) is treated as "strong" to ensure notification
        # For enhanced mode, if hands > 0 it means we found an active trade
        primary_signal.strength = "strong" if primary_signal.hands > 0 else "weak"
        return primary_signal
    secondary_signal = compute_signal(
        bars=secondary_bars,
        fast_period=args.fast_2,
        slow_period=args.slow_2,
        atr_period=args.atr_2,
        stop_atr_multiplier=args.stop_mult_2,
        take_profit_multiplier=args.tp_mult_2,
        sr_lookback=args.sr_lookback_2,
        equity=args.equity,
        risk_pct=args.risk_pct,
        contract_multiplier=args.contract_multiplier,
        use_enhanced=args.enhanced,
        trend_filter_period=args.trend_period,
        trend_slope_threshold=args.trend_slope,
        pullback_dist_atr=args.pullback_dist,
        filter_pullback_n=args.filter_pullback_n,
        filter_breakout_m=args.filter_breakout_m,
        filter_atr_factor=args.filter_atr_factor,
        max_entries=args.max_entries,
        use_entry_filter=args.use_entry_filter,
    )
    if secondary_signal is None:
        return None
    if secondary_signal.direction != primary_signal.direction:
        return Signal(
            direction="观望",
            entry=secondary_signal.entry,
            stop=secondary_signal.stop,
            take_profit=secondary_signal.take_profit,
            support=secondary_signal.support,
            resistance=secondary_signal.resistance,
            hands=0,
            risk=0.0,
            reason="方向不一致",
            strength="weak",
        )
    return Signal(
        direction=secondary_signal.direction,
        entry=secondary_signal.entry,
        stop=secondary_signal.stop,
        take_profit=secondary_signal.take_profit,
        support=secondary_signal.support,
        resistance=secondary_signal.resistance,
        hands=secondary_signal.hands,
        risk=secondary_signal.risk,
        reason=f"{primary_signal.reason}+{secondary_signal.reason}",
        strength="strong" if secondary_signal.hands > 0 else "weak",
    )


def run_once(args: argparse.Namespace) -> Optional[str]:
    log_debug(args.debug, f"开始执行 once: source={args.source} symbol={args.symbol}")
    required = max(args.slow, args.atr, args.slow_2, args.atr_2) + 5
    username = args.tq_username or os.getenv("TQ_USERNAME")
    password = args.tq_password or os.getenv("TQ_PASSWORD")
    count = args.tq_count if args.source == "tq" else args.tdx_count
    primary_bars, used_symbol = get_bars(
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
        username=username,
        password=password,
        timeout=args.tq_timeout,
        wait_update_once=not args.once,
        increment=args.increment,
        cache_file=args.cache_file,
        increment_count=args.increment_count,
        increment_overlap=args.increment_overlap,
        required=required,
        debug=args.debug,
    )
    secondary_bars = None
    if args.period_2:
        secondary_kwargs = {
            "csv_dir": args.csv_dir,
            "csv_path": args.csv_path,
            "csv_path_daily": args.csv_path_daily,
            "csv_path_60": args.csv_path_60,
            "tdx_symbol": args.tdx_symbol,
            "tdx_host": args.tdx_host,
            "tdx_port": args.tdx_port,
            "tdx_market": args.tdx_market,
            "tdx_auto_main": args.tdx_auto_main,
            "tq_symbol": args.tq_symbol,
            "username": username,
            "password": password,
            "timeout": args.tq_timeout,
            "wait_update_once": not args.once,
            "increment": args.increment,
            "cache_file": args.cache_file,
            "increment_count": args.increment_count,
            "increment_overlap": args.increment_overlap,
            "required": required,
            "debug": args.debug,
        }
        if args.source == "tq":
            secondary_kwargs["tq_symbol"] = used_symbol
        if args.source == "tdx":
            secondary_kwargs["tdx_symbol"] = used_symbol
        secondary_bars, _ = get_bars(
            source=args.source,
            symbol=args.symbol,
            period=args.period_2,
            count=count,
            **secondary_kwargs,
        )
    if not primary_bars:
        log_debug(args.debug, "主周期无有效K线")
        return None
    log_debug(args.debug, f"主周期K线数量: {len(primary_bars)}")
    signal = compute_dual_signal(primary_bars, secondary_bars, args)
    
    # Apply Entry Filter if enabled
    if args.use_entry_filter and signal and signal.direction != "观望":
        from entry_filter import check_entry_filter
        allowed, reason = check_entry_filter(primary_bars, signal, args)
        if not allowed:
            log_debug(args.debug, f"信号被过滤: {reason}")
            # Modify signal to "观望"
            signal.direction = "观望"
            signal.hands = 0
            signal.risk = 0.0
            signal.reason = reason
            signal.strength = "weak"
            # Return None or the modified signal?
            # If we return None, run_once returns None.
            # If we return signal(观望), run_once logs "无有效信号".
            # Let's keep the signal object but neutralized.
    
    if signal is None or signal.direction == "观望":
        log_debug(args.debug, "无有效信号或处于观望")
        return None
    latest_date = primary_bars[-1].date if primary_bars else None
    payload = signal_payload(used_symbol, signal, latest_date)
    # Ensure compatibility with Monitor/SignalState by adding bar_index
    payload["bar_index"] = len(primary_bars)
    payload["last_notify_bar_index"] = len(primary_bars)
    
    if not is_new_signal(payload, args.state_file):
        log_debug(args.debug, "信号未变化，跳过提醒")
        return None
    message = format_signal(used_symbol, signal)
    notify(message, args.popup, args.webhook, level="SIGNAL", **payload)
    return message


def run_watch(args: argparse.Namespace) -> None:
    while True:
        run_once(args)
        time.sleep(args.interval)


def demo_signal() -> str:
    prices = [3500 + i * 2 for i in range(80)]
    bars = [
        PriceBar(
            date=None,
            open=v - 5,
            high=v + 5,
            low=v - 8,
            close=v,
        )
        for v in prices
    ]
    signal = compute_signal(
        bars=bars,
        fast_period=20,
        slow_period=60,
        atr_period=14,
        stop_atr_multiplier=2.0,
        take_profit_multiplier=2.0,
        sr_lookback=20,
        equity=50000,
        risk_pct=0.02,
        contract_multiplier=10,
    )
    if signal is None:
        return ""
    return format_signal("RB", signal)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, choices=["file", "tdx", "tq"], default="tq")
    parser.add_argument("--csv-dir", type=Path, default=Path("."))
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--csv-path-daily", type=Path, default=None)
    parser.add_argument("--csv-path-60", type=Path, default=None)
    parser.add_argument("--symbol", type=str, default="RB")
    parser.add_argument("--period", type=str, default="1d")
    parser.add_argument("--period-2", type=str, default=None)
    parser.add_argument("--tdx-symbol", type=str, default=None)
    parser.add_argument("--tdx-host", type=str, default="119.147.212.81")
    parser.add_argument("--tdx-port", type=int, default=7727)
    parser.add_argument("--tdx-count", type=int, default=800)
    parser.add_argument("--tdx-market", type=int, default=None)
    parser.add_argument("--tdx-auto-main", action="store_true", default=True)
    parser.add_argument("--tq-symbol", type=str, default=None)
    parser.add_argument("--tq-count", type=int, default=5000)
    parser.add_argument("--tq-username", type=str, default=None)
    parser.add_argument("--tq-password", type=str, default=None)
    parser.add_argument("--tq-timeout", type=int, default=10)
    parser.add_argument("--tq-check", action="store_true")
    parser.add_argument("--cache-file", type=Path, default=Path("bars_cache.json"))
    parser.add_argument("--increment-count", type=int, default=200)
    parser.add_argument("--increment-overlap", type=int, default=20)
    parser.add_argument("--no-increment", action="store_false", dest="increment", default=True)
    parser.add_argument("--equity", type=float, default=50000)
    parser.add_argument("--risk-pct", type=float, default=0.02)
    parser.add_argument("--contract-multiplier", type=float, default=10)
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=60)
    parser.add_argument("--atr", type=int, default=14)
    parser.add_argument("--stop-mult", type=float, default=2.0)
    parser.add_argument("--tp-mult", type=float, default=2.0)
    parser.add_argument("--sr-lookback", type=int, default=20)
    parser.add_argument("--fast-2", type=int, default=10)
    parser.add_argument("--slow-2", type=int, default=30)
    parser.add_argument("--atr-2", type=int, default=14)
    parser.add_argument("--stop-mult-2", type=float, default=2.0)
    parser.add_argument("--tp-mult-2", type=float, default=2.0)
    parser.add_argument("--sr-lookback-2", type=int, default=20)
    parser.add_argument("--state-file", type=Path, default=Path("signal_state.json"))
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--cooldown-bars", type=int, default=5)
    parser.add_argument("--confirm-state-file", type=Path, default=Path("confirm_state.json"))
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--backtest-wait", type=int, default=10)
    parser.add_argument("--init-state", action="store_true")
    parser.add_argument("--init-allow-normal", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--popup", action="store_true")
    parser.add_argument("--webhook", type=str, default=None)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--debug", action="store_true")
    # Enhanced Logic Params
    parser.add_argument("--enhanced", action="store_true", default=False)
    parser.add_argument("--trend-period", type=int, default=5)
    parser.add_argument("--trend-slope", type=float, default=0.1)
    parser.add_argument("--pullback-dist", type=float, default=1.0)
    # Entry Filter Params
    parser.add_argument("--use-entry-filter", action="store_true", default=False)
    parser.add_argument("--filter-pullback-n", type=int, default=5)
    parser.add_argument("--filter-breakout-m", type=int, default=20)
    parser.add_argument("--filter-atr-factor", type=float, default=0.5)
    parser.add_argument("--max-entries", type=int, default=2, help="Limit number of entries per trend leg")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.demo:
        print(demo_signal())
        return
    if args.init_state:
        from runner.init_state import start_init
        ok = start_init(args, compute_dual_signal, signal_payload)
        print("初始化成功" if ok else "初始化未执行")
        return
    if args.backtest:
        from runner.backtest_confirm import ConfirmBacktester
        print(f"🚀 启动 Confirm 回测 | 品种: {args.symbol} | 周期: {args.period}")
        required = max(args.slow, args.atr, args.slow_2, args.atr_2) + 5
        username = args.tq_username or os.getenv("TQ_USERNAME")
        password = args.tq_password or os.getenv("TQ_PASSWORD")
        count = args.tq_count if args.source == "tq" else args.tdx_count
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
            username=username,
            password=password,
            timeout=args.tq_timeout,
            wait_update_once=False,
            increment=args.increment,
            cache_file=args.cache_file,
            increment_count=args.increment_count,
            increment_overlap=args.increment_overlap,
            required=required,
            debug=args.debug,
        )
        if not bars:
            print("❌ 回测失败: 无法获取足够的K线数据")
            return
        
        tester = ConfirmBacktester(compute_dual_signal, args.atr, args.backtest_wait)
        result = tester.run(bars, args)
        
        print("\n📊 回测结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.tq_check:
        username = args.tq_username or os.getenv("TQ_USERNAME")
        password = args.tq_password or os.getenv("TQ_PASSWORD")
        print(f"TQ_USERNAME={'已设置' if username else '未设置'}")
        print(f"TQ_PASSWORD={'已设置' if password else '未设置'}")
        return
    if args.once:
        run_once(args)
        return
    
    # Use new runner for monitoring
    from runner.monitor import start_monitor
    start_monitor(args, compute_dual_signal, signal_payload)


if __name__ == "__main__":
    main()
