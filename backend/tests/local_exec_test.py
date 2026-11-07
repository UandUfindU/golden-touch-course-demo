
import asyncio
import sys
import os
import json
from unittest.mock import MagicMock

# Setup Path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from app.services.execution_service import ExecutionService, execution_service

# Mock Session Manager to avoid DB dependency
mock_session_manager = MagicMock()
mock_session_manager.log_backtest_result = MagicMock(side_effect=lambda *args, **kwargs: asyncio.sleep(0))
execution_service.session_manager = mock_session_manager

async def test_local_execution():
    print("[-] Starting Local Execution Test (No API, Mocked DB)...")

    # User provided Graph (EXACT MATCH)
    # Removing 'limit': 100 from n1 to match user input exactly.
    graph_json = {
      "nodes": [
        {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "timeframe": "1h", "output_name": "data"}},
        {"id": "n2", "type": "indicator.ma", "data": {"window": 12, "output_name": "ma_short"}},
        {"id": "n3", "type": "indicator.ma", "data": {"window": 26, "output_name": "ma_long"}},
        {"id": "n4", "type": "custom.logic.crossover", "data": {"output_name": "is_crossover"}},
        {"id": "n5", "type": "logic.condition", "data": {"condition_expr": "is_crossover"}},
        {"id": "n6", "type": "signal.buy", "data": {"amount": 1.0}},
        {"id": "n7", "type": "logic.condition", "data": {"condition_expr": "is_crossover == -1"}},
        {"id": "n8", "type": "signal.sell", "data": {"amount": 1.0}}
      ],
      "edges": [
        {"source": "n1", "target": "n2", "type": "data", "source_port": "data", "target_port": "source"},
        {"source": "n1", "target": "n3", "type": "data", "source_port": "data", "target_port": "source"},
        {"source": "n2", "target": "n4", "type": "data", "source_port": "values", "target_port": "series_a"},
        {"source": "n3", "target": "n4", "type": "data", "source_port": "values", "target_port": "series_b"},
        {"source": "n4", "target": "n5", "source_port": "crossover", "target_port": "condition_input", "type": "data"},
        {"source": "n5", "target": "n6", "source_port": "result", "target_port": "condition", "type": "control"},
        {"source": "n4", "target": "n7", "source_port": "crossover", "target_port": "condition_input", "type": "data"},
        {"source": "n7", "target": "n8", "source_port": "result", "target_port": "condition", "type": "control"}
      ]
    }

    print("[-] Invoking execution_service.execute_backtest...")
    
    try:
        async for event in execution_service.execute_backtest(
            session_id="local_test",
            graph_json=graph_json,
            # We must provide config with at least initial capital, as per service logic
            # Also set limit to 500 to confirm speed
            config={"initial_capital": 100000.0, "limit": 500}
        ):
            if event['type'] == 'log':
                content = event.get('content')
                if "Signal" in content or "EXECUTED" in content:
                    print(f"  🔥 [Streamed Log] {content}")
                else:
                    print(f"  [Log] {content}")
            else:
                 print(f"  [Event] {event['type']}: {str(event.get('content') or event.get('metrics'))}")
            
            if event['type'] == 'result':
                print(f"  [Trades] Found {len(event.get('trades', []))} trades:")
                for t in event.get('trades', [])[:5]:
                    print(f"    - {t}")
            
            if event['type'] == 'error':
                print("❌ Test Failed with Error.")
                return

    except Exception as e:
        print(f"❌ Exception caught: {e}")
        import traceback
        traceback.print_exc()
        return

    print("✅ Test Completed.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_local_execution())
