"""
Input Node - Defines the input boundary for a subgraph (Tool scope).

When a subgraph is encapsulated as a reusable tool/node, this node
defines what inputs the tool expects.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class InputNodeInput(BaseModel):
    """
    Configuration for the Input boundary node.
    This defines the schema of inputs the subgraph expects.
    """
    schema_definition: Dict[str, Any] = Field(
        default={},
        description="JSON Schema defining expected input parameters"
    )
    # At runtime, actual input data is injected by the engine
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Actual input data passed to the subgraph"
    )


class InputNodeOutput(BaseModel):
    """Output is the data passed through for downstream nodes"""
    data: Dict[str, Any] = Field(description="Input data passed to subgraph")


@register_node(
    category=NodeCategory.UTILITY,
    name="tool.input",
    scopes=[NodeScope.TOOL]
)
class InputNode(BaseNode):
    """
    Input Node - Entry point for tool/subgraph definitions.
    
    When creating a reusable tool from a subgraph, this node marks
    the input boundary. The schema_definition describes what parameters
    the tool accepts, and the GraphRunner injects actual data at runtime.
    """
    description = "Subgraph input boundary"
    InputSchema = InputNodeInput
    OutputSchema = InputNodeOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Pass through the input data
        # The engine is responsible for injecting 'data' from the caller
        return {
            "data": params.data or {}
        }
