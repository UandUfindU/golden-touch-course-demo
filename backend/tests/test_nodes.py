
import pytest
from app.nodes.registry import registry
from app.nodes.impl.core.flow.if_node import LogicIfNode, LogicIfInput
from app.nodes.base import Context
from app.core.enums import NodeCategory

def test_node_registration():
    """Verify LogicIfNode is registered correctly"""
    meta_list = registry.get_all_metadata()
    # Check if logic.if is in metadata
    found = next((m for m in meta_list if m["name"] == "logic.if"), None)
    assert found is not None
    assert found["category"] == NodeCategory.FLOW
    assert "strategy" in found["scopes"]
    # Check properties
    assert "condition" in found["input_schema"]["properties"]

def test_node_execution():
    """Verify LogicIfNode run logic"""
    node = registry.get_node("logic.if")
    
    # Mock Context
    ctx_true = Context(
        run_id="test_run", 
        workflow_id="wf1", 
        node_id="n1",
        inputs={"condition": True}
    )
    
    res_true = node.run(ctx_true)
    assert res_true["branch"] == "true"
    
    ctx_false = Context(
        run_id="test_run", 
        workflow_id="wf1", 
        node_id="n1",
        inputs={"condition": False}
    )
    res_false = node.run(ctx_false)
    assert res_false["branch"] == "false"
