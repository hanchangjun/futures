from datetime import datetime
from typing import Optional, Tuple

from .types import SignalResult


def format_advice(
    symbol: str,
    period: str,
    signal: Optional[SignalResult],
    equity: float,
    decision: Optional[Tuple[bool, str]] = None,
) -> str:
    if decision is not None and not decision[0]:
        return f"信号被拦截\n原因: {decision[1]}"
    if signal is None:
        return "无有效信号"
    if signal.direction in ("观望", "无信号"):
        return f"方向: 观望\n原因: {signal.reason}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    risk_ratio = 0.0
    if equity > 0:
        risk_ratio = signal.risk / equity
    lines = [
        f"时间: {now_str}",
        f"品种: {symbol}",
        f"周期: {period}",
        f"方向: {signal.direction}",
        f"入场价: {signal.entry}",
        f"止损价: {signal.stop}",
        f"止盈价: {signal.take_profit}",
        f"建议手数: {signal.hands}",
        f"预计风险(元): {signal.risk}",
        f"账户风险占比: {risk_ratio}",
        f"信号依据: {signal.reason}",
    ]
    return "\n".join(lines)
