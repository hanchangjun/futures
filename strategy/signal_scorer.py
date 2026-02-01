import yaml
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

# Configure logger
logger = logging.getLogger(__name__)

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
    Standard signal object for scoring and filtering.
    Contains all necessary raw data to evaluate the signal.
    """
    signal_id: str
    signal_type: SignalType
    timestamp: datetime
    price: float
    
    # Structure related
    is_structure_complete: bool = False
    structure_quality: float = 0.0  # 0-100 scale based on geometry
    
    # Divergence related
    divergence_score: float = 0.0   # Pre-calculated or raw metric
    
    # Volume/Price
    volume: float = 0.0
    avg_volume: float = 0.0
    
    # Time
    trend_duration: float = 0.0
    
    # Position
    position_level: float = 0.0 # 0-100 relative to range
    
    # Sub-level
    has_sub_level_structure: bool = False
    
    # Strength
    momentum_val: float = 0.0
    
    # Confirmation
    is_fractal_confirmed: bool = False
    
    # Additional context
    meta: Dict[str, Any] = field(default_factory=dict)

class SignalScorer:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.weights = self.config.get('scorer', {}).get('weights', {})
        
    def _load_config(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def calculate_score(self, signal: ScorableSignal) -> float:
        """
        Calculate comprehensive score (0-100) for the signal.
        """
        total_score = 0.0
        total_weight = 0.0
        
        details = {}
        
        # Define dimensions and their calculation methods
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
                # Clamp score 0-100
                score = max(0.0, min(100.0, score))
                
                weighted_score = score * weight
                total_score += weighted_score
                total_weight += weight
                
                details[dim] = round(score, 2)
        
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        final_score = round(final_score, 2)
        
        logger.info(f"Signal {signal.signal_id} Score: {final_score}, Details: {details}")
        signal.meta['score_details'] = details
        signal.meta['final_score'] = final_score
        
        return final_score

    def calculate_dimension_score(self, dimension: str, signal: ScorableSignal) -> float:
        """
        Public method to calculate score for a specific dimension.
        """
        method_name = f"_score_{dimension}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(signal)
        return 0.0

    # --- Dimension Scoring Logic ---

    def _score_structure(self, signal: ScorableSignal) -> float:
        """
        Score based on structure completeness and quality.
        """
        score = 0.0
        if signal.is_structure_complete:
            score += 50
        score += signal.structure_quality * 0.5
        return score

    def _score_divergence(self, signal: ScorableSignal) -> float:
        """
        Score based on divergence metrics.
        Assuming signal.divergence_score is already a 0-100 metric or calculated here.
        """
        return signal.divergence_score

    def _score_volume_price(self, signal: ScorableSignal) -> float:
        """
        Score based on Volume/Price relationship.
        """
        if signal.avg_volume <= 0:
            return 50.0
        
        vol_ratio = signal.volume / signal.avg_volume
        # High volume on signal usually good? Depends on signal type.
        # Assuming higher volume confirmation is better.
        if vol_ratio > 2.0:
            return 100.0
        elif vol_ratio > 1.5:
            return 80.0
        elif vol_ratio > 1.0:
            return 60.0
        else:
            return 40.0

    def _score_time(self, signal: ScorableSignal) -> float:
        """
        Score based on time duration/symmetry.
        """
        # Example logic: Longer trend duration might imply stronger reversal for 1B
        # Or proper consolidation time for 3B.
        # This is highly strategy dependent. Using placeholder logic based on duration.
        if signal.trend_duration > 100:
            return 90.0
        elif signal.trend_duration > 50:
            return 70.0
        return 50.0

    def _score_position(self, signal: ScorableSignal) -> float:
        """
        Score based on relative position.
        """
        # e.g. buying at low position is better.
        # If signal is Buy (B1/B2/B3), lower position is better?
        # If signal is Sell, higher position is better?
        # Assuming position_level is 0-100 (0=Low, 100=High)
        
        is_buy = signal.signal_type.value.endswith('B')
        if is_buy:
            return 100.0 - signal.position_level
        else:
            return signal.position_level

    def _score_sub_level(self, signal: ScorableSignal) -> float:
        """
        Score based on sub-level structure.
        """
        return 100.0 if signal.has_sub_level_structure else 0.0

    def _score_strength(self, signal: ScorableSignal) -> float:
        """
        Score based on momentum/strength.
        """
        return signal.momentum_val

    def _score_confirmation(self, signal: ScorableSignal) -> float:
        """
        Score based on fractal confirmation.
        """
        return 100.0 if signal.is_fractal_confirmed else 0.0
