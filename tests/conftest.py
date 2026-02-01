import pytest
from strategy.third_class_config import ThirdClassConfig
from strategy.third_class_signal import ThirdClassSignal
from strategy.rules import ThirdClassRules

@pytest.fixture
def base_config():
    return ThirdClassConfig()

@pytest.fixture
def signal_analyzer(base_config):
    return ThirdClassSignal(base_config)

@pytest.fixture
def rules_engine(base_config):
    return ThirdClassRules(base_config)

@pytest.fixture
def valid_3b_context():
    return {
        'zd': 100.0,
        'zg': 110.0,
        'gg': 115.0, # Center High
        'dd': 95.0,  # Center Low
        'center_bars': 20, # Segments
        'leave_bar': {'high': 130.0, 'low': 110.0, 'count': 10},
        'retrace_bar': {'high': 125.0, 'low': 115.0, 'count': 3}, # Low > ZG (115 > 110)
        'volume_leave': 1000,
        'volume_retrace': 500,
        'higher_tf_buy': True,
        'lower_tf_buy': True,
        'higher_tf_sell': False,
        'lower_tf_sell': False
    }

@pytest.fixture
def valid_3s_context():
    return {
        'zd': 100.0,
        'zg': 110.0,
        'gg': 115.0,
        'dd': 95.0,
        'center_bars': 20,
        'leave_bar': {'high': 100.0, 'low': 80.0, 'count': 10}, # Low < ZD (80 < 100)
        'retrace_bar': {'high': 95.0, 'low': 85.0, 'count': 3}, # High < ZD (95 < 100)
        'volume_leave': 1000,
        'volume_retrace': 500,
        'higher_tf_buy': False,
        'lower_tf_buy': False,
        'higher_tf_sell': True,
        'lower_tf_sell': True
    }
