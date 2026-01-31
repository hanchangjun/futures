from typing import List, Optional
from .common import ChanBar, Fractal, FXType, Bi, Trend

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

def find_bi(bars: List[ChanBar], fractals: List[Fractal]) -> List[Bi]:
    """
    识别笔 (Simple Version)
    规则：
    1. 顶底交替
    2. 中间至少包含 1 根独立 K 线 (即 顶分型index 和 底分型index 差值 >= 4? 
       分型本身占3根，共用一边。如果不共用，index差至少是 4:
       Top(i), i+1, i+2, i+3, Bottom(i+4) -> 差4.
       老笔定义：顶底之间不含顶底K线，至少1根。
       i_top=1, i_bot=5. 中间是 2,3,4. 
       实际上只要 index_diff >= 4 即可满足“中间有K线”。
       
       (新笔定义比较复杂，允许共用，这里先用老笔定义简化实现)
    3. 高低点验证：向上一笔，顶必须高于底；向下一笔，底必须低于顶。
    """
    bis = []
    if not fractals:
        return bis
        
    current_start_fx = fractals[0]
    
    for i in range(1, len(fractals)):
        fx = fractals[i]
        
        # 必须是不同类型的分型
        if fx.type == current_start_fx.type:
            # 同类型，看是否更极端
            if fx.type == FXType.TOP:
                if fx.high > current_start_fx.high:
                    current_start_fx = fx # 更新为更高的顶
            else: # BOTTOM
                if fx.low < current_start_fx.low:
                    current_start_fx = fx # 更新为更低的底
            continue
            
        # 不同类型，检查是否成笔
        # 1. 距离检查
        if fx.index - current_start_fx.index < 4:
            continue
            
        # 2. 高低点检查
        if current_start_fx.type == FXType.BOTTOM and fx.type == FXType.TOP:
            # 向上笔
            if fx.high <= current_start_fx.low: # 顶比底还低，不可能
                continue
            # 找到一笔
            bis.append(Bi(start_fx=current_start_fx, end_fx=fx, type=Trend.UP))
            current_start_fx = fx
            
        elif current_start_fx.type == FXType.TOP and fx.type == FXType.BOTTOM:
            # 向下笔
            if fx.low >= current_start_fx.high: # 底比顶还高，不可能
                continue
            # 找到一笔
            bis.append(Bi(start_fx=current_start_fx, end_fx=fx, type=Trend.DOWN))
            current_start_fx = fx
            
    return bis
