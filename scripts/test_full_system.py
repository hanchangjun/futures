import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from web.main import app
import json
from datetime import datetime

client = TestClient(app)

def run_tests():
    report = ["# ChanQuant System Test Report"]
    report.append(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## 1. System Health Checks")
    
    success_count = 0
    total_count = 0

    # 1. Frontend Access
    total_count += 1
    try:
        res = client.get("/")
        if res.status_code == 200:
            report.append("- [x] **Frontend UI**: Accessible (HTTP 200)")
            success_count += 1
        else:
            report.append(f"- [ ] **Frontend UI**: Failed (HTTP {res.status_code})")
    except Exception as e:
        report.append(f"- [ ] **Frontend UI**: Error ({str(e)})")

    # 2. Documentation
    total_count += 1
    try:
        res = client.get("/api/docs/strategy")
        data = res.json()
        if "content" in data and len(data["content"]) > 0:
            report.append("- [x] **API Documentation**: Loaded Successfully")
            success_count += 1
        else:
            report.append("- [ ] **API Documentation**: Failed (Empty content)")
    except Exception as e:
        report.append(f"- [ ] **API Documentation**: Error ({str(e)})")

    report.append("")
    report.append("## 2. Strategy Analysis Engine")

    # 3. Standard Strategy
    symbol = "KQ.m@SHFE.rb" # Default Rebar
    period = "30m"
    
    total_count += 1
    try:
        report.append(f"### Testing Standard Strategy ({symbol}, {period})")
        start = time.time()
        res = client.get(f"/api/analysis/{symbol}/{period}?strategy_name=standard")
        duration = time.time() - start
        
        data = res.json()
        if "centers" in data and "bis_count" in data:
            report.append(f"- [x] **Analysis Execution**: Success ({duration:.2f}s)")
            report.append(f"  - Generated {data['bis_count']} Bis")
            report.append(f"  - Identified {len(data['centers'])} ZhongShu Centers")
            success_count += 1
        else:
            report.append("- [ ] **Analysis Execution**: Failed (Invalid Response)")
            if "error" in data:
                report.append(f"  - Error: {data['error']}")
    except Exception as e:
        report.append(f"- [ ] **Analysis Execution**: Exception ({str(e)})")

    # 4. Pure Chan Strategy
    total_count += 1
    try:
        report.append("")
        report.append(f"### Testing Pure Chan Strategy ({symbol}, {period})")
        start = time.time()
        res = client.get(f"/api/analysis/{symbol}/{period}?strategy_name=pure_chan")
        duration = time.time() - start
        
        data = res.json()
        if "centers" in data and "signals" in data:
            report.append(f"- [x] **Analysis Execution**: Success ({duration:.2f}s)")
            report.append(f"  - Generated {data['bis_count']} Bis")
            report.append(f"  - Identified {len(data['centers'])} ZhongShu Centers")
            report.append(f"  - Generated {len(data['signals'])} Trading Signals")
            success_count += 1
            
            # Check Signal Structure
            if len(data['signals']) > 0:
                s = data['signals'][0]
                keys = ['type', 'price', 'desc', 'dt']
                if all(k in s for k in keys):
                    report.append("  - [x] **Signal Format**: Valid (Contains type, price, desc, dt)")
                    report.append(f"  - Sample Signal: {s['type']} @ {s['price']} - {s['desc']}")
                else:
                    report.append(f"  - [ ] **Signal Format**: Invalid. Found keys: {list(s.keys())}")
            else:
                report.append("  - [!] No signals generated in recent history (Expected if market is choppy)")
        else:
            report.append("- [ ] **Analysis Execution**: Failed (Invalid Response)")
            if "error" in data:
                report.append(f"  - Error: {data['error']}")
    except Exception as e:
        report.append(f"- [ ] **Analysis Execution**: Exception ({str(e)})")

    report.append("")
    report.append("## 3. Test Summary")
    report.append(f"- **Total Tests**: {total_count}")
    report.append(f"- **Passed**: {success_count}")
    report.append(f"- **Failed**: {total_count - success_count}")
    report.append(f"- **Status**: {'PASS' if success_count == total_count else 'FAIL'}")

    # Write Report
    os.makedirs("docs", exist_ok=True)
    with open("docs/system_test_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    
    print("\n".join(report))

if __name__ == "__main__":
    run_tests()
