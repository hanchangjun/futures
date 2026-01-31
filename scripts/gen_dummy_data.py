import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def generate_sine_data(start_date, periods, freq, base_price=3500, amp=100, noise_std=5):
    dates = pd.date_range(start=start_date, periods=periods, freq=freq)
    
    # Generate trend + sine wave + noise
    x = np.linspace(0, 4 * np.pi, periods)
    trend = np.linspace(0, 50, periods) # Slight upward trend
    sine = amp * np.sin(x)
    noise = np.random.normal(0, noise_std, periods)
    
    close = base_price + trend + sine + noise
    
    # Generate OHLC
    data = []
    for i in range(periods):
        c = close[i]
        o = c + np.random.normal(0, noise_std)
        h = max(o, c) + abs(np.random.normal(0, noise_std/2))
        l = min(o, c) - abs(np.random.normal(0, noise_std/2))
        data.append({
            "datetime": dates[i],
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": int(np.random.uniform(1000, 5000))
        })
        
    return pd.DataFrame(data)

def main():
    output_dir = "backtest/data"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Generate 30m data
    # 30 days * 10 hours * 2 = 600 bars. Let's generate 2000 bars.
    print("Generating 30m data...")
    df_30m = generate_sine_data(datetime.now() - timedelta(days=60), 2000, "30min", base_price=3500, amp=100)
    # TQSDK/CSV format usually: datetime, open, high, low, close, volume, ...
    # Our file_feed expects: date, open, high, low, close, volume
    df_30m.to_csv(f"{output_dir}/KQ.m@SHFE.rb_30m.csv", index=False)
    
    # 2. Generate 1d data
    print("Generating 1d data...")
    df_1d = generate_sine_data(datetime.now() - timedelta(days=365), 500, "D", base_price=3500, amp=100)
    df_1d.to_csv(f"{output_dir}/KQ.m@SHFE.rb_1d.csv", index=False)
    
    print(f"Data generated in {output_dir}")

if __name__ == "__main__":
    main()
