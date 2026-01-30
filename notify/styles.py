from typing import Any, Dict, Union

def format_signal(data: Dict[str, Any]) -> str:
    """
    Format signal data into a Markdown message.
    Expected keys: direction, entry, stop, take_profit, hands, risk, reason
    """
    symbol = data.get("symbol", "未知合约")
    direction = data.get("direction", "未知")
    entry = data.get("entry", 0.0)
    stop = data.get("stop", 0.0)
    take_profit = data.get("take_profit", "N/A")
    support = data.get("support", "N/A")
    resistance = data.get("resistance", "N/A")
    hands = data.get("hands", 0)
    risk = data.get("risk", 0.0)
    reason = data.get("reason", "无")
    
    # Define color/emoji based on direction
    icon = "⚪"
    if direction in ("做多", "多"):
        icon = "🟢"
    elif direction in ("做空", "空"):
        icon = "🔴"
        
    return f"""## {icon} 交易信号触发
> **合约**: {symbol}
> **方向**: <font color="warning">{direction}</font>
> **入场价**: {entry}
> **止损价**: {stop}
> **止盈价**: {take_profit}
> **支撑位**: <font color="comment">{support}</font>
> **压力位**: <font color="comment">{resistance}</font>
> **建议手数**: {hands}
> **预计风险**: {risk:.2f} 元
> **依据**: {reason}
"""

def format_error(message: str) -> str:
    """
    Format error message into a Markdown message.
    """
    return f"""## ⛔ 系统异常警报
> **错误详情**: 
> <font color="warning">{message}</font>
> 
> 请立即检查系统状态！
"""
