
import unittest
import sys
import os
import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.first_class_signal import FirstClassSignalDetector
from strategy.chan_core import Bi, Zhongshu, Signal

class TestFirstClassSignalDetector(unittest.TestCase):
    
    def setUp(self):
        self.detector = FirstClassSignalDetector()
        self.now = datetime.datetime.now()

    def create_mock_bi(self, bi_id, direction, start_price, end_price, volume_sum=1000, macd_sum=10.0, diff_peak=1.0):
        bi = Bi(
            bi_id=bi_id,
            direction=direction,
            start_price=start_price,
            end_price=end_price,
            start_time=self.now,
            end_time=self.now,
            high=max(start_price, end_price),
            low=min(start_price, end_price),
            bars=5
        )
        bi.volume_sum = volume_sum
        bi.macd_data = {'sum': macd_sum, 'diff_peak': diff_peak}
        return bi

    def create_mock_zhongshu(self, zs_id, zg, zd, gg, dd, bi_list):
        zs = Zhongshu(
            zs_id=zs_id,
            zg=zg,
            zd=zd,
            gg=gg,
            dd=dd,
            start_time=self.now,
            end_time=self.now,
            bi_list=bi_list
        )
        return zs

    def test_detect_1B_success(self):
        # Scenario: Down Trend with 2 Zhongshus, New Low, MACD Divergence
        
        # 1. Create Bis
        # ZS1 Bis
        b1 = self.create_mock_bi(1, 'down', 100, 90)
        b2 = self.create_mock_bi(2, 'up', 90, 95)
        b3 = self.create_mock_bi(3, 'down', 95, 88) # ZS1: ZG=95, ZD=90 (approx)
        
        # Connection
        b4 = self.create_mock_bi(4, 'up', 88, 92)
        
        # ZS2 Bis
        b5 = self.create_mock_bi(5, 'down', 92, 85)
        b6 = self.create_mock_bi(6, 'up', 85, 89)
        b7 = self.create_mock_bi(7, 'down', 89, 82) # ZS2: ZG=89, ZD=85
        
        # Enter Bi for ZS2 (b4 is entering bi to ZS2?) 
        # ZS2 consists of b5, b6, b7. Entering bi is b4.
        # Leaving Bi (Signal Candidate)
        b8 = self.create_mock_bi(8, 'up', 82, 86) # Correction
        b9 = self.create_mock_bi(9, 'down', 86, 80, volume_sum=500, macd_sum=5.0, diff_peak=0.5) 
        # b9 is leaving bi. b4 is entering bi.
        
        # Configure ZS
        zs1 = self.create_mock_zhongshu(1, 95, 90, 100, 88, [b1, b2, b3])
        zs2 = self.create_mock_zhongshu(2, 89, 85, 92, 82, [b5, b6, b7])
        
        # Context
        context = {
            'zhongshu_list': [zs1, zs2],
            'bi_list': [b1, b2, b3, b4, b5, b6, b7, b8, b9]
        }
        
        # Set entering bi (b4) stats to be stronger than b9
        b4.volume_sum = 1000
        b4.macd_data = {'sum': 10.0, 'diff_peak': 1.0}
        
        # Detect
        signal = self.detector.detect_1B(b9, context)
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '1B')
        self.assertEqual(signal.price, 80)
        self.assertTrue(signal.score >= 60)
        
        # Verify Extra Info
        self.assertIn('trend_strength', signal.extra_info)
        self.assertIn('divergence_level', signal.extra_info)
        self.assertIn('volume_confirmation', signal.extra_info)

    def test_detect_1B_no_divergence(self):
        # Scenario: Down Trend but No Divergence
        
        # ... Similar setup ...
        # ZS2
        b5 = self.create_mock_bi(5, 'down', 92, 85)
        b6 = self.create_mock_bi(6, 'up', 85, 89)
        b7 = self.create_mock_bi(7, 'down', 89, 82)
        
        b4 = self.create_mock_bi(4, 'up', 88, 92, volume_sum=1000, macd_sum=10.0)
        
        # Leaving Bi (Stronger than entering)
        b9 = self.create_mock_bi(9, 'down', 86, 70, volume_sum=2000, macd_sum=20.0, diff_peak=2.0)
        
        zs1 = self.create_mock_zhongshu(1, 95, 90, 100, 88, [])
        zs2 = self.create_mock_zhongshu(2, 89, 85, 92, 82, [b5, b6, b7])
        
        context = {
            'zhongshu_list': [zs1, zs2],
            'bi_list': [b4, b5, b6, b7, b9] # Minimal list
        }
        
        signal = self.detector.detect_1B(b9, context)
        self.assertIsNone(signal)

    def test_detect_1S_success(self):
        # Scenario: Up Trend with 2 Zhongshus, New High, MACD Divergence
        
        # ZS1 (Low)
        b1 = self.create_mock_bi(1, 'up', 10, 20)
        b2 = self.create_mock_bi(2, 'down', 20, 15)
        b3 = self.create_mock_bi(3, 'up', 15, 22) # ZS1
        
        # Connection
        b4 = self.create_mock_bi(4, 'down', 22, 18)
        
        # ZS2 (High)
        b5 = self.create_mock_bi(5, 'up', 18, 25)
        b6 = self.create_mock_bi(6, 'down', 25, 20)
        b7 = self.create_mock_bi(7, 'up', 20, 28) # ZS2: ZG=25, ZD=20, GG=28
        
        # Enter Bi to ZS2 is b4 (Down? No, entering bi for Up Trend ZS is usually Up?)
        # Standard Up Trend: Up-Down-Up (ZS).
        # Entering Bi is the one *before* ZS.
        # If ZS starts with Up (b5), entering bi is b4 (Down).
        # Wait, Divergence in Up Trend: Compare Leaving Up Bi vs Entering Up Bi?
        # Chan Theory: Compare b_leave (Up) with b_enter (Up).
        # My code: _find_enter_bi gets "bi before ZS first bi".
        # If ZS = [b5(up), b6(down), b7(up)], first is b5.
        # Enter bi = b4 (down).
        # Comparison: b_leave (Up) vs b_enter (Down)? No, that's not right.
        # MACD Divergence compares same direction.
        
        # Let's check _find_enter_bi implementation and logic.
        # "比较：最后一段离开中枢的笔 vs 前一段进入中枢的笔"
        # If ZS is Up-Down-Up (Direction Up? No, ZS has no direction, but the Trend does).
        # In Up Trend, ZS is typically formed by Up-Down-Up? Or Down-Up-Down?
        # If Up Trend: ... Up(Enter) -> [Down-Up-Down](ZS) -> Up(Leave).
        # Then Enter is Up, Leave is Up. They match.
        
        # If ZS is [Up, Down, Up] (Standard ZS in Up Trend? No, ZS is overlap).
        # ZS is defined by 3 overlapping bis.
        # If Up Trend:
        # b_enter (Up) -> [b1(Down), b2(Up), b3(Down)] (ZS) -> b_leave (Up).
        # My _find_enter_bi finds b_enter.
        # So I need to construct ZS such that it starts with Down bi?
        # Or my ZS construction logic in chan_core.py?
        # ZS is just 3 consecutive bis.
        
        # If I want to test 1S (Up Trend Top), I need:
        # b_enter (Up) -> ZS [Down, Up, Down] -> b_leave (Up).
        
        b4 = self.create_mock_bi(4, 'up', 15, 25, volume_sum=1000, macd_sum=10.0) # Enter
        
        b5 = self.create_mock_bi(5, 'down', 25, 20)
        b6 = self.create_mock_bi(6, 'up', 20, 24)
        b7 = self.create_mock_bi(7, 'down', 24, 21) # ZS: 20-24
        
        b8 = self.create_mock_bi(8, 'up', 21, 30, volume_sum=500, macd_sum=5.0) # Leave
        
        zs2 = self.create_mock_zhongshu(2, 24, 20, 25, 20, [b5, b6, b7])
        zs1 = self.create_mock_zhongshu(1, 15, 10, 15, 10, []) # Lower ZS
        
        context = {
            'zhongshu_list': [zs1, zs2],
            'bi_list': [b4, b5, b6, b7, b8]
        }
        
        signal = self.detector.detect_1S(b8, context)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.type, '1S')

if __name__ == '__main__':
    unittest.main()
