
import requests
import sys
import json

BASE_URL = "http://localhost:8000"

def test_analyze_endpoint():
    print("Testing /api/analysis endpoint...")
    
    # Test Standard
    url = f"{BASE_URL}/api/analysis/KQ.m@SHFE.rb/30m?limit=200&strategy_name=standard"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ Standard Analysis: OK. Centers: {len(data.get('centers', []))}, Strategy: {data.get('strategy')}")
        else:
            print(f"❌ Standard Analysis Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"❌ Standard Analysis Error: {e}")

    # Test Pure Chan
    url = f"{BASE_URL}/api/analysis/KQ.m@SHFE.rb/30m?limit=200&strategy_name=pure_chan"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if data.get('strategy') is None:
                print(f"⚠️ Pure Chan Strategy Missing! Response: {json.dumps(data, indent=2)}")
            
            signals = data.get('signals', [])
            print(f"✅ Pure Chan Analysis: OK. Centers: {len(data.get('centers', []))}, Strategy: {data.get('strategy')}")
            print(f"   Signals Found: {len(signals)}")
            for s in signals:
                print(f"   - {s.get('type')}: {s.get('desc')} @ {s.get('dt')}")
        else:
            print(f"❌ Pure Chan Analysis Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"❌ Pure Chan Analysis Error: {e}")

def test_backtest_endpoint():
    print("\nTesting /api/action/backtest endpoint...")
    
    # Test Standard
    payload = {
        "symbol": "KQ.m@SHFE.rb",
        "period": "30m",
        "days": 10,
        "filter_period": "1d",
        "strategy_name": "standard"
    }
    try:
        res = requests.post(f"{BASE_URL}/api/action/backtest", json=payload)
        if res.status_code == 200:
            data = res.json()
            result = data.get("result", {})
            print(f"✅ Standard Backtest: OK. Trades: {result.get('total_trades')}, ROI: {result.get('roi'):.2f}%")
        else:
            print(f"❌ Standard Backtest Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"❌ Standard Backtest Error: {e}")

    # Test Pure Chan
    payload["strategy_name"] = "pure_chan"
    try:
        res = requests.post(f"{BASE_URL}/api/action/backtest", json=payload)
        if res.status_code == 200:
            data = res.json()
            result = data.get("result", {})
            print(f"✅ Pure Chan Backtest: OK. Trades: {result.get('total_trades')}, ROI: {result.get('roi'):.2f}%")
        else:
            print(f"❌ Pure Chan Backtest Failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"❌ Pure Chan Backtest Error: {e}")

if __name__ == "__main__":
    try:
        test_analyze_endpoint()
        test_backtest_endpoint()
    except Exception as e:
        print(f"Verification Failed: {e}")
