
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.nodes.impl.data.fetch_stock import FetchStockNode, FetchStockInput
from app.nodes.base import Context

def test_us_stock_fetch():
    print("Testing US Stock Fetching...")
    node = FetchStockNode()
    
    # Input for Apple stock
    inputs = {
        "market": "us",
        "symbol": "AAPL",
        "timeframe": "1d",
        "limit": 5
    }
    
    # Mock context
    ctx = Context(
        run_id="test_run",
        workflow_id="test_workflow",
        node_id="test_node",
        inputs=inputs
    )
    
    try:
        result = node.run(ctx)
        if "error" in result:
            print(f"FAILED: {result['error']}")
        else:
            print("SUCCESS: Fetched data for AAPL")
            print(f"Data points: {result['count']}")
            print(f"Sample: {result['data'][0] if result['data'] else 'None'}")
    except Exception as e:
        import traceback
        print(f"CRASHED: {e}")
        traceback.print_exc()

def test_yfinance_direct():
    """Test yfinance directly to see if the issue is with yfinance or the node."""
    print("\n--- Direct yfinance test ---")
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        df = ticker.history(period="5d", interval="1d")
        print(f"yfinance returned: {len(df)} rows")
        print(df.head())
    except Exception as e:
        import traceback
        print(f"yfinance direct test FAILED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_yfinance_direct()
    test_us_stock_fetch()
