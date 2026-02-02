import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chan.k_merge import merge_klines
from chan.common import ChanBar

# Lazy import to avoid circular dependency if any (though first_class_signal imports chan_core)
# We can import inside method or at top if circularity is handled.
# first_class_signal imports Signal, Bi, Zhongshu from chan_core.
# So we can't import FirstClassSignalDetector at top level of chan_core easily without circularity.
# We will import inside __init__ or methods.

# --- Data Structures ---

class Bi:
    """笔的数据结构"""
    
    def __init__(self, bi_id, direction, start_price, end_price, 
                 start_time, end_time, high, low, bars, start_index=0, end_index=0):
        self.id = bi_id
        self.direction = direction  # 'up' or 'down'
        self.start_price = start_price
        self.end_price = end_price
        self.start_time = start_time
        self.end_time = end_time
        self.high = high           # 笔内最高价
        self.low = low             # 笔内最低价
        self.bars = bars           # 包含的K线数量
        self.start_index = start_index # 在原始K线列表中的起始索引
        self.end_index = end_index     # 在原始K线列表中的结束索引
        self.macd_data = None      # MACD指标数据
        self.volume_sum = 0        # 笔内成交量总和
        self.所属中枢 = None        # 所属的中枢
        
    def length(self):
        """笔的长度（价格幅度）"""
        return abs(self.end_price - self.start_price)
    
    def duration(self):
        """笔的持续时间"""
        # Ensure datetime objects
        if isinstance(self.end_time, str):
            # Parse if string? Or assume datetime.
            pass
        return (self.end_time - self.start_time).total_seconds() / 3600  # 小时

class Zhongshu:
    """中枢数据结构"""
    
    def __init__(self, zs_id, zg, zd, gg, dd, start_time, end_time, bi_list):
        self.id = zs_id
        self.ZG = zg  # 重叠区间最高底
        self.ZD = zd  # 重叠区间最低顶
        self.GG = gg  # 波动高点
        self.DD = dd  # 波动低点
        self.start_time = start_time
        self.end_time = end_time
        self.bi_list = bi_list    # 构成中枢的笔
        self.level = None         # 中枢级别
        self.completed = False    # 是否完成
        
    def height(self):
        """中枢高度"""
        return self.ZG - self.ZD
    
    def center(self):
        """中枢中心"""
        return (self.ZG + self.ZD) / 2

    @property
    def zg(self): return self.ZG
    @property
    def zd(self): return self.ZD
    @property
    def gg(self): return self.GG
    @property
    def dd(self): return self.DD


class Signal:
    """买卖点信号"""
    
    def __init__(self, signal_type, price, time, score, 
                 zhongshu=None, bi=None, extra_info=None):
        self.type = signal_type    # '1B', '1S', '2B', '2S', '3B', '3S'
        self.price = price         # 信号价格
        self.time = time           # 信号时间
        self.score = score         # 信号强度分数(0-100)
        self.zhongshu = zhongshu   # 相关中枢
        self.bi = bi               # 相关笔
        self.extra_info = extra_info or {}
        self.confirmed = False     # 是否已确认
        self.executed = False      # 是否已执行

# --- Detector ---

class Segment:
    """线段 (Segment)"""
    def __init__(self, start_bi, end_bi, bi_list, direction):
        self.start_bi = start_bi
        self.end_bi = end_bi
        self.bi_list = bi_list
        self.direction = direction # 'up' or 'down'
        
        self.start_time = start_bi.start_time
        self.end_time = end_bi.end_time
        
        if self.direction == 'up':
            self.low = start_bi.low
            self.high = end_bi.high
            self.start_price = self.low
            self.end_price = self.high
        else:
            self.high = start_bi.high
            self.low = end_bi.low
            self.start_price = self.high
            self.end_price = self.low

class StandardZhongshu:
    """标准中枢 (Standard Center formed by Segments)"""
    def __init__(self, zs_id, zg, zd, gg, dd, start_time, end_time, segments):
        self.zs_id = zs_id
        self.zg = zg # High of Lows (Upper bound of overlap)
        self.zd = zd # Low of Highs (Lower bound of overlap)
        self.gg = gg # High of Highs
        self.dd = dd # Low of Lows
        self.start_time = start_time
        self.end_time = end_time
        self.segments = segments
        self.level = 'segment'
        
    @property
    def ZG(self): return self.zg
    @property
    def ZD(self): return self.zd

class ChanTheorySignalDetector:
    """缠论三类买卖点检测器"""
    
    def __init__(self, config=None):
        # 默认配置参数
        self.config = {
            '趋势中枢数': 2,              # 趋势至少需要的中枢数量
            'MACD背驰阈值': 0.3,         # 面积衰减30%以上
            '紧邻笔最大间隔': 3,          # 紧邻笔的最大K线间隔
            '分型确认K线数': 3,           # 分型确认需要的K线数
            '有效突破比例': 0.01,         # 有效突破幅度(1%)
            '螺纹钢特性': {
                '最小波动': 1,            # 1元/吨
                '有效波动阈值': 10,       # 10元/吨为有效波动
                '交易时段权重': {         # 不同时段的可靠性权重
                    '日盘': 1.0,
                    '夜盘': 0.8
                }
            }
        }
        
        if config:
            self.config.update(config)
        
        # 状态存储
        self.中枢列表: List[Zhongshu] = []      # 所有识别的中枢
        self.笔列表: List[Bi] = []        # 所有识别的笔
        self.买卖点记录: List[Signal] = []    # 历史买卖点
        
        # MACD计算参数
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        from .first_class_signal import FirstClassSignalDetector
        from .second_class_signal import SecondClassSignalDetector
        from .third_class_signal import ThirdClassSignalDetector
        self.first_class_detector = FirstClassSignalDetector(self.config)
        self.second_class_detector = SecondClassSignalDetector()
        self.third_class_detector = ThirdClassSignalDetector(self.config)

    # --- Implementation of Core Logic ---

    def analyze(self, raw_bars: List[any]):
        """
        Main entry point for analysis.
        raw_bars: List of PriceBar objects (original K-lines).
        """
        if not raw_bars:
            return
            
        # 1. Preprocess (Calculate MACD on raw bars)
        self._calculate_indicators(raw_bars)
        
        # 2. Merge K-lines (Chan Inclusion Handling)
        self.chan_bars = merge_klines(raw_bars)
        
        # 3. Identify Bis (using Chan Bars)
        self._identify_bis(self.chan_bars)
        
        # 4. Identify Zhongshus
        self._identify_zhongshus()

        # 5. Identify Segments
        self._identify_segments()
        
        # 6. Identify Standard Zhongshus
        self._identify_standard_zhongshus()
        
        # 7. Detect Signals
        self._detect_signals(self.chan_bars)

    def _calculate_indicators(self, bars):
        # Assuming bars have .close property
        closes = pd.Series([b.close for b in bars])
        ema_fast = closes.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = closes.ewm(span=self.macd_slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.macd_signal, adjust=False).mean()
        macd_bar = (dif - dea) * 2
        
        self.difs = dif.values
        self.deas = dea.values
        self.macd_bars = macd_bar.values
        self.volumes = np.array([getattr(b, 'volume', 0) for b in bars])
        
        # Map timestamps to indices for easy lookup if needed
        # Or we rely on date matching.
        # ChanBar has .index property pointing to the index in original bars (usually end index).
        # We'll use that.

    def _identify_bis(self, bars):
        """
        Identify Bis based on Fractals and Config.
        bars: Merged ChanBars
        """
        self.笔列表 = []
        if len(bars) < 5:
            return

        # 1. Detect Fractals (on merged bars)
        fractals = []
        for i in range(1, len(bars) - 1):
            curr = bars[i]
            prev = bars[i-1]
            next_b = bars[i+1]
            
            if curr.high > prev.high and curr.high > next_b.high:
                fractals.append({'index': i, 'type': 'top', 'price': curr.high, 'time': curr.date, 'orig_index': curr.index})
            elif curr.low < prev.low and curr.low < next_b.low:
                fractals.append({'index': i, 'type': 'bottom', 'price': curr.low, 'time': curr.date, 'orig_index': curr.index})
        
        if not fractals:
            return

        # 2. Construct Bis
        curr_start_fx = fractals[0]
        bi_id_counter = 0
        
        for i in range(1, len(fractals)):
            fx = fractals[i]
            
            # Must be different type
            if fx['type'] == curr_start_fx['type']:
                # Update if more extreme
                if fx['type'] == 'top':
                    if fx['price'] > curr_start_fx['price']:
                        curr_start_fx = fx
                else:
                    if fx['price'] < curr_start_fx['price']:
                        curr_start_fx = fx
                continue
                
            # Check K-line distance
            if abs(fx['index'] - curr_start_fx['index']) < 4:
                continue
                
            # Check Amplitude (Rebar specifics)
            amp = abs(fx['price'] - curr_start_fx['price'])
            rb_config = self.config.get('螺纹钢特性', {})
            min_fluctuation = rb_config.get('有效波动阈值', 0)
            if amp < min_fluctuation:
                continue
            
            # Validate High/Low
            if curr_start_fx['type'] == 'bottom' and fx['type'] == 'top':
                if fx['price'] <= curr_start_fx['price']: continue
                direction = 'up'
                high = fx['price']
                low = curr_start_fx['price']
            elif curr_start_fx['type'] == 'top' and fx['type'] == 'bottom':
                if fx['price'] >= curr_start_fx['price']: continue
                direction = 'down'
                high = curr_start_fx['price']
                low = fx['price']
            else:
                continue
                
            # Create Bi
            bi_id_counter += 1
            
            # MACD Calculation mapping
            # curr_start_fx['orig_index'] is the end index of the bar in original list
            # fx['orig_index'] is end index of the bar in original list
            # We need the range between them.
            s_orig = curr_start_fx['orig_index']
            e_orig = fx['orig_index']
            # Ensure order
            start_idx = min(s_orig, e_orig)
            end_idx = max(s_orig, e_orig)
            
            macd_sum = 0
            diff_peak = 0
            volume_sum = 0
            if end_idx < len(self.macd_bars):
                 segment = self.macd_bars[start_idx:end_idx+1]
                 macd_sum = np.sum(np.abs(segment))
                 diff_peak = np.max(np.abs(self.difs[start_idx:end_idx+1]))
                 if hasattr(self, 'volumes') and end_idx < len(self.volumes):
                     volume_sum = np.sum(self.volumes[start_idx:end_idx+1])

            bi = Bi(
                bi_id=bi_id_counter,
                direction=direction,
                start_price=curr_start_fx['price'],
                end_price=fx['price'],
                start_time=curr_start_fx['time'],
                end_time=fx['time'],
                high=high,
                low=low,
                bars=abs(fx['index'] - curr_start_fx['index']),
                start_index=curr_start_fx['orig_index'],
                end_index=fx['orig_index']
            )
            bi.macd_data = {
                'sum': macd_sum,
                'diff_peak': diff_peak
            }
            bi.volume_sum = volume_sum
            
            self.笔列表.append(bi)
            curr_start_fx = fx

    def _identify_zhongshus(self):
        """
        Identify Zhongshus from Bis.
        """
        self.中枢列表 = []
        bis = self.笔列表
        if len(bis) < 3:
            return
            
        i = 0
        zs_id_counter = 0
        while i <= len(bis) - 3:
            b1 = bis[i]
            b2 = bis[i+1]
            b3 = bis[i+2]
            
            # Overlap
            zg = min(b1.high, b2.high, b3.high)
            zd = max(b1.low, b2.low, b3.low)
            
            if zg > zd:
                zs_id_counter += 1
                zs = Zhongshu(
                    zs_id=zs_id_counter,
                    zg=zg,
                    zd=zd,
                    gg=max(b1.high, b2.high, b3.high),
                    dd=min(b1.low, b2.low, b3.low),
                    start_time=b1.start_time,
                    end_time=b3.end_time,
                    bi_list=[b1, b2, b3]
                )
                
                # Extension
                j = i + 3
                while j < len(bis):
                    bn = bis[j]
                    # Check overlap with [zd, zg]
                    if not (bn.high < zd or bn.low > zg):
                        zs.end_time = bn.end_time
                        zs.bi_list.append(bn)
                        # Update GG/DD
                        zs.GG = max(zs.GG, bn.high)
                        zs.DD = min(zs.DD, bn.low)
                        j += 1
                    else:
                        break
                
                self.中枢列表.append(zs)
                # Mark Bis as belonging to this ZS
                for b in zs.bi_list:
                    b.所属中枢 = zs
                    
                i = j # Continue from the bi that left
            else:
                i += 1

    def _identify_segments(self):
        """
        识别线段 (Segments)
        基于笔的特征序列分型识别
        """
        self.线段列表 = []
        bis = self.笔列表
        if len(bis) < 3:
            return

        potential_points = [] 
        
        for i in range(1, len(bis)-1):
            prev = bis[i-1]
            curr = bis[i]
            next_b = bis[i+1]
            
            # Top Fenxing
            if curr.high > prev.high and curr.high > next_b.high:
                potential_points.append({'index': i, 'type': 'top', 'price': curr.high})
            # Bottom Fenxing
            elif curr.low < prev.low and curr.low < next_b.low:
                potential_points.append({'index': i, 'type': 'bottom', 'price': curr.low})
        
        if not potential_points:
            return
            
        segments = []
        curr_start = potential_points[0]
        
        for i in range(1, len(potential_points)):
            p = potential_points[i]
            
            if p['type'] == curr_start['type']:
                if p['type'] == 'top' and p['price'] > curr_start['price']:
                    curr_start = p
                elif p['type'] == 'bottom' and p['price'] < curr_start['price']:
                    curr_start = p
                continue
            
            if p['index'] - curr_start['index'] >= 3:
                direction = 'down' if curr_start['type'] == 'top' else 'up'
                seg_bis = bis[curr_start['index'] : p['index'] + 1]
                seg = Segment(bis[curr_start['index']], bis[p['index']], seg_bis, direction)
                segments.append(seg)
                curr_start = p
                
        self.线段列表 = segments

    def _identify_standard_zhongshus(self):
        """
        识别标准中枢 (Standard Zhongshu)
        基于线段列表构建
        """
        self.标准中枢列表 = []
        segs = self.线段列表
        if len(segs) < 3:
            return
            
        i = 0
        zs_id_counter = 0
        
        while i <= len(segs) - 3:
            s1 = segs[i]
            s2 = segs[i+1]
            s3 = segs[i+2]
            
            zg = min(s1.high, s2.high, s3.high)
            zd = max(s1.low, s2.low, s3.low)
            
            if zg > zd:
                zs_id_counter += 1
                gg = max(s1.high, s2.high, s3.high)
                dd = min(s1.low, s2.low, s3.low)
                zs_segs = [s1, s2, s3]
                
                j = i + 3
                while j < len(segs):
                    sn = segs[j]
                    if not (sn.high < zd or sn.low > zg):
                        zs_segs.append(sn)
                        gg = max(gg, sn.high)
                        dd = min(dd, sn.low)
                        j += 1
                    else:
                        break
                        
                zs = StandardZhongshu(zs_id_counter, zg, zd, gg, dd, s1.start_time, zs_segs[-1].end_time, zs_segs)
                self.标准中枢列表.append(zs)
                i = j 
            else:
                i += 1

    def _detect_signals(self, bars):
        """
        Detect 1B/2B/3B Signals.
        """
        self.买卖点记录 = []
        bis = self.笔列表
        centers = self.中枢列表
        if len(bis) < 2:
            return
            
        # Iterate over Bis to find signals
        # We assume analysis is done on history + current
        # Logic similar to ChanTradingSignals
        
        for i in range(2, len(bis)):
            curr_bi = bis[i]
            prev_bi = bis[i-2] # Same direction
            
            # Find relevant center
            valid_center = None
            for c in reversed(centers):
                # Center must end before this bi starts? 
                # Or center includes previous bis.
                # Usually we look for the center that this bi is leaving or relating to.
                # If bi is part of center, it's not a buy point (usually).
                # Buy point is usually the END of a bi.
                if c.end_time <= curr_bi.start_time: 
                    valid_center = c
                    break
            
            if not valid_center:
                continue
                
            
            # --- 1B/1S ---
            # 使用 FirstClassSignalDetector 进行检测
            
            # 构建上下文 (仅包含当前时刻及之前的数据)
            current_centers = [c for c in centers if c.end_time <= curr_bi.start_time]
            context = {
                'zhongshu_list': current_centers,
                'bi_list': bis[:i+1],
                'signals': self.买卖点记录,
                'bars': bars
            }
            
            if curr_bi.direction == 'down': # Potential 1B
                sig = self.first_class_detector.detect_1B(curr_bi, context)
                if sig:
                    sig.zhongshu = valid_center
                    self.买卖点记录.append(sig)
                         
            elif curr_bi.direction == 'up': # Potential 1S
                sig = self.first_class_detector.detect_1S(curr_bi, context)
                if sig:
                    sig.zhongshu = valid_center
                    self.买卖点记录.append(sig)
            
            # --- 2B/2S ---
            # 使用 SecondClassSignalDetector 进行检测
            if curr_bi.direction == 'down': # Potential 2B
                sig = self.second_class_detector.detect_2B(curr_bi, context)
                if sig:
                    sig.zhongshu = valid_center # 2B relates to the same center usually? Or new one? 
                    # Actually 2B is related to 1B, which is related to a center.
                    # We can inherit center from 1B if needed, or just keep valid_center if it's still valid.
                    # But 2B happens after 1B, so likely same center context.
                    self.买卖点记录.append(sig)
            
            elif curr_bi.direction == 'up': # Potential 2S
                sig = self.second_class_detector.detect_2S(curr_bi, context)
                if sig:
                    sig.zhongshu = valid_center
                    self.买卖点记录.append(sig)
            
            # --- 3B/3S ---
            # 使用 ThirdClassSignalDetector 进行检测
            if curr_bi.direction == 'down': # Potential 3B
                sig = self.third_class_detector.detect_3B(curr_bi, context)
                if sig:
                    # 3B usually confirms the center break, so valid_center might be the one broken.
                    # detect_3B logic finds the last completed center from context, which should be valid_center.
                    if not sig.zhongshu:
                        sig.zhongshu = valid_center
                    self.买卖点记录.append(sig)
                    
            elif curr_bi.direction == 'up': # Potential 3S
                sig = self.third_class_detector.detect_3S(curr_bi, context)
                if sig:
                    if not sig.zhongshu:
                        sig.zhongshu = valid_center
                    self.买卖点记录.append(sig)
