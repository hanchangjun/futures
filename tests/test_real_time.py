import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from strategy.real_time import RealTimeTradingSystem
from strategy.chan_core import Signal
from datafeed import PriceBar

class TestRealTimeTradingSystem(unittest.TestCase):
    def setUp(self):
        self.symbol = "RB"
        self.notifier_mock = MagicMock()
        self.strategy_mock = MagicMock()
        # Ensure strategy has the attribute
        self.strategy_mock.买卖点记录 = []
        
        self.system = RealTimeTradingSystem(
            symbol=self.symbol,
            notifier=self.notifier_mock
        )
        # Inject mock strategy
        self.system.strategy = self.strategy_mock
        self.system.data_source = "mock"

    @patch('strategy.real_time.get_bars')
    def test_run_once_no_data(self, mock_get_bars):
        mock_get_bars.return_value = ([], "No data")
        
        self.system.run_once()
        
        mock_get_bars.assert_called_with(
            source="mock", 
            symbol="RB", 
            period="30m", 
            count=2000
        )
        self.strategy_mock.analyze.assert_not_called()

    @patch('strategy.real_time.get_bars')
    def test_run_once_new_signal(self, mock_get_bars):
        # Mock bars
        bars = [PriceBar(date=datetime.now(), open=100, high=110, low=90, close=105)]
        mock_get_bars.return_value = (bars, "OK")
        
        # Mock signal
        signal = Signal(
            signal_type="1B",
            price=105,
            time=datetime(2023, 1, 1, 10, 0),
            score=90
        )
        self.strategy_mock.买卖点记录 = [signal]
        
        self.system.run_once()
        
        # Verify analysis called
        self.strategy_mock.analyze.assert_called_with(bars)
        
        # Verify notification sent
        self.notifier_mock.send_order_notification.assert_called_once()
        
        # Check call args
        args, _ = self.notifier_mock.send_order_notification.call_args
        order = args[0]
        self.assertEqual(order['type'], 'BUY') # 1B -> BUY
        self.assertEqual(order['price'], 105)
        self.assertEqual(order['signal'], signal)

    @patch('strategy.real_time.get_bars')
    def test_run_once_duplicate_signal(self, mock_get_bars):
        bars = [PriceBar(date=datetime.now(), open=100, high=110, low=90, close=105)]
        mock_get_bars.return_value = (bars, "OK")
        
        signal = Signal(
            signal_type="1B",
            price=105,
            time=datetime(2023, 1, 1, 10, 0),
            score=90
        )
        self.strategy_mock.买卖点记录 = [signal]
        
        # First run
        self.system.run_once()
        self.notifier_mock.send_order_notification.assert_called_once()
        self.notifier_mock.reset_mock()
        
        # Second run (same signal)
        self.system.run_once()
        self.notifier_mock.send_order_notification.assert_not_called()

    @patch('strategy.real_time.get_bars')
    def test_run_once_newer_signal(self, mock_get_bars):
        bars = [PriceBar(date=datetime.now(), open=100, high=110, low=90, close=105)]
        mock_get_bars.return_value = (bars, "OK")
        
        signal1 = Signal(
            signal_type="1B",
            price=105,
            time=datetime(2023, 1, 1, 10, 0),
            score=90
        )
        self.strategy_mock.买卖点记录 = [signal1]
        
        # First run
        self.system.run_once()
        self.notifier_mock.send_order_notification.assert_called_once()
        self.notifier_mock.reset_mock()
        
        # Second run (new signal)
        signal2 = Signal(
            signal_type="1S",
            price=110,
            time=datetime(2023, 1, 1, 11, 0),
            score=80
        )
        self.strategy_mock.买卖点记录 = [signal1, signal2]
        
        self.system.run_once()
        self.notifier_mock.send_order_notification.assert_called_once()
        args, _ = self.notifier_mock.send_order_notification.call_args
        self.assertEqual(args[0]['type'], 'SELL') # 1S -> SELL

if __name__ == '__main__':
    unittest.main()
