import unittest
from datetime import datetime
from strategy.rebar.main_strategy import RiskManager, TradeSignal, SignalType, Position, MarketData

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            "risk_control": {
                "atr_period": 14,
                "signals": {
                    "1B": {"sl_multiplier": 1.2, "initial_pos": 0.03, "add_pos_target": 0.05},
                    "2B": {"initial_pos": 0.02, "max_pos": 0.08},
                    "3B": {"initial_pos": 0.02, "allow_add": False}
                },
                "global": {
                    "max_single_loss": 0.02,
                    "max_total_drawdown": 0.05
                }
            }
        }
        self.rm = RiskManager(self.config)
        self.rm.current_equity = 100000
        self.rm.peak_equity = 100000

    def test_1b_stop_loss(self):
        # SL = Low - 1.2 * ATR
        atr = 10.0
        signal = TradeSignal(
            signal_id="1", signal_type=SignalType.B1, timestamp=datetime.now(),
            price=3600, meta={"structure_low": 3590}
        )
        sl = self.rm.get_stop_loss_price(signal, atr, None)
        # 3590 - 1.2 * 10 = 3578
        self.assertEqual(sl, 3578)

    def test_position_sizing_1b(self):
        signal = TradeSignal("2", SignalType.B1, datetime.now(), 3600)
        allowed, size, reason = self.rm.check_entry_risk(signal, 100000)
        self.assertTrue(allowed)
        self.assertEqual(size, 0.03)

    def test_position_sizing_3b_no_add(self):
        signal = TradeSignal("3", SignalType.B3, datetime.now(), 3600)
        allowed, size, reason = self.rm.check_entry_risk(signal, 100000)
        self.assertTrue(allowed)
        self.assertEqual(size, 0.02)
        # Re-check logic if "No Add" is implemented for existing positions
        # Currently check_entry_risk just returns initial size. 
        # Logic for "No Add" would be in update or context check.

    def test_max_drawdown_rejection(self):
        self.rm.peak_equity = 100000
        # Current equity 94000 -> 6% DD > 5% limit
        allowed, size, reason = self.rm.check_entry_risk(TradeSignal("4", SignalType.B1, datetime.now(), 3600), 94000)
        self.assertFalse(allowed)
        self.assertIn("Max Drawdown", reason)

    def test_single_loss_force_close(self):
        # Pos: Long at 3600, Size 0.5 (50% equity for easy math to trigger 2% loss)
        # 2% of equity loss = 0.02.
        # If price drops X%, PnL = 0.5 * X.
        # We need 0.5 * X < -0.02 => X < -0.04 (4% drop).
        pos = Position(
            symbol="RB", direction="LONG", avg_price=3600, quantity=0.5, current_price=3600,
            signal_type=SignalType.B1, stop_loss=3000
        )
        self.rm.positions["RB"] = pos
        
        # Price 3400 (Drop 200/3600 = 5.5%)
        actions = self.rm.update_position("RB", 3400, 100000)
        self.assertIn("FORCE_CLOSE_LOSS", actions)

if __name__ == '__main__':
    unittest.main()
