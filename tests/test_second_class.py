import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from strategy.second_class_signal import SecondClassSignalDetector
from strategy.chan_core import Bi, Signal

class TestSecondClassSignalDetector(unittest.TestCase):
    def setUp(self):
        self.detector = SecondClassSignalDetector()

    def create_mock_bi(self, id, direction, start_price, end_price, start_time=None, end_time=None):
        if not start_time:
            start_time = datetime.now()
        if not end_time:
            end_time = start_time + timedelta(minutes=30)
            
        # Bi(bi_id, start_price, end_price, start_time, end_time, high, low, direction, bars)
        high = max(start_price, end_price)
        low = min(start_price, end_price)
        
        bi = Bi(
            id, # bi_id
            direction, # direction
            float(start_price), # start_price
            float(end_price), # end_price
            start_time, # start_time
            end_time, # end_time
            float(high), # high
            float(low), # low
            10 # bars
        )
        bi.volume_sum = 1000
        return bi

    def test_detect_2B_success(self):
        # Setup: 1B -> Up -> 2B(Down)
        t0 = datetime(2023, 1, 1, 10, 0)
        
        # 1B Bi (Down)
        b1 = self.create_mock_bi(1, 'down', 100, 90, t0, t0 + timedelta(minutes=30))
        sig1b = Signal('1B', 90, b1.end_time, 80, None, b1)
        
        # Up Bi
        b2 = self.create_mock_bi(2, 'up', 90, 110, t0 + timedelta(minutes=30), t0 + timedelta(minutes=60))
        b2.bars = 3 # Small duration
        
        # 2B Bi (Down) - Higher Low (100 > 90) - Ratio 0.5 (Perfect)
        b3 = self.create_mock_bi(3, 'down', 110, 100, t0 + timedelta(minutes=60), t0 + timedelta(minutes=90))
        b3.bars = 3 # Small duration
        
        context = {
            'bi_list': [b1, b2, b3],
            'signals': [sig1b]
        }
        
        signal = self.detector.detect_2B(b3, context)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '2B')
        self.assertEqual(signal.price, 100)
        self.assertTrue(signal.score >= 60)
        self.assertEqual(signal.extra_info['related_1B'], sig1b)

    def test_detect_2B_fail_lower_low(self):
        # Setup: 1B -> Up -> Down(Lower Low)
        b1 = self.create_mock_bi(1, 'down', 100, 90)
        sig1b = Signal('1B', 90, b1.end_time, 80, None, b1)
        b2 = self.create_mock_bi(2, 'up', 90, 100)
        b3 = self.create_mock_bi(3, 'down', 100, 80) # Lower than 90
        
        context = {
            'bi_list': [b1, b2, b3],
            'signals': [sig1b]
        }
        
        signal = self.detector.detect_2B(b3, context)
        self.assertIsNone(signal)

    def test_detect_2B_fail_not_first(self):
        # Setup: 1B -> Up -> Down(1st) -> Up -> Down(2nd)
        b1 = self.create_mock_bi(1, 'down', 100, 90)
        sig1b = Signal('1B', 90, b1.end_time, 80, None, b1)
        b2 = self.create_mock_bi(2, 'up', 90, 100)
        b3 = self.create_mock_bi(3, 'down', 100, 95) # 1st pullback
        b4 = self.create_mock_bi(4, 'up', 95, 105)
        b5 = self.create_mock_bi(5, 'down', 105, 98) # 2nd pullback
        
        context = {
            'bi_list': [b1, b2, b3, b4, b5],
            'signals': [sig1b]
        }
        
        # Try to detect on b5
        signal = self.detector.detect_2B(b5, context)
        self.assertIsNone(signal)
        
        # Try on b3 (should succeed if valid)
        # b2 bars=10, b3 bars=10. Total 20 bars. Score low on time.
        # But structural check should pass.
        # Ratio: 100->95 (5/10=0.5). Score 30.
        # Time: 20 -> Score 5.
        # Base: 24. Vol: 16. Total: 24+30+5+16=75.
        signal = self.detector.detect_2B(b3, context)
        self.assertIsNotNone(signal)

    def test_detect_2S_success(self):
        # Setup: 1S -> Down -> 2S(Up)
        b1 = self.create_mock_bi(1, 'up', 90, 100)
        sig1s = Signal('1S', 100, b1.end_time, 80, None, b1)
        
        b2 = self.create_mock_bi(2, 'down', 100, 80)
        b2.bars = 3
        # 2S (Up) - Lower High (90 < 100)
        b3 = self.create_mock_bi(3, 'up', 80, 90)
        b3.bars = 3
        
        # Fall 20. Retracement 10. Ratio 0.5.
        
        context = {
            'bi_list': [b1, b2, b3],
            'signals': [sig1s]
        }
        
        signal = self.detector.detect_2S(b3, context)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '2S')

if __name__ == '__main__':
    unittest.main()
