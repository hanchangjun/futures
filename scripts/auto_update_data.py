import time
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.import_data import run_import

# Configuration
SYMBOLS = ["KQ.m@SHFE.rb", "KQ.m@CZCE.FG"] 
PERIODS = ["30m", "1d"]
INTERVAL_SECONDS = 3600 # 1 hour

def update_all():
    print(f"[{datetime.now()}] Starting scheduled data update...")
    tq_user = os.getenv("TQ_USERNAME")
    tq_pass = os.getenv("TQ_PASSWORD")
    
    if not tq_user or not tq_pass:
        print("Warning: TQ_USERNAME/TQ_PASSWORD not set. Update might fail if credentials are needed.")
    
    for symbol in SYMBOLS:
        for period in PERIODS:
            try:
                # Count=1000 ensures we cover recent history even if there are gaps
                print(f"Updating {symbol} {period}...")
                run_import(symbol, period, count=1000, tq_user=tq_user, tq_pass=tq_pass)
            except Exception as e:
                print(f"Error updating {symbol} {period}: {e}")
    print(f"[{datetime.now()}] Update cycle completed.")

def main():
    print(f"Data Auto-Updater Started.")
    print(f"Target Symbols: {SYMBOLS}")
    print(f"Update Interval: {INTERVAL_SECONDS} seconds")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            update_all()
            print(f"Sleeping for {INTERVAL_SECONDS} seconds...")
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nAuto-Updater stopped by user.")

if __name__ == "__main__":
    main()
