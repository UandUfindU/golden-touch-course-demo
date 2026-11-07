"""
Loop Node - Iterates over a list and executes a subgraph for each item.

Part of core/flow nodes, available in all scopes.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class LoopInput(BaseModel):
    """Loop node configuration"""
    items: List[Any] = Field(
        description="List of items to iterate over"
    )
    subgraph_id: Optional[str] = Field(
        default=None,
        description="ID of the subgraph to execute for each item"
    )
    parallel: bool = Field(
        default=False,
        description="Whether to execute iterations in parallel"
    )


class LoopOutput(BaseModel):
    results: List[Any] = Field(
        default=[],
        description="Results from each iteration"
    )
    iteration_count: int = Field(description="Number of iterations completed")


@register_node(
    category=NodeCategory.FLOW,
    name="flow.loop",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class LoopNode(BaseNode):
    """
    Loop Node - Iterates over items and executes logic for each.
    
    For simple cases (no subgraph), it just iterates and outputs.
    For complex cases (with subgraph_id), the GraphRunner will:
    1. For each item, create a new context with the item as input
    2. Execute the referenced subgraph
    3. Collect results from each execution
    
    This is a "meta" node - its full behavior depends on the engine.
    """
    description = "Loop over a list of items"
    InputSchema = LoopInput
    OutputSchema = LoopOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # If no subgraph is specified, just return the items as-is
        # with metadata about the loop structure.
        # The GraphRunner handles actual subgraph execution.
        
        if not params.subgraph_id:
            # Simple case: just pass through items
            return {
                "results": params.items,
                "iteration_count": len(params.items)
            }
        
        # With subgraph: this return signals to the engine
        # that subgraph execution is needed.
        # The actual execution is handled by GraphRunner.
        return {
            "results": [],  # Will be populated by engine
            "iteration_count": len(params.items),
            "_pending_subgraph": params.subgraph_id,
            "_items": params.items,
            "_parallel": params.parallel
        }
