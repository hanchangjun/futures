
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath("e:/project/futures/futures"))

from signal.zone import detect_zone, MarketZone, analyze_market

def test_zones():
    # Mock data setup
    # Assume ATR = 10
    atr = 10.0
    
    print("Testing Zone Logic...\n")
    
    # Case 1: Noise (Flat slope)
    # EMA60 changes by 0.2 over 5 bars -> 0.2/10 = 0.02 < 0.05
    c1 = [100] * 10
    e20_1 = [100] * 10
    e60_1 = [100, 100, 100, 100, 100, 100.2, 100.2, 100.2, 100.2, 100.2] 
    # Note: slope calc uses [-1] - [-(5+1)]. Index -1 is 100.2, index -6 is 100.
    # diff = 0.2. slope_norm = 0.02.
    
    res1, reason1 = detect_zone(c1, e20_1, e60_1, atr)
    print(f"Case 1 (Noise-Flat): Expect RANGE_NOISE. Got: {res1.value} ({reason1})")
    
    # Case 2: Start (Recent Cross + Slope)
    # Cross happened 5 bars ago. Slope is high.
    # EMA20 > EMA60. 
    c2 = [110] * 30
    e20_2 = [100 + i for i in range(30)] # 100...129
    e60_2 = [105 + i*0.5 for i in range(30)] # 105...119.5
    # Cross check: 
    # i=0: 100 vs 105 (Bear)
    # i=10: 110 vs 110 (Cross)
    # i=29: 129 vs 119.5 (Bull)
    # Cross was at i=10. Current i=29. Bars since cross = 19 <= 20.
    # Slope: (119.5 - (105 + 24*0.5)) = 119.5 - 117 = 2.5. 2.5/10 = 0.25 > 0.05.
    # Spread: abs(129 - 119.5) = 9.5. 9.5/10 = 0.95 > 0.3.
    
    res2, reason2 = detect_zone(c2, e20_2, e60_2, atr)
    print(f"Case 2 (Start): Expect TREND_START. Got: {res2.value} ({reason2})")
    
    # Case 3: Extend (Old Cross)
    # Cross happened 30 bars ago.
    c3 = [150] * 60
    e20_3 = [100 + i for i in range(60)]
    e60_3 = [90 + i*0.8 for i in range(60)] # Slope 0.8 * 5 = 4.0 / 10 = 0.4.
    # Always Bull. Cross bars > 50.
    # Dist: |150 - (90 + 59*0.8)| = |150 - 137.2| = 12.8. 12.8/10 = 1.28 < 3.5.
    
    res3, reason3 = detect_zone(c3, e20_3, e60_3, atr)
    print(f"Case 3 (Extend): Expect TREND_EXTEND. Got: {res3.value} ({reason3})")
    
    # Case 4: Exhaust (Too far)
    # EMA60 at 100. Close at 140. ATR 10. Dist = 4 ATR.
    c4 = [140] * 10
    e20_4 = [120] * 10
    e60_4 = [100 + i*0.2 for i in range(10)] # Slope 1.0/10 = 0.1 > 0.05.
    
    res4, reason4 = detect_zone(c4, e20_4, e60_4, atr)
    print(f"Case 4 (Exhaust): Expect TREND_EXHAUST. Got: {res4.value} ({reason4})")

    # Full Perm Check
    perm = analyze_market(c2, e20_2, e60_2, atr)
    print(f"\nPermission Check (Start): {perm}")

if __name__ == "__main__":
    test_zones()
