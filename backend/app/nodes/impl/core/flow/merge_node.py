"""
Merge Node - Combines outputs from multiple upstream branches.

Part of core/flow nodes, available in all scopes.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class MergeInput(BaseModel):
    """Merge node collects outputs from upstream nodes via context"""
    merge_strategy: str = Field(
        default="all",
        description="How to merge: 'all' (wait for all), 'any' (first available), 'concat' (list)"
    )


class MergeOutput(BaseModel):
    merged_data: Dict[str, Any] = Field(
        default={},
        description="Merged data from all upstream branches"
    )


@register_node(
    category=NodeCategory.FLOW,
    name="flow.merge",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class MergeNode(BaseNode):
    """
    Merge Node - Combines outputs from multiple upstream branches.
    
    Unlike LogicIf which splits flow, Merge joins multiple branches back together.
    The GraphRunner should wait for all specified upstream nodes to complete
    before executing this node.
    """
    description = "Merge multiple branches into one"
    InputSchema = MergeInput
    OutputSchema = MergeOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # In actual execution, the GraphRunner populates ctx.inputs
        # with outputs from all upstream nodes keyed by source node_id.
        
        # Strategy: collect all inputs except the merge_strategy param
        merged = {}
        for key, value in ctx.inputs.items():
            if key != "merge_strategy":
                merged[key] = value
        
        return {"merged_data": merged}
