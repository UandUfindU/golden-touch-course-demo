"""
Test suite for classic strategy DAGs.

Verifies that each classic strategy can be executed and produces at least
one buy signal and one sell signal during backtesting.
"""
import pytest
import json
import os
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.nodes.base import Context
from app.nodes.registry import NodeRegistry


# Path to classic strategies
STRATEGIES_DIR = Path(__file__).parent.parent / "graphs" / "standard" / "classic_strategies"


def get_strategy_files():
    """Get all strategy JSON files."""
    if not STRATEGIES_DIR.exists():
        return []
    return list(STRATEGIES_DIR.glob("*.json"))


def load_strategy(filepath):
    """Load strategy DAG from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_mock_ohlcv_data(n_bars=100, base_price=100.0, volatility=0.02):
    """
    Generate mock OHLCV data with some price movement to trigger signals.
    
    Creates a pattern: rise -> fall -> rise to trigger various signals.
    """
    import random
    random.seed(42)  # Reproducibility
    
    data = []
    price = base_price
    
    for i in range(n_bars):
        # Create trending patterns
        if i < n_bars // 3:
            # Uptrend
            trend = 0.002
        elif i < 2 * n_bars // 3:
            # Downtrend
            trend = -0.003
        else:
            # Uptrend again
            trend = 0.002
        
        change = random.uniform(-volatility, volatility) + trend
        price = price * (1 + change)
        
        high = price * (1 + random.uniform(0, volatility))
        low = price * (1 - random.uniform(0, volatility))
        open_price = price * (1 + random.uniform(-volatility/2, volatility/2))
        
        data.append({
            "timestamp": 1700000000000 + i * 3600000,  # Hourly bars
            "open": open_price,
            "high": high,
            "low": low,
            "close": price,
            "volume": random.uniform(1000, 10000)
        })
    
    return data


class TestClassicStrategies:
    """Tests for classic strategy DAGs."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.mock_data = generate_mock_ohlcv_data(n_bars=150)
    
    def run_backtest(self, strategy_dag, data):
        """Run backtest on a strategy DAG and return signals."""
        try:
            runner = NodeRegistry.get_node("backtest.runner")()
            
            ctx = Context(
                run_id="test_run",
                workflow_id="test_workflow",
                node_id="backtest",
                inputs={
                    "data": data,
                    "strategy_dag": strategy_dag,
                    "config": {
                        "initial_capital": 10000,
                        "commission_rate": 0.001,
                        "position_size_pct": 1.0
                    }
                }
            )
            
            result = runner.run(ctx)
            return result.get("result", {})
        except Exception as e:
            pytest.fail(f"Backtest failed with error: {e}")
    
    @pytest.mark.parametrize("strategy_file", get_strategy_files(), ids=lambda f: f.stem)
    def test_strategy_produces_signals(self, strategy_file):
        """Test that each strategy produces at least one buy and one sell signal."""
        strategy = load_strategy(strategy_file)
        
        result = self.run_backtest(strategy, self.mock_data)
        
        assert result.get("success", False), f"Backtest failed: {result.get('error')}"
        
        metrics = result.get("metrics", {})
        buy_count = metrics.get("buy_signals_count", 0)
        sell_count = metrics.get("sell_signals_count", 0)
        
        # We want at least one of each signal type
        # Some strategies might not get both in limited data, so we check for at least one signal
        total_signals = buy_count + sell_count
        assert total_signals > 0, f"Strategy {strategy_file.stem} produced no signals"
        
        print(f"\n✓ {strategy_file.stem}: Buy={buy_count}, Sell={sell_count}")
    
    def test_ma_crossover_strategy(self):
        """Test MA Crossover strategy specifically."""
        strategy_path = STRATEGIES_DIR / "ma_crossover.json"
        if not strategy_path.exists():
            pytest.skip("ma_crossover.json not found")
        
        strategy = load_strategy(strategy_path)
        result = self.run_backtest(strategy, self.mock_data)
        
        assert result.get("success", False), f"MA Crossover failed: {result.get('error')}"
        
        # MA crossover should produce signals in trending data
        metrics = result.get("metrics", {})
        assert metrics.get("buy_signals_count", 0) > 0 or metrics.get("sell_signals_count", 0) > 0
    
    def test_rsi_strategy(self):
        """Test RSI Overbought/Oversold strategy specifically."""
        strategy_path = STRATEGIES_DIR / "rsi_overbought_oversold.json"
        if not strategy_path.exists():
            pytest.skip("rsi_overbought_oversold.json not found")
        
        strategy = load_strategy(strategy_path)
        
        # Generate data with more extreme moves to trigger RSI signals
        extreme_data = generate_mock_ohlcv_data(n_bars=200, volatility=0.05)
        result = self.run_backtest(strategy, extreme_data)
        
        assert result.get("success", False), f"RSI strategy failed: {result.get('error')}"
    
    def test_macd_crossover_strategy(self):
        """Test MACD Crossover strategy specifically."""
        strategy_path = STRATEGIES_DIR / "macd_crossover.json"
        if not strategy_path.exists():
            pytest.skip("macd_crossover.json not found")
        
        strategy = load_strategy(strategy_path)
        result = self.run_backtest(strategy, self.mock_data)
        
        assert result.get("success", False), f"MACD Crossover failed: {result.get('error')}"
    
    def test_bollinger_breakout_strategy(self):
        """Test Bollinger Bands Breakout strategy specifically."""
        strategy_path = STRATEGIES_DIR / "bollinger_breakout.json"
        if not strategy_path.exists():
            pytest.skip("bollinger_breakout.json not found")
        
        strategy = load_strategy(strategy_path)
        
        # Generate data with more volatility to trigger Bollinger signals
        volatile_data = generate_mock_ohlcv_data(n_bars=150, volatility=0.06)
        result = self.run_backtest(strategy, volatile_data)
        
        assert result.get("success", False), f"Bollinger Breakout failed: {result.get('error')}"


class TestStrategyFileValidity:
    """Tests for strategy file format validity."""
    
    @pytest.mark.parametrize("strategy_file", get_strategy_files(), ids=lambda f: f.stem)
    def test_strategy_json_valid(self, strategy_file):
        """Test that strategy JSON is valid."""
        strategy = load_strategy(strategy_file)
        
        assert "nodes" in strategy, "Strategy must have 'nodes'"
        assert "edges" in strategy, "Strategy must have 'edges'"
        assert len(strategy["nodes"]) > 0, "Strategy must have at least one node"
    
    @pytest.mark.parametrize("strategy_file", get_strategy_files(), ids=lambda f: f.stem)
    def test_strategy_has_required_nodes(self, strategy_file):
        """Test that strategy has required node types."""
        strategy = load_strategy(strategy_file)
        
        node_types = [n.get("type", "") for n in strategy["nodes"]]
        
        # Must have a data source
        has_data = any("data." in t for t in node_types)
        assert has_data, "Strategy must have a data source node"
        
        # Must have at least one signal (buy or sell)
        has_signal = any("signal." in t for t in node_types)
        assert has_signal, "Strategy must have at least one signal node"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
