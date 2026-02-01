import time
import cProfile
import pstats
import random
from datetime import datetime
from strategy.signal_scorer import SignalScorer, ScorableSignal, SignalType
from strategy.signal_filter import SignalFilter

def generate_random_signal(i):
    return ScorableSignal(
        signal_id=f"SIG_{i}",
        signal_type=random.choice(list(SignalType)),
        timestamp=datetime.now(),
        price=100.0 + random.uniform(-10, 10),
        is_structure_complete=random.choice([True, False]),
        structure_quality=random.uniform(0, 100),
        divergence_score=random.uniform(0, 100),
        volume=random.uniform(100, 500),
        avg_volume=200,
        trend_duration=random.uniform(20, 200),
        position_level=random.uniform(0, 100),
        has_sub_level_structure=random.choice([True, False]),
        momentum_val=random.uniform(0, 100),
        is_fractal_confirmed=random.choice([True, False]),
        meta={
            'minutes_to_news': random.choice([None, 100, 10]),
            'limit_proximity_percent': random.uniform(0, 5)
        }
    )

def run_benchmark():
    filter_sys = SignalFilter("config.yaml")
    signals = [generate_random_signal(i) for i in range(1000)]
    
    print(f"Benchmarking 1000 signals...")
    
    # Timing
    start_time = time.time()
    results = []
    for sig in signals:
        res = filter_sys.filter_signal(sig)
        results.append(res)
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time_ms = (total_time / 1000) * 1000
    
    print(f"Total Time: {total_time:.4f}s")
    print(f"Avg Time per Signal: {avg_time_ms:.4f}ms")
    
    pass_count = sum(1 for r in results if r)
    print(f"Pass Rate: {pass_count}/1000 ({pass_count/10.0}%)")
    
    if avg_time_ms <= 5.0:
        print("PERFORMANCE: PASS (<= 5ms)")
    else:
        print("PERFORMANCE: FAIL (> 5ms)")

def run_profile():
    print("\nRunning cProfile...")
    cProfile.run('run_benchmark()', 'benchmark.prof')
    
    stats = pstats.Stats('benchmark.prof')
    stats.strip_dirs().sort_stats('cumtime').print_stats(10)
    print("Profile saved to benchmark.prof")

if __name__ == "__main__":
    run_benchmark()
    run_profile()
