
import requests
import json
import sys
import time

# Direct Execution API Endpoint
EXEC_URL = "http://localhost:8000/api/v1/backtest/run"

def test_direct_execution_api():
    print(f"[*] Testing Direct Execution API: {EXEC_URL}")
    
    session_id = f"test-exec-{int(time.time())}"
    
    # 1. Define a valid graph with Data Fetching
    # This graph mimics what the LLM would generate: Fetch -> MA -> Crossover -> Signal
    graph_payload = {
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

    # 2. Payload - NO data_context required now!
    request_body = {
        "session_id": session_id,
        "graph_json": graph_payload,
        "config": {
            "initial_capital": 50000.0
        }
    }
    
    print("[*] Sending Graph (No Data Context)...")
    
    try:
        with requests.post(EXEC_URL, json=request_body, stream=True) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code}")
                print(r.text)
                return False
                
            print("[*] Connected. Streaming Events...")
            
            has_logs = False
            has_fetched_data = False
            has_result = False
            
            for line in r.iter_lines():
                if line:
                    print(f"[API Stream] {line}") # Added line to print non-empty streaming chunks
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data = json.loads(decoded[6:])
                        event_type = data.get("type")
                        content = data.get("content", "")
                        
                        if event_type == "log":
                            print(f"  [Log] {content}")
                            has_logs = True
                            if "Fetched" in content or "Loaded" in content:
                                has_fetched_data = True
                                
                        elif event_type == "error":
                            print(f"  [Error] {content}")
                            return False
                            
                        elif event_type == "result":
                            metrics = data.get("metrics", {})
                            print(f"  [Result] Sharpe: {metrics.get('sharpe_ratio')}, Trades: {metrics.get('total_trades')}")
                            has_result = True
            
            if has_fetched_data:
                print("[PASS] Backend successfully fetched data internally.")
            else:
                print("[FAIL] Did not see data fetching log.")
                return False
                
            if has_result:
                print("[PASS] Received final backtest result.")
            else:
                print("[FAIL] Did not receive execution result.")
                return False
                
            return True

    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_direct_execution_api()
    sys.exit(0 if success else 1)
