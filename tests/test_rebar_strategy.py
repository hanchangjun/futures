import unittest
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.rebar_strategy import RebarOptimizedChanSystem
from strategy.chan_core import Signal

class TestRebarOptimizedChanSystem(unittest.TestCase):
    def setUp(self):
        self.system = RebarOptimizedChanSystem()
        self.mock_context = {'basis': 0}

    def test_integer_level_adjustment(self):
        # 1. Price near 3600 (3610) -> Should be reduced (0.8)
        signal = Signal('1B', 3610, datetime(2023, 1, 1), 100)
        # 1月 seasonal is 0.9. Day time (00:00) -> 0.7 (Night quiet? Wait 00:00 is < 1)
        # 00:00 is < 1, so '夜盘_清淡' = 0.7
        # Total expected: 100 * 0.8 (int) * 0.9 (season) * 1.0 (basis) * 0.7 (time) * 1.0 (contract)
        # = 100 * 0.504 = 50.4
        
        # Let's test _integer_level_adjustment specifically first
        adj = self.system._integer_level_adjustment(3610)
        self.assertEqual(adj, 0.8)
        
        # Price far from level (3650) -> 1.0
        adj = self.system._integer_level_adjustment(3650)
        self.assertEqual(adj, 1.0)

    def test_seasonal_adjustment(self):
        # March (3) -> 1.2
        time = datetime(2023, 3, 15)
        adj = self.system._seasonal_adjustment(time)
        self.assertEqual(adj, 1.2)
        
        # July (7) -> 0.8
        time = datetime(2023, 7, 15)
        adj = self.system._seasonal_adjustment(time)
        self.assertEqual(adj, 0.8)

    def test_trading_time_adjustment(self):
        # Day (10:00) -> 1.0
        time = datetime(2023, 1, 1, 10, 0)
        adj = self.system._trading_time_adjustment(time)
        self.assertEqual(adj, 1.0)
        
        # Night Active (22:00) -> 0.9
        time = datetime(2023, 1, 1, 22, 0)
        adj = self.system._trading_time_adjustment(time)
        self.assertEqual(adj, 0.9)
        
        # Night Quiet (00:30) -> 0.7
        time = datetime(2023, 1, 1, 0, 30)
        adj = self.system._trading_time_adjustment(time)
        self.assertEqual(adj, 0.7)

    def test_full_adjustment(self):
        # Combine all
        # Price 3650 (1.0), March (1.2), Day (1.0), Basis (1.0)
        # Score 50 -> 50 * 1.0 * 1.2 * 1.0 * 1.0 = 60
        signal = Signal('1B', 3650, datetime(2023, 3, 15, 10, 0), 50)
        adjusted = self.system.adjust_signal_for_rebar(signal, self.mock_context)
        self.assertAlmostEqual(adjusted.score, 60.0)
        
        # Cap at 100
        signal = Signal('1B', 3650, datetime(2023, 3, 15, 10, 0), 90)
        # 90 * 1.2 = 108 -> 100
        adjusted = self.system.adjust_signal_for_rebar(signal, self.mock_context)
        self.assertEqual(adjusted.score, 100)

if __name__ == '__main__':
    unittest.main()
