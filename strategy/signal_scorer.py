"""
更新后的SignalScorer，使用统一配置系统
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime
from enum import Enum

from config import get_scorer_config, get_logger

logger = get_logger(__name__)


class SignalType(Enum):
    B1 = "1B"
    B2 = "2B"
    B3 = "3B"
    S1 = "1S"
    S2 = "2S"
    S3 = "3S"


@dataclass
class ScorableSignal:
    """
    标准信号对象，用于评分和过滤
    包含所有必要的原始数据来评估信号
    """
    signal_id: str
    signal_type: SignalType
    timestamp: datetime
    price: float

    # 结构相关
    is_structure_complete: bool = False
    structure_quality: float = 0.0  # 0-100 scale based on geometry

    # 背驰相关
    divergence_score: float = 0.0   # 预计算或原始指标

    # 量价
    volume: float = 0.0
    avg_volume: float = 0.0

    # 时间
    trend_duration: float = 0.0

    # 位置
    position_level: float = 0.0 # 0-100 相对范围

    # 次级别
    has_sub_level_structure: bool = False

    # 强度
    momentum_val: float = 0.0

    # 确认
    is_fractal_confirmed: bool = False

    # 额外上下文
    meta: Dict[str, Any] = field(default_factory=dict)


class SignalScorer:
    """信号评分器 - 使用统一配置"""

    def __init__(self):
        self.config = get_scorer_config()
        self.weights = self.config.weights

    def calculate_score(self, signal: ScorableSignal) -> float:
        """
        计算信号的综合评分 (0-100)
        """
        total_score = 0.0
        total_weight = 0.0

        details = {}

        # 定义维度和计算方法
        dimensions = {
            'structure': self._score_structure,
            'divergence': self._score_divergence,
            'volume_price': self._score_volume_price,
            'time': self._score_time,
            'position': self._score_position,
            'sub_level': self._score_sub_level,
            'strength': self._score_strength,
            'confirmation': self._score_confirmation
        }

        for dim, scorer_func in dimensions.items():
            weight = self.weights.get(dim, 0)
            if weight > 0:
                score = scorer_func(signal)
                # 限制分数在0-100
                score = max(0.0, min(100.0, score))

                weighted_score = score * weight
                total_score += weighted_score
                total_weight += weight

                details[dim] = round(score, 2)

        final_score = total_score / total_weight if total_weight > 0 else 0.0
        final_score = round(final_score, 2)

        logger.info(f"信号 {signal.signal_id} 评分: {final_score}, 详情: {details}")
        signal.meta['score_details'] = details
        signal.meta['final_score'] = final_score

        return final_score

    def calculate_dimension_score(self, dimension: str, signal: ScorableSignal) -> float:
        """
        计算特定维度的评分
        """
        method_name = f"_score_{dimension}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(signal)
        return 0.0

    # --- 维度评分逻辑 ---

    def _score_structure(self, signal: ScorableSignal) -> float:
        """基于结构完整性和质量评分"""
        score = 0.0
        if signal.is_structure_complete:
            score += 50
        score += signal.structure_quality * 0.5
        return score

    def _score_divergence(self, signal: ScorableSignal) -> float:
        """基于背驰指标评分"""
        return signal.divergence_score

    def _score_volume_price(self, signal: ScorableSignal) -> float:
        """基于量价关系评分"""
        if signal.avg_volume <= 0:
            return 50.0

        vol_ratio = signal.volume / signal.avg_volume
        # 高成交量确认信号通常更好
        if vol_ratio > 2.0:
            return 100.0
        elif vol_ratio > 1.5:
            return 80.0
        elif vol_ratio > 1.0:
            return 60.0
        else:
            return 40.0

    def _score_time(self, signal: ScorableSignal) -> float:
        """基于时间持续时间/对称性评分"""
        # 例如：较长趋势持续时间可能暗示更强的反转（对于1B）
        # 或适当的整理时间（对于3B）
        if signal.trend_duration > 100:
            return 90.0
        elif signal.trend_duration > 50:
            return 70.0
        return 50.0

    def _score_position(self, signal: ScorableSignal) -> float:
        """基于相对位置评分"""
        # 例如：在低位买入更好
        # 如果signal是Buy (B1/B2/B3)，较低位置更好
        # 如果signal是Sell，较高位置更好
        # 假设 position_level 是 0-100 (0=低, 100=高)

        is_buy = signal.signal_type.value.endswith('B')
        if is_buy:
            return 100.0 - signal.position_level
        else:
            return signal.position_level

    def _score_sub_level(self, signal: ScorableSignal) -> float:
        """基于次级别结构评分"""
        return 100.0 if signal.has_sub_level_structure else 0.0

    def _score_strength(self, signal: ScorableSignal) -> float:
        """基于动量/强度评分"""
        return signal.momentum_val

    def _score_confirmation(self, signal: ScorableSignal) -> float:
        """基于分型确认评分"""
        return 100.0 if signal.is_fractal_confirmed else 0.0
