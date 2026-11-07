"""
Tests for the Engine module (GraphExecutor, DAGtoPython, validate_graph).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from app.nodes.impl.engine import GraphExecutorNode, DAGtoPythonNode, validate_graph
from app.nodes.base import Context


class TestValidateGraph:
    """Tests for the validate_graph utility."""
    
    def test_empty_graph(self):
        """Empty graph should be valid."""
        result = validate_graph({"nodes": [], "edges": []})
        assert result.valid is True
        assert "Empty" in result.summary
    
    def test_cycle_detection(self):
        """Graph with cycles should be invalid."""
        dag = {
            "nodes": [
                {"id": "a", "type": "core.input"},
                {"id": "b", "type": "core.output"}
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "a"}  # Cycle!
            ]
        }
        result = validate_graph(dag)
        assert result.valid is False
        assert any("cycle" in i["message"].lower() for i in result.issues)
    
    def test_missing_node_reference(self):
        """Edge referencing non-existent node should error."""
        dag = {
            "nodes": [{"id": "a", "type": "core.input"}],
            "edges": [{"source": "a", "target": "z"}]  # z doesn't exist
        }
        result = validate_graph(dag)
        assert result.valid is False
        assert any("non-existent" in i["message"].lower() for i in result.issues)


class TestDAGtoPython:
    """Tests for DAGtoPythonNode."""
    
    def test_simple_conversion(self):
        """Test basic DAG to Python conversion."""
        dag = {
            "nodes": [
                {"id": "n1", "type": "data.fetch_kline", "data": {"symbol": "BTC/USDT"}},
                {"id": "n2", "type": "logic.ma", "data": {"period": 20}}
            ],
            "edges": [
                {"source": "n1", "target": "n2", "target_port": "source"}
            ]
        }
        
        node = DAGtoPythonNode()
        ctx = Context(
            run_id="test", workflow_id="w", node_id="conv",
            inputs={"dag": dag}
        )
        
        result = node.run(ctx)
        
        assert result["node_count"] == 2
        assert "fetch_kline" in result["python_code"]
        assert "ma" in result["python_code"]
        assert 'symbol="BTC/USDT"' in result["python_code"]


class TestGraphExecutor:
    """Tests for GraphExecutorNode."""
    
    def test_empty_graph(self):
        """Empty graph should succeed with empty output."""
        executor = GraphExecutorNode()
        ctx = Context(
            run_id="test", workflow_id="w", node_id="exec",
            inputs={"dag": {"nodes": [], "edges": []}, "inputs": {}}
        )
        
        result = executor.run(ctx)
        
        assert result["success"] is True
        assert result["outputs"] == {}
    
    def test_input_output_pass_through(self):
        """Simple input -> output should pass data through."""
        dag = {
            "nodes": [
                {"id": "in", "type": "core.input", "data": {}},
                {"id": "out", "type": "core.output", "data": {}}
            ],
            "edges": [
                {"source": "in", "target": "out", "source_port": "value", "target_port": "result"}
            ]
        }
        
        executor = GraphExecutorNode()
        ctx = Context(
            run_id="test", workflow_id="w", node_id="exec",
            inputs={"dag": dag, "inputs": {"value": 42}}
        )
        
        result = executor.run(ctx)
        
        assert result["success"] is True
        assert result["outputs"]["result"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
