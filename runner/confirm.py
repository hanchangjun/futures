from typing import Tuple, Dict, Any, List
from signals.indicators import atr

def check_confirm(bars: List[Any], pending: Dict[str, Any], atr_period: int) -> Tuple[bool, float, float, str]:
    """
    Check whether the pending signal is confirmed.
    Rule: price breaks in the signal direction by at least 0.5 * ATR from entry.

    Returns: (confirmed, last_close, last_atr, reason)
    """
    if not bars or len(bars) < atr_period + 2:
        return False, 0.0, 0.0, "K线不足"
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    atr_series = atr(highs, lows, closes, atr_period)
    if not atr_series:
        return False, closes[-1], 0.0, "ATR无效"
    last_atr = atr_series[-1]
    threshold = 0.5 * last_atr
    entry = float(pending.get("entry", 0.0))
    direction = pending.get("direction")
    last_close = closes[-1]

    if direction == "多":
        if last_close >= entry + threshold:
            return True, last_close, last_atr, "价格向上突破0.5ATR"
        return False, last_close, last_atr, "未达到上破阈值"
    if direction == "空":
        if last_close <= entry - threshold:
            return True, last_close, last_atr, "价格向下突破0.5ATR"
        return False, last_close, last_atr, "未达到下破阈值"
    return False, last_close, last_atr, "非方向性信号"
