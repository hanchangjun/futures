import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def check_analysis(symbol="KQ.m@SHFE.rb", period="30m", strategy="pure_chan"):
    print(f"Checking Analysis for {symbol} {period} {strategy}...")
    try:
        url = f"{BASE_URL}/api/analysis/{symbol}/{period}?limit=100&strategy_name={strategy}"
        res = requests.get(url)
        data = res.json()
        
        if "error" in data:
            print(f"Error in response: {data['error']}")
            return

        centers = data.get("centers", [])
        print(f"Centers count: {len(centers)}")
        if len(centers) > 0:
            c = centers[0]
            print(f"Sample Center: {json.dumps(c, indent=2)}")
            # Check for keys
            required = ["start_dt", "end_dt", "zg", "zd"]
            missing = [k for k in required if k not in c]
            if missing:
                print(f"Missing keys in center: {missing}")
            else:
                print("Center keys valid.")
        else:
            print("No centers found.")

        bi_list = data.get("bi_list", [])
        print(f"Bi count: {len(bi_list)}")
        
        signals = data.get("signals", [])
        print(f"Signals count: {len(signals)}")
        if len(signals) > 0:
            s = signals[0]
            print(f"Sample Signal: {json.dumps(s, indent=2)}")

    except Exception as e:
        print(f"Exception: {e}")

def check_bars(symbol="KQ.m@SHFE.rb", period="30m"):
    print(f"Checking Bars for {symbol} {period}...")
    try:
        url = f"{BASE_URL}/api/bars/{symbol}/{period}?limit=10"
        res = requests.get(url)
        data = res.json()
        print(f"Bars count: {len(data)}")
        if len(data) > 0:
            print(f"Sample Bar: {json.dumps(data[0], indent=2)}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_bars()
    print("-" * 20)
    check_analysis()
