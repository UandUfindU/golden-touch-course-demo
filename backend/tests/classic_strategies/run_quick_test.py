"""Quick test script to verify classic strategies work."""
import json
import sys
import random
from pathlib import Path

sys.path.insert(0, '.')

from app.nodes.base import Context
from app.nodes.impl.backtest.runner import BacktestRunnerNode

def generate_mock_data(n_bars=100):
    """Generate mock OHLCV data with trending pattern."""
    random.seed(42)
    data = []
    price = 100.0
    
    for i in range(n_bars):
        if i < n_bars // 3:
            trend = 0.002  # Uptrend
        elif i < 2 * n_bars // 3:
            trend = -0.003  # Downtrend  
        else:
            trend = 0.002  # Uptrend again
        
        change = random.uniform(-0.02, 0.02) + trend
        price *= (1 + change)
        
        data.append({
            'timestamp': 1700000000000 + i * 3600000,
            'open': price * (1 + random.uniform(-0.005, 0.005)),
            'high': price * (1 + random.uniform(0, 0.02)),
            'low': price * (1 - random.uniform(0, 0.02)),
            'close': price,
            'volume': random.uniform(1000, 10000)
        })
    
    return data

def test_strategy(filepath):
    """Test a single strategy file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        strategy = json.load(f)
    
    print(f"\n{'='*50}")
    print(f"Testing: {strategy.get('name', filepath.stem)}")
    print(f"  Nodes: {len(strategy.get('nodes', []))}")
    print(f"  Edges: {len(strategy.get('edges', []))}")
    
    data = generate_mock_data(150)
    
    runner = BacktestRunnerNode()
    ctx = Context(
        run_id='test', 
        workflow_id='wf', 
        node_id='bt',
        inputs={
            'data': data,
            'strategy_dag': strategy,
            'config': {'initial_capital': 10000}
        }
    )
    
    result = runner.run(ctx)
    res = result.get('result', {})
    
    if res.get('success'):
        metrics = res.get('metrics', {})
        print(f"  ✓ Success!")
        print(f"    Buy Signals:  {metrics.get('buy_signals_count', 0)}")
        print(f"    Sell Signals: {metrics.get('sell_signals_count', 0)}")
        print(f"    Total Trades: {metrics.get('total_trades', 0)}")
        return True
    else:
        print(f"  ✗ Failed: {str(res.get('error', 'Unknown'))[:100]}")
        return False

def main():
    print("=" * 50)
    print("Classic Strategy Test Runner")
    print("=" * 50)
    
    strategies_dir = Path('graphs/standard/classic_strategies')
    strategy_files = list(strategies_dir.glob('*.json'))
    
    print(f"Found {len(strategy_files)} strategies")
    
    passed = 0
    failed = 0
    
    for filepath in strategy_files:
        try:
            if test_strategy(filepath):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

if __name__ == '__main__':
    main()
