import requests
import sys
import time

BASE_URL = "http://127.0.0.1:8001"

def check_server_health():
    print(f"Checking server health at {BASE_URL}...")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        if resp.status_code == 200:
            print("[PASS] Server is reachable and serving UI.")
            return True
        else:
            print(f"[FAIL] Server returned status code {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[FAIL] Connection refused. Server might be down.")
        return False
    except Exception as e:
        print(f"[FAIL] Error checking server: {e}")
        return False

def check_api_endpoints():
    endpoints = [
        ("/api/backtests", "Backtest History"),
        ("/api/signals?limit=1", "Signals"),
        ("/api/analysis/TEST_SYM/1d", "Chart Analysis (Dummy)")
    ]
    
    all_passed = True
    for path, name in endpoints:
        print(f"Checking API: {name} ({path})...")
        try:
            resp = requests.get(f"{BASE_URL}{path}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if path == "/api/backtests" and not isinstance(data, list):
                     print(f"[FAIL] {name}: Expected list, got {type(data)}")
                     all_passed = False
                else:
                    print(f"[PASS] {name} OK")
            else:
                print(f"[FAIL] {name}: Status {resp.status_code}")
                all_passed = False
        except Exception as e:
            print(f"[FAIL] {name}: Exception {e}")
            all_passed = False
            
    return all_passed

if __name__ == "__main__":
    if check_server_health():
        if check_api_endpoints():
            print("\n>>> ALL SYSTEM CHECKS PASSED <<<")
            sys.exit(0)
        else:
            print("\n>>> SOME API CHECKS FAILED <<<")
            sys.exit(1)
    else:
        print("\n>>> SERVER HEALTH CHECK FAILED <<<")
        sys.exit(1)
