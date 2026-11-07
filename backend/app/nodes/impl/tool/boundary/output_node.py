"""
Output Node - Defines the output boundary for a subgraph (Tool scope).

When a subgraph is encapsulated as a reusable tool/node, this node
defines what outputs the tool produces.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class OutputNodeInput(BaseModel):
    """
    Configuration for the Output boundary node.
    Receives data from upstream nodes in the subgraph.
    """
    schema_definition: Dict[str, Any] = Field(
        default={},
        description="JSON Schema defining output structure"
    )
    # Data from upstream nodes is passed here
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data to output from the subgraph"
    )


class OutputNodeOutput(BaseModel):
    """Output is passed back to the caller of the subgraph"""
    result: Dict[str, Any] = Field(description="Final output of the subgraph/tool")


@register_node(
    category=NodeCategory.UTILITY,
    name="tool.output",
    scopes=[NodeScope.TOOL]
)
class OutputNode(BaseNode):
    """
    Output Node - Exit point for tool/subgraph definitions.
    
    When creating a reusable tool from a subgraph, this node marks
    the output boundary. Data reaching this node becomes the tool's output.
    """
    description = "Subgraph output boundary"
    InputSchema = OutputNodeInput
    OutputSchema = OutputNodeOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Pass through as the subgraph's final output
        # The engine will capture this and return it to the caller
        return {
            "result": params.data or {}
        }
