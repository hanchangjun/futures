"""
信号过滤器与确认器 - 使用统一配置系统
"""
from typing import Dict, Any
from datetime import datetime

from config import get_filter_config, get_logger
from strategy.signal_scorer import ScorableSignal, SignalType

logger = get_logger(__name__)


class SignalFilter:
    """信号过滤器 - 使用统一配置"""

    def __init__(self):
        self.config = get_filter_config()

    def filter_signal(self, signal: ScorableSignal, market_context: Dict[str, Any] = None) -> bool:
        """
        综合过滤信号

        Args:
            signal: 待过滤的信号
            market_context: 市场上下文（当前价格、波动率等）

        Returns:
            True 表示通过过滤，False 表示被拒绝
        """
        if market_context is None:
            market_context = {}

        # 1. 强制检查（必须满足的基础条件）
        if not self._check_mandatory_conditions(signal):
            logger.debug(f"信号 {signal.signal_id} 未通过强制检查")
            return False

        # 2. 排除条件检查
        if not self._check_exclusion_conditions(signal, market_context):
            logger.debug(f"信号 {signal.signal_id} 触发排除条件")
            return False

        # 3. 质量评分过滤
        if not self._check_score_threshold(signal):
            logger.debug(f"信号 {signal.signal_id} 评分不足: {signal.meta.get('final_score', 0)}")
            return False

        # 4. 市场状态过滤
        if not self._check_market_state(signal, market_context):
            logger.debug(f"信号 {signal.signal_id} 市场状态不符合")
            return False

        # 5. 风险管理过滤
        if not self._risk_management_check(signal, market_context):
            logger.debug(f"信号 {signal.signal_id} 风控检查未通过")
            return False

        logger.info(f"信号 {signal.signal_id} 通过所有过滤器")
        return True

    def confirm_signal(
        self,
        signal: ScorableSignal,
        market_context: Dict[str, Any]
    ) -> bool:
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

        signal_type_str = signal.signal_type.value
        if signal_type_str in confirmation_methods:
            return confirmation_methods[signal_type_str](signal, market_context)

        return False

    # --- 过滤器逻辑 ---

    def _check_mandatory_conditions(self, signal: ScorableSignal) -> bool:
        """强制条件：如数据完整性、核心结构有效性"""
        # 结构完整性检查
        if self.config.check_structure_complete and not signal.is_structure_complete:
            return False

        # 分型确认检查
        if self.config.check_fractal_confirmation and not signal.is_fractal_confirmed:
            return False

        # 价格位置清晰检查
        if self.config.check_position_clear:
            # 这里可以添加更多逻辑，比如价格是否在有效范围内
            pass

        return True

    def _check_exclusion_conditions(
        self,
        signal: ScorableSignal,
        market_context: Dict[str, Any]
    ) -> bool:
        """
        检查是否满足排除条件
        返回 True 表示通过检查（即不被排除，保留）
        返回 False 表示命中排除条件（即被排除，丢弃）
        """
        # 检查是否接近涨跌停
        current_price = market_context.get('current_price', signal.price)
        limit_up = market_context.get('limit_up', float('inf'))
        limit_down = market_context.get('limit_down', 0)

        limit_move_pct = self.config.limit_move_percent
        if limit_move_pct > 0:
            # 如果价格接近涨跌停（使用limit_move_percent阈值）
            range_percent = market_context.get('range_percent', 0)
            if range_percent >= limit_move_pct:
                logger.debug(f"价格波动过大: {range_percent}% >= {limit_move_pct}%")
                return False

        # 检查是否在低流动性时段
        if 'trading_session' in market_context:
            session = market_context['trading_session']
            if session == 'low_liquidity':
                logger.debug("处于低流动性时段")
                return False

        return True

    def _check_market_state(
        self,
        signal: ScorableSignal,
        market_context: Dict[str, Any]
    ) -> bool:
        """市场状态：如ATR波动率是否足够"""
        # 示例：如果波动率太低，可能不交易
        atr = market_context.get('atr', 0)
        min_atr = market_context.get('min_atr', 0)

        if min_atr > 0 and atr < min_atr:
            logger.debug(f"波动率过低: ATR={atr} < {min_atr}")
            return False

        return True

    def _risk_management_check(
        self,
        signal: ScorableSignal,
        market_context: Dict[str, Any]
    ) -> bool:
        """风控检查：如止损距离是否过大"""
        # 示例：止损距离超过价格的2%则放弃
        stop_distance = market_context.get('stop_distance', 0)
        stop_distance_pct = (stop_distance / signal.price) * 100 if signal.price > 0 else 0

        max_stop_pct = market_context.get('max_stop_pct', 2.0)
        if stop_distance_pct > max_stop_pct:
            logger.debug(f"止损距离过大: {stop_distance_pct:.2f}% > {max_stop_pct}%")
            return False

        return True

    def _check_score_threshold(self, signal: ScorableSignal) -> bool:
        """检查评分是否达到阈值"""
        score = signal.meta.get('final_score', 0)
        return score >= self.config.min_score

    # --- 确认逻辑 ---

    def _confirm_1B(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """1B确认条件"""
        confirmation_conditions = [
            # 条件1：价格不再创新低
            lambda: market_context.get('current_price', 0) > signal.price,

            # 条件2：出现底分型确认
            lambda: self._is_bottom_fenxing_confirmed(signal, market_context),

            # 条件3：成交量放大
            lambda: self._volume_increase_confirmation(signal, market_context),

            # 条件4：次级别出现买点
            lambda: self._has_lower_level_buy_signal(signal, market_context)
        ]

        # 满足至少3个条件
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 3

    def _confirm_2B(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """2B确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', 0) > signal.price,
            lambda: self._is_bottom_fenxing_confirmed(signal, market_context),
            lambda: self._volume_shrink_during_pullback(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    def _confirm_3B(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """3B确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', 0) > signal.price,
            lambda: self._has_lower_level_buy_signal(signal, market_context),
            lambda: self._volume_pattern_confirmation(signal, market_context),
            lambda: self._break_previous_high(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    def _confirm_1S(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """1S确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            lambda: self._is_top_fenxing_confirmed(signal, market_context),
            lambda: self._volume_increase_confirmation(signal, market_context),
            lambda: self._has_lower_level_sell_signal(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 3

    def _confirm_2S(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """2S确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            lambda: self._is_top_fenxing_confirmed(signal, market_context),
            lambda: self._volume_shrink_during_pullback(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    def _confirm_3S(self, signal: ScorableSignal, market_context: Dict[str, Any]) -> bool:
        """3S确认条件"""
        confirmation_conditions = [
            lambda: market_context.get('current_price', float('inf')) < signal.price,
            lambda: self._has_lower_level_sell_signal(signal, market_context),
            lambda: self._volume_pattern_confirmation(signal, market_context),
            lambda: self._break_previous_low(signal, market_context)
        ]
        satisfied = sum(1 for cond in confirmation_conditions if cond())
        return satisfied >= 2

    # --- 辅助方法 ---

    def _is_bottom_fenxing_confirmed(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """检查底分型是否确认"""
        return context.get('fenxing_confirmed', True)

    def _is_top_fenxing_confirmed(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """检查顶分型是否确认"""
        return context.get('fenxing_confirmed', True)

    def _volume_increase_confirmation(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """成交量放大确认"""
        return context.get('volume_increase', True)

    def _volume_shrink_during_pullback(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """回调缩量确认"""
        return context.get('volume_shrink', True)

    def _volume_pattern_confirmation(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """特定形态成交量配合"""
        return True

    def _has_lower_level_buy_signal(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """次级别买点"""
        return context.get('lower_level_buy', False)

    def _has_lower_level_sell_signal(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """次级别卖点"""
        return context.get('lower_level_sell', False)

    def _break_previous_high(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """突破前高"""
        if 'leave_bi' in signal.meta:
            prev_high = signal.meta['leave_bi'].high
            return context.get('current_price', 0) > prev_high
        return False

    def _break_previous_low(
        self,
        signal: ScorableSignal,
        context: Dict[str, Any]
    ) -> bool:
        """跌破前低"""
        if 'leave_bi' in signal.meta:
            prev_low = signal.meta['leave_bi'].low
            return context.get('current_price', float('inf')) < prev_low
        return False
