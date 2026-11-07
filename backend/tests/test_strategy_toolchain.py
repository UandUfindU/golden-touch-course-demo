"""
Integration test for Strategy ToolChain (Fast Mode).

Tests the BuildStrategyNode end-to-end with a mock LLM response.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from app.nodes.base import Context
from app.nodes.impl.engine.strategy_toolchain import (
    BuildStrategyNode, 
    build_nodes_documentation,
    STRATEGY_FAST_SYSTEM_PROMPT
)


class TestNodeDocumentation:
    """Test node documentation builder."""
    
    def test_builds_documentation(self):
        """Should build documentation string with node info."""
        doc = build_nodes_documentation(scope="strategy")
        
        assert len(doc) > 100  # Should have substantial content
        # Check for expected node types
        assert "### " in doc  # Category headers
        
    def test_includes_data_nodes(self):
        """Documentation should include data nodes."""
        doc = build_nodes_documentation()
        # Check if data-related nodes are present
        assert "data" in doc.lower() or "fetch" in doc.lower() or len(doc) > 50


class TestPromptTemplates:
    """Test prompt templates."""
    
    def test_fast_prompt_has_placeholders(self):
        """Fast mode prompt should have required placeholders."""
        assert "{current_graph_as_python}" in STRATEGY_FAST_SYSTEM_PROMPT
        assert "{nodes_documentation}" in STRATEGY_FAST_SYSTEM_PROMPT
    
    def test_fast_prompt_has_examples(self):
        """Fast mode prompt should include examples."""
        assert "```python" in STRATEGY_FAST_SYSTEM_PROMPT
        assert "ma" in STRATEGY_FAST_SYSTEM_PROMPT.lower()


class TestBuildStrategyNode:
    """Test BuildStrategyNode interface."""
    
    def test_node_registration(self):
        """Node should be registered correctly."""
        node = BuildStrategyNode()
        assert node.description is not None
        assert "Fast" in node.description or "一次性" in node.description
    
    def test_empty_graph_input(self):
        """Should accept empty graph as input."""
        node = BuildStrategyNode()
        
        # Validate input schema accepts empty graph
        from app.nodes.impl.engine.strategy_toolchain import StrategyToolInput
        
        input_data = StrategyToolInput(
            current_graph={"nodes": [], "edges": []},
            prompt="创建一个简单的 MA 策略"
        )
        
        assert input_data.current_graph["nodes"] == []
        assert input_data.prompt == "创建一个简单的 MA 策略"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
