from typing import List, Optional
from dataclasses import dataclass
from .common import Bi, Trend

@dataclass
class Duan:
    """线段 (Line Segment)"""
    start_bi: Bi
    end_bi: Bi
    bi_list: List[Bi]
    direction: Trend
    
    @property
    def high(self) -> float:
        return max(b.high for b in self.bi_list)
    
    @property
    def low(self) -> float:
        return min(b.low for b in self.bi_list)

def find_duan(bis: List[Bi]) -> List[Duan]:
    """
    线段生成 (简化版)
    标准定义：特征序列的顶底分型。
    简化定义：
    1. 至少由3笔组成。
    2. 前三笔必须有重叠。
    3. 线段破坏：
       - 向上线段被向下线段破坏（特征序列出现底分型）
       
    这里实现一个极其简化的版本：
    每3笔如果不创新高/新低，就可能形成复杂线段。
    
    Version 0.1: 机械化划分，不做严格特征序列处理。
    仅作为示例：
    将连续的 3 笔作为一个 Duan，如果有更长的趋势，则延伸。
    """
    # TODO: 实现严格的特征序列处理
    # 目前仅做占位，为了跑通流程，我们假设每 3 笔构成一个 Duan (这是错误的，但为了架构先行)
    
    duans = []
    if len(bis) < 3:
        return duans
        
    # 临时逻辑：把所有笔连起来，暂时每 3 笔打断一下（仅用于测试UI）
    # 实际逻辑极复杂，需要维护 CurrentDuan 状态
    
    return duans
