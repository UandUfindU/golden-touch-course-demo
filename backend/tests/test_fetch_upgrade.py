"""Test fetch_stock.py upgrade"""
import sys
import os

# Support running from golden_touch or golden_touch/backend
script_dir = os.path.dirname(os.path.abspath(__file__))  # tests/
backend_dir = os.path.dirname(script_dir)  # backend/
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.nodes.impl.data.fetch_stock import FetchStockNode
from app.nodes.base import Context

node = FetchStockNode()

# Test US stock via AkShare (primary)
print('='*50)
print('Testing US stock (TSLA) - AkShare primary')
print('='*50)
ctx = Context(
    run_id='test-run',
    workflow_id='test-workflow', 
    node_id='test-node',
    inputs={
        'market': 'us', 
        'symbol': 'TSLA', 
        'timeframe': '1d', 
        'limit': 3
    }
)
result = node.run(ctx)
if 'error' in result:
    print(f'Error: {result["error"]}')
else:
    print(f'Success! Got {result["count"]} records')
    if result['data']:
        print(f'Last: {result["data"][-1]}')

# Test CN stock
print()
print('='*50)
print('Testing CN stock (600519) - AkShare')
print('='*50)
ctx2 = Context(
    run_id='test-run',
    workflow_id='test-workflow',
    node_id='test-node',
    inputs={
        'market': 'cn', 
        'symbol': '600519', 
        'timeframe': '1d', 
        'limit': 3
    }
)
result2 = node.run(ctx2)
if 'error' in result2:
    print(f'Error: {result2["error"]}')
else:
    print(f'Success! Got {result2["count"]} records')
    if result2['data']:
        print(f'Last: {result2["data"][-1]}')
