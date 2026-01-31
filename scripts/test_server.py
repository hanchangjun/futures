import requests
import sys

BASE_URL = "http://127.0.0.1:8001"

def test_endpoint(name, path):
    print(f"Testing {name} ({path})...")
    try:
        resp = requests.get(f"{BASE_URL}{path}", timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"Response type: {type(data)}")
                if isinstance(data, list):
                    print(f"List length: {len(data)}")
                    if len(data) > 0:
                        print(f"First item keys: {data[0].keys()}")
                elif isinstance(data, dict):
                    print(f"Keys: {data.keys()}")
                else:
                    print(f"Content: {str(data)[:100]}")
            except Exception as e:
                print(f"JSON Decode Error: {e}")
                print(f"Raw content: {resp.text[:200]}")
        else:
            print(f"Error Content: {resp.text[:200]}")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    test_endpoint("Root", "/")
    test_endpoint("Backtests", "/api/backtests")
    test_endpoint("Signals", "/api/signals?limit=1")
    # Test a chart endpoint if we know a symbol - using a dummy one first to see if 404 or connection error
    test_endpoint("Analysis (Dummy)", "/api/analysis/TEST/1d")
