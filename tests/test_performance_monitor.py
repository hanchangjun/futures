import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timedelta
from strategy.performance_monitor import PerformanceMonitor
from strategy.chan_core import Signal
from datafeed.base import PriceBar

class TestPerformanceMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = PerformanceMonitor()
        
        # Mock Market Data
        dates = [datetime(2023, 1, 1, 10, i) for i in range(30)]
        self.market_df = pd.DataFrame({
            'date': dates,
            'open': [100] * 30,
            'high': [110] * 30,
            'low': [90] * 30,
            'close': [105] * 30,
            'volume': [1000] * 30
        })
        
        # Create PriceBar list for compatibility test
        self.market_bars = [
            PriceBar(d, 100, 110, 90, 105, 1000) for d in dates
        ]

    def test_monitor_signals_basic(self):
        # Create a signal at index 0
        signal = Signal(
            signal_type="1B",
            price=100,
            time=self.market_df['date'].iloc[0],
            score=80
        )
        
        self.monitor.monitor_signals([signal], self.market_df)
        
        self.assertEqual(len(self.monitor.metrics_history), 1)
        metric = self.monitor.metrics_history[0]
        self.assertEqual(metric['signal_type'], '1B')
        self.assertEqual(metric['entry_price'], 100)
        # MFE: High(110) - Entry(100) = 10
        self.assertEqual(metric['max_favorable'], 10)
        # MAE: Entry(100) - Low(90) = 10
        self.assertEqual(metric['max_adverse'], 10)
        # Final (20 periods): Close(105) - Entry(100) = 5
        self.assertEqual(metric['final_return'], 5)

    def test_monitor_signals_short(self):
        signal = Signal(
            signal_type="1S",
            price=100,
            time=self.market_df['date'].iloc[0],
            score=80
        )
        
        self.monitor.monitor_signals([signal], self.market_df)
        
        metric = self.monitor.metrics_history[0]
        # MFE Short: Entry(100) - Low(90) = 10
        self.assertEqual(metric['max_favorable'], 10)
        # MAE Short: High(110) - Entry(100) = 10
        self.assertEqual(metric['max_adverse'], 10)
        # Final Short: Entry(100) - Close(105) = -5
        self.assertEqual(metric['final_return'], -5)

    def test_optimize_parameters(self):
        # Add mock metrics history
        # 10 good trades, 10 bad trades
        for i in range(20):
            self.monitor.metrics_history.append({
                'signal_type': '1B',
                'score': 80 if i < 15 else 50, # High scores mostly win
                'final_return': 10 if i < 15 else -10,
                'timestamp': datetime.now(),
                'max_favorable': 20,
                'max_adverse': 5
            })
            
        params = self.monitor.optimize_parameters()
        
        self.assertIn('1B', params)
        # Should have good parameters because win rate is 15/20 = 75%
        # Threshold likely around 80 or lower
        # Since score 80 wins and 50 loses, best threshold should exclude 50.
        # Threshold 80: 15 trades, 100% win rate.
        # Threshold 50: 20 trades, 75% win rate.
        # Both good, but 80 might be better expectancy.
        self.assertTrue(params['1B']['min_score'] >= 50)

    def test_input_conversion(self):
        """Test with List[PriceBar] input"""
        signal = Signal(
            signal_type="1B",
            price=100,
            time=self.market_bars[0].date,
            score=80
        )
        
        self.monitor.monitor_signals([signal], self.market_bars)
        self.assertEqual(len(self.monitor.metrics_history), 1)

if __name__ == '__main__':
    unittest.main()
