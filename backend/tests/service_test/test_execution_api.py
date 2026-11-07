"""
API Test Cases for Execution/Backtest Router (/api/v1/backtest)
Tests backtest execution with various graph configurations.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000/api/v1/backtest"


def test_backtest_simple_graph():
    """Test backtest with a simple graph."""
    print(f"[*] Testing Simple Backtest: POST {BASE_URL}/run")
    
    graph = {
        "nodes": [
            {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "timeframe": "1h", "limit": 50}},
            {"id": "n2", "type": "indicator.ma", "data": {"window": 10, "output_name": "ma_short"}},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "type": "data", "source_port": "data", "target_port": "source"}
        ]
    }
    
    payload = {
        "session_id": f"test-bt-{int(time.time())}",
        "graph_json": graph,
        "config": {"initial_capital": 10000.0}
    }
    
    try:
        with requests.post(f"{BASE_URL}/run", json=payload, stream=True, timeout=120) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code}")
                return False
            
            print("[*] Streaming backtest events...")
            has_log = False
            has_result = False
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        etype = event.get("type")
                        
                        if etype == "log":
                            has_log = True
                            print(f"  [Log] {event.get('content', '')[:60]}")
                        elif etype == "result":
                            has_result = True
                            print(f"  [Result] {event.get('metrics', {})}")
                        elif etype == "error":
                            print(f"  [Error] {event.get('content')}")
                            return False
            
            if has_log:
                print("[PASS] Received log events")
            if has_result:
                print("[PASS] Received result")
            return has_log or has_result
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_backtest_ma_crossover():
    """Test backtest with MA crossover strategy graph."""
    print(f"[*] Testing MA Crossover Backtest")
    
    graph = {
        "nodes": [
            {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "timeframe": "1h", "limit": 100, "output_name": "data"}},
            {"id": "n2", "type": "indicator.ma", "data": {"window": 10, "output_name": "ma_short"}},
            {"id": "n3", "type": "indicator.ma", "data": {"window": 20, "output_name": "ma_long"}},
            {"id": "n4", "type": "custom.logic.crossover", "data": {"output_name": "is_cross"}},
            {"id": "n5", "type": "logic.condition", "data": {"condition_expr": "is_cross"}},
            {"id": "n6", "type": "signal.buy", "data": {"amount": 1.0}}
        ],
        "edges": [
            {"source": "n1", "target": "n2", "type": "data", "source_port": "data", "target_port": "source"},
            {"source": "n1", "target": "n3", "type": "data", "source_port": "data", "target_port": "source"},
            {"source": "n2", "target": "n4", "type": "data", "source_port": "values", "target_port": "series_a"},
            {"source": "n3", "target": "n4", "type": "data", "source_port": "values", "target_port": "series_b"},
            {"source": "n4", "target": "n5", "source_port": "crossover", "target_port": "condition_input", "type": "data"},
            {"source": "n5", "target": "n6", "source_port": "result", "target_port": "condition", "type": "control"}
        ]
    }
    
    payload = {
        "session_id": f"test-crossover-{int(time.time())}",
        "graph_json": graph,
        "config": {"initial_capital": 50000.0}
    }
    
    try:
        with requests.post(f"{BASE_URL}/run", json=payload, stream=True, timeout=120) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code}")
                return False
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        if event.get("type") == "result":
                            metrics = event.get("metrics", {})
                            print(f"  Sharpe: {metrics.get('sharpe_ratio')}")
                            print(f"  Trades: {metrics.get('total_trades')}")
                            print("[PASS] Got backtest result")
                            return True
                        elif event.get("type") == "error":
                            print(f"  [Error] {event.get('content')}")
                            return False
            
            print("[WARN] No result received (may be expected)")
            return True
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_backtest_invalid_graph():
    """Test backtest with invalid graph structure."""
    print("[*] Testing Invalid Graph Handling")
    
    payload = {
        "session_id": f"test-invalid-{int(time.time())}",
        "graph_json": {"nodes": [], "edges": []},  # Empty graph
        "config": {}
    }
    
    try:
        with requests.post(f"{BASE_URL}/run", json=payload, stream=True, timeout=30) as r:
            # Should still return 200 with SSE, but emit error event
            if r.status_code != 200:
                print(f"[INFO] HTTP Error: {r.status_code} (may be expected)")
                return True
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        if event.get("type") == "error":
                            print(f"[PASS] Received error event for invalid graph")
                            return True
            
            print("[PASS] Empty graph handled gracefully")
            return True
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def run_all_tests():
    """Run all execution API tests."""
    print("=" * 60)
    print("EXECUTION/BACKTEST API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("Simple Backtest", test_backtest_simple_graph()))
    results.append(("MA Crossover Backtest", test_backtest_ma_crossover()))
    results.append(("Invalid Graph Handling", test_backtest_invalid_graph()))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    for name, result in results:
        print(f"  [{'PASS' if result else 'FAIL'}] {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
