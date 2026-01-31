from typing import List, Optional
from dataclasses import dataclass
from .common import Bi, Trend

@dataclass
class ZhongShu:
    """中枢 (Pivot)"""
    start_bi_index: int
    end_bi_index: int
    zg: float # 中枢高点 (Min(Highs))
    zd: float # 中枢低点 (Max(Lows))
    direction: Trend # 中枢方向 (进入段方向)
    level: int = 0 # 级别 (0: 本级别, 1: 扩展)
    
    @property
    def gg(self) -> float:
        """中枢最高波动点"""
        return self.zg # 简化，实际应为区间内最高点
        
    @property
    def dd(self) -> float:
        """中枢最低波动点"""
        return self.zd # 简化

def find_zhongshu(bis: List[Bi]) -> List[ZhongShu]:
    """
    识别中枢
    定义：至少三笔重叠。
    ZG = min(High1, High2, High3)
    ZD = max(Low1, Low2, Low3)
    有效中枢: ZG > ZD
    """
    centers = []
    if len(bis) < 3:
        return centers
    
    i = 0
    while i <= len(bis) - 3:
        b1 = bis[i]
        b2 = bis[i+1]
        b3 = bis[i+2]
        
        # 必须是连续的三笔 (方向已在Bi生成时保证交替)
        
        # 计算重叠区间
        # 每一笔都有 High 和 Low
        highs = [b1.high, b2.high, b3.high]
        lows = [b1.low, b2.low, b3.low]
        
        zg = min(highs)
        zd = max(lows)
        
        if zg > zd:
            # 找到一个中枢
            zs = ZhongShu(
                start_bi_index=i,
                end_bi_index=i+2,
                zg=zg,
                zd=zd,
                direction=b1.direction # 进入段方向
            )
            
            # 尝试延伸 (Extension)
            # 检查后续笔是否还在中枢范围内 (脱离必须是一笔完全离开，且回拉不触及)
            # 简单延伸：只要后续笔跟 [zd, zg] 有重叠，就认为是延伸
            j = i + 3
            while j < len(bis):
                bn = bis[j]
                # 判断重叠
                # 笔的区间 [bn.low, bn.high] 与 [zd, zg] 有交集
                is_overlap = not (bn.high < zd or bn.low > zg)
                
                if is_overlap:
                    zs.end_bi_index = j
                    # 可以在这里更新 GG, DD
                    j += 1
                else:
                    # 离开中枢
                    # 检查是否是第三类买卖点 (离开后不回回拉) -> 这是策略层的
                    break
            
            centers.append(zs)
            i = j # 从离开的那一笔开始找下一个
        else:
            i += 1
            
    return centers
