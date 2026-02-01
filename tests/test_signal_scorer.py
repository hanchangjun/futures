import pytest
from datetime import datetime
from strategy.signal_scorer import SignalScorer, ScorableSignal, SignalType

@pytest.fixture
def scorer():
    # Use default config or mock
    return SignalScorer("config.yaml")

def test_score_calculation_basics(scorer):
    sig = ScorableSignal(
        signal_id="TEST001",
        signal_type=SignalType.B1,
        timestamp=datetime.now(),
        price=100.0,
        is_structure_complete=True,
        structure_quality=80.0,
        divergence_score=90.0,
        volume=201,
        avg_volume=100, # Ratio 2.01 -> 100
        trend_duration=120, # >100 -> 90
        position_level=20.0, # Buy @ 20 -> 80
        has_sub_level_structure=True, # 100
        momentum_val=50.0,
        is_fractal_confirmed=True # 100
    )
    
    score = scorer.calculate_score(sig)
    # Check details
    details = sig.meta.get('score_details', {})
    
    assert details['structure'] == 50 + 40 # 90
    assert details['divergence'] == 90
    assert details['volume_price'] == 100 # > 2.0
    assert details['time'] == 90 # > 100
    assert details['sub_level'] == 100
    assert details['confirmation'] == 100
    
    assert score > 0
    assert score <= 100

def test_score_weights_handling(scorer):
    # If we zero out weights, score should be 0?
    # But scorer loads config. We can modify scorer.weights directly for testing
    scorer.weights = {k: 0 for k in scorer.weights}
    scorer.weights['structure'] = 100
    
    sig = ScorableSignal(
        signal_id="TEST002",
        signal_type=SignalType.B1,
        timestamp=datetime.now(),
        price=100.0,
        is_structure_complete=True, # 50
        structure_quality=0.0
    )
    
    score = scorer.calculate_score(sig)
    assert score == 50.0

def test_dimension_score_method(scorer):
    sig = ScorableSignal(
        signal_id="TEST003",
        signal_type=SignalType.B1,
        timestamp=datetime.now(),
        price=100.0,
        divergence_score=75.5
    )
    val = scorer.calculate_dimension_score('divergence', sig)
    assert val == 75.5

def test_volume_logic(scorer):
    sig = ScorableSignal(
        signal_id="TEST_VOL",
        signal_type=SignalType.B1,
        timestamp=datetime.now(),
        price=100.0,
        volume=100,
        avg_volume=100 # Ratio 1.0
    )
    # Ratio 1.0 -> 40 (<=1.0)
    score = scorer.calculate_dimension_score('volume_price', sig)
    assert score == 40.0
    
    sig.volume = 160 # Ratio 1.6 -> >1.5 -> 80
    score = scorer.calculate_dimension_score('volume_price', sig)
    assert score == 80.0
