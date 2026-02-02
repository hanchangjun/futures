
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime
from fastapi.testclient import TestClient
from web.main import app

# Initialize TestClient
client = TestClient(app)

import unittest
import io

def run_diagnostics(test_type="full"):
    """
    Runs system diagnostic or specific functional tests.
    test_type: 'full', 'signal_filter', 'rebar', 'real_time'
    """
    if test_type != "full":
        return _run_unit_test(test_type)

    report = []
    report.append(f"# ChanQuant System Diagnostic Report")
    report.append(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    results = {
        "success": 0,
        "total": 0,
        "details": []
    }
    
    # --- 1. System Health ---
    report.append("## 1. System Health Checks")
    _check_endpoint(report, results, "Frontend UI", "/")
    _check_endpoint(report, results, "API Documentation", "/api/docs/strategy")
    
    # --- 2. Strategy Analysis ---
    report.append("")
    report.append("## 2. Strategy Analysis Engine")
    
    # Use a default symbol that should exist (or mock it if needed)
    # Ideally we use a symbol we know exists. Assuming "KQ.m@SHFE.rb" or similar.
    # If using TQSDK, it might need real connection. If DB, needs data.
    # We'll try the default one used in the app.
    symbol = "KQ.m@SHFE.rb"
    period = "30m"
    
    # Test Standard Strategy
    _test_strategy(report, results, "Standard Strategy", symbol, period, "standard")
    
    # Test Pure Chan Strategy
    _test_strategy(report, results, "Pure Chan Strategy", symbol, period, "pure_chan")
    
    # Test Real-Time System Init (Unit Check)
    _test_realtime_init(report, results)
    
    # Summary
    report.append("")
    report.append("## Summary")
    report.append(f"**Total Tests**: {results['total']}")
    report.append(f"**Passed**: {results['success']}")
    report.append(f"**Failed**: {results['total'] - results['success']}")
    
    status = "PASS" if results['success'] == results['total'] else "FAIL"
    
    return {
        "status": status,
        "report": "\n".join(report),
        "timestamp": datetime.now().isoformat()
    }

def _check_endpoint(report, results, name, url):
    results['total'] += 1
    try:
        start = time.time()
        res = client.get(url)
        duration = time.time() - start
        
        if res.status_code == 200:
            report.append(f"- [x] **{name}**: Accessible (HTTP 200) - {duration:.3f}s")
            results['success'] += 1
            return True
        else:
            report.append(f"- [ ] **{name}**: Failed (HTTP {res.status_code})")
            return False
    except Exception as e:
        report.append(f"- [ ] **{name}**: Error ({str(e)})")
        return False

def _test_strategy(report, results, name, symbol, period, strategy_name):
    results['total'] += 1
    report.append(f"### Testing {name} ({symbol}, {period})")
    
    try:
        start = time.time()
        # Mocking or assuming data exists. 
        # If no data, the API might return empty but valid structure.
        res = client.get(f"/api/analysis/{symbol}/{period}?strategy_name={strategy_name}")
        duration = time.time() - start
        
        data = res.json()
        
        if res.status_code != 200:
             report.append(f"- [ ] **Execution**: Failed (HTTP {res.status_code})")
             if "error" in data:
                 report.append(f"  - Error: {data['error']}")
             return

        # Check for error in JSON even if 200 OK (some APIs do this)
        if "error" in data and data["error"]:
             report.append(f"- [ ] **Execution**: Failed with App Error")
             report.append(f"  - Error: {data['error']}")
             return

        # Validate Structure
        if "centers" in data and "bis_count" in data:
            report.append(f"- [x] **Execution**: Success ({duration:.2f}s)")
            report.append(f"  - Generated {data['bis_count']} Bis")
            report.append(f"  - Identified {len(data['centers'])} ZhongShu Centers")
            
            if "signals" in data:
                 report.append(f"  - Generated {len(data['signals'])} Signals")
                 if len(data['signals']) > 0:
                     s = data['signals'][0]
                     report.append(f"  - Sample: {s.get('type')} @ {s.get('price')}")
            
            results['success'] += 1
        else:
            report.append("- [ ] **Execution**: Invalid Response Structure")
            report.append(f"  - Keys received: {list(data.keys())}")
            
    except Exception as e:
        report.append(f"- [ ] **Execution**: Exception ({str(e)})")
        import traceback
        report.append(f"```\n{traceback.format_exc()}\n```")

def _test_realtime_init(report, results):
    results['total'] += 1
    report.append("")
    report.append("### Testing Real-Time System Initialization")
    try:
        from strategy.real_time import RealTimeTradingSystem
        from strategy.notification import WeChatNotifier
        
        # Test Init
        sys = RealTimeTradingSystem(symbol="rb2505", webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=TEST")
        if sys and sys.period == "30m":
             report.append("- [x] **Initialization**: Success (Defaults correct)")
             results['success'] += 1
        else:
             report.append("- [ ] **Initialization**: Failed (Attributes incorrect)")
    except Exception as e:
        report.append(f"- [ ] **Initialization**: Error ({str(e)})")

if __name__ == "__main__":
        print(run_diagnostics()['report'])

def _run_unit_test(test_type):
    """
    Helper to run specific unit test modules and return report.
    """
    report = []
    module_name = ""
    title = ""
    
    if test_type == "signal_filter":
        module_name = "tests.test_signal_filter"
        title = "Signal Filter & Confirmation Test"
    elif test_type == "rebar":
        module_name = "tests.test_rebar_strategy"
        title = "Rebar Strategy Optimization Test"
    elif test_type == "real_time":
        module_name = "tests.test_real_time"
        title = "Real-Time Trading System Test"
    else:
        return {
            "status": "ERROR",
            "report": f"Unknown test type: {test_type}",
            "timestamp": datetime.now().isoformat()
        }
        
    report.append(f"# {title}")
    report.append(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    try:
        # Create a suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(module_name)
        
        # Capture output
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        
        # Format Report
        output = stream.getvalue()
        
        report.append(f"**Status**: {'PASS' if result.wasSuccessful() else 'FAIL'}")
        report.append(f"**Ran**: {result.testsRun} tests")
        report.append(f"**Errors**: {len(result.errors)}")
        report.append(f"**Failures**: {len(result.failures)}")
        report.append("")
        report.append("### Console Output")
        report.append("```text")
        report.append(output)
        report.append("```")
        
        status = "PASS" if result.wasSuccessful() else "FAIL"
        
    except Exception as e:
        import traceback
        report.append(f"**Error Running Test**: {str(e)}")
        report.append("```")
        report.append(traceback.format_exc())
        report.append("```")
        status = "ERROR"

    return {
        "status": status,
        "report": "\n".join(report),
        "timestamp": datetime.now().isoformat()
    }
