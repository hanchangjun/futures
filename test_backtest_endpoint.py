import requests
import json

BASE_URL = "http://localhost:8000"

def test_backtest():
    print("Testing Event Backtest Endpoint...")
    payload = {
        "symbol": "KQ.m@SHFE.rb",
        "period": "30m",
        "days": 30,
        "filter_period": "1d",
        "strategy_name": "pure_chan"
    }
    
    try:
        url = f"{BASE_URL}/api/action/backtest"
        res = requests.post(url, json=payload)
        
        if res.status_code != 200:
            print(f"Failed with status {res.status_code}")
            print(res.text)
            return
            
        data = res.json()
        print("Backtest Response:")
        # Print summary instead of full json
        if "metrics" in data:
            print(f"Metrics: {json.dumps(data['metrics'], indent=2)}")
        else:
            print(f"Response keys: {data.keys()}")
            
        if "error" in data:
            print(f"Error: {data['error']}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_backtest()
