"""
Integration tests for Logic Nodes (MA, RSI, LogicIf).

Tests both Hybrid (vectorized) and Event (step-by-step) modes.
"""
import pytest
import os
import sys
import math

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.logic import MANode, RSINode, LogicIfNode


def generate_trend_data(length: int = 100, trend: float = 0.5) -> list:
    """Generate synthetic trending price data."""
    data = []
    price = 100.0
    for i in range(length):
        price += trend + 0.5 * math.sin(i * 0.1)  # Trend + oscillation
        data.append({
            "timestamp": 1000 + i * 1000,
            "open": price - 0.5,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price,
            "volume": 1000
        })
    return data


class TestMANode:
    """Test MANode with dual-mode support."""
    
    def test_sma_hybrid_mode(self):
        """Test SMA calculation in hybrid mode."""
        node = MANode()
        data = [float(i) for i in range(1, 21)]  # 1 to 20
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="ma",
            inputs={"data": data, "period": 5, "ma_type": "sma", "mode": "hybrid"}
        )
        
        result = node.run(ctx)
        
        assert len(result["values"]) == 20
        assert result["values"][0:4] == [None, None, None, None]  # Not enough data
        assert result["values"][4] == 3.0  # MA(1,2,3,4,5) = 3.0
        assert result["values"][-1] == 18.0  # MA(16,17,18,19,20) = 18
        print(f"[MA/SMA] Hybrid: {result['values'][-5:]}")
    
    def test_ema_hybrid_mode(self):
        """Test EMA calculation."""
        node = MANode()
        data = [float(i) for i in range(1, 51)]
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="ma",
            inputs={"data": data, "period": 10, "ma_type": "ema", "mode": "hybrid"}
        )
        
        result = node.run(ctx)
        
        assert len(result["values"]) == 50
        assert result["values"][8] is None  # Not enough data
        assert result["values"][9] is not None  # First EMA value
        print(f"[MA/EMA] Last 5: {result['values'][-5:]}")
    
    def test_sma_event_mode(self):
        """Test SMA in event mode (single value)."""
        node = MANode()
        data = [float(i) for i in range(1, 21)]
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="ma",
            inputs={
                "data": data, 
                "period": 5, 
                "ma_type": "sma", 
                "mode": "event",
                "current_index": 9  # Index 9 -> values 6,7,8,9,10 -> MA = 8.0
            }
        )
        
        result = node.run(ctx)
        
        assert result["current_value"] == 8.0
        print(f"[MA/SMA] Event mode at index 9: {result['current_value']}")
    
    def test_with_ohlcv_data(self):
        """Test MA with OHLCV dict data."""
        node = MANode()
        data = generate_trend_data(50)
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="ma",
            inputs={"data": data, "period": 10, "price_field": "close"}
        )
        
        result = node.run(ctx)
        
        assert len(result["values"]) == 50
        assert result["current_value"] is not None
        print(f"[MA] With OHLCV: last value = {result['current_value']:.2f}")


class TestRSINode:
    """Test RSINode."""
    
    def test_rsi_hybrid_mode(self):
        """Test RSI calculation in hybrid mode."""
        node = RSINode()
        # Generate trending up data (should have high RSI)
        data = [100 + i * 0.5 for i in range(50)]
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="rsi",
            inputs={"data": data, "period": 14, "mode": "hybrid"}
        )
        
        result = node.run(ctx)
        
        assert len(result["values"]) == 50
        # Strong uptrend should have high RSI
        assert result["current_value"] > 70
        print(f"[RSI] Uptrend RSI: {result['current_value']:.1f}")
    
    def test_rsi_downtrend(self):
        """Test RSI with downtrend data."""
        node = RSINode()
        data = [100 - i * 0.5 for i in range(50)]
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="rsi",
            inputs={"data": data, "period": 14}
        )
        
        result = node.run(ctx)
        
        # Strong downtrend should have low RSI
        assert result["current_value"] < 30
        print(f"[RSI] Downtrend RSI: {result['current_value']:.1f}")
    
    def test_rsi_event_mode(self):
        """Test RSI in event mode."""
        node = RSINode()
        data = generate_trend_data(100)
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="rsi",
            inputs={"data": data, "period": 14, "mode": "event", "current_index": 50}
        )
        
        result = node.run(ctx)
        
        assert result["current_value"] is not None
        assert 0 <= result["current_value"] <= 100
        print(f"[RSI] Event mode at index 50: {result['current_value']:.1f}")


class TestLogicIfNode:
    """Test LogicIfNode."""
    
    def test_simple_comparison(self):
        """Test simple comparison expression."""
        node = LogicIfNode()
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="logic_if",
            inputs={
                "condition_expr": "close > ma20",
                "context": {"close": 105, "ma20": 100}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"] is True
        assert result["action"] == "true_branch"
        print(f"[LogicIf] close(105) > ma20(100) = {result['result']}")
    
    def test_complex_expression(self):
        """Test complex expression with multiple conditions."""
        node = LogicIfNode()
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="logic_if",
            inputs={
                "condition_expr": "rsi < 30 and close > open",
                "context": {"rsi": 25, "close": 102, "open": 100}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"] is True
        print(f"[LogicIf] RSI oversold + bullish bar = {result['result']}")
    
    def test_false_condition(self):
        """Test condition that evaluates to False."""
        node = LogicIfNode()
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="logic_if",
            inputs={
                "condition_expr": "volume > avg_volume * 2",
                "context": {"volume": 1000, "avg_volume": 800}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"] is False
        assert result["action"] == "false_branch"
    
    def test_error_handling(self):
        """Test error handling for invalid expressions."""
        node = LogicIfNode()
        
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="logic_if",
            inputs={
                "condition_expr": "undefined_var > 100",
                "context": {}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"] is False
        assert result["error"] is not None
        print(f"[LogicIf] Error handling: {result['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
