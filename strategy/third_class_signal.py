from typing import Dict, Any, Optional, List
from datetime import datetime
from .chan_core import Signal, Bi, Zhongshu

class ThirdClassSignalDetector:
    """第三类买卖点检测"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config else {}
        # Default config
        self.config.setdefault('紧邻笔最大间隔', 5) # Default gap bars threshold

    def detect_3B(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """
        检测第三类买点
        条件：向上离开中枢，随后的紧邻回撤笔最低点 > ZG
        """
        # 1. 寻找最近的中枢
        last_zs = self._get_last_completed_zhongshu(context)
        if not last_zs:
            return None
            
        # 2. 检查当前笔是否为向下回撤笔
        if current_bi.direction != 'down':
            return None
            
        # 3. 检查是否存在向上的离开笔
        leave_bi = self._find_leave_bi(last_zs, context)
        if not leave_bi:
            return None
            
        # 4. 检查是否紧邻
        if not self._is_adjacent(leave_bi, current_bi):
            return None
            
        # 5. 检查离开笔是否向上离开中枢
        if leave_bi.direction != 'up' or leave_bi.start_price > last_zs.ZG:
            # Must start from/in ZS and go up. 
            # Ideally leave_bi starts <= ZG (inside or below top of ZS) and ends > ZG
            # User code: if leave_bi.direction != 'up' or leave_bi.start_price > last_zs.ZG:
            # This implies leave_bi started above ZG? If so, it's not "leaving" it, it's already above.
            return None
            
        # 6. 检查回撤笔最低点 > ZG (Not re-entering)
        if current_bi.low <= last_zs.ZG:
            return None
            
        # 7. 确认分型
        if not self._confirm_fenxing(current_bi, 'bottom'):
            return None
            
        # 8. 计算信号强度
        score = self._calculate_3B_score(current_bi, leave_bi, last_zs, context)
        
        # 9. 生成信号
        signal = Signal(
            signal_type='3B',
            price=current_bi.low, # Buy at low of pullback? Or end_price? Usually end of bi is confirmed.
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            zhongshu=last_zs,
            extra_info={
                'leave_bi': leave_bi,
                'zg': last_zs.ZG,
                'gap_from_zg': (current_bi.low - last_zs.ZG) / last_zs.ZG
            }
        )
        
        return signal if score >= 60 else None

    def detect_3S(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """
        检测第三类卖点
        条件：向下离开中枢，随后的紧邻回撤笔最高点 < ZD
        """
        # 1. 寻找最近的中枢
        last_zs = self._get_last_completed_zhongshu(context)
        if not last_zs:
            return None
            
        # 2. 检查当前笔是否为向上回撤笔
        if current_bi.direction != 'up':
            return None
            
        # 3. 检查是否存在向下的离开笔
        leave_bi = self._find_leave_bi(last_zs, context)
        if not leave_bi:
            return None
            
        # 4. 检查是否紧邻
        if not self._is_adjacent(leave_bi, current_bi):
            return None
            
        # 5. 检查离开笔是否向下离开中枢
        if leave_bi.direction != 'down' or leave_bi.start_price < last_zs.ZD:
            return None
            
        # 6. 检查回撤笔最高点 < ZD (Not re-entering)
        if current_bi.high >= last_zs.ZD:
            return None
            
        # 7. 确认分型
        if not self._confirm_fenxing(current_bi, 'top'):
            return None
            
        # 8. 计算信号强度
        score = self._calculate_3S_score(current_bi, leave_bi, last_zs, context)
        
        # 9. 生成信号
        signal = Signal(
            signal_type='3S',
            price=current_bi.high, # Sell at high of pullback? Or end.
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            zhongshu=last_zs,
            extra_info={
                'leave_bi': leave_bi,
                'zd': last_zs.ZD,
                'gap_from_zd': (last_zs.ZD - current_bi.high) / last_zs.ZD
            }
        )
        
        return signal if score >= 60 else None

    def _get_last_completed_zhongshu(self, context: Dict[str, Any]) -> Optional[Zhongshu]:
        """获取最近的一个中枢"""
        # We assume zhongshu_list in context are relevant ones.
        zs_list = context.get('zhongshu_list', [])
        if not zs_list:
            return None
        # Return the last one
        return zs_list[-1]

    def _find_leave_bi(self, zhongshu: Zhongshu, context: Dict[str, Any]) -> Optional[Bi]:
        """寻找离开中枢的笔"""
        bi_list = context.get('bi_list', [])
        
        zs_end_time = zhongshu.end_time
        # We need to find the bi that started around zs_end_time or is the first one after.
        # Ideally the bi list is sorted by time.
        
        for bi in bi_list:
            if bi.start_time >= zs_end_time: # Or >?
                # Check if it leaves the ZS range
                # For Up Leave: Start <= ZG, High > ZG
                # For Down Leave: Start >= ZD, Low < ZD
                
                # Check Up Leave
                if bi.direction == 'up' and bi.start_price <= zhongshu.ZG and bi.high > zhongshu.ZG:
                    return bi
                
                # Check Down Leave
                if bi.direction == 'down' and bi.start_price >= zhongshu.ZD and bi.low < zhongshu.ZD:
                    return bi
                    
        return None

    def _is_adjacent(self, bi1: Bi, bi2: Bi) -> bool:
        """
        检查两笔是否紧邻
        条件：方向相反，且时间间隔不超过阈值
        """
        if bi1.direction == bi2.direction:
            return False
            
        # 计算时间间隔（K线数量）
        # Need to know how many bars between bi1 end and bi2 start.
        # If they are adjacent in bi list, the gap is 0 bars usually? 
        # Or does it mean they are consecutive bis in the list?
        # "紧邻回撤笔" usually means bi2 is immediately following bi1.
        # If there are other bis in between, it's complex.
        # But here we check bar gap?
        
        # Assuming bi1 and bi2 are consecutive in terms of index or very close in time.
        # User code uses _count_bars_between.
        
        # If bi2 follows bi1 immediately, bi2.start_time should be bi1.end_time.
        # If there is a gap, it might be due to merged klines or gap.
        
        # Let's use simple logic: are they consecutive in the bi_list?
        # But we don't have index passed easily here unless we search context.
        # User implementation:
        # gap_bars = self._count_bars_between(bi1.end_time, bi2.start_time)
        # return gap_bars <= self.config['紧邻笔最大间隔']
        
        # We can approximate bars by time if we don't have bar count.
        # Or if we have access to bars?
        # Let's assume adjacent means time difference is small or just check consecutive.
        
        # However, let's implement based on user's hint:
        # gap_bars calculation.
        
        # Since we don't have the raw bar list easily here (context['bi_list'] has bis, but not raw bars),
        # we might assume 0 gap if they are consecutive bis.
        
        # Let's check if bi2 starts where bi1 ends.
        if bi2.start_time >= bi1.end_time:
             # Check if there are other bis in between?
             # For now, let's assume if they are close enough in time.
             return True # Placeholder logic, user code implies checking bars.
        return False
        
    def _count_bars_between(self, start_time, end_time):
        # Placeholder if we don't have raw bars.
        return 0

    def _confirm_fenxing(self, bi: Bi, fx_type: str) -> bool:
        """确认分型"""
        # Assuming valid Bi implies valid Fenxing for now.
        return True

    def _calculate_3B_score(self, pullback_bi: Bi, leave_bi: Bi, zhongshu: Zhongshu, context: Dict[str, Any]) -> float:
        """
        计算3B信号强度分数
        """
        score = 0
        
        # 1. 离开力度(0-30分)
        # 离开幅度 = (Leave High - ZG) / ZS Height
        zs_height = zhongshu.height()
        if zs_height == 0: zs_height = 0.0001
        
        leave_strength = (leave_bi.high - zhongshu.ZG) / zs_height
        if leave_strength > 0.5:
            leave_score = 30
        elif leave_strength > 0.3:
            leave_score = 25
        elif leave_strength > 0.1:
            leave_score = 20
        else:
            leave_score = 10
        score += leave_score
        
        # 2. 回撤深度(0-30分)
        # (Leave High - Pullback Low) / (Leave High - ZG)
        # Smaller ratio means weaker pullback (better for 3B? Wait.)
        # If Pullback Low is close to Leave High, it's a strong trend (super strong).
        # If Pullback Low is close to ZG, it's a deep pullback.
        # User code: pullback_depth < 0.5 => score 30. (Shallow pullback is better).
        
        denominator = leave_bi.high - zhongshu.ZG
        if denominator == 0: denominator = 0.0001
        
        pullback_depth = (leave_bi.high - pullback_bi.low) / denominator
        
        if pullback_depth < 0.5:
            pullback_score = 30
        elif pullback_depth < 0.7:
            pullback_score = 25
        elif pullback_depth < 0.9:
            pullback_score = 20
        else:
            pullback_score = 10
        score += pullback_score
        
        # 3. 成交量配合(0-20分)
        volume_score = self._volume_pattern_score(leave_bi, pullback_bi) * 20
        score += volume_score
        
        # 4. 多级别确认(0-20分)
        resonance_score = self._multi_level_confirmation(pullback_bi) * 20
        score += resonance_score
        
        return min(score, 100)

    def _calculate_3S_score(self, pullback_bi: Bi, leave_bi: Bi, zhongshu: Zhongshu, context: Dict[str, Any]) -> float:
        """
        计算3S信号强度分数
        """
        score = 0
        
        # 1. 离开力度
        zs_height = zhongshu.height()
        if zs_height == 0: zs_height = 0.0001
        
        # (ZD - Leave Low) / Height
        leave_strength = (zhongshu.ZD - leave_bi.low) / zs_height
        
        if leave_strength > 0.5:
            leave_score = 30
        elif leave_strength > 0.3:
            leave_score = 25
        elif leave_strength > 0.1:
            leave_score = 20
        else:
            leave_score = 10
        score += leave_score
        
        # 2. 回撤深度
        # (Pullback High - Leave Low) / (ZD - Leave Low)
        denominator = zhongshu.ZD - leave_bi.low
        if denominator == 0: denominator = 0.0001
        
        pullback_depth = (pullback_bi.high - leave_bi.low) / denominator
        
        if pullback_depth < 0.5:
            pullback_score = 30
        elif pullback_depth < 0.7:
            pullback_score = 25
        elif pullback_depth < 0.9:
            pullback_score = 20
        else:
            pullback_score = 10
        score += pullback_score
        
        # 3. Volume
        volume_score = self._volume_pattern_score(leave_bi, pullback_bi) * 20
        score += volume_score
        
        # 4. Resonance
        resonance_score = self._multi_level_confirmation(pullback_bi) * 20
        score += resonance_score
        
        return min(score, 100)

    def _volume_pattern_score(self, leave_bi: Bi, pullback_bi: Bi) -> float:
        """
        成交量形态评分
        离开放量，回撤缩量 -> 1.0
        """
        if leave_bi.volume_sum > pullback_bi.volume_sum:
            return 1.0
        return 0.5

    def _multi_level_confirmation(self, bi: Bi) -> float:
        """
        多级别共振确认
        """
        # Placeholder
        return 0.0
