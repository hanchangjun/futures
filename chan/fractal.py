from typing import List, Optional
from .common import ChanBar, Fractal, FXType

def find_fractals(bars: List[ChanBar]) -> List[Fractal]:
    """
    识别顶底分型
    顶分型：中间K线 High 最高，且 Low 最高 (严格定义需左<中>右)
    底分型：中间K线 Low 最低，且 High 最低
    """
    fractals = []
    if len(bars) < 3:
        return fractals

    for i in range(1, len(bars) - 1):
        left = bars[i-1]
        curr = bars[i]
        right = bars[i+1]
        
        # 顶分型
        if curr.high > left.high and curr.high > right.high and \
           curr.low > left.low and curr.low > right.low:
            fractals.append(Fractal(
                type=FXType.TOP,
                index=i,
                price=curr.high,
                high=curr.high,
                low=curr.low,
                date=curr.date
            ))
        
        # 底分型
        elif curr.low < left.low and curr.low < right.low and \
             curr.high < left.high and curr.high < right.high:
            fractals.append(Fractal(
                type=FXType.BOTTOM,
                index=i,
                price=curr.low,
                high=curr.high,
                low=curr.low,
                date=curr.date
            ))
            
    return fractals
