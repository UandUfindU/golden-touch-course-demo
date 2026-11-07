"""
Test CrossOverNode logic.
"""
import pytest
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.logic import CrossOverNode


class TestCrossOverNode:
    """Test CrossOverNode."""
    
    def test_hybrid_crossover(self):
        """Test vectorized crossover detection."""
        node = CrossOverNode()
        
        # Fast crosses Slow from below at index 2
        # Index: 0   1   2   3
        # Fast:  10, 10, 12, 13
        # Slow:  11, 11, 11, 11
        fast = [10.0, 10.0, 12.0, 13.0]
        slow = [11.0, 11.0, 11.0, 11.0]
        
        ctx = Context(
            run_id="t", workflow_id="w", node_id="cross",
            inputs={"fast_line": fast, "slow_line": slow, "mode": "hybrid"}
        )
        
        result = node.run(ctx)
        signals = result["crossover"]
        
        assert signals[0] == 0
        assert signals[1] == 0
        assert signals[2] == 1  # Golden Cross
        assert signals[3] == 0
        print(f"Hybrid Signals: {signals}")

    def test_event_crossover(self):
        """Test event-mode crossover."""
        node = CrossOverNode()
        fast = [10.0, 12.0]
        slow = [11.0, 11.0]
        
        # At index 1: Fast(12) > Slow(11) AND PrevFast(10) < PrevSlow(11) -> Cross
        ctx = Context(
            run_id="t", workflow_id="w", node_id="cross",
            inputs={"fast_line": fast, "slow_line": slow, "mode": "event", "current_index": 1}
        )
        
        result = node.run(ctx)
        assert result["current_signal"] == 1
        print("Event Signal (Index 1): Golden Cross")

    def test_death_cross(self):
        """Test bearish crossover."""
        node = CrossOverNode()
        # Fast crosses Slow from above at index 2
        fast = [12.0, 12.0, 10.0]
        slow = [11.0, 11.0, 11.0]
        
        ctx = Context(
            run_id="t", workflow_id="w", node_id="cross",
            inputs={"fast_line": fast, "slow_line": slow, "mode": "hybrid"}
        )
        
        result = node.run(ctx)
        assert result["crossover"][2] == -1
        print("Death Cross Detected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
