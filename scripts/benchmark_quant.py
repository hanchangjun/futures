import time
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategy.quant_logic import is_downtrend
from strategy.quant_types import IQuantCenter

class MockCenter:
    def __init__(self, gg, dd, start, end, count, start_index=0, end_index=0):
        self.gg = gg
        self.dd = dd
        self.start_time = start
        self.end_time = end
        self.count = count
        self.start_index = start_index
        self.end_index = end_index

def benchmark_is_downtrend():
    # Setup data
    c1 = MockCenter(110, 100, datetime(2023,1,1), datetime(2023,1,2), 10, 0, 10)
    c2 = MockCenter(100, 90, datetime(2023,1,3), datetime(2023,1,4), 10, 20, 50)
    centers = [c1, c2]
    current_price = 85.0
    
    # Warmup
    for _ in range(100):
        is_downtrend(centers, current_price)
        
    # Benchmark
    iterations = 10000
    start_time = time.time()
    
    for _ in range(iterations):
        is_downtrend(centers, current_price)
        
    end_time = time.time()
    total_time = end_time - start_time
    avg_time_ms = (total_time / iterations) * 1000
    
    print(f"Benchmark is_downtrend:")
    print(f"Total time for {iterations} iterations: {total_time:.4f}s")
    print(f"Average time per call: {avg_time_ms:.4f} ms")
    
    if avg_time_ms < 1.0:
        print("PASS: Performance < 1ms")
    else:
        print("FAIL: Performance > 1ms")

if __name__ == "__main__":
    benchmark_is_downtrend()
