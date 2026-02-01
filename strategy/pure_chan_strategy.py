import sys
import os
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datafeed.base import PriceBar
from chan.common import Trend, FXType
from chan.k_merge import merge_klines

# --- Helper Functions ---
def calculate_macd(bars: List[PriceBar], fast=12, slow=26, signal=9):
    """Calculate MACD for list of PriceBars"""
    closes = pd.Series([b.close for b in bars])
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = (dif - dea) * 2
    return dif, dea, macd_bar

def calculate_atr(bars: List[PriceBar], period=14):
    if not bars:
        return 0
    highs = pd.Series([b.high for b in bars])
    lows = pd.Series([b.low for b in bars])
    closes = pd.Series([b.close for b in bars])
    
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean().iloc[-1]
    return atr

# --- Data Classes for Pure Strategy ---
class SimpleFractal:
    def __init__(self, index, price, type, date):
        self.index = index
        self.price = price
        self.type = type
        self.date = date

class SimpleBi:
    def __init__(self, start_fx, end_fx, direction, bars: List[PriceBar]=None):
        self.start_fx = start_fx
        self.end_fx = end_fx
        self.direction = direction
        self.low = min(start_fx.price, end_fx.price)
        self.high = max(start_fx.price, end_fx.price)
        
        # Metrics for Divergence
        self.macd_sum = 0
        self.volume_sum = 0
        self.slope = 0
        
        if bars:
            # Extract bars covered by this Bi
            # Note: fractals use index from merged klines, so we need to access merged klines here
            # But we passed 'bars' which might be the merged ones if passed correctly
            pass

    def calculate_metrics(self, difs, deas, macd_bars, merged_bars):
        # Indices in merged_bars (ChanBars)
        start_chan_idx = self.start_fx.index
        end_chan_idx = self.end_fx.index
        
        # Resolve to original indices
        # merged_bars is list of ChanBar, each has .index pointing to end of original bar
        if start_chan_idx >= len(merged_bars) or end_chan_idx >= len(merged_bars):
            return

        s_orig = merged_bars[start_chan_idx].index
        e_orig = merged_bars[end_chan_idx].index
        
        # Ensure correct range
        s, e = min(s_orig, e_orig), max(s_orig, e_orig)
        
        # Check bounds against macd arrays
        if s >= len(macd_bars) or e >= len(macd_bars):
            return

        segment_macd = macd_bars[s:e+1]
        self.macd_sum = np.sum(np.abs(segment_macd)) 
        
        # Slope
        price_diff = self.end_fx.price - self.start_fx.price
        time_diff = e - s # In bars
        if time_diff > 0:
            self.slope = price_diff / time_diff

class SimpleCenter:
    def __init__(self, zg, zd, start_bi_index, end_bi_index):
        self.zg = zg
        self.zd = zd
        self.gg = zg # Placeholder, ideally max of contained bars
        self.dd = zd # Placeholder
        self.start_bi_index = start_bi_index
        self.end_bi_index = end_bi_index
        self.level = 0 # 0=Default

class ChanPositionManagement:
    """基于缠论走势结构的仓位管理"""
    
    def __init__(self, total_capital=100000):
        self.total_capital = total_capital
        
    def calculate_position_size(self, signal_type: str) -> Dict:
        """
        根据买卖点类型确定仓位
        """
        # Rules from user
        rules = {
            '1B': {'base': 0.10, 'max': 0.20, 'desc': 'Trend Divergence Buy'},
            '1S': {'base': 0.10, 'max': 0.20, 'desc': 'Trend Divergence Sell'},
            '2B': {'base': 0.07, 'max': 0.15, 'desc': 'Pullback Buy'},
            '2S': {'base': 0.07, 'max': 0.15, 'desc': 'Pullback Sell'},
            '3B': {'base': 0.05, 'max': 0.08, 'desc': 'Trend Continuation Buy'},
            '3S': {'base': 0.05, 'max': 0.08, 'desc': 'Trend Continuation Sell'}
        }
        
        rule = rules.get(signal_type, {'base': 0.05, 'max': 0.05, 'desc': 'Unknown'})
        
        return {
            "ratio": rule['base'],
            "amount": self.total_capital * rule['base'],
            "info": f"{rule['desc']} - Base {int(rule['base']*100)}%"
        }

    def get_stoploss(self, signal_type: str, direction: Trend, entry_price: float, 
                     center: SimpleCenter, bi: SimpleBi, 
                     curr_date: datetime, atr: float = 0) -> float:
        """
        基于缠论结构的动态止损
        """
        sl_price = entry_price
        
        # 1. Determine Structure SL Point
        if "1" in signal_type: # 1B/1S
            sl_price = bi.low if direction == Trend.DOWN else bi.high
            
        elif "2" in signal_type: # 2B/2S
            # 2B: Drop below 1st buy point or this buy point low
            sl_price = bi.low if direction == Trend.DOWN else bi.high
            
        elif "3" in signal_type: # 3B/3S
            # 3B: Drop back to ZhongShu (ZG) or break pullback low
            if direction == Trend.DOWN: # 3B (Pullback is Down)
                # Use the tighter of Bi Low or Center ZG
                # But to avoid instant stop if ZG is close, we default to Bi Low (Structure)
                sl_price = bi.low
            else: # 3S
                sl_price = bi.high
                
        # 2. Adjustments (Night & ATR)
        is_night = False
        if curr_date:
            # Simple check for SHFE Night Session (21:00-02:30)
            # Need to handle cross-midnight
            t = curr_date.time()
            if t >= time(21, 0) or t <= time(2, 30):
                is_night = True
        
        # Base Buffer: 0.5 ATR (or 10 ticks if ATR=0?)
        # If ATR is 0, use 0.2% of price as fallback
        base_buffer = (0.5 * atr) if atr > 0 else (entry_price * 0.002)
        
        # Night Adjustment: Widen by 30%
        if is_night:
            base_buffer *= 1.3
            
        if direction == Trend.DOWN: # Buy Signal (Bi was Down)
            final_sl = sl_price - base_buffer
        else: # Sell Signal
            final_sl = sl_price + base_buffer
            
        return final_sl

class ChanTradingSignals:
    """基于缠论三类买卖点的信号生成"""
    
    def __init__(self):
        self.signals = []
        self.pos_mgr = ChanPositionManagement()
        
    def check_divergence(self, curr_bi: SimpleBi, prev_bi: SimpleBi) -> bool:
        """
        Check divergence between two Bis of same direction.
        Criteria:
        1. Price makes new High/Low
        2. MACD Area decreases OR Slope decreases
        """
        if curr_bi.direction != prev_bi.direction:
            return False
            
        is_divergent = False
        
        if curr_bi.direction == Trend.UP:
            if curr_bi.high > prev_bi.high: # New High
                if curr_bi.macd_sum < prev_bi.macd_sum * 0.7: # Area shrunk > 30%
                    is_divergent = True
                elif abs(curr_bi.slope) < abs(prev_bi.slope) * 0.6: # Slope decreased > 40%
                    is_divergent = True
        else: # DOWN
            if curr_bi.low < prev_bi.low: # New Low
                if curr_bi.macd_sum < prev_bi.macd_sum * 0.7:
                    is_divergent = True
                elif abs(curr_bi.slope) < abs(prev_bi.slope) * 0.6:
                    is_divergent = True
                    
        return is_divergent

    def process_signals(self, bis: List[SimpleBi], centers: List[SimpleCenter], bars: List[PriceBar]) -> List[Dict]:
        """
        Generate signals based on Bis and Centers.
        """
        signals = []
        if len(bis) < 2:
            return signals
            
        # Calculate ATR (Use latest for now, ideally rolling)
        atr = calculate_atr(bars) if bars else 0
            
        # Iterate through Bis to find signals
        # We start from index 2 to have enough history
        for i in range(2, len(bis)):
            curr_bi = bis[i]
            
            # Find the most recent center before this Bi
            valid_center = None
            for c in reversed(centers):
                if c.end_bi_index < i:
                    valid_center = c
                    break
            
            if not valid_center:
                continue
                
            # --- 3rd Class Signal (3B/3S) ---
            # Strict Check: Must be the immediate pullback after leaving center (Departure Bi + Return Bi)
            # Center ends at end_bi_index. Departure is end_bi_index+1. Return is end_bi_index+2.
            if i - valid_center.end_bi_index == 2:
                leave_bi = bis[i-1]
                
                if leave_bi.direction == Trend.UP and curr_bi.direction == Trend.DOWN:
                    # Potential 3B
                    # Ensure departure actually started from/below ZG (otherwise it was already floating above)
                    # We check leave_bi.start_fx.price vs ZG. 
                    # Since it's UP bi, start is Low.
                    if leave_bi.start_fx.price <= valid_center.zg * 1.005: # Allow tiny buffer or strict <=
                        if leave_bi.high > valid_center.zg: # Left upwards
                            if curr_bi.low > valid_center.zg: # Pullback didn't touch ZG
                                signal_type = "3B"
                                price = curr_bi.end_fx.price
                                
                                # Position Management
                                pos = self.pos_mgr.calculate_position_size(signal_type)
                                sl = self.pos_mgr.get_stoploss(signal_type, curr_bi.direction, price, valid_center, curr_bi, curr_bi.end_fx.date, atr)
                                
                                signals.append({
                                    "type": signal_type,
                                    "price": price,
                                    "desc": f"Pure 3B (Low {curr_bi.low} > ZG {valid_center.zg})",
                                    "dt": curr_bi.end_fx.date,
                                    "sl": sl,
                                    "tp": price + 2 * (price - valid_center.zg),
                                    "priority": 0.4,
                                    "pos": pos
                                })
                
                elif leave_bi.direction == Trend.DOWN and curr_bi.direction == Trend.UP:
                    # Potential 3S
                    # Ensure departure started from/above ZD
                    if leave_bi.start_fx.price >= valid_center.zd * 0.995:
                        if leave_bi.low < valid_center.zd: # Left downwards
                            if curr_bi.high < valid_center.zd: # Pullback didn't touch ZD
                                signal_type = "3S"
                                price = curr_bi.end_fx.price
                                
                                # Position Management
                                pos = self.pos_mgr.calculate_position_size(signal_type)
                                sl = self.pos_mgr.get_stoploss(signal_type, curr_bi.direction, price, valid_center, curr_bi, curr_bi.end_fx.date, atr)
                                
                                signals.append({
                                    "type": signal_type,
                                    "price": price,
                                    "desc": f"Pure 3S (High {curr_bi.high} < ZD {valid_center.zd})",
                                    "dt": curr_bi.end_fx.date,
                                    "sl": sl,
                                    "tp": price - 2 * (valid_center.zd - price),
                                    "priority": 0.4,
                                    "pos": pos
                                })

            # --- 1st Class Signal (1B/1S) ---
            prev_bi = bis[i-2]
            is_1st_signal = False
            signal_type = ""
            
            if self.check_divergence(curr_bi, prev_bi):
                if curr_bi.direction == Trend.DOWN: # Potential 1B
                    if curr_bi.low < valid_center.zd:
                        is_1st_signal = True
                        signal_type = "1B"
                elif curr_bi.direction == Trend.UP: # Potential 1S
                    if curr_bi.high > valid_center.zg:
                        is_1st_signal = True
                        signal_type = "1S"
            
            if is_1st_signal:
                price = curr_bi.end_fx.price
                pos = self.pos_mgr.calculate_position_size(signal_type)
                sl = self.pos_mgr.get_stoploss(signal_type, curr_bi.direction, price, valid_center, curr_bi, curr_bi.end_fx.date, atr)
                
                signals.append({
                    "type": signal_type,
                    "price": price,
                    "desc": f"Pure {signal_type} (Divergence vs Bi {prev_bi.start_fx.index})",
                    "dt": curr_bi.end_fx.date,
                    "sl": sl, 
                    "tp": valid_center.zg if signal_type == "1B" else valid_center.zd,
                    "priority": 0.35,
                    "pos": pos
                })

            # --- 2nd Class Signal (2B/2S) ---
            if curr_bi.direction == Trend.DOWN: # Potential 2B
                prev_low_bi = bis[i-2]
                if curr_bi.low > prev_low_bi.low:
                    if prev_low_bi.low < valid_center.zd:
                         signal_type = "2B"
                         price = curr_bi.end_fx.price
                         pos = self.pos_mgr.calculate_position_size(signal_type)
                         sl = self.pos_mgr.get_stoploss(signal_type, curr_bi.direction, price, valid_center, curr_bi, curr_bi.end_fx.date, atr)
                         
                         signals.append({
                            "type": signal_type,
                            "price": price,
                            "desc": "Pure 2B (Higher Low)",
                            "dt": curr_bi.end_fx.date,
                            "sl": sl,
                            "tp": valid_center.zg,
                            "priority": 0.25,
                            "pos": pos
                        })
                        
            elif curr_bi.direction == Trend.UP: # Potential 2S
                prev_high_bi = bis[i-2]
                if curr_bi.high < prev_high_bi.high:
                    if prev_high_bi.high > valid_center.zg:
                        signal_type = "2S"
                        price = curr_bi.end_fx.price
                        pos = self.pos_mgr.calculate_position_size(signal_type)
                        sl = self.pos_mgr.get_stoploss(signal_type, curr_bi.direction, price, valid_center, curr_bi, curr_bi.end_fx.date, atr)
                        
                        signals.append({
                            "type": signal_type,
                            "price": price,
                            "desc": "Pure 2S (Lower High)",
                            "dt": curr_bi.end_fx.date,
                            "sl": sl,
                            "tp": valid_center.zd,
                            "priority": 0.25,
                            "pos": pos
                        })

        return signals

class PureChanTheoryEngine:
    """纯缠论分析引擎 - Adapted from User Input"""
    
    def __init__(self, symbol):
        self.symbol = symbol
        self.is_rb = "rb" in symbol.lower()
        self.min_bi_len = 5 
        self.bi_amplitude_threshold = 20 if self.is_rb else 0 
        
    def detect_fractal(self, klines, level='standard'): 
        fractals = []
        if len(klines) < 3:
            return fractals
            
        for i in range(1, len(klines) - 1):
            left = klines[i-1]
            curr = klines[i]
            right = klines[i+1]
            
            if curr.high > left.high and curr.high > right.high:
                f = SimpleFractal(index=i, price=curr.high, type=FXType.TOP, date=curr.date)
                fractals.append(f)
            elif curr.low < left.low and curr.low < right.low:
                f = SimpleFractal(index=i, price=curr.low, type=FXType.BOTTOM, date=curr.date)
                fractals.append(f)
                
        return fractals

    def construct_bi(self, fractals, klines, difs, deas, macd_bars): 
        if not fractals:
            return []
            
        bis = []
        current_bi_start = fractals[0]
        
        for i in range(1, len(fractals)):
            curr_f = fractals[i]
            
            if curr_f.type == current_bi_start.type:
                if curr_f.type == FXType.TOP:
                    if curr_f.price > current_bi_start.price:
                        current_bi_start = curr_f
                else:
                    if curr_f.price < current_bi_start.price:
                        current_bi_start = curr_f
                continue
                
            dist = abs(curr_f.index - current_bi_start.index)
            if dist < 5:
                continue
                
            amp = abs(curr_f.price - current_bi_start.price)
            if self.is_rb and amp < self.bi_amplitude_threshold:
                continue
                
            direction = Trend.UP if curr_f.type == FXType.TOP else Trend.DOWN
            if direction == Trend.UP:
                 if curr_f.price <= current_bi_start.price: continue
            else:
                 if curr_f.price >= current_bi_start.price: continue
            
            bi = SimpleBi(start_fx=current_bi_start, end_fx=curr_f, direction=direction)
            
            # Calculate metrics
            bi.calculate_metrics(difs, deas, macd_bars, klines)
            
            bis.append(bi)
            current_bi_start = curr_f
            
        return bis

    def identify_segment_and_zhongshu(self, bis): 
        centers = []
        if len(bis) < 3:
            return centers
            
        for i in range(len(bis) - 2):
            b1 = bis[i]
            b2 = bis[i+1]
            b3 = bis[i+2]
            
            min1, max1 = min(b1.start_fx.price, b1.end_fx.price), max(b1.start_fx.price, b1.end_fx.price)
            min2, max2 = min(b2.start_fx.price, b2.end_fx.price), max(b2.start_fx.price, b2.end_fx.price)
            min3, max3 = min(b3.start_fx.price, b3.end_fx.price), max(b3.start_fx.price, b3.end_fx.price)
            
            zg = min(max1, max2, max3)
            zd = max(min1, min2, min3)
            
            if zg > zd: 
                center = SimpleCenter(zg=zg, zd=zd, start_bi_index=i, end_bi_index=i+2)
                centers.append(center)
                
        return centers

from .chan_core import ChanTheorySignalDetector, Signal
from chan.common import Trend

class PureChanStrategy:
    """
    Implementation of the 'Pure Chan Theory' strategy using the new Core Detector.
    """
    def __init__(self, symbol: str, period: str):
        self.symbol = symbol
        self.period = period
        self.detector = ChanTheorySignalDetector({
            '螺纹钢特性': {
                '最小波动': 1,
                '有效波动阈值': 10 if 'rb' in symbol.lower() else 0
            }
        })
        self.pos_mgr = ChanPositionManagement() # Reuse existing

    def run(self, bars: List[PriceBar]) -> List[Dict]:
        if not bars:
            return []

        # Run Analysis
        self.detector.analyze(bars)
        
        # Convert Signals to Dicts
        output_signals = []
        
        # Calculate ATR for SL/TP (Reuse helper)
        atr = calculate_atr(bars)
        
        for sig in self.detector.买卖点记录:
            # Map Signal to Output Format
            # sig.type is '1B', '3B' etc.
            
            # Determine direction for PosMgr (If Signal is Buy, Trend was Down -> Up)
            # Actually Signal Type tells us.
            direction = Trend.DOWN if 'B' in sig.type else Trend.UP
            # Note: ChanPositionManagement.get_stoploss expects 'direction' of the SIGNAL?
            # get_stoploss(signal_type, direction, ...)
            # Logic in get_stoploss: if direction == Trend.DOWN: Buy Signal.
            # So we pass Trend.DOWN for Buy Signals.
            
            # We need to map new Bi/Center to SimpleBi/SimpleCenter expected by PosMgr?
            # Or assume PosMgr uses duck typing?
            # PosMgr uses: bi.low, bi.high, center.zg, center.zd.
            # Our new classes have these (Bi.low, Zhongshu.ZG).
            # But case might differ (ZG vs zg).
            # Zhongshu has .ZG .ZD .GG .DD.
            # SimpleCenter has .zg .zd .gg .dd.
            # I should align them or modify PosMgr.
            # Let's wrap/adapter or modify PosMgr to handle .ZG / .zg
            # Or easier: Create an adapter object or just ensure attribute access works.
            # Python is dynamic.
            # SimpleCenter has .zg. Zhongshu has .ZG.
            # I will check if I can alias them in Zhongshu class.
            
            # Map Bi/Center for PosMgr
            # We pass sig.bi and sig.zhongshu
            
            # Pos Size
            pos_info = self.pos_mgr.calculate_position_size(sig.type)
            
            # Stop Loss
            # PosMgr expects: get_stoploss(signal_type, direction, entry_price, center, bi, date, atr)
            # It accesses center.zg/zd and bi.low/high.
            # Our new Zhongshu uses Uppercase ZG. SimpleCenter uses lowercase.
            # I will modify the passed objects or PosMgr.
            # Modifying PosMgr is risky if used elsewhere.
            # I will add lowercase properties to Zhongshu class in chan_core.py.
            
            sl = self.pos_mgr.get_stoploss(
                sig.type, 
                direction, 
                sig.price, 
                sig.zhongshu, 
                sig.bi, 
                sig.time, 
                atr
            )
            
            # TP
            # Simple logic: 2 * Risk or based on Center
            tp = 0
            if 'B' in sig.type:
                tp = sig.zhongshu.ZG if sig.zhongshu else sig.price * 1.02
            else:
                tp = sig.zhongshu.ZD if sig.zhongshu else sig.price * 0.98

            output_signals.append({
                "type": sig.type,
                "price": sig.price,
                "desc": f"{sig.type} (Score: {sig.score})",
                "dt": sig.time,
                "sl": sl,
                "tp": tp,
                "priority": sig.score / 200.0, # 0.4-0.5 range
                "pos": pos_info
            })
            
        return output_signals

