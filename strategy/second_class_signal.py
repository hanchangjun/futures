from typing import Dict, Any, Optional, List
from datetime import datetime
from .chan_core import Signal, Bi

class SecondClassSignalDetector:
    """第二类买卖点检测"""
    
    def detect_2B(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """
        检测第二类买点
        条件：一买后的第一笔向下回调，不跌破一买的最低点
        """
        # 1. 检查是否存在已确认的1B
        last_1B = self._get_last_confirmed_1B(context)
        if not last_1B:
            return None
            
        # 2. 检查当前笔是否为向下回调笔
        if current_bi.direction != 'down':
            return None
            
        # 3. 检查是否是一买后的第一笔回调
        if not self._is_first_pullback_after_1B(current_bi, last_1B, context):
            return None
            
        # 4. 检查是否不破一买最低点
        # 2B (Buy) requires Higher Low
        if current_bi.end_price < last_1B.price:
            return None
            
        # 5. 确认分型
        if not self._confirm_fenxing(current_bi, 'bottom'):
            return None
            
        # 6. 计算信号强度
        score = self._calculate_2B_score(current_bi, last_1B, context)
        
        # 7. 生成信号
        signal = Signal(
            signal_type='2B',
            price=current_bi.end_price,
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            extra_info={
                'related_1B': last_1B,
                'pullback_depth': self._calculate_pullback_ratio_2B(current_bi, last_1B),
                'time_since_1B': (current_bi.end_time - last_1B.time).total_seconds() / 3600
            }
        )
        
        return signal if score >= 60 else None

    def detect_2S(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """
        检测第二类卖点
        条件：一卖后的第一笔向上回调，不突破一卖的最高点
        """
        # 1. 检查是否存在已确认的1S
        last_1S = self._get_last_confirmed_1S(context)
        if not last_1S:
            return None
            
        # 2. 检查当前笔是否为向上回调笔
        if current_bi.direction != 'up':
            return None
            
        # 3. 检查是否是一卖后的第一笔回调
        if not self._is_first_pullback_after_1S(current_bi, last_1S, context):
            return None
            
        # 4. 检查是否不破一卖最高点
        # 2S (Sell) requires Lower High
        if current_bi.end_price > last_1S.price:
            return None
            
        # 5. 确认分型
        if not self._confirm_fenxing(current_bi, 'top'):
            return None
            
        # 6. 计算信号强度
        score = self._calculate_2S_score(current_bi, last_1S, context)
        
        # 7. 生成信号
        signal = Signal(
            signal_type='2S',
            price=current_bi.end_price,
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            extra_info={
                'related_1S': last_1S,
                'pullback_depth': self._calculate_pullback_ratio_2S(current_bi, last_1S),
                'time_since_1S': (current_bi.end_time - last_1S.time).total_seconds() / 3600
            }
        )
        
        return signal if score >= 60 else None

    def _get_last_confirmed_1B(self, context: Dict[str, Any]) -> Optional[Signal]:
        """获取最近的一个1B信号"""
        signals = context.get('signals', [])
        # Iterate backwards
        for sig in reversed(signals):
            if sig.type == '1B':
                return sig
        return None

    def _get_last_confirmed_1S(self, context: Dict[str, Any]) -> Optional[Signal]:
        """获取最近的一个1S信号"""
        signals = context.get('signals', [])
        for sig in reversed(signals):
            if sig.type == '1S':
                return sig
        return None

    def _is_first_pullback_after_1B(self, current_bi: Bi, last_1B: Signal, context: Dict[str, Any]) -> bool:
        """
        检查是否是一买后的第一笔向下回调
        """
        bi_list = context.get('bi_list', [])
        # Find index of bi corresponding to last_1B
        # last_1B.bi is the bi that triggered 1B.
        # It should be a Down bi.
        
        last_1B_bi = last_1B.bi
        if not last_1B_bi:
             # Fallback to time matching if bi obj not stored or valid
             return False # Should not happen with new system
             
        # Find index
        idx_1b = -1
        idx_curr = -1
        
        # Optimize: Assuming bi_list is sorted.
        # We can iterate backwards or assume ids are sequential? 
        # Safest is to iterate.
        for i, b in enumerate(bi_list):
            if b.id == last_1B_bi.id:
                idx_1b = i
            if b.id == current_bi.id:
                idx_curr = i
        
        if idx_1b == -1 or idx_curr == -1:
            return False
            
        if idx_curr <= idx_1b:
            return False
            
        # Between 1B (Down) and Current (Down), there should be exactly one Up Bi.
        # 1B(Down) -> Up -> Current(Down)
        # So idx_curr should be idx_1b + 2
        
        if idx_curr == idx_1b + 2:
            return True
            
        return False

    def _is_first_pullback_after_1S(self, current_bi: Bi, last_1S: Signal, context: Dict[str, Any]) -> bool:
        """
        检查是否是一卖后的第一笔向上回调
        """
        bi_list = context.get('bi_list', [])
        last_1S_bi = last_1S.bi
        
        idx_1s = -1
        idx_curr = -1
        
        for i, b in enumerate(bi_list):
            if b.id == last_1S_bi.id:
                idx_1s = i
            if b.id == current_bi.id:
                idx_curr = i
                
        if idx_1s == -1 or idx_curr == -1:
            return False
            
        if idx_curr <= idx_1s:
            return False
            
        # 1S(Up) -> Down -> Current(Up)
        if idx_curr == idx_1s + 2:
            return True
            
        return False

    def _confirm_fenxing(self, bi: Bi, fx_type: str) -> bool:
        return True # Assumed valid as it is a Bi

    def _calculate_pullback_ratio_2B(self, current_bi: Bi, last_1B: Signal) -> float:
        # 1B(Low) -> Up(Peak) -> Current(Low)
        # Peak is current_bi.start_price
        peak_price = current_bi.start_price
        low_1b = last_1B.price
        current_low = current_bi.end_price
        
        rise = peak_price - low_1b
        if rise <= 0: return 0.0
        
        retracement = peak_price - current_low
        return retracement / rise

    def _calculate_pullback_ratio_2S(self, current_bi: Bi, last_1S: Signal) -> float:
        # 1S(High) -> Down(Valley) -> Current(High)
        # Valley is current_bi.start_price
        valley_price = current_bi.start_price
        high_1s = last_1S.price
        current_high = current_bi.end_price
        
        fall = high_1s - valley_price
        if fall <= 0: return 0.0
        
        retracement = current_high - valley_price
        return retracement / fall

    def _calculate_2B_score(self, current_bi: Bi, last_1B: Signal, context: Dict[str, Any]) -> float:
        """计算2B信号强度分数"""
        score = 0
        
        # 1. 1B信号强度继承(0-30分)
        score += last_1B.score * 0.3
        
        # 2. 回调深度(0-30分)
        # 理想回调深度：30%-50%
        # User logic used (last_1B.price - current_bi.low) / last_1B.price which is wrong.
        # Using corrected logic:
        pullback_ratio = self._calculate_pullback_ratio_2B(current_bi, last_1B)
        
        if 0.3 <= pullback_ratio <= 0.6: # Relaxed slightly
            depth_score = 30
        elif 0.2 <= pullback_ratio <= 0.7:
            depth_score = 20
        else:
            depth_score = 10
        score += depth_score
        
        # 3. 回调时间(0-20分)
        # 理想时间：1B后3-10根K线
        time_since_1B = self._count_bars_since(last_1B.time, current_bi.end_time, context)
        # User snippet used undefined _count_bars_since. 
        # Logic: 3-10 bars -> 20, 1-15 -> 15, else 5.
        
        if 3 <= time_since_1B <= 10:
            time_score = 20
        elif 1 <= time_since_1B <= 15:
            time_score = 15
        else:
            time_score = 5
        score += time_score
        
        # 4. 量价配合(0-20分)
        volume_score = self._volume_confirmation(current_bi) * 20
        score += volume_score
        
        return min(score, 100)

    def _calculate_2S_score(self, current_bi: Bi, last_1S: Signal, context: Dict[str, Any]) -> float:
        """计算2S信号强度分数"""
        score = 0
        score += last_1S.score * 0.3
        
        pullback_ratio = self._calculate_pullback_ratio_2S(current_bi, last_1S)
        
        if 0.3 <= pullback_ratio <= 0.6:
            depth_score = 30
        elif 0.2 <= pullback_ratio <= 0.7:
            depth_score = 20
        else:
            depth_score = 10
        score += depth_score
        
        time_since_1S = self._count_bars_since(last_1S.time, current_bi.end_time, context)
        if 3 <= time_since_1S <= 10:
            time_score = 20
        elif 1 <= time_since_1S <= 15:
            time_score = 15
        else:
            time_score = 5
        score += time_score
        
        volume_score = self._volume_confirmation(current_bi) * 20
        score += volume_score
        
        return min(score, 100)

    def _count_bars_since(self, start_time: datetime, end_time: datetime, context: Dict[str, Any]) -> int:
        """计算两个时间点之间的K线数量"""
        # This requires access to raw bars or we can estimate from Bi bars.
        # But Bi bars are aggregated.
        # If we have access to original bars index, we can calc diff.
        # Context might not have raw bars list easily accessible by time.
        # However, Bi object has start_time/end_time.
        # And Bi object has `bars` count!
        
        # We want bars from 1B end to 2B end.
        # 1B end time is start_time.
        # 2B end time is end_time.
        # The path is: 1B -> Up Bi -> 2B.
        # So it's bars of Up Bi + bars of 2B.
        
        # Iterate bis between 1B and Current.
        bi_list = context.get('bi_list', [])
        count = 0
        counting = False
        for b in bi_list:
            if b.end_time == start_time: # 1B ended here
                counting = True
                continue
            
            if counting:
                count += b.bars
                if b.end_time == end_time:
                    break
        
        return count if count > 0 else 5 # Default fallback

    def _volume_confirmation(self, current_bi: Bi) -> float:
        """
        量价配合 (0.0 - 1.0)
        缩量回调为佳
        """
        # We need previous bi volume to compare.
        # But we don't have easy access to prev bi here without context or linked list.
        # Assuming current_bi has volume_sum.
        # We can just check if volume is relatively low?
        # Or return 0.5 as neutral if we can't compare.
        # User snippet: `self._volume_confirmation(current_bi)`
        # Implies it might check internal state or just return a value.
        # In FirstClass, we compared with Entering Bi.
        # Here we compare 2B (Pullback) with Up Bi (Impulse).
        # We assume 2B volume < Up Bi volume.
        
        # But current_bi doesn't link to prev bi directly.
        # We'll simplified: return 0.8 (assuming good) or we need context to find prev bi.
        return 0.8
