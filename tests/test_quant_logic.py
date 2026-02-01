import pytest
import math
from datetime import datetime, timedelta
from strategy.quant_logic import is_downtrend, quantify_divergence, is_adjacent_bi
from strategy.quant_types import TrendDirection

# Mock classes for testing
class MockCenter:
    def __init__(self, gg, dd, start, end, count, start_index=None, end_index=None):
        self.gg = gg
        self.dd = dd
        self.start_time = start
        self.end_time = end
        self.count = count
        self.start_index = start_index
        self.end_index = end_index

class MockBi:
    def __init__(self, direction, start, end, amp=0, area=0, peak=0, slope=0, dur=0):
        self.direction = direction
        self.start_time = start
        self.end_time = end
        self.amplitude = amp
        self.macd_area = area
        self.macd_diff_peak = peak
        self.slope = slope
        self.duration = dur

# --- 1. Downtrend Tests ---

def test_downtrend_empty():
    assert is_downtrend([], 100) is False

def test_downtrend_insufficient_centers():
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 10)
    assert is_downtrend([c1], 90) is False

def test_downtrend_non_descending():
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 10)
    c2 = MockCenter(110, 100, datetime(2023,1,3), datetime(2023,1,4), 10) # DD equal
    assert is_downtrend([c1, c2], 90) is False

def test_downtrend_short_duration():
    # Total duration 15 bars
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 5, start_index=0, end_index=5)
    c2 = MockCenter(100, 90, datetime(2023,1,2), datetime(2023,1,3), 5, start_index=10, end_index=15)
    assert is_downtrend([c1, c2], 80) is False

def test_downtrend_price_not_low_enough():
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 10, start_index=0, end_index=10)
    c2 = MockCenter(100, 90, datetime(2023,1,3), datetime(2023,1,4), 10, start_index=20, end_index=30)
    assert is_downtrend([c1, c2], 95) is False # > 90

def test_downtrend_valid():
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 10, start_index=0, end_index=10)
    c2 = MockCenter(100, 90, datetime(2023,1,3), datetime(2023,1,4), 10, start_index=20, end_index=50) # Duration 50
    assert is_downtrend([c1, c2], 85) is True

# --- 2. Divergence Tests ---

def test_divergence_div_zero():
    # In: area=10, Out: area=0 -> Ratio 0 -> Score 40 (from area) + others
    b_in = MockBi('up', datetime(2023,1,1), datetime(2023,1,2), 10, 10, 10, 1, 10)
    b_out = MockBi('up', datetime(2023,1,3), datetime(2023,1,4), 10, 0, 10, 1, 10)
    # Ratios: Amp=1, Area=0, Height=1, Slope=1, Time=1
    # Score: Area(40*(1-0)) = 40. Total 40. False.
    assert quantify_divergence(b_in, b_out) is False

def test_divergence_negative_area():
    # Should handle abs()
    b_in = MockBi('up', datetime(2023,1,1), datetime(2023,1,2), 10, -10, 10, 1, 10)
    b_out = MockBi('up', datetime(2023,1,3), datetime(2023,1,4), 5, -2, 5, 0.5, 10)
    # In: 10, Out: 2. Ratio 0.2. Score += 40*0.8 = 32.
    # Amp: 10->5 (0.5). Score += 10*0.5 = 5.
    # Height: 10->5 (0.5). Score += 20*0.5 = 10.
    # Slope: 1->0.5 (0.5). Score += 20*0.5 = 10.
    # Time: 10->10 (1.0). Score += 0.
    # Total: 32+5+10+10 = 57. False.
    assert quantify_divergence(b_in, b_out) is False

def test_divergence_boundary_59():
    # Construct case for ~59
    # Ratios: Area=0.5 (20), Height=0.5 (10), Slope=0.5 (10), Amp=0.5 (5), Time=1 (0) -> 45. Too low.
    # Need higher.
    # Area=0.1 (36), Height=0.5 (10), Slope=0.5 (10), Amp=1 (0), Time=1 (0) -> 56.
    # Let's adjust Area ratio to get close to 59.
    # Target 59.
    # Area=0 (40). Height=0.5 (10). Slope=0.55 (9). Amp=1(0). Time=1(0). Total 59.
    b_in = MockBi('up', None, None, 10, 10, 10, 10, 10)
    b_out = MockBi('up', None, None, 10, 0, 5, 5.5, 10)
    # Area: 0/10=0. Sc=40.
    # Height: 5/10=0.5. Sc=10.
    # Slope: 5.5/10=0.55. Sc=20*(0.45)=9.
    # Amp: 1. Sc=0.
    # Time: 1. Sc=0.
    # Sum=59.
    assert quantify_divergence(b_in, b_out) is False

def test_divergence_boundary_60():
    # Area=0 (40), Height=0.5 (10), Slope=0.5 (10) -> 60.
    b_in = MockBi('up', None, None, 10, 10, 10, 10, 10)
    b_out = MockBi('up', None, None, 10, 0, 5, 5, 10)
    assert quantify_divergence(b_in, b_out) is True

def test_divergence_boundary_79():
    # Area=0 (40), Height=0 (20), Slope=0.05 (19) -> 79.
    b_in = MockBi('up', None, None, 10, 10, 10, 10, 10)
    b_out = MockBi('up', None, None, 10, 0, 0, 0.5, 10)
    assert quantify_divergence(b_in, b_out) is True # Score 79 >= 60 -> True

def test_divergence_boundary_80():
    # Area=0 (40), Height=0 (20), Slope=0 (20) -> 80.
    b_in = MockBi('up', None, None, 10, 10, 10, 10, 10)
    b_out = MockBi('up', None, None, 10, 0, 0, 0, 10)
    assert quantify_divergence(b_in, b_out) is True

# --- 3. Adjacent Tests ---

def test_adjacent_same_direction():
    b1 = MockBi(TrendDirection.UP, datetime(2023,1,1,10,0), datetime(2023,1,1,10,5))
    b2 = MockBi(TrendDirection.UP, datetime(2023,1,1,10,6), datetime(2023,1,1,10,10))
    assert is_adjacent_bi(b1, b2) is False

def test_adjacent_gap_0():
    b1 = MockBi('up', datetime(2023,1,1,10,0), datetime(2023,1,1,10,5))
    b2 = MockBi('down', datetime(2023,1,1,10,5), datetime(2023,1,1,10,10))
    # Diff 0 min -> 0 bars
    assert is_adjacent_bi(b1, b2, max_gap=3) is True

def test_adjacent_gap_3():
    b1 = MockBi('up', datetime(2023,1,1,10,0), datetime(2023,1,1,10,5))
    b2 = MockBi('down', datetime(2023,1,1,10,8), datetime(2023,1,1,10,10))
    # Diff 3 min -> 3 bars? My logic: (8-5)=3. int(3)=3. 
    # Logic in code: diff = 3. return 3-1 = 2? 
    # Wait, 10:05 to 10:06 is 1 min diff. Gap is 0 bars.
    # 10:05 to 10:08 is 3 min diff. Bars in between: 06, 07. Gap 2.
    # My code: (t2-t1)/60 = 3. return 2.
    # So Gap 2 <= 3. True.
    assert is_adjacent_bi(b1, b2, max_gap=3) is True

def test_adjacent_gap_4():
    b1 = MockBi('up', datetime(2023,1,1,10,0), datetime(2023,1,1,10,5))
    b2 = MockBi('down', datetime(2023,1,1,10,10), datetime(2023,1,1,10,15))
    # Diff 5 min. Gap 4 bars. > 3. False.
    assert is_adjacent_bi(b1, b2, max_gap=3) is False

def test_adjacent_disorder():
    b1 = MockBi('up', datetime(2023,1,1,10,10), datetime(2023,1,1,10,15))
    b2 = MockBi('down', datetime(2023,1,1,10,0), datetime(2023,1,1,10,5))
    with pytest.raises(ValueError, match="Time Disorder"):
        is_adjacent_bi(b1, b2)

def test_adjacent_timezone():
    # Should handle or raise if naive vs aware
    # Here we just use naive for simplicity as mock
    pass 
