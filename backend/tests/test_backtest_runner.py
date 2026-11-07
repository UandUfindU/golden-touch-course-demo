"""
Integration tests for Backtest Engine.

Tests BacktestRunnerNode with synthetic market data.
"""
import pytest
import os
import sys
import math

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.backtest import BacktestRunnerNode
from app.nodes.impl.data.fetch_stock import FetchStockNode


def generate_sine_data(periods: int = 100, amplitude: float = 10, base_price: float = 100) -> list:
    """Generate synthetic sine wave price data for testing."""
    data = []
    for i in range(periods):
        # Sine wave with slight upward trend
        price = base_price + amplitude * math.sin(i * 2 * math.pi / 20) + i * 0.1
        data.append({
            "timestamp": 1704067200000 + i * 86400000,  # Daily bars starting 2024-01-01
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000000
        })
    return data


class TestBacktestRunnerNode:
    """Test BacktestRunnerNode."""
    
    def test_simple_buy_and_hold(self):
        """Test a simple buy signal at start."""
        node = BacktestRunnerNode()
        data = generate_sine_data(50)
        
        # Simple DAG: just a buy node
        dag = {
            "nodes": [
                {"id": "n1", "type": "signal.buy", "data": {"condition": "True"}}
            ],
            "edges": []
        }
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
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
        
        assert result["result"]["success"], f"Backtest failed: {result['result'].get('error')}"
        assert result["result"]["bars_processed"] == 50
        assert len(result["result"]["trades"]) > 0
        
        print(f"\n[Backtest] Buy & Hold:")
        print(f"  Initial: ${result['result']['initial_capital']:.2f}")
        print(f"  Final: ${result['result']['final_equity']:.2f}")
        print(f"  Trades: {len(result['result']['trades'])}")
        if result["result"]["metrics"]:
            print(f"  Total Return: {result['result']['metrics']['total_return']:.2f}%")
    
    def test_condition_based_strategy(self):
        """Test a conditional buy/sell strategy."""
        node = BacktestRunnerNode()
        data = generate_sine_data(100)
        
        # DAG with condition: buy when price crosses above a threshold
        dag = {
            "nodes": [
                {"id": "n1", "type": "flow.if", "data": {"condition_expr": "close > 105"}},
                {"id": "n2", "type": "tool.buy", "data": {}},
                {"id": "n3", "type": "flow.if", "data": {"condition_expr": "close < 95"}},
                {"id": "n4", "type": "tool.sell", "data": {}}
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n3", "target": "n4"}
            ]
        }
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": dag,
                "config": {
                    "initial_capital": 10000,
                    "commission_rate": 0.001
                }
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"]["success"]
        
        metrics = result["result"]["metrics"]
        print(f"\n[Backtest] Conditional Strategy:")
        print(f"  Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Total Return: {metrics['total_return']:.2f}%")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
    
    @pytest.mark.parametrize("cover_on_signal", [False, True])
    def test_short_settlement_matches_equity_and_net_trade_pnl(self, cover_on_signal):
        data = generate_sine_data(3)
        for bar, price in zip(data, [100.0, 90.0, 90.0]):
            bar.update(open=price, high=price, low=price, close=price)
        nodes = [{"id": "sell", "type": "signal.sell", "data": {"condition": "close == 100"}}]
        if cover_on_signal:
            nodes.append({"id": "buy", "type": "signal.buy", "data": {"condition": "close == 90"}})
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": {"nodes": nodes, "edges": []},
                "config": {"initial_capital": 1000, "commission_rate": 0.01},
            },
        )

        result = BacktestRunnerNode().run(ctx)["result"]

        assert result["success"], result.get("error")
        trades = result["trades"]
        assert [trade["direction"] for trade in trades] == (["short", "long"] if cover_on_signal else ["short"])
        assert trades[0]["pnl"] == pytest.approx(trades[0]["quantity"] * (100 - 90 - 0.01 * (100 + 90)))
        assert result["final_equity"] == pytest.approx(1000 + sum(trade["pnl"] for trade in trades))
        assert result["equity_curve"][-1]["equity"] == result["final_equity"]
        assert result["metrics"]["total_return"] == pytest.approx((result["final_equity"] - 1000) / 10)

    def test_backtest_reuses_prefetched_market_history(self, monkeypatch):
        calls = []
        monkeypatch.setattr(FetchStockNode, "run", lambda self, ctx: calls.append(ctx) or {})
        data = generate_sine_data(5)
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": {
                    "nodes": [{"id": "prices", "type": "data.fetch_stock", "data": {"symbol": "AAPL"}}],
                    "edges": [],
                },
            },
        )

        result = BacktestRunnerNode().run(ctx)["result"]

        assert result["success"]
        assert len(result["equity_curve"]) == 5
        assert not calls

    def test_explicit_signal_can_filter_out_a_crossover(self):
        dag = {
            "nodes": [
                {"id": "cross", "type": "indicator.crossover", "data": {"output_name": "cross"}},
                {"id": "buy", "type": "signal.buy", "data": {"condition": "cross == 1 and close > 100"}},
            ],
            "edges": [],
        }
        runner = BacktestRunnerNode()

        assert runner._evaluate_conditions(dag, {"close": 95}, {"cross": 1}) is None
        assert runner._evaluate_conditions(dag, {"close": 105}, {"cross": 1}) == "buy"

    def test_empty_data(self):
        """Test handling of empty data."""
        node = BacktestRunnerNode()
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
            inputs={
                "data": [],
                "strategy_dag": {"nodes": [], "edges": []},
                "config": {}
            }
        )
        
        result = node.run(ctx)
        
        assert not result["result"]["success"]
        assert "empty" in result["result"]["error"].lower()
    
    def test_metrics_calculation(self):
        """Test that metrics are calculated correctly."""
        node = BacktestRunnerNode()
        data = generate_sine_data(200)
        
        # Alternating buy/sell strategy
        dag = {
            "nodes": [
                {"id": "n1", "type": "flow.if", "data": {"condition_expr": "close > 110"}},
                {"id": "n2", "type": "tool.sell", "data": {}},
                {"id": "n3", "type": "flow.if", "data": {"condition_expr": "close < 90"}},
                {"id": "n4", "type": "tool.buy", "data": {}}
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n3", "target": "n4"}
            ]
        }
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="backtest",
            inputs={
                "data": data,
                "strategy_dag": dag,
                "config": {"initial_capital": 10000}
            }
        )
        
        result = node.run(ctx)
        metrics = result["result"]["metrics"]
        
        assert result["result"]["success"]
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert metrics["total_trades"] == metrics["winning_trades"] + metrics["losing_trades"]
        
        print(f"\n[Backtest] Metrics Validation:")
        print(f"  Sharpe: {metrics['sharpe_ratio']:.3f}")
        print(f"  Sortino: {metrics['sortino_ratio']:.3f}")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
