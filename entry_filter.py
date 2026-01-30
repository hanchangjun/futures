
from typing import List, Optional, Tuple, Any
from dataclasses import dataclass

# Define protocols/types locally to avoid circular imports if possible,
# or just assume duck typing for Signal and PriceBar.

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
    # Pad to match length
    padding = [result[0]] * (len(highs) - len(result))
    return padding + result

def check_entry_filter(
    bars: List[Any], 
    signal: Any, 
    args: Any
) -> Tuple[bool, str]:
    """
    Apply entry filters: Pullback (Rule A) or Structure Breakout (Rule B).
    Returns (True, reason) if allowed, (False, reason) if denied.
    """
    
    # If signal is already "观望" or None, no need to filter
    if not signal or signal.direction == "观望":
        return True, ""

    # Parse params
    # We assume args has these attributes. If not, use defaults.
    pullback_n = getattr(args, "filter_pullback_n", 5)
    breakout_m = getattr(args, "filter_breakout_m", 20)
    atr_factor = getattr(args, "filter_atr_factor", 0.5)
    
    # Need at least max(N, M) + lookback for indicators
    required_len = max(pullback_n, breakout_m) + max(args.slow, args.atr)
    if len(bars) < required_len:
        # Not enough data to filter safely? 
        # Strategy usually needs ~60+ bars. If we are here, we probably have enough.
        pass

    # Recalculate indicators
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    
    fast = ema(closes, args.fast)
    slow = ema(closes, args.slow)
    atr_series = atr(highs, lows, closes, args.atr)
    
    if not fast or not slow or not atr_series:
        return False, "Filter: Indicator Error"

    # Current bar index
    curr_idx = len(bars) - 1
    
    # --- Rule A: EMA Pullback ---
    # Logic: In last N bars, price touched FastEMA +/- ATR*factor
    
    has_pullback = False
    
    # We check the window [curr_idx - N + 1 ... curr_idx]
    # Actually, "Recent N bars" usually includes current? Or previous N?
    # Let's check previous N bars including current.
    
    start_idx = max(0, curr_idx - pullback_n + 1)
    
    if signal.direction == "多":
        # Trend: Fast > Slow (Implicit, checked by compute_signal)
        # Condition: Low <= FastEMA + 0.5*ATR
        for i in range(start_idx, curr_idx + 1):
            threshold = fast[i] + atr_factor * atr_series[i]
            if lows[i] <= threshold:
                has_pullback = True
                break
                
    elif signal.direction == "空":
        # Condition: High >= FastEMA - 0.5*ATR
        for i in range(start_idx, curr_idx + 1):
            threshold = fast[i] - atr_factor * atr_series[i]
            if highs[i] >= threshold:
                has_pullback = True
                break

    # --- Rule B: Structure Breakout ---
    # Logic: Close > Max(Highs of last M) for Long
    
    is_breakout = False
    
    # Breakout lookback window: [curr_idx - M ... curr_idx - 1]
    # Exclude current bar for the "Highs of last M" calculation?
    # Usually "Breakout of N-day high" means Close > Max(High[t-N...t-1])
    
    bo_start_idx = max(0, curr_idx - breakout_m)
    bo_end_idx = curr_idx # range is exclusive at end, so up to curr_idx-1
    
    if bo_end_idx > bo_start_idx:
        if signal.direction == "多":
            # Max high of previous M bars
            recent_high = max(highs[bo_start_idx:bo_end_idx])
            if closes[curr_idx] > recent_high:
                is_breakout = True
        elif signal.direction == "空":
            # Min low of previous M bars
            recent_low = min(lows[bo_start_idx:bo_end_idx])
            if closes[curr_idx] < recent_low:
                is_breakout = True
    
    # Combine Rules
    if has_pullback:
        return True, f"{signal.reason} + 回撤确认"
    
    if is_breakout:
        return True, f"{signal.reason} + 结构突破"
        
    return False, "无回撤/无结构突破"
