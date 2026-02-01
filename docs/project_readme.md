# Signal Priority and Filtering System

A comprehensive system for scoring and filtering trading signals based on multi-dimensional criteria.

## Features

- **Multi-dimensional Scoring**: Scores signals (0-100) based on Structure, Divergence, Volume/Price, Time, Position, Sub-level, Strength, and Confirmation.
- **Configurable Weights**: All scoring weights and thresholds are defined in `config.yaml`.
- **Robust Filtering**:
  - **Mandatory Checks**: Structure completeness, Fractal confirmation.
  - **Exclusion Rules**: Major news windows, Low liquidity periods, Limit moves, Contract switch weeks.
  - **Score Threshold**: Signals below 70 are rejected.
- **High Performance**: End-to-end processing < 0.1ms per signal.
- **Structured Logging**: JSON-formatted logs for easy auditing.

## Installation

Requires Python 3.9+.

```bash
pip install pyyaml pytest
```

## Configuration

Edit `config.yaml` to adjust weights and rules:

```yaml
scorer:
  weights:
    structure: 20
    divergence: 20
    # ...
  thresholds:
    min_score: 60.0

filter:
  mandatory:
    check_structure_complete: true
  exclusion:
    major_news_window_minutes: 30
  acceptance:
    min_score: 70.0
```

## Usage

### Scoring a Signal

```python
from datetime import datetime
from strategy.signal_scorer import SignalScorer, ScorableSignal, SignalType

# Initialize scorer
scorer = SignalScorer("config.yaml")

# Create signal object
signal = ScorableSignal(
    signal_id="SIG001",
    signal_type=SignalType.B1,
    timestamp=datetime.now(),
    price=100.0,
    is_structure_complete=True,
    structure_quality=85.0,
    divergence_score=90.0,
    volume=200,
    avg_volume=100,
    # ... populate other fields
)

# Calculate score
score = scorer.calculate_score(signal)
print(f"Signal Score: {score}")
print(f"Details: {signal.meta['score_details']}")
```

### Filtering a Signal

```python
from strategy.signal_filter import SignalFilter

# Initialize filter (automatically loads scorer)
signal_filter = SignalFilter("config.yaml")

# Check signal
is_passed = signal_filter.filter_signal(signal)

if is_passed:
    print("Signal Accepted!")
else:
    print("Signal Rejected.")
```

## Testing & Benchmark

Run unit tests:
```bash
python -m pytest tests/
```

Run performance benchmark:
```bash
python benchmark.py
```
Benchmark output includes execution time stats and saves a `benchmark.prof` file for profiling analysis.

## Logging Format

Logs are output in JSON format:
```json
{"signal_id": "SIG_0", "timestamp": "2023-10-27T10:00:00", "score": 75.5, "pass_flag": true, "reject_reason": null}
```
