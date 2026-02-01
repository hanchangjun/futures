import sys
import os
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import engine, get_db
from database.models import ChanSignal, StockBar
from datafeed.tq_feed import fetch_tq_bars, resolve_tq_symbol
from datafeed.base import PriceBar, parse_timestamp
from chan.k_merge import merge_klines
from chan.fractal import find_fractals
from chan.bi import find_bi, Bi
from chan.center import find_zhongshu, ZhongShu
from chan.indicators import calculate_macd, calculate_atr
from chan.common import Trend

class ChanStrategy:
    def __init__(self, symbol, period):
        self.symbol = symbol
        self.period = period
        
    def get_atr(self, idx):
        if not hasattr(self, 'atr_series') or idx < 0 or idx >= len(self.atr_series):
            return 0.0
        val = self.atr_series.iloc[idx]
        return val if not pd.isna(val) else 0.0

    def check_1b_conditions(self, curr_bi_idx: int, bis: List[Bi], centers: List[ZhongShu]) -> dict:
        """
        第一类买点条件 (优化版)
        :return: result_dict or None
        """
        curr_bi = bis[curr_bi_idx]
        
        # 1. 基础方向
        if curr_bi.direction != Trend.DOWN:
            return None
            
        # 2. 寻找归属的最后一个中枢
        last_center = None
        # 搜索逻辑：找到一个中枢，其 end_bi_index == curr_bi_idx - 1
        target_end_idx = curr_bi_idx - 1
        
        for c in reversed(centers):
            if c.end_bi_index == target_end_idx:
                last_center = c
                break
        
        if not last_center:
            return None
            
        # 3. 趋势要求：包含至少两个依次向下的同级别中枢 (Trend Divergence)
        prev_center = None
        for c in reversed(centers):
            if c.end_bi_index < last_center.start_bi_index:
                # 简单判断：位置更高
                if c.zd > last_center.zg: # 严格趋势：不重叠
                    prev_center = c
                    break
                elif c.zd > last_center.zd: # 宽松趋势：重心下移
                    prev_center = c
                    break
        
        # 标记是否满足严格趋势 (2个中枢)
        is_trend = (prev_center is not None)
        
        # 4. 价格要求：离开段创出新低 (相比进入段低点 和 中枢ZD)
        # 进入段：last_center.start_bi_index - 1
        enter_bi_idx = last_center.start_bi_index - 1
        if enter_bi_idx < 0:
            return None
            
        enter_bi = bis[enter_bi_idx]
        
        # 必须创新低
        if not (curr_bi.low < last_center.zd and curr_bi.low < enter_bi.low):
            return None
            
        # 5. 背驰要求：MACD 面积或高度
        # 面积减少 > 30% (即 < 0.7)
        is_area_divergence = (curr_bi.macd_area < enter_bi.macd_area * 0.7)
        
        if not is_area_divergence:
            return None
            
        # 6. 确认机制 (隐含：curr_bi 已完成)
        
        # 计算止损位
        atr = self.get_atr(curr_bi.end_fx.index)
        if atr == 0: atr = curr_bi.end_fx.price * 0.01
                 
        sl_price = curr_bi.low - atr * 0.5 # 紧凑止损
        
        return {
            "type": "1B",
            "desc": f"趋势背驰 (Area: {curr_bi.macd_area:.1f} < {enter_bi.macd_area:.1f} * 0.7) Trend:{is_trend}",
            "sl": sl_price,
            "is_trend": is_trend
        }

    def check_1s_conditions(self, curr_bi_idx: int, bis: List[Bi], centers: List[ZhongShu]) -> dict:
        """
        第一类卖点条件 (优化版)
        """
        curr_bi = bis[curr_bi_idx]
        
        if curr_bi.direction != Trend.UP:
            return None
            
        last_center = None
        target_end_idx = curr_bi_idx - 1
        
        for c in reversed(centers):
            if c.end_bi_index == target_end_idx:
                last_center = c
                break
        
        if not last_center:
            return None
            
        prev_center = None
        for c in reversed(centers):
            if c.end_bi_index < last_center.start_bi_index:
                if c.zg < last_center.zd: # 严格
                    prev_center = c
                    break
                elif c.zg < last_center.zg: # 宽松
                    prev_center = c
                    break
                    
        is_trend = (prev_center is not None)
        
        enter_bi_idx = last_center.start_bi_index - 1
        if enter_bi_idx < 0:
            return None
        enter_bi = bis[enter_bi_idx]
        
        # 价格创新高
        if not (curr_bi.high > last_center.zg and curr_bi.high > enter_bi.high):
            return None
            
        # 背驰
        is_area_divergence = (curr_bi.macd_area < enter_bi.macd_area * 0.7)
        
        if not is_area_divergence:
            return None
            
        atr = self.get_atr(curr_bi.end_fx.index)
        if atr == 0: atr = curr_bi.end_fx.price * 0.01
        
        sl_price = curr_bi.high + atr * 0.5
        
        return {
            "type": "1S",
            "desc": f"趋势背驰 (Area: {curr_bi.macd_area:.1f} < {enter_bi.macd_area:.1f} * 0.7) Trend:{is_trend}",
            "sl": sl_price,
            "is_trend": is_trend
        }

    def run(self, bars: List[PriceBar]) -> List[dict]:
        """
        执行策略
        """
        if not bars:
            return []
            
        self.bars = bars
        
        # 1. Calc MACD
        macd_df = calculate_macd(bars)
        
        # 1.1 Calc ATR for Stop Loss
        self.atr_series = calculate_atr(bars, period=14)
        
        # 2. Chan Processing
        chan_bars = merge_klines(bars)
        fractals = find_fractals(chan_bars)
        bis = find_bi(chan_bars, fractals)
        
        # 3. Compute Dynamics
        bis = self.compute_bi_dynamics(bis, chan_bars, macd_df)
        
        print(f"DEBUG: Bars={len(bars)}, Bis={len(bis)}")

        # 4. Find Centers
        centers = find_zhongshu(bis)
        
        signals = []
        
        if len(bis) < 3:
            return signals
            
        # Iterate all bis starting from index 2 to find historical signals
        # Start from 3 to ensure enough history for checks
        for i in range(3, len(bis)):
            curr_bi = bis[i]
            prev_bi = bis[i-2]
            
            # --- Strategy 1: Trend Divergence (Beichi) Optimized ---
            res_1b = self.check_1b_conditions(i, bis, centers)
            if res_1b:
                signals.append({
                    "type": "1B",
                    "price": curr_bi.end_fx.price,
                    "desc": f"{res_1b['desc']} [Pos:10%] [SL:{res_1b['sl']:.2f}]",
                    "dt": curr_bi.end_fx.date,
                    "sl": res_1b["sl"],
                    "tp": curr_bi.end_fx.price + (curr_bi.end_fx.price - res_1b["sl"]) * 2,
                    "pos": {"ratio": 0.1, "msg": "10% (Trend Reversal)"}
                })
            
            res_1s = self.check_1s_conditions(i, bis, centers)
            if res_1s:
                signals.append({
                    "type": "1S",
                    "price": curr_bi.end_fx.price,
                    "desc": f"{res_1s['desc']} [Pos:10%] [SL:{res_1s['sl']:.2f}]",
                    "dt": curr_bi.end_fx.date,
                    "sl": res_1s["sl"],
                    "tp": curr_bi.end_fx.price - (res_1s["sl"] - curr_bi.end_fx.price) * 2,
                    "pos": {"ratio": 0.1, "msg": "10% (Trend Reversal)"}
                })
            
            # --- Strategy 3: 2nd Buy/Sell (Second Chance) ---
            # 2B: After a 1B (Potential Bottom), the next pullback does not make a new low.
            
            if i >= 4: # Need i-4 to check if i-2 was divergence
                # Check if i-2 was a 1B/1S candidate (Loose check for 2B context)
                candidate_bi = bis[i-2]
                pre_candidate_bi = bis[i-4]
                
                is_1b_candidate = False
                is_1s_candidate = False
                
                if candidate_bi.direction == pre_candidate_bi.direction:
                     if candidate_bi.macd_area < pre_candidate_bi.macd_area:
                         if candidate_bi.direction == Trend.DOWN and candidate_bi.low < pre_candidate_bi.low:
                             is_1b_candidate = True
                         elif candidate_bi.direction == Trend.UP and candidate_bi.high > pre_candidate_bi.high:
                             is_1s_candidate = True
                
                # Check 2B
                if curr_bi.direction == Trend.DOWN and is_1b_candidate:
                    if curr_bi.low > candidate_bi.low:
                         atr_val = self.get_atr(curr_bi.end_fx.index)
                         if atr_val == 0: atr_val = curr_bi.end_fx.price * 0.01

                         sl_raw = candidate_bi.low # 2B SL at 1B Low
                         sl = sl_raw - 1.0 * atr_val
                         risk = curr_bi.end_fx.price - sl
                         tp = curr_bi.end_fx.price + 2.0 * risk if risk > 0 else None
                         
                         signals.append({
                            "type": "2B",
                            "price": curr_bi.end_fx.price,
                            "desc": f"二买 (HL > {candidate_bi.low}) [Pos:7%] [SL:{sl:.2f}]",
                            "dt": curr_bi.end_fx.date,
                            "sl": sl,
                            "tp": tp,
                            "pos": {"ratio": 0.07, "msg": "7% (Trend Confirm)"}
                        })
                
                # Check 2S
                if curr_bi.direction == Trend.UP and is_1s_candidate:
                    if curr_bi.high < candidate_bi.high:
                         atr_val = self.get_atr(curr_bi.end_fx.index)
                         if atr_val == 0: atr_val = curr_bi.end_fx.price * 0.01

                         sl_raw = candidate_bi.high # 2S SL at 1S High
                         sl = sl_raw + 1.0 * atr_val
                         risk = sl - curr_bi.end_fx.price
                         tp = curr_bi.end_fx.price - 2.0 * risk if risk > 0 else None
                         
                         signals.append({
                            "type": "2S",
                            "price": curr_bi.end_fx.price,
                            "desc": f"二卖 (LH < {candidate_bi.high}) [Pos:7%] [SL:{sl:.2f}]",
                            "dt": curr_bi.end_fx.date,
                            "sl": sl,
                            "tp": tp,
                            "pos": {"ratio": 0.07, "msg": "7% (Trend Confirm)"}
                        })

            # --- Strategy 2: 3rd Buy/Sell (Pivot Pullback) ---
            
            valid_center = None
            for c in reversed(centers):
                if c.end_bi_index < i - 1:
                    valid_center = c
                    break
            
            if valid_center:
                if curr_bi.direction == Trend.DOWN: # Potential 3B
                     # Leaving Bi (i-1) must be UP and break ZG
                     leaving_bi = bis[i-1]
                     if leaving_bi.direction == Trend.UP and leaving_bi.high > valid_center.zg:
                         # Pullback Bi (i) must stay above ZG
                         if curr_bi.low > valid_center.zg:
                             atr_val = self.get_atr(curr_bi.end_fx.index)
                             if atr_val == 0: atr_val = curr_bi.end_fx.price * 0.01
                             
                             sl_raw = valid_center.zg # 3B SL at ZG or Low
                             sl = sl_raw - 1.0 * atr_val
                             risk = curr_bi.end_fx.price - sl
                             tp = curr_bi.end_fx.price + 2.0 * risk if risk > 0 else None
                             
                             signals.append({
                                "type": "3B",
                                "price": curr_bi.end_fx.price,
                                "desc": f"三买 (Low: {curr_bi.low} > ZG: {valid_center.zg}) [Pos:5%] [SL:{sl:.2f}]",
                                "dt": curr_bi.end_fx.date,
                                "sl": sl,
                                "tp": tp,
                                "pos": {"ratio": 0.05, "msg": "5% (Trend Follow)"}
                            })

                elif curr_bi.direction == Trend.UP: # Potential 3S
                     # Leaving Bi (i-1) must be DOWN and break ZD
                     leaving_bi = bis[i-1]
                     if leaving_bi.direction == Trend.DOWN and leaving_bi.low < valid_center.zd:
                         # Pullback Bi (i) must stay below ZD
                         if curr_bi.high < valid_center.zd:
                             atr_val = self.get_atr(curr_bi.end_fx.index)
                             if atr_val == 0: atr_val = curr_bi.end_fx.price * 0.01
                             
                             sl_raw = valid_center.zd
                             sl = sl_raw + 1.0 * atr_val
                             risk = sl - curr_bi.end_fx.price
                             tp = curr_bi.end_fx.price - 2.0 * risk if risk > 0 else None
                             
                             signals.append({
                               "type": "3S",
                               "price": curr_bi.end_fx.price,
                               "desc": f"三卖 (High: {curr_bi.high} < ZD: {valid_center.zd}) [Pos:5%] [SL:{sl:.2f}]",
                               "dt": curr_bi.end_fx.date,
                               "sl": sl,
                               "tp": tp,
                               "pos": {"ratio": 0.05, "msg": "5% (Trend Follow)"}
                           })
        
        return signals

    def compute_bi_dynamics(self, bis, chan_bars, macd_df):
        for bi in bis:
             start_cb = chan_bars[bi.start_fx.index]
             end_cb = chan_bars[bi.end_fx.index]
             
             # Map to raw indices
             if not start_cb.elements or not end_cb.elements:
                 continue
                 
             s_idx = start_cb.elements[0]
             e_idx = end_cb.elements[-1]
             
             if s_idx < len(macd_df) and e_idx < len(macd_df):
                 segment = macd_df.iloc[s_idx : e_idx + 1]
                 bi.macd_area = segment['macd'].abs().sum()
             
        return bis

    def save_signals(self, signals):
        if not signals:
            return
            
        session = Session(bind=engine)
        try:
            for s in signals:
                # Check duplicate
                exists = session.query(ChanSignal).filter(
                    ChanSignal.symbol == self.symbol,
                    ChanSignal.period == self.period,
                    ChanSignal.dt == s['dt'],
                    ChanSignal.signal_type == s['type']
                ).first()
                
                if not exists:
                    sig = ChanSignal(
                        symbol=self.symbol,
                        period=self.period,
                        dt=s['dt'],
                        signal_type=s['type'],
                        price=s['price'],
                        desc=s['desc'],
                        created_at=datetime.now()
                    )
                    session.add(sig)
                    print(f"Saved Signal: {self.symbol} {s['type']} at {s['dt']}")
            session.commit()
        except Exception as e:
            print(f"Error saving signals: {e}")
            session.rollback()
        finally:
            session.close()

from .pure_chan_strategy import PureChanStrategy

def run_strategy(symbol, period="30m", count=2000, source="db", strategy_name="standard"):
    """
    Programmatic entry point for strategy execution
    """
    bars = []
    if source == "tq":
        tq_symbol = resolve_tq_symbol(symbol)
        bars = fetch_tq_bars(
            symbol=tq_symbol,
            period=period,
            count=count,
            username=os.getenv("TQ_USERNAME"),
            password=os.getenv("TQ_PASSWORD"),
            timeout=30,
            wait_update_once=False,
            debug=True
        )
    elif source == "db":
        # Load from DB
        session = Session(bind=engine)
        db_bars = session.query(StockBar).filter(
            StockBar.symbol == symbol,
            StockBar.period == period
        ).order_by(StockBar.dt.desc()).limit(count).all()
        
        # Convert to PriceBar
        for b in reversed(db_bars):
             bars.append(PriceBar(
                 date=parse_timestamp(b.dt),
                 open=b.open,
                 high=b.high,
                 low=b.low,
                 close=b.close,
                 volume=b.volume
             ))
        session.close()

    if not bars:
        print("No bars found.")
        return 0

    # Dispatch Strategy
    if strategy_name == "pure_chan":
        print(f"Running Pure Chan Strategy for {symbol} {period}...")
        strat = PureChanStrategy(symbol, period)
    else:
        print(f"Running Standard Chan Strategy for {symbol} {period}...")
        strat = ChanStrategy(symbol, period)

    signals = strat.run(bars)
    
    # Save signals (Reuse existing save method if possible, or adapt)
    if hasattr(strat, 'save_signals'):
        strat.save_signals(signals)
    else:
        # Fallback for PureChanStrategy if I haven't added it yet
        # Reuse ChanStrategy's logic
        saver = ChanStrategy(symbol, period)
        saver.save_signals(signals)

    return len(signals)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="KQ.m@SHFE.rb")
    parser.add_argument("--period", default="30m")
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--source", default="tq", help="tq or db")
    
    args = parser.parse_args()
    run_strategy(args.symbol, args.period, args.count, args.source)
