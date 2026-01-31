import pandas as pd
import numpy as np
from typing import List
from datafeed.base import PriceBar

def calculate_macd(bars: List[PriceBar], fast=12, slow=26, signal=9):
    """
    计算 MACD
    返回 DataFrame，包含 diff, dea, macd
    """
    if not bars:
        return pd.DataFrame()
        
    closes = np.array([b.close for b in bars])
    
    # 使用 pandas 计算 EMA 比较方便
    series = pd.Series(closes)
    
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    
    diff = ema_fast - ema_slow
    dea = diff.ewm(span=signal, adjust=False).mean()
    macd = (diff - dea) * 2
    
    return pd.DataFrame({
        "diff": diff,
        "dea": dea,
        "macd": macd
    })

def compute_bi_macd(bi_list, bars, macd_df):
    """
    计算每一笔的 MACD 动力学指标
    1. 面积: 对应区间内 MACD 红绿柱面积之和（绝对值）
    2. 高度: 对应区间内 MACD 柱子的最大绝对值 (或 Diff 的高低点)
    """
    # 建立 Bar Index 到 MACD 的映射
    # 假设 bars 和 macd_df 是一一对应的，且顺序一致
    
    for bi in bi_list:
        # 获取笔覆盖的 K 线区间
        # Start: bi.start_fx.index (底分型底或顶分型顶)
        # End: bi.end_fx.index
        
        # 注意: 笔的区间通常指两个分型极值点之间的区间
        # 严格来说，是从 start_fx.index 到 end_fx.index
        
        start_idx = bi.start_fx.index
        end_idx = bi.end_fx.index
        
        # 确保索引在范围内
        if start_idx < 0 or end_idx >= len(macd_df):
            continue
            
        segment_macd = macd_df.iloc[start_idx : end_idx + 1]
        
        # 计算面积 (MACD 柱子之和)
        # 向上笔通常看红柱面积，向下笔看绿柱面积
        # 但为了通用，直接计算区间内 MACD 的绝对值之和，或者保留符号之和
        
        # 改进：如果是向上笔，主要关注红柱子(macd > 0)
        # 如果是向下笔，主要关注绿柱子(macd < 0)
        
        macd_values = segment_macd['macd'].values
        diff_values = segment_macd['diff'].values
        
        bi.macd_area = np.sum(np.abs(macd_values)) # 绝对面积，代表总力度
        
        # 也可以计算净面积
        bi.macd_net_area = np.sum(macd_values)
        
        # 记录 Diff 的极值，用于判断背驰 (Diff 不创新高/低)
        if bi.direction.name == 'UP':
            bi.diff_peak = np.max(diff_values)
        else:
            bi.diff_peak = np.min(diff_values)
            
    return bi_list
