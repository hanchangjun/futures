from typing import Dict, Any, List, Optional
import math
import numpy as np
from .chan_core import Signal, Bi, Zhongshu

class FirstClassSignalDetector:
    """第一类买卖点检测"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = {
            '趋势中枢数': 2,
            'MACD背驰阈值': 0.3,
            '螺纹钢特性': {}
        }
        if config:
            self.config.update(config)

    def detect_1B(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """
        检测第一类买点
        条件：创新低 + MACD背驰
        """
        # 0. 必须是向下笔
        if current_bi.direction != 'down':
            return None

        # 1. 检查是否处于下跌趋势
        if not self._is_down_trend(context):
            return None
            
        # 2. 检查是否创新低
        if not self._is_new_low(current_bi, context):
            return None
            
        # 3. 检查MACD背驰
        if not self._check_macd_divergence(current_bi, context):
            return None
            
        # 4. 确认分型
        if not self._confirm_fenxing(current_bi, 'bottom'):
            return None
            
        # 5. 计算信号强度
        score = self._calculate_1B_score(current_bi, context)
        
        # 6. 生成信号
        signal = Signal(
            signal_type='1B',
            price=current_bi.end_price, # Use end_price (low)
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            extra_info={
                'trend_strength': self._trend_strength(context),
                'divergence_level': self._divergence_level(current_bi, context),
                'volume_confirmation': self._volume_confirmation(current_bi, context)
            }
        )
        
        return signal if score >= 60 else None

    def detect_1S(self, current_bi: Bi, context: Dict[str, Any]) -> Optional[Signal]:
        """检测第一类卖点（对称逻辑）"""
        # 0. 必须是向上笔
        if current_bi.direction != 'up':
            return None

        # 1. 检查是否处于上涨趋势
        if not self._is_up_trend(context):
            return None
            
        # 2. 检查是否创新高
        if not self._is_new_high(current_bi, context):
            return None
            
        # 3. 检查MACD背驰
        if not self._check_macd_divergence(current_bi, context):
            return None
            
        # 4. 确认分型
        if not self._confirm_fenxing(current_bi, 'top'):
            return None
            
        # 5. 计算信号强度
        score = self._calculate_1S_score(current_bi, context)
        
        # 6. 生成信号
        signal = Signal(
            signal_type='1S',
            price=current_bi.end_price, # Use end_price (high)
            time=current_bi.end_time,
            score=score,
            bi=current_bi,
            extra_info={
                'trend_strength': self._trend_strength(context),
                'divergence_level': self._divergence_level(current_bi, context),
                'volume_confirmation': self._volume_confirmation(current_bi, context)
            }
        )
        
        return signal if score >= 60 else None

    def _is_down_trend(self, context):
        """
        判断是否处于下跌趋势
        条件：至少两个依次向下的同级别中枢
        """
        zs_list = context.get('zhongshu_list', [])
        if len(zs_list) < self.config['趋势中枢数']:
            return False
            
        # 检查最后两个中枢是否依次下降
        # 注意：context可能包含所有中枢，我们需要看最近的。
        # 假设zs_list是按时间排序的
        last_zs = zs_list[-1]
        prev_zs = zs_list[-2]
        
        if last_zs.DD >= prev_zs.DD: # 简单判断：新中枢的低点比旧中枢低 (or ZG/ZD comparison)
            # 标准缠论：ZD_new < ZD_old (Loose) or GG_new < DD_old (Strict)
            # User code used: zs_list[i].DD >= zs_list[i-1].DD return False
            return False
            
        return True

    def _is_up_trend(self, context):
        """判断是否处于上涨趋势"""
        zs_list = context.get('zhongshu_list', [])
        if len(zs_list) < self.config['趋势中枢数']:
            return False
            
        last_zs = zs_list[-1]
        prev_zs = zs_list[-2]
        
        # 依次上升
        if last_zs.GG <= prev_zs.GG:
            return False
            
        return True

    def _is_new_low(self, current_bi, context):
        """检查是否创出新低"""
        zs_list = context.get('zhongshu_list', [])
        if not zs_list:
            return False
            
        last_zs = zs_list[-1]
        # 比较笔的低点和中枢的波动低点(DD)
        # current_bi is 'down', so check its end_price (low)
        return current_bi.low < last_zs.DD

    def _is_new_high(self, current_bi, context):
        """检查是否创出新高"""
        zs_list = context.get('zhongshu_list', [])
        if not zs_list:
            return False
            
        last_zs = zs_list[-1]
        return current_bi.high > last_zs.GG

    def _check_macd_divergence(self, current_bi, context):
        """
        检查MACD背驰
        比较：最后一段离开中枢的笔 vs 前一段进入中枢的笔
        """
        leave_bi = current_bi
        enter_bi = self._find_enter_bi(context)
        
        if not enter_bi:
            return False
            
        # 计算MACD面积
        leave_area = self._calculate_macd_area(leave_bi)
        enter_area = self._calculate_macd_area(enter_bi)
        
        # 检查背驰：离开段面积 < 进入段面积 * (1 - 阈值)
        threshold = self.config['MACD背驰阈值']
        # 注意：MACD面积通常取绝对值比较
        area_divergence = leave_area < enter_area * (1 - threshold)
        
        # 检查黄白线高度 (Diff Peak)
        leave_macd_peak = self._get_macd_peak(leave_bi)
        enter_macd_peak = self._get_macd_peak(enter_bi)
        
        # Peak comparison
        line_divergence = leave_macd_peak < enter_macd_peak * (1 - threshold/2)
        
        return area_divergence or line_divergence

    def _find_enter_bi(self, context) -> Optional[Bi]:
        """寻找进入中枢的笔"""
        zs_list = context.get('zhongshu_list', [])
        if not zs_list:
            return None
        
        last_zs = zs_list[-1]
        if not last_zs.bi_list:
            return None
            
        # 中枢的第一笔
        first_bi_in_zs = last_zs.bi_list[0]
        
        # 进入笔是中枢第一笔的前一笔
        # 我们需要从 context['bi_list'] 中查找
        all_bis = context.get('bi_list', [])
        
        # Find index by ID or reference
        try:
            # Assuming bi.id is sequential or we can find index
            idx = -1
            for i, b in enumerate(all_bis):
                if b.id == first_bi_in_zs.id:
                    idx = i
                    break
            
            if idx > 0:
                return all_bis[idx - 1]
        except:
            pass
            
        return None

    def _calculate_macd_area(self, bi: Bi) -> float:
        """计算笔的MACD面积 (绝对值)"""
        if bi.macd_data and 'sum' in bi.macd_data:
            return bi.macd_data['sum']
        return 0.0

    def _get_macd_peak(self, bi: Bi) -> float:
        """获取笔的MACD双线峰值 (绝对值)"""
        if bi.macd_data and 'diff_peak' in bi.macd_data:
            return bi.macd_data['diff_peak']
        return 0.0

    def _confirm_fenxing(self, bi: Bi, fx_type: str) -> bool:
        """
        确认分型
        实际在Bi生成时已经确认了顶底分型，这里可以再次校验或加入额外逻辑
        """
        # Bi本身就是由顶底分型定义的，所以默认是成立的
        # 这里可以加入 '分型停顿' 逻辑，或者 '包含关系处理后的分型'
        # 简单起见，返回True，因为输入已经是Bi了
        return True

    def _calculate_1B_score(self, current_bi: Bi, context: Dict[str, Any]) -> float:
        """计算1B信号强度分数(0-100)"""
        score = 0
        
        # 1. 趋势强度(0-30分)
        trend_score = min(30, self._trend_strength(context) * 30)
        score += trend_score
        
        # 2. 背驰强度(0-40分)
        divergence_score = self._divergence_level(current_bi, context) * 40
        score += divergence_score
        
        # 3. 量价配合(0-20分)
        volume_score = self._volume_confirmation(current_bi, context) * 20
        score += volume_score
        
        # 4. 多级别共振(0-10分)
        resonance_score = self._multi_level_resonance(current_bi) * 10
        score += resonance_score
        
        return min(score, 100)

    def _calculate_1S_score(self, current_bi: Bi, context: Dict[str, Any]) -> float:
        """计算1S信号强度分数(0-100)"""
        # Logic is identical to 1B for scoring structure, just context differs
        return self._calculate_1B_score(current_bi, context)

    def _trend_strength(self, context) -> float:
        """
        趋势强度 (0.0 - 1.0)
        基于中枢数量、深度等
        """
        zs_list = context.get('zhongshu_list', [])
        count = len(zs_list)
        if count >= 3: return 1.0
        if count == 2: return 0.8
        return 0.5

    def _divergence_level(self, current_bi: Bi, context: Dict[str, Any]) -> float:
        """
        背驰程度 (0.0 - 1.0)
        """
        leave_bi = current_bi
        enter_bi = self._find_enter_bi(context)
        if not enter_bi: return 0.5
        
        leave_area = self._calculate_macd_area(leave_bi)
        enter_area = self._calculate_macd_area(enter_bi)
        
        if enter_area == 0: return 0.0
        
        ratio = leave_area / enter_area
        # ratio < 1 means divergence. smaller is better.
        # If ratio is 0.5, divergence is strong.
        # If ratio is 0.9, weak.
        # If ratio > 1, no divergence (should have been filtered, but return 0)
        
        if ratio >= 1.0: return 0.0
        
        # Map 1.0 -> 0.0, 0.5 -> 0.8, 0.0 -> 1.0
        divergence = 1.0 - ratio
        return min(1.0, divergence * 1.2) # Boost slightly

    def _volume_confirmation(self, current_bi: Bi, context: Dict[str, Any]) -> float:
        """
        量价配合 (0.0 - 1.0)
        背驰段成交量萎缩为佳
        """
        leave_bi = current_bi
        enter_bi = self._find_enter_bi(context)
        if not enter_bi: return 0.5
        
        v_leave = leave_bi.volume_sum
        v_enter = enter_bi.volume_sum
        
        if v_enter == 0: return 0.5
        
        ratio = v_leave / v_enter
        if ratio < 0.8: return 1.0
        if ratio < 1.0: return 0.7
        return 0.3

    def _multi_level_resonance(self, current_bi: Bi) -> float:
        """
        多级别共振 (0.0 - 1.0)
        Placeholder for advanced multi-timeframe check.
        """
        return 0.5
