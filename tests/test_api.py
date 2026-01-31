import pytest
from unittest.mock import patch, MagicMock
from database.models import BacktestResult

def test_read_signals(client, db_session):
    response = client.get("/api/signals")
    assert response.status_code == 200
    assert response.json() == {"data": [], "total": 0, "page": 1, "limit": 20}

def test_trigger_backtest_success(client, db_session, sample_bars):
    # Patch get_bars to return sample data
    # Note: web.main imports run_event_backtest inside the function, 
    # so we patch where it is defined or imported in that module.
    # runner.event_backtest imports get_bars from datafeed.
    
    with patch("runner.event_backtest.get_bars", return_value=(sample_bars, "TEST")):
        response = client.post("/api/action/backtest", json={
            "symbol": "TEST",
            "period": "1m",
            "days": 1,
            "tq_user": "user",
            "tq_pass": "pass",
            "count": 100,
            "filter_period": None
        })
        
        data = response.json()
        assert response.status_code == 200, f"Status code: {response.status_code}, Response: {data}"
        assert data["status"] == "success", f"Backtest failed: {data.get('message')}"
        assert "db_id" in data
        
        # Verify DB persistence
        result = db_session.query(BacktestResult).first()
        assert result is not None
        assert result.symbol == "TEST"
        # Check trades serialization (should be list of dicts with ISO dates)
        # Even if no trades, the field should be a list
        assert isinstance(result.trades, list)
        assert isinstance(result.logs, list)

def test_backtest_history(client, db_session):
    # Create a dummy result
    result = BacktestResult(
        symbol="TEST_HIST",
        period="5m",
        days=5,
        start_dt=None,
        end_dt=None,
        initial_capital=10000,
        final_equity=11000,
        pnl=1000,
        roi=10.0,
        total_trades=5,
        win_rate=60.0,
        trades=[],
        logs=[],
        positions={}
    )
    db_session.add(result)
    db_session.commit()
    
    response = client.get("/api/backtests")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "TEST_HIST"
