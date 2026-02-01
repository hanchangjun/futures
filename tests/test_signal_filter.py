import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.signal_filter import SignalFilterAndConfirmer
from strategy.chan_core import Signal, Bi, Zhongshu

class TestSignalFilterAndConfirmer(unittest.TestCase):
    def setUp(self):
        self.config = {'min_signal_score': 60}
        self.filter = SignalFilterAndConfirmer(self.config)
        
        # Mock objects
        self.mock_bi = Bi(1, 'up', 100, 110, None, None, 110, 100, 10)
        self.mock_zs = Zhongshu(1, 100, 90, 105, 95, None, None, [])
        self.mock_signal = Signal('1B', 100, None, 70, self.mock_zs, self.mock_bi)
        
        self.mock_context = {
            'current_price': 105,
            'fenxing_confirmed': True,
            'volume_increase': True,
            'lower_level_buy': True,
            'volume_shrink': True,
            'lower_level_sell': True
        }

    def test_filter_signal_pass(self):
        result = self.filter.filter_signal(self.mock_signal, self.mock_context)
        self.assertTrue(result)

    def test_filter_signal_fail_score(self):
        self.mock_signal.score = 50
        result = self.filter.filter_signal(self.mock_signal, self.mock_context)
        self.assertFalse(result)

    def test_filter_signal_fail_hard(self):
        self.mock_signal.bi = None
        result = self.filter.filter_signal(self.mock_signal, self.mock_context)
        self.assertFalse(result)

    def test_confirm_1B(self):
        # 1B: Price > Signal, Fenxing, Volume, Lower Level
        # All true in mock_context
        result = self.filter.confirm_signal(self.mock_signal, self.mock_context)
        self.assertTrue(result)
        
    def test_confirm_1B_fail(self):
        # Fail multiple conditions
        bad_context = {
            'current_price': 90, # Fail (Current < Signal 100)
            'fenxing_confirmed': False, # Fail
            'volume_increase': False, # Fail
            'lower_level_buy': False # Fail
        }
        result = self.filter.confirm_signal(self.mock_signal, bad_context)
        self.assertFalse(result)

    def test_confirm_3B(self):
        # 3B Setup
        leave_bi = Bi(2, 'up', 100, 120, None, None, 120, 100, 10)
        signal = Signal('3B', 105, None, 80, self.mock_zs, self.mock_bi)
        signal.extra_info = {'leave_bi': leave_bi}
        
        context = {
            'current_price': 121, # > leave_bi.high (120) -> Break previous high
            'lower_level_buy': True,
            # Other checks usually pass by default in helper or simple lambda
        }
        
        # confirm_3B:
        # 1. Price > Signal (121 > 105) - OK
        # 2. Lower Level Buy - OK
        # 3. Volume Pattern - Default True
        # 4. Break Prev High (121 > 120) - OK
        
        result = self.filter.confirm_signal(signal, context)
        self.assertTrue(result)

    def test_confirm_1S(self):
        signal = Signal('1S', 100, None, 70, self.mock_zs, self.mock_bi)
        context = {
            'current_price': 90, # < Signal - OK
            'fenxing_confirmed': True,
            'volume_increase': True,
            'lower_level_sell': True
        }
        result = self.filter.confirm_signal(signal, context)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
