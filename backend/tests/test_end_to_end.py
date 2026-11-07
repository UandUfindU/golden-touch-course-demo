"""
End-to-End Integration Test for NL2DAG Backtesting Pipeline.

Tests the complete flow:
1. Generate synthetic data
2. Define strategy DAG with indicators
3. Run backtest
4. Validate metrics
"""
import pytest
import os
import sys
import math

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.backtest import BacktestRunnerNode
from app.nodes.impl.logic import MANode, LogicIfNode


def generate_trend_data(length: int = 200, trend: float = 0.3, 
                        volatility: float = 2.0) -> list:
    """Generate synthetic trending price data with oscillations."""
    data = []
    price = 100.0
    for i in range(length):
        # Trend + sine wave oscillation + random noise
        noise = volatility * math.sin(i * 0.5) * math.cos(i * 0.1)
        price += trend + noise
        data.append({
            "timestamp": 1704067200000 + i * 86400000,  # Daily bars
            "open": price - 0.5,
            "high": price + 1.5,
            "low": price - 1.5,
            "close": price,
            "volume": 1000000 + i * 1000
        })
    return data


class TestEndToEnd:
    """End-to-end integration tests."""
    
    def test_ma_crossover_strategy(self):
        """
        Test a classic MA crossover strategy:
        - Buy when close > MA20
        - Sell when close < MA20
        
        On trending data, this should be profitable.
        """
        node = BacktestRunnerNode()
        data = generate_trend_data(200, trend=0.3)
        
        # Strategy DAG: MA20 indicator with crossover logic
        dag = {
            "nodes": [
                {
                    "id": "ma20",
                    "type": "logic.ma",
                    "data": {"period": 20, "ma_type": "sma", "output_name": "ma20"}
                },
                {
                    "id": "buy_condition",
                    "type": "flow.if",
                    "data": {"condition_expr": "close > ma20"}
                },
                {
                    "id": "buy_signal",
                    "type": "tool.buy",
                    "data": {}
                },
                {
                    "id": "sell_condition",
                    "type": "flow.if",
                    "data": {"condition_expr": "close < ma20"}
                },
                {
                    "id": "sell_signal",
                    "type": "tool.sell",
                    "data": {}
                }
            ],
            "edges": [
                {"source": "ma20", "target": "buy_condition"},
                {"source": "buy_condition", "target": "buy_signal"},
                {"source": "ma20", "target": "sell_condition"},
                {"source": "sell_condition", "target": "sell_signal"}
            ]
        }
        
        ctx = Context(
            run_id="e2e_test", workflow_id="wf_e2e", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": dag,
                "config": {
                    "initial_capital": 10000,
                    "commission_rate": 0.001,
                    "position_size_pct": 1.0
                }
            }
        )
        
        result = node.run(ctx)
        
        # Assertions
        assert result["result"]["success"], f"Backtest failed: {result['result'].get('error')}"
        assert result["result"]["bars_processed"] == 200
        
        metrics = result["result"]["metrics"]
        
        print("\n" + "="*60)
        print("END-TO-END TEST: MA Crossover Strategy")
        print("="*60)
        print(f"Initial Capital: ${result['result']['initial_capital']:,.2f}")
        print(f"Final Equity: ${result['result']['final_equity']:,.2f}")
        print(f"Total Return: {metrics['total_return']:.2f}%")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print("="*60)
        
        # On uptrending data, MA crossover should be profitable
        assert metrics['total_return'] > 0, "Strategy should be profitable on uptrend"
    
    def test_rsi_mean_reversion_strategy(self):
        """
        Test RSI mean reversion strategy:
        - Buy when RSI < 30 (oversold)
        - Sell when RSI > 70 (overbought)
        """
        node = BacktestRunnerNode()
        
        # Generate oscillating data (good for mean reversion)
        data = []
        price = 100.0
        for i in range(150):
            price = 100 + 15 * math.sin(i * 0.15)  # Strong oscillation
            data.append({
                "timestamp": 1704067200000 + i * 86400000,
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1000000
            })
        
        dag = {
            "nodes": [
                {
                    "id": "rsi14",
                    "type": "logic.rsi",
                    "data": {"period": 14, "output_name": "rsi"}
                },
                {
                    "id": "oversold",
                    "type": "flow.if",
                    "data": {"condition_expr": "rsi < 30"}
                },
                {
                    "id": "buy_signal",
                    "type": "tool.buy",
                    "data": {}
                },
                {
                    "id": "overbought",
                    "type": "flow.if",
                    "data": {"condition_expr": "rsi > 70"}
                },
                {
                    "id": "sell_signal",
                    "type": "tool.sell",
                    "data": {}
                }
            ],
            "edges": [
                {"source": "rsi14", "target": "oversold"},
                {"source": "oversold", "target": "buy_signal"},
                {"source": "rsi14", "target": "overbought"},
                {"source": "overbought", "target": "sell_signal"}
            ]
        }
        
        ctx = Context(
            run_id="e2e_test", workflow_id="wf_e2e", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": dag,
                "config": {"initial_capital": 10000}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"]["success"]
        
        print("\n" + "="*60)
        print("END-TO-END TEST: RSI Mean Reversion Strategy")
        print("="*60)
        print(f"Final Equity: ${result['result']['final_equity']:,.2f}")
        print(f"Total Trades: {result['result']['metrics']['total_trades']}")
        print(f"Win Rate: {result['result']['metrics']['win_rate']:.1f}%")
        print("="*60)
    
    def test_indicator_precomputation(self):
        """Verify indicators are correctly pre-computed."""
        node = BacktestRunnerNode()
        data = generate_trend_data(50)
        
        dag = {
            "nodes": [
                {"id": "ma5", "type": "logic.ma", "data": {"period": 5, "output_name": "ma5"}},
                {"id": "ma20", "type": "logic.ma", "data": {"period": 20, "output_name": "ma20"}}
            ],
            "edges": []
        }
        
        precomputed = node._precompute_indicators(dag, data)
        
        assert "ma5" in precomputed
        assert "ma20" in precomputed
        assert len(precomputed["ma5"]) == 50
        assert precomputed["ma5"][3] is None  # Not enough data
        assert precomputed["ma5"][4] is not None  # First valid MA5
        
        print(f"\n[Precompute] MA5 first valid: {precomputed['ma5'][4]:.2f}")
        print(f"[Precompute] MA20 first valid: {precomputed['ma20'][19]:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
