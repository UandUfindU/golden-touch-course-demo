
import pytest
import sys
import os
import pandas as pd
import numpy as np

# Ensure backend is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from app.nodes.impl.backtest import BacktestRunnerNode
from app.nodes.base import Context

def generate_data():
    data = []
    price = 100.0
    for i in range(200):
        if i < 50:
            rsi_val = 75.0
            price += 1.0
        elif i < 100:
            rsi_val = 25.0
            price -= 1.0
        else:
            rsi_val = 50.0
            price += 0.1
            
        data.append({
            "timestamp": 1000000 + i * 60000,
            "open": price, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 1000,
            "my_rsi": rsi_val 
        })
    return data

def test_entry_condition_analysis():
    """
    Test that High RSI trades are identified as winners and Low RSI as losers,
    and that entry_analysis reflects this stats difference.
    """
    data = generate_data()
    
    dag = {
        "nodes": [
            {"id": "rsi_loader", "type": "logic.ma", "data": {"period": 1, "price_field": "my_rsi", "output_name": "rsi_val"}},
            {"id": "signal_gen", "type": "logic.if", "data": {
                "condition_expr": "rsi_val > 70 or rsi_val < 30"
            }},
            {"id": "bi", "type": "tool.buy", "data": {}}
        ],
        "edges": [
            {"source": "rsi_loader", "target": "signal_gen"},
            {"source": "signal_gen", "target": "bi"}
        ]
    }
    
    runner = BacktestRunnerNode()
    inputs = {
        "data": data,
        "strategy_dag": dag,
        "config": {
            "initial_capital": 10000.0,
            "commission_rate": 0.0,
            "position_size_pct": 0.1
        }
    }
    
    ctx = Context(run_id="test", workflow_id="w", node_id="b", inputs=inputs)
    result = runner.run(ctx)["result"]
    
    assert result["success"] is True, f"Backtest failed: {result.get('error')}"
    metrics = result["metrics"]
    
    # Check Entry Analysis
    analysis = metrics["entry_analysis"]
    assert analysis is not None
    assert "rsi_val" in analysis
    
    stats = analysis["rsi_val"]
    
    # Expect Winning Trades (first 50 bars) to have RSI ~ 75
    assert stats["win_avg"] > 70.0 
    
    # Expect Losing Trades (next 50 bars) to have RSI ~ 25
    assert stats["loss_avg"] < 30.0
    
    # Ensure there is a significant difference
    assert stats["win_avg"] > stats["loss_avg"]

if __name__ == "__main__":
    test_entry_condition_analysis()
