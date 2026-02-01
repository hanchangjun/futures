import copy
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.chan_core import ChanTheorySignalDetector, Signal

class RebarOptimizedChanSystem(ChanTheorySignalDetector):
    """螺纹钢优化的缠论系统"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 螺纹钢特定优化配置
        self.rebar_config = {
            '关键价格位': [3600, 3700, 3800, 3900, 4000],  # 整数关口
            '季节性因子': self._seasonal_factors(),
            '基差影响权重': 0.2,  # 基差对信号的调整权重
            '库存周期权重': 0.15,  # 库存周期权重
            '交易时段调整': {
                '日盘': 1.0,
                '夜盘_活跃': 0.9,   # 21:00-23:00
                '夜盘_清淡': 0.7    # 23:00-01:00
            }
        }
        # Update config with rebar specifics if needed
        if config and 'rebar_config' in config:
            self.rebar_config.update(config['rebar_config'])

    def _detect_signals(self, bars):
        """
        Override _detect_signals to apply rebar optimizations after detection.
        """
        # 1. Run standard detection
        super()._detect_signals(bars)
        
        # 2. Apply optimizations to all detected signals
        adjusted_signals = []
        for signal in self.买卖点记录:
            # Construct context for this signal
            # In a real system, basis and other data would come from data source
            # Here we use placeholders or extract from bar if available
            market_context = {
                'basis': 0,  # Placeholder: fetch basis for signal.time
                'inventory': 0 # Placeholder: fetch inventory for signal.time
            }
            
            # Apply adjustment
            adjusted_signal = self.adjust_signal_for_rebar(signal, market_context)
            adjusted_signals.append(adjusted_signal)
            
        self.买卖点记录 = adjusted_signals

    def adjust_signal_for_rebar(self, signal: Signal, market_context: Dict[str, Any]) -> Signal:
        """
        针对螺纹钢特性调整信号
        """
        adjusted_signal = copy.deepcopy(signal)
        
        # 1. 整数关口调整
        adjustment = self._integer_level_adjustment(signal.price)
        adjusted_signal.score *= adjustment
        
        # 2. 季节性调整
        seasonal_factor = self._seasonal_adjustment(signal.time)
        adjusted_signal.score *= seasonal_factor
        
        # 3. 基差调整
        basis_adjustment = self._basis_adjustment(market_context.get('basis', 0))
        adjusted_signal.score *= basis_adjustment
        
        # 4. 交易时段调整
        time_adjustment = self._trading_time_adjustment(signal.time)
        adjusted_signal.score *= time_adjustment
        
        # 5. 主力合约调整
        contract_adjustment = self._contract_adjustment(signal.time)
        adjusted_signal.score *= contract_adjustment
        
        # 限制分数范围
        adjusted_signal.score = max(0, min(100, adjusted_signal.score))
        
        return adjusted_signal
    
    def _integer_level_adjustment(self, price: float) -> float:
        """
        整数关口效应调整
        """
        for level in self.rebar_config['关键价格位']:
            # 如果在整数关口附近（±20点），降低信号可靠性
            # (Assuming breakout signals near levels might be false breaks, 
            # or maybe support/resistance makes it better? 
            # User code says: return 0.8 -> 降低可靠性. 
            # Usually near integer levels, price might fluctuate or fake break.)
            if abs(price - level) < 20:
                return 0.8  # 降低20%的可靠性
                
        return 1.0
    
    def _seasonal_adjustment(self, time: datetime) -> float:
        """
        季节性调整
        """
        month = time.month
        
        # 螺纹钢季节性规律
        # Use the factors from config or the method logic provided by user
        # User provided specific logic in _seasonal_adjustment, so we use that.
        # But we also have self.rebar_config['季节性因子']
        
        seasonal_factors = {
            1: 0.9,   # 1月：淡季
            2: 0.8,   # 2月：春节
            3: 1.2,   # 3月：金三银四开始
            4: 1.3,   # 4月：旺季
            5: 1.1,   # 5月：旺季延续
            6: 0.9,   # 6月：梅雨季
            7: 0.8,   # 7月：淡季
            8: 0.9,   # 8月：淡季
            9: 1.1,   # 9月：旺季前备货
            10: 1.2,  # 10月：旺季
            11: 1.0,  # 11月：旺季尾声
            12: 0.9   # 12月：淡季
        }
        
        return seasonal_factors.get(month, 1.0)

    def _seasonal_factors(self) -> Dict[int, float]:
        """
        Return the seasonal factors dictionary
        """
        return {
            1: 0.9, 2: 0.8, 3: 1.2, 4: 1.3, 5: 1.1, 6: 0.9,
            7: 0.8, 8: 0.9, 9: 1.1, 10: 1.2, 11: 1.0, 12: 0.9
        }

    def _basis_adjustment(self, basis: float) -> float:
        """
        基差调整
        """
        # Placeholder logic:
        # If basis is large (positive), spot > future, implies future might rise (bullish)
        # If basis is large negative, future > spot, implies future might fall (bearish)
        # But here we adjust 'score'.
        # We assume positive basis supports Buy signals, negative basis supports Sell signals?
        # Since we don't know signal type here easily (signal object has type), 
        # but adjust_signal_for_rebar has access to signal.
        # However, this method only takes basis.
        # User snippet: adjusted_signal.score *= basis_adjustment
        # This implies a general confidence adjustment based on basis magnitude?
        # Or maybe small basis = stable?
        # Let's return 1.0 for now to be safe, as logic isn't specified.
        # Or maybe slightly > 1 if basis is high?
        return 1.0

    def _trading_time_adjustment(self, time: datetime) -> float:
        """
        交易时段调整
        """
        hour = time.hour
        # Night active: 21:00-23:00
        if 21 <= hour < 23:
            return self.rebar_config['交易时段调整']['夜盘_活跃']
        # Night quiet: 23:00-01:00 (Next day? Usually futures night session is 21:00-23:00 or 01:00)
        # Rebar night session is 21:00 - 23:00 usually.
        # Some exchange times go to 1:00 or 2:30.
        # Let's follow config: 23:00-01:00
        elif 23 <= hour or hour < 1:
            return self.rebar_config['交易时段调整']['夜盘_清淡']
        # Day: 9:00 - 15:00 (default)
        else:
            return self.rebar_config['交易时段调整']['日盘']

    def _contract_adjustment(self, time: datetime) -> float:
        """
        主力合约调整
        """
        # Placeholder: Maybe signals on non-main contracts are less reliable?
        # But we usually run strategy on continuous main.
        # Return 1.0 default
        return 1.0
