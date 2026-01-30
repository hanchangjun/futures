from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PriceBar:
    date: Optional[datetime]
    open: float
    high: float
    low: float
    close: float


@dataclass
class SignalResult:
    direction: str
    entry: float
    stop: float
    take_profit: Optional[float]
    hands: int
    risk: float
    reason: str
