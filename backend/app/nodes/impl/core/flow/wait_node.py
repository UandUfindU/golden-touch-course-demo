"""
Wait Node - Synchronization point for parallel branches.

Waits for all specified upstream nodes to complete before triggering downstream.
Part of core/flow nodes, available in all scopes.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class WaitInput(BaseModel):
    """Wait node configuration"""
    timeout_seconds: int = Field(
        default=300,
        description="Maximum time to wait for all upstream nodes (seconds)"
    )


class WaitOutput(BaseModel):
    completed: bool = Field(description="Whether all upstream nodes completed")
    upstream_data: Dict[str, Any] = Field(
        default={},
        description="Data from completed upstream nodes"
    )


@register_node(
    category=NodeCategory.FLOW,
    name="flow.wait",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class WaitNode(BaseNode):
    """
    Wait Node - Synchronization point for parallel execution.
    
    This node acts as a barrier - it waits until ALL upstream nodes
    have completed before passing through to downstream nodes.
    
    The actual waiting logic is handled by the GraphRunner, which
    only triggers this node when all incoming edges are satisfied.
    This node just passes through the upstream data.
    """
    description = "Wait for all upstream nodes to complete"
    InputSchema = WaitInput
    OutputSchema = WaitOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # The GraphRunner handles the actual synchronization.
        # When this node runs, all upstream nodes have already completed.
        # We simply collect and pass through the upstream data.
        
        upstream_data = {}
        for key, value in ctx.inputs.items():
            if key != "timeout_seconds":
                upstream_data[key] = value
        
        return {
            "completed": True,
            "upstream_data": upstream_data
        }
