"""
Integration test for CrossOver Strategy and Enhanced Metrics.

Tests:
1. Golden Cross strategy on trending data
2. Verification of enhanced metrics (Holding time, Risk/Reward)
"""
import pytest
import os
import sys
import math

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.backtest import BacktestRunnerNode
from app.nodes.impl.logic import MANode, CrossOverNode


def generate_crossover_data(length: int = 100) -> list:
    """
    Generate data where:
    - First 50 bars: Slow MA > Fast MA (Downtrend)
    - Next 50 bars: Fast MA > Slow MA (Uptrend)
    
    Price starts at 100, drops to 50, then valid up to 150.
    """
    data = []
    price = 100.0
    for i in range(100):
        if i < 40:
            price -= 1.0  # Downtrend
        elif i < 60:
            price += 0.5  # Consolidation
        else:
            price += 2.0  # Strong Uptrend
            
        data.append({
            "timestamp": 1704067200000 + i * 86400000,
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000000
        })
    return data


class TestCrossOverStrategy:
    """Test CrossOver Strategy E2E."""
    
    def test_ma_crossover_metrics(self):
        """
        Strategy:
        - MA5 (Fast)
        - MA20 (Slow)
        - CrossOver Node detects Golden Cross -> Buy
        - CrossOver Node detects Death Cross -> Sell (not tested here since we end high)
        """
        node = BacktestRunnerNode()
        data = generate_crossover_data(100)
        
        dag = {
            "nodes": [
                {
                    "id": "ma5",
                    "type": "logic.ma",
                    "data": {"period": 5, "output_name": "ma5"}
                },
                {
                    "id": "ma20",
                    "type": "logic.ma",
                    "data": {"period": 20, "output_name": "ma20"}
                },
                {
                    "id": "cross",
                    "type": "logic.crossover",
                    "data": {
                        "fast_line": "ma5", 
                        "slow_line": "ma20",
                        "output_name": "crossover"
                    }
                },
                {
                    "id": "buy_signal",
                    "type": "tool.buy",
                    "data": {}
                }
            ],
            "edges": [
                {"source": "cross", "target": "buy_signal"}
            ]
        }
        
        ctx = Context(
            run_id="test", workflow_id="wf", node_id="bt",
            inputs={
                "data": data,
                "strategy_dag": dag,
                "config": {"initial_capital": 10000}
            }
        )
        
        result = node.run(ctx)
        res = result["result"]
        
        assert res["success"], f"Backtest failed: {res.get('error')}"
        
        m = res["metrics"]
        print("\n" + "="*40)
        print("CrossOver Strategy Results")
        print("="*40)
        print(f"Total Return: {m['total_return']:.2f}%")
        print(f"Total Trades: {m['total_trades']}")
        print(f"Buy Signals: {m.get('buy_signals_count', 0)}")
        print(f"Avg Holding Time: {m.get('avg_holding_time_bars', 0)} bars")
        
        # We expect at least one trade (the big uptrend start)
        assert m['total_trades'] >= 1
        assert m['total_return'] > 0
        
        # Verify enhanced metrics existence
        assert 'avg_holding_time_bars' in m
        assert 'top_10_wins' in m


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
