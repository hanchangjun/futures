
import sys
import os
import unittest
from datetime import datetime, time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.pure_chan_strategy import ChanPositionManagement, SimpleBi, SimpleCenter, Trend, SimpleFractal

class TestChanPositionManagement(unittest.TestCase):
    def setUp(self):
        self.pm = ChanPositionManagement(total_capital=100000)
        
    def test_position_size(self):
        # Test 1B
        res = self.pm.calculate_position_size('1B')
        self.assertEqual(res['ratio'], 0.10)
        self.assertEqual(res['amount'], 10000.0)
        
        # Test 2B
        res = self.pm.calculate_position_size('2B')
        self.assertEqual(res['ratio'], 0.07)
        
        # Test 3B
        res = self.pm.calculate_position_size('3B')
        self.assertEqual(res['ratio'], 0.05)
        
    def test_stoploss_1b_down(self):
        # 1B Buy (Trend Down)
        # Entry at end of Down Bi. SL at Bi Low.
        # Bi: Down. Start High, End Low.
        
        f_start = SimpleFractal(0, 3100, 'TOP', datetime(2025,1,1,10,0))
        f_end = SimpleFractal(1, 3000, 'BOTTOM', datetime(2025,1,1,11,0)) # Low
        bi = SimpleBi(f_start, f_end, Trend.DOWN)
        
        # Center (irrelevant for 1B logic but passed)
        center = SimpleCenter(3200, 3100, 0, 1)
        
        # Case 1: Day, ATR=0
        sl = self.pm.get_stoploss('1B', Trend.DOWN, 3000, center, bi, datetime(2025,1,1,11,0), atr=0)
        # Base buffer if ATR=0 is 0.2% = 6.0
        # SL = 3000 - 6 = 2994
        self.assertAlmostEqual(sl, 2994.0)
        
        # Case 2: Day, ATR=10
        sl = self.pm.get_stoploss('1B', Trend.DOWN, 3000, center, bi, datetime(2025,1,1,11,0), atr=10)
        # Base buffer = 0.5 * 10 = 5
        # SL = 3000 - 5 = 2995
        self.assertEqual(sl, 2995.0)
        
        # Case 3: Night, ATR=10
        # Night: 21:30
        sl = self.pm.get_stoploss('1B', Trend.DOWN, 3000, center, bi, datetime(2025,1,1,21,30), atr=10)
        # Base buffer = 5 * 1.3 = 6.5
        # SL = 3000 - 6.5 = 2993.5
        self.assertEqual(sl, 2993.5)
        
    def test_stoploss_3b_down(self):
        # 3B Buy (Pullback Down)
        # Bi: Down.
        f_start = SimpleFractal(0, 3100, 'TOP', datetime(2025,1,1,10,0))
        f_end = SimpleFractal(1, 3050, 'BOTTOM', datetime(2025,1,1,11,0))
        bi = SimpleBi(f_start, f_end, Trend.DOWN)
        
        center = SimpleCenter(3040, 3000, 0, 0) # ZG=3040. Bi Low 3050 > ZG.
        
        # SL = Bi Low = 3050.
        # Buffer = 0.5 * 10 = 5.
        # Final SL = 3045.
        sl = self.pm.get_stoploss('3B', Trend.DOWN, 3050, center, bi, datetime(2025,1,1,11,0), atr=10)
        self.assertEqual(sl, 3045.0)

if __name__ == '__main__':
    unittest.main()
