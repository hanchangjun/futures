# Second Class Signal (2B/2S) Refactoring
## Overview
This module implements a systematic refactoring of the Second Class Buy/Sell Point (2B/2S) logic based on Chan Theory. It addresses previous defects related to ambiguous definitions, level confusion, missing confirmations, and undefined time windows.

## Key Features
1.  **Strict Terminology**: Explicit definitions for "Current Level", "Sub-Level", "Bi", etc.
2.  **Level Decoupling**: Uses `LevelValidator` to ensure structural integrity.
3.  **Multi-Confirmation**: Requires Fractal Closure, Sub-Level 1B/1S, and Sub-Sub-Level MACD Divergence.
4.  **Filters**:
    *   **Time**: 3-21 Bars for Pullback.
    *   **Space**: No overlap with Previous ZhongShu (Strong 2B/2S).
5.  **Symmetry**: Fully symmetric implementation for Buy (2B) and Sell (2S) signals.
6.  **Scoring**: Strength score (0-1) provided for every signal.

## Usage Example
```python
from strategy.second_class_signal import SecondClassSignal
from strategy.common_types import SignalResult

# Initialize
validator = SecondClassSignal()

# Context (populated from strategy engine)
context = {
    'curr_bi': current_pullback_bi,
    'prev_bi': previous_leaving_bi,
    'centers': centers_list,
    'last_zhongshu_high': 3500,
    'last_zhongshu_low': 3480,
    # ... other required fields
}

# Check 2B
result = validator.conditions_2B(context)
if result:
    print(f"2B Signal Found! Strength: {result.meta['strength']}")
    print(f"Details: {result.meta}")
else:
    print(f"Rejected: {result.meta['rejection_reason']}")
```

## Threshold Tuning
The `SecondClassSignal` class uses a `CONSTANTS` dictionary for easy tuning:

*   `RETRACE_MIN` (0.3): Minimum retrace depth (Fibonacci 0.382 approx).
*   `RETRACE_MAX` (0.9): Maximum retrace depth.
*   `VALID_K_RANGE` (3, 21): Time window for pullback duration (in bars).
*   `MACD_DIV_THRESHOLD` (0.1): Minimum divergence value.
*   `STRENGTH_STRONG` (0.7): Threshold for STRONG signal classification.

## Performance Benchmark
(Placeholder for Backtest Results)
*   **Period**: 2015-2023 (CSI 300 5min)
*   **Win Rate Improvement**: >3% (Target)
*   **Risk/Reward Ratio Improvement**: >5% (Target)
*   **Significance**: p < 0.05 (Target)

*Note: Run `tests/test_second_class.py` to verify logic symmetry and constraint enforcement.*
