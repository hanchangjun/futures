from datetime import datetime
from typing import List, Tuple

from .risk_gate import allow_trade
from .session import is_trade_time
from .types import SignalResult


def can_emit_signal(
    now: datetime,
    signal: SignalResult,
    sessions: List[Tuple[str, str]],
    trade_enabled: bool,
    today_loss: float,
    max_daily_loss: float,
) -> Tuple[bool, str]:
    if not trade_enabled:
        return False, "交易已关闭"
    if today_loss >= max_daily_loss:
        return False, "超过当日最大亏损"
    if not is_trade_time(now, sessions):
        return False, "非交易时间"
    if signal.direction in ["观望", "无信号"]:
        return False, "无有效趋势"
    return True, "OK"
