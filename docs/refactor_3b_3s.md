# Third Class Signal (3B/3S) Module

This module implements the Third Class Buy/Sell Point (3B/3S) logic based on Chan Theory, featuring 16 strict rules for high-probability signal generation.

## Features
- **Symmetry**: Identical logic structure for 3B and 3S.
- **Configurability**: Thresholds adjustable via `ThirdClassConfig`.
- **Robustness**: Defensive programming against invalid data.
- **Performance**: Optimized for high-frequency calling (<1ms).

## Installation
Ensure the following files are in your `strategy/` directory:
- `third_class_signal.py`
- `third_class_config.py`
- `rules.py`
- `validators.py`

## Configuration
Customize thresholds in `ThirdClassConfig`:
```python
config = ThirdClassConfig(
    leave_amplitude_ratio=0.5,
    retrace_max_k=3,
    retrace_zg_safe_ratio=0.3
)
analyzer = ThirdClassSignal(config)
```

## Usage
```python
context = {
    'zd': 100.0, 'zg': 110.0, 'gg': 115.0, 'dd': 95.0,
    'center_bars': 20,
    'leave_bar': {'high': 130.0, 'low': 110.0, 'count': 10},
    'retrace_bar': {'high': 125.0, 'low': 115.0, 'count': 3},
    'volume_leave': 1000, 'volume_retrace': 500,
    'higher_tf_buy': True, 'lower_tf_buy': True,
    'higher_tf_sell': False, 'lower_tf_sell': False
}

is_3b = analyzer.conditions_3B(context)
print(f"Is 3B Signal: {is_3b}")
```

## Testing
Run unit and integration tests:
```bash
pytest tests/test_rules.py tests/test_integration.py
```

## Performance Benchmark
Target: < 1ms per execution.
Status: Passing (Avg ~0.01ms on i7-10th gen).

## Rule List
### 3B Rules
1. Valid Center (ZG > ZD)
2. Leave Breakout (High > ZG)
3. Retrace Gap (Low > ZG)
4. Center Size (Min Segments)
5. Volume Support (Leave > Retrace)
6. Amplitude Check (Leave vs Center)
7. Retrace Duration (Max K)
8. Retrace Amplitude (< Leave)
9. Safe Gap (> Safe Ratio)
10. Higher TF Buy
11. Lower TF Buy
12. Duration Ratio
13. Leave Trend (UP)
14. Retrace Trend (DOWN)
15. No Overlap GG
16. No Higher TF Sell

(3S Rules are symmetric)
