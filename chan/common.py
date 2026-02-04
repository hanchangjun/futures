from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

class Trend(Enum):
    UP = 1      # 上升
    DOWN = -1   # 下降
    NONE = 0    # 无趋势/初始状态

class FXType(Enum):
    TOP = 1     # 顶分型
    BOTTOM = -1 # 底分型

@dataclass
class ChanBar:
    """经过包含处理后的K线"""
    index: int          # 原始K线结束索引
    date: datetime
    high: float
    low: float
    open: float         # 开盘价 (第一根包含K线的开盘价)
    close: float        # 收盘价 (最后一根包含K线的收盘价)
    elements: List[int] # 包含的原始K线索引列表

@dataclass
class Fractal:
    """分型 (Fen Xing)"""
    type: FXType
    index: int          # 对应 ChanBar 的索引
    price: float        # 顶/底 价格
    high: float
    low: float
    date: datetime

@dataclass
class Bi:
    """笔 (Stroke)"""
    start_fx: Fractal
    end_fx: Fractal
    type: FXType # 这里的 type 实际上没怎么用，主要用 direction
    
    # 动力学属性
    macd_area: float = 0.0      # MACD 面积
    macd_net_area: float = 0.0  # MACD 净面积
    diff_peak: float = 0.0      # Diff 极值

    @property
    def direction(self) -> Trend:
        if self.start_fx.type == FXType.BOTTOM and self.end_fx.type == FXType.TOP:
            return Trend.UP
        elif self.start_fx.type == FXType.TOP and self.end_fx.type == FXType.BOTTOM:
            return Trend.DOWN
        return Trend.NONE
        
    @property
    def high(self) -> float:
        return max(self.start_fx.high, self.end_fx.high)
        
    @property
    def low(self) -> float:
        return min(self.start_fx.low, self.end_fx.low)
