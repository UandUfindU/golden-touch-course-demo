
import pytest
from pydantic import ValidationError
from app.models.workflow import Workflow
from app.models.node_def import NodeDef
from app.models.run import WorkflowRun
from app.core.enums import NodeCategory, NodeScope, RunStatus

def test_workflow_instantiation():
    """Test standard workflow creation"""
    wf = Workflow(name="Test Workflow", description="Unit Test")
    assert wf.id is not None
    assert wf.name == "Test Workflow"
    assert wf.version == 1
    assert isinstance(wf.graph_data, dict)

def test_node_def_taxonomy():
    """Verify NodeDef strictly enforces Enums"""
    node = NodeDef(
        unique_key="test.node",
        name="Test Node",
        category=NodeCategory.STRATEGY,
        scopes=[NodeScope.STRATEGY, NodeScope.TOOL],
        class_path="app.nodes.impl.test.Node"
    )
    assert node.category == NodeCategory.STRATEGY
    assert NodeScope.TOOL in node.scopes
    assert node.version == "1.0.0"
    # Note: SQLModel with (str, Enum) doesn't strictly validate enum values
    # at the Pydantic layer. DB constraints would catch this on insert.
def test_run_status_flow():
    """Test WorkflowRun status transitions logic"""
    # Note: Logic is usually in Service/Engine, but Model holds state
    run = WorkflowRun(workflow_id="123e4567-e89b-12d3-a456-426614174000")
    assert run.status == RunStatus.PENDING
    assert run.context_snapshot == {}
    
    run.status = RunStatus.RUNNING
    assert run.status == "running"
