from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

# Avoid circular imports for type hinting
# from datafeed.base import PriceBar

@dataclass
class Event:
    """Base Event class"""
    type: str

@dataclass
class MarketEvent(Event):
    """Event triggered when new market data is received"""
    bar: Any # PriceBar
    symbol: str
    
    def __init__(self, bar, symbol):
        self.type = 'MARKET'
        self.bar = bar
        self.symbol = symbol

@dataclass
class SignalEvent(Event):
    """Event triggered by Strategy"""
    symbol: str
    dt: datetime
    signal_type: str # 'LONG', 'SHORT', 'EXIT_LONG', 'EXIT_SHORT'
    price: float
    strength: str = "normal"
    sl: Optional[float] = None # Stop Loss Price
    tp: Optional[float] = None # Take Profit Price
    
    def __init__(self, symbol, dt, signal_type, price, strength="normal", sl=None, tp=None):
        self.type = 'SIGNAL'
        self.symbol = symbol
        self.dt = dt
        self.signal_type = signal_type
        self.price = price
        self.strength = strength
        self.sl = sl
        self.tp = tp

@dataclass
class OrderEvent(Event):
    """Event triggered by Portfolio to execute a trade"""
    symbol: str
    order_type: str # 'MKT', 'LMT'
    quantity: int
    direction: str # 'BUY', 'SELL'
    price: Optional[float] = None
    
    def __init__(self, symbol, order_type, quantity, direction, price=None):
        self.type = 'ORDER'
        self.symbol = symbol
        self.order_type = order_type
        self.quantity = quantity
        self.direction = direction
        self.price = price

@dataclass
class FillEvent(Event):
    """Event triggered by Broker when order is filled"""
    symbol: str
    dt: datetime
    quantity: int
    direction: str
    fill_price: float
    commission: float
    
    def __init__(self, symbol, dt, quantity, direction, fill_price, commission=0.0):
        self.type = 'FILL'
        self.symbol = symbol
        self.dt = dt
        self.quantity = quantity
        self.direction = direction
        self.fill_price = fill_price
        self.commission = commission
