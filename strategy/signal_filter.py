from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

class SignalFilterAndConfirmer:
    """信号过滤器与确认器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.filter_rules = self._build_filter_rules()
    
    def _build_filter_rules(self):
        """构建过滤规则集合"""
        return {
            'hard': self._check_hard_conditions,
            'exclusion': self._check_exclusion_conditions,
            'score': lambda s, c: s.score >= self.config.get('min_signal_score', 60),
            'market': self._check_market_state,
            'risk': self._risk_management_check
        }
    
    def filter_signal(self, signal, market_context: Dict[str, Any]) -> bool:
        """
        综合过滤信号
        """
        # 1. 必须满足的硬性条件
        if not self._check_hard_conditions(signal, market_context):
            return False
            
        # 2. 排除条件检查
        if not self._check_exclusion_conditions(signal, market_context):
            return False
            
        # 3. 质量评分过滤
        if signal.score < self.config.get('min_signal_score', 60):
            return False
            
        # 4. 市场状态过滤
        if not self._check_market_state(signal, market_context):
            return False
            
        # 5. 风险管理过滤
        if not self._risk_management_check(signal, market_context):
            return False
            
        return True
    
    def confirm_signal(self, signal, market_context: Dict[str, Any]) -> bool:
        """
        信号确认机制
        通常在信号触发后的后续K线进行确认
        """
        confirmation_methods = {
            '1B': self._confirm_1B,
            '2B': self._confirm_2B,
            '3B': self._confirm_3B,
            '1S': self._confirm_1S,
            '2S': self._confirm_2S,
            '3S': self._confirm_3S,
        }
        
        if signal.type in confirmation_methods:
            return confirmation_methods[signal.type](signal, market_context)
            
        return False
    
    # --- Filter Logic ---
    
    def _check_hard_conditions(self, signal, context) -> bool:
        """硬性条件：如数据完整性、核心结构有效性"""
        if not signal.bi or not signal.zhongshu:
            return False
        return True
        
    def _check_exclusion_conditions(self, signal, context) -> bool:
        """
        检查是否满足排除条件
        返回 True 表示通过检查（即不被排除，保留）
        返回 False 表示命中排除条件（即被排除，丢弃）
        """
        # 默认通过，没有命中排除条件
        return True 
        
    def _check_market_state(self, signal, context) -> bool:
        """市场状态：如ATR波动率是否足够"""
        # 示例：如果波动率太低，可能不交易
        return True
        
    def _risk_management_check(self, signal, context) -> bool:
        """风控检查：如止损距离是否过大"""
        # 示例：Stop Loss > 2% 则放弃
        return True

    # --- Confirmation Logic (Buy) ---

    def _confirm_1B(self, signal, market_context):
        """1B确认条件"""
        confirmation_conditions = [
            # 条件1：价格不再创新低 (当前价格 > 信号价格/底分型底)
            lambda: market_context.get('current_price', 0) > signal.price,
            
            # 条件2：出现底分型确认 (假设 context 提供了分型信息或通过 helper 检查)
            lambda: self._is_bottom_fenxing_confirmed(signal, market_context),
            
            # 条件3：成交量放大
            lambda: self._volume_increase_confirmation(signal, market_context),
            
            # 条件4：次级别出现买点
            lambda: self._has_lower_level_buy_signal(signal, market_context)
        ]
        
        # 满足至少3个条件
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 3
        
    def _confirm_2B(self, signal, market_context):
        """2B确认条件"""
        # 2B是回踩不破低，确认需要：
        # 1. 回踩结束（底分型）
        # 2. 价格开始回升
        confirmation_conditions = [
            lambda: market_context.get('current_price', 0) > signal.price,
            lambda: self._is_bottom_fenxing_confirmed(signal, market_context),
            lambda: self._volume_shrink_during_pullback(signal, market_context) # 回调缩量
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    def _confirm_3B(self, signal, market_context):
        """3B确认条件"""
        confirmation_conditions = [
            # 条件1：价格不再跌破回撤低点
            lambda: market_context.get('current_price', 0) > signal.price,
            
            # 条件2：出现次级别买点
            lambda: self._has_lower_level_buy_signal(signal, market_context),
            
            # 条件3：成交量配合 (离开放量，回撤缩量 - 已经在Detector打分里了，这里确认后续放量?)
            lambda: self._volume_pattern_confirmation(signal, market_context),
            
            # 条件4：突破前高 (确认趋势延续)
            lambda: self._break_previous_high(signal, market_context)
        ]
        
        # 满足至少2个条件
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    # --- Confirmation Logic (Sell) ---

    def _confirm_1S(self, signal, market_context):
        """1S确认条件"""
        confirmation_conditions = [
            # 条件1：价格不再创新高
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            
            # 条件2：出现顶分型确认
            lambda: self._is_top_fenxing_confirmed(signal, market_context),
            
            # 条件3：成交量 (背驰通常缩量，或者反转放量?) -> 1S通常是背驰，量价背离
            # 这里简单用"成交量确认"逻辑
            lambda: self._volume_increase_confirmation(signal, market_context), 
            
            # 条件4：次级别出现卖点
            lambda: self._has_lower_level_sell_signal(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 3

    def _confirm_2S(self, signal, market_context):
        """2S确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            lambda: self._is_top_fenxing_confirmed(signal, market_context),
            lambda: self._volume_shrink_during_pullback(signal, market_context) # 反抽缩量
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    def _confirm_3S(self, signal, market_context):
        """3S确认条件"""
        confirmation_conditions = [
            # 条件1：价格不再突破反抽高点
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            
            # 条件2：次级别卖点
            lambda: self._has_lower_level_sell_signal(signal, market_context),
            
            # 条件3：成交量配合
            lambda: self._volume_pattern_confirmation(signal, market_context),
            
            # 条件4：跌破前低
            lambda: self._break_previous_low(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    # --- Helper Methods ---
    
    def _is_bottom_fenxing_confirmed(self, signal, context) -> bool:
        """检查底分型是否确认"""
        # 实际逻辑需要访问K线数据
        return context.get('fenxing_confirmed', True) # Default True for now
        
    def _is_top_fenxing_confirmed(self, signal, context) -> bool:
        """检查顶分型是否确认"""
        return context.get('fenxing_confirmed', True)

    def _volume_increase_confirmation(self, signal, context) -> bool:
        """成交量放大确认"""
        return context.get('volume_increase', True)
        
    def _volume_shrink_during_pullback(self, signal, context) -> bool:
        """回调缩量确认"""
        return context.get('volume_shrink', True)

    def _volume_pattern_confirmation(self, signal, context) -> bool:
        """特定形态成交量配合"""
        return True

    def _has_lower_level_buy_signal(self, signal, context) -> bool:
        """次级别买点"""
        return context.get('lower_level_buy', False)
        
    def _has_lower_level_sell_signal(self, signal, context) -> bool:
        """次级别卖点"""
        return context.get('lower_level_sell', False)

    def _break_previous_high(self, signal, context) -> bool:
        """突破前高"""
        # 对于3B，前高是离开笔的高点
        # signal.extra_info['leave_bi'].high
        if 'leave_bi' in signal.extra_info:
            prev_high = signal.extra_info['leave_bi'].high
            return context.get('current_price', 0) > prev_high
        return False
        
    def _break_previous_low(self, signal, context) -> bool:
        """跌破前低"""
        # 对于3S，前低是离开笔的低点
        if 'leave_bi' in signal.extra_info:
            prev_low = signal.extra_info['leave_bi'].low
            return context.get('current_price', float('inf')) < prev_low
        return False
