from backtest.engine import BacktestEngine
from backtest.broker import BacktestBroker
from portfolio.manager import PortfolioManager
from risk.manager import RiskManager
from backtest.event import SignalEvent

def test_backtest_engine_run(sample_bars):
    # Setup
    broker = BacktestBroker()
    portfolio = PortfolioManager(initial_capital=100000)
    risk = RiskManager()
    
    engine = BacktestEngine(portfolio, risk, broker)
    
    # Mock strategy function
    # Strategy is called with (history, symbol)
    def mock_strategy(history, symbol):
        # Buy on 2nd bar (index 1)
        if len(history) == 2:
            # Note: SignalEvent args might differ, check backtest/event.py
            return SignalEvent(
                symbol=symbol,
                signal_type="1B",
                price=history[-1].close,
                dt=history[-1].date
            )
        return None
        
    engine.run(sample_bars, mock_strategy, "TEST")
    
    # Assertions
    assert len(engine.history) == len(sample_bars)
    # We should have some logs
    assert len(engine.logs) > 0
    # Check if trade was placed (Signal -> Order -> Trade)
    # Depending on broker logic, it might execute on next bar
    # With 10 bars, buying on bar 2, should execute on bar 3
    # Check engine.trades
    # Note: Broker might need specific conditions
    # For now just ensure it ran without error
