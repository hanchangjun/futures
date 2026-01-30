from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

# Define Zones
class MarketZone(Enum):
    TREND_START = "TREND_START"       # 趋势启动
    TREND_EXTEND = "TREND_EXTEND"     # 趋势扩展
    TREND_EXHAUST = "TREND_EXHAUST"   # 趋势衰竭
    RANGE_NOISE = "RANGE_NOISE"       # 震荡噪音

# Define Trade Permissions
@dataclass
class ZonePermission:
    zone: MarketZone
    allow_breakout: bool
    allow_pullback: bool
    allow_add: bool
    description: str

def get_zone_permission(zone: MarketZone) -> ZonePermission:
    if zone == MarketZone.TREND_START:
        return ZonePermission(zone, True, True, True, "允许全功能交易 (突破/回调/加仓)")
    elif zone == MarketZone.TREND_EXTEND:
        return ZonePermission(zone, False, True, True, "仅允许回调与加仓，禁止追高突破")
    elif zone == MarketZone.TREND_EXHAUST:
        return ZonePermission(zone, False, False, False, "禁止开新仓，建议收紧止损或分批止盈")
    else: # RANGE_NOISE
        return ZonePermission(zone, False, False, False, "禁止任何交易")

def detect_zone(
    closes: List[float],
    ema20: List[float],
    ema60: List[float],
    atr_val: float,
    slope_period: int = 5
) -> Tuple[MarketZone, str]:
    """
    Detect market zone based on EMA structure and ATR.
    
    Args:
        closes: List of close prices
        ema20: List of EMA20 values (same length as closes)
        ema60: List of EMA60 values (same length as closes)
        atr_val: Current ATR value
        slope_period: Period to calculate slope (default 5)
        
    Returns:
        (MarketZone, Reason String)
    """
    if len(closes) < slope_period + 1 or atr_val <= 0:
        return MarketZone.RANGE_NOISE, "数据不足"

    # Current values
    c = closes[-1]
    e20 = ema20[-1]
    e60 = ema60[-1]
    
    # 1. Calculate Normalized Slope of EMA60 (Trend Strength)
    # Slope = (Current - N_bars_ago) / ATR
    # Threshold: 0.1 ATR per 5 bars is a decent trend standard for RB
    prev_e60 = ema60[-(slope_period + 1)]
    slope_raw = e60 - prev_e60
    slope_norm = abs(slope_raw) / atr_val
    
    # 2. Calculate EMA Spread (Trend Stability)
    spread = abs(e20 - e60)
    spread_atr = spread / atr_val
    
    # 3. Calculate Extension (Mean Reversion Risk)
    # Distance from Close to EMA60
    dist_mean = abs(c - e60)
    dist_mean_atr = dist_mean / atr_val
    
    # 4. Determine Cross State (Trend Direction)
    # Scan back to find when EMA20 crossed EMA60
    cross_bars = 999
    is_bull = e20 > e60
    
    # Look back up to 50 bars to find the cross
    lookback = min(len(ema20), 50)
    for i in range(1, lookback):
        idx = -(i + 1)
        prev_is_bull = ema20[idx] > ema60[idx]
        if prev_is_bull != is_bull:
            cross_bars = i
            break
            
    # === ZONE JUDGMENT LOGIC ===
    
    # PRIORITY 1: NOISE (震荡噪音)
    # Condition A: Slope is flat (< 0.05 ATR/5bars)
    # Condition B: Spread is tight (< 0.3 ATR)
    if slope_norm < 0.05:
        return MarketZone.RANGE_NOISE, f"EMA60走平(Slope={slope_norm:.2f})"
    if spread_atr < 0.3:
        return MarketZone.RANGE_NOISE, f"均线粘合(Spread={spread_atr:.2f}ATR)"

    # PRIORITY 2: EXHAUST (趋势衰竭)
    # Condition: Price deviates too far from EMA60 (> 3.5 ATR)
    # This indicates overbought/oversold and high risk of snapback
    if dist_mean_atr > 3.5:
        return MarketZone.TREND_EXHAUST, f"乖离率过大(Dist={dist_mean_atr:.2f}ATR)"
        
    # PRIORITY 3: START (趋势启动)
    # Condition A: Recent crossover (<= 20 bars)
    # Condition B: Slope is picking up (> 0.05) - already checked by NOISE filter
    # Condition C: Spread is expanding (implied by recent cross + current separation)
    if cross_bars <= 20:
        return MarketZone.TREND_START, f"趋势初成(Cross={cross_bars}bars)"
        
    # PRIORITY 4: EXTEND (趋势扩展)
    # Condition: Trend persisted (> 20 bars) and not exhausted
    return MarketZone.TREND_EXTEND, f"趋势延续(Slope={slope_norm:.2f})"

# Helper for integration
def analyze_market(bars_close: List[float], bars_ema20: List[float], bars_ema60: List[float], current_atr: float) -> dict:
    zone, reason = detect_zone(bars_close, bars_ema20, bars_ema60, current_atr)
    perm = get_zone_permission(zone)
    return {
        "zone": zone.value,
        "reason": reason,
        "can_breakout": perm.allow_breakout,
        "can_pullback": perm.allow_pullback,
        "can_add": perm.allow_add,
        "desc": perm.description
    }
