from typing import List
from datafeed.base import PriceBar
from .common import ChanBar, Trend

def merge_klines(bars: List[PriceBar]) -> List[ChanBar]:
    """
    K线包含处理
    规则：
    1. 趋势方向：假设第一根和第二根确定初始方向。
       若 High2 > High1 且 Low2 > Low1 => UP
       若 High2 < High1 且 Low2 < Low1 => DOWN
       否则包含。
    2. 包含处理：
       UP方向: High = Max(H1, H2), Low = Max(L1, L2) -> "高高"
       DOWN方向: High = Min(H1, H2), Low = Min(L1, L2) -> "低低"
    """
    if len(bars) < 2:
        return []

    chan_bars = []
    
    # 初始化第一根
    first = bars[0]
    curr_chan = ChanBar(
        index=0,
        date=first.date,
        high=first.high,
        low=first.low,
        open=first.open,
        close=first.close,
        elements=[0]
    )
    chan_bars.append(curr_chan)
    
    # 初始趋势假设为 UP (也可以根据前两根判断，但在流式处理中通常需要状态)
    # 这里简单起见，动态判断
    current_trend = Trend.UP 

    for i in range(1, len(bars)):
        raw = bars[i]
        prev = chan_bars[-1]
        
        # 判断包含关系
        # 1. raw 包含 prev (raw 包 prev) -> 极其少见，通常是后一根包前一根
        # 2. prev 包含 raw (prev 包 raw)
        
        is_inclusive = (raw.high <= prev.high and raw.low >= prev.low) or \
                       (prev.high <= raw.high and prev.low >= raw.low)
        
        if is_inclusive:
            # 处理包含
            if current_trend == Trend.UP:
                # 上升趋势中包含：取高点大的，低点大的 (高高)
                new_high = max(prev.high, raw.high)
                new_low = max(prev.low, raw.low)
            else:
                # 下降趋势中包含：取高点小的，低点小的 (低低)
                new_high = min(prev.high, raw.high)
                new_low = min(prev.low, raw.low)
            
            # 更新最后一根 ChanBar
            prev.high = new_high
            prev.low = new_low
            prev.date = raw.date # 时间取最新的
            prev.close = raw.close # 收盘价取最新的
            prev.index = i       # 索引更新
            prev.elements.append(i)
            
        else:
            # 不包含，产生新 K 线
            # 确定新的趋势方向
            if raw.high > prev.high and raw.low > prev.low:
                current_trend = Trend.UP
            elif raw.high < prev.high and raw.low < prev.low:
                current_trend = Trend.DOWN
            # else: 仅仅是接触或者其他非包含情况，保持 trend 不变?
            # 实际上如果不包含，必然是完全向上或向下（除了包含就是非包含）
            
            new_bar = ChanBar(
                index=i,
                date=raw.date,
                high=raw.high,
                low=raw.low,
                open=raw.open,
                close=raw.close,
                elements=[i]
            )
            chan_bars.append(new_bar)
            
    return chan_bars
