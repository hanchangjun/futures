import math
from typing import List, Optional

from .indicators import atr, ema
from .types import PriceBar, SignalResult


def compute_signal(
    bars: List[PriceBar],
    fast_period: int,
    slow_period: int,
    atr_period: int,
    stop_atr_multiplier: float,
    take_profit_multiplier: float,
    equity: float,
    risk_pct: float,
    contract_multiplier: float,
) -> Optional[SignalResult]:
    def build_result(
        direction: str,
        entry: float,
        stop: float,
        take_profit: Optional[float],
        hands: int,
        risk: float,
        reason: str,
    ) -> SignalResult:
        return SignalResult(
            direction=direction,
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            hands=hands,
            risk=risk,
            reason=reason,
        )

    if len(bars) < max(slow_period, atr_period) + 2:
        return None
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    if not fast or not slow:
        return None
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
        return build_result(
            direction="观望",
            entry=entry,
            stop=entry,
            take_profit=None,
            hands=0,
            risk=0.0,
            reason="无趋势",
        )
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return None
    if direction == "多":
        take_profit = entry + stop_distance * take_profit_multiplier
    else:
        take_profit = entry - stop_distance * take_profit_multiplier
    risk_per_contract = stop_distance * contract_multiplier
    if risk_per_contract <= 0:
        return None
    total_risk = equity * risk_pct
    hands = int(math.floor(total_risk / risk_per_contract))
    if hands <= 0:
        return build_result(
            direction="无信号",
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            hands=0,
            risk=0.0,
            reason="手数不足",
        )
    risk = hands * risk_per_contract
    reason = f"EMA{fast_period}/{slow_period}"
    return build_result(
        direction=direction,
        entry=entry,
        stop=stop,
        take_profit=take_profit,
        hands=hands,
        risk=risk,
        reason=reason,
    )
