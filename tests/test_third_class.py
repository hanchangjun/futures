import unittest
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.third_class_signal import ThirdClassSignalDetector
from strategy.chan_core import Bi, Signal, Zhongshu

class TestThirdClassSignalDetector(unittest.TestCase):
    def setUp(self):
        self.detector = ThirdClassSignalDetector()

    def create_mock_bi(self, id, direction, start_price, end_price, start_time, end_time):
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

    def create_mock_zhongshu(self, id, zg, zd, start_time, end_time, bi_list):
        # GG/DD not critical for logic usually, just range
        gg = zg + 10
        dd = zd - 10
        zs = Zhongshu(id, zg, zd, gg, dd, start_time, end_time, bi_list)
        zs.completed = True
        return zs

    def test_detect_3B_success(self):
        # Setup
        t0 = datetime(2023, 1, 1, 10, 0)
        
        # Zhongshu (90-100)
        # We need bis for ZS to be valid in context? 
        # Logic uses context['zhongshu_list']
        
        # ZS Bis (Dummy)
        b1 = self.create_mock_bi(1, 'up', 90, 100, t0, t0+timedelta(minutes=30))
        b2 = self.create_mock_bi(2, 'down', 100, 90, t0+timedelta(minutes=30), t0+timedelta(minutes=60))
        b3 = self.create_mock_bi(3, 'up', 90, 100, t0+timedelta(minutes=60), t0+timedelta(minutes=90))
        
        zs = self.create_mock_zhongshu(1, 100, 90, t0, t0+timedelta(minutes=90), [b1, b2, b3])
        
        # Leave Bi (Up): 95 -> 110 (Leaves ZG=100)
        t_leave_start = t0 + timedelta(minutes=90)
        t_leave_end = t0 + timedelta(minutes=120)
        leave_bi = self.create_mock_bi(4, 'up', 95, 110, t_leave_start, t_leave_end)
        
        # Pullback Bi (Down): 110 -> 102 (Stays above ZG=100)
        t_pb_start = t_leave_end
        t_pb_end = t0 + timedelta(minutes=150)
        pullback_bi = self.create_mock_bi(5, 'down', 110, 102, t_pb_start, t_pb_end)
        
        context = {
            'zhongshu_list': [zs],
            'bi_list': [b1, b2, b3, leave_bi, pullback_bi]
        }
        
        signal = self.detector.detect_3B(pullback_bi, context)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '3B')
        self.assertEqual(signal.price, 102)
        self.assertTrue(signal.score >= 60)
        self.assertEqual(signal.extra_info['leave_bi'].id, leave_bi.id)

    def test_detect_3B_fail_reenter(self):
        # Setup similar to success but pullback goes too low
        t0 = datetime(2023, 1, 1, 10, 0)
        zs = self.create_mock_zhongshu(1, 100, 90, t0, t0+timedelta(minutes=90), [])
        
        leave_bi = self.create_mock_bi(4, 'up', 95, 110, t0+timedelta(minutes=90), t0+timedelta(minutes=120))
        
        # Pullback to 98 (<= 100)
        pullback_bi = self.create_mock_bi(5, 'down', 110, 98, t0+timedelta(minutes=120), t0+timedelta(minutes=150))
        
        context = {
            'zhongshu_list': [zs],
            'bi_list': [leave_bi, pullback_bi] # Simplified bi list
        }
        
        signal = self.detector.detect_3B(pullback_bi, context)
        self.assertIsNone(signal)

    def test_detect_3B_fail_not_leave(self):
        t0 = datetime(2023, 1, 1, 10, 0)
        zs = self.create_mock_zhongshu(1, 100, 90, t0, t0+timedelta(minutes=90), [])
        
        # Leave Bi High 99 <= 100 (Not leaving)
        leave_bi = self.create_mock_bi(4, 'up', 90, 99, t0+timedelta(minutes=90), t0+timedelta(minutes=120))
        pullback_bi = self.create_mock_bi(5, 'down', 99, 95, t0+timedelta(minutes=120), t0+timedelta(minutes=150))
        
        context = {
            'zhongshu_list': [zs],
            'bi_list': [leave_bi, pullback_bi]
        }
        
        signal = self.detector.detect_3B(pullback_bi, context)
        self.assertIsNone(signal)

    def test_detect_3S_success(self):
        # Setup
        t0 = datetime(2023, 1, 1, 10, 0)
        
        # Zhongshu (90-100)
        zs = self.create_mock_zhongshu(1, 100, 90, t0, t0+timedelta(minutes=90), [])
        
        # Leave Bi (Down): 95 -> 80 (Leaves ZD=90)
        leave_bi = self.create_mock_bi(4, 'down', 95, 80, t0+timedelta(minutes=90), t0+timedelta(minutes=120))
        
        # Pullback Bi (Up): 80 -> 88 (Stays below ZD=90)
        pullback_bi = self.create_mock_bi(5, 'up', 80, 88, t0+timedelta(minutes=120), t0+timedelta(minutes=150))
        
        context = {
            'zhongshu_list': [zs],
            'bi_list': [leave_bi, pullback_bi]
        }
        
        signal = self.detector.detect_3S(pullback_bi, context)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '3S')
        self.assertEqual(signal.price, 88)
        self.assertTrue(signal.score >= 60)

if __name__ == '__main__':
    unittest.main()
