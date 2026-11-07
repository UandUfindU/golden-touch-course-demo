from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole

class InputNodeInput(BaseModel):
    """Configuration for Input Node."""
    name: str = Field(..., description="Name of the input parameter (e.g., 'user_query')")
    default_value: Optional[Any] = Field(None, description="Default value if not provided")
    description: str = Field("", description="Description of this input")

class InputNodeOutput(BaseModel):
    """Output schema for Input Node."""
    value: Any = Field(..., description="The value passed from the parent graph")

@register_node(
    category=NodeCategory.STRUCTURE,
    name="structure.input",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.HEAD
)
class InputNode(BaseNode):
    """
    Sub-graph Input Gateway.
    
    Acts as a placeholder inside a Composite Node. When the composite node runs,
    it passes values from its own inputs to these nodes.
    """
    description = "Defines an input port for a Sub-Graph"
    InputSchema = InputNodeInput
    OutputSchema = InputNodeOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # In a real execution scenario via GraphExecutor, the value should 
        # have been injected into ctx.inputs['value'] OR the inputs themselves 
        # act as the value source if standardized.
        #
        # Convention: usage in GraphExecutor:
        # executor maps `composite_inputs[params.name]` -> `input_node_inputs['value']`
        
        # However, for simplicity, if 'value' is present in inputs, use it.
        # If not, check if 'default_value' is usable.
        
        val = ctx.inputs.get("value", params.default_value)
        
        return {
            "value": val
        }


class OutputNodeInput(BaseModel):
    """Configuration for Output Node."""
    name: str = Field(..., description="Name of the output parameter (e.g., 'report')")
    value: Any = Field(..., description="The value to export from the sub-graph")
    description: str = Field("", description="Description of this output")

class OutputNodeOutput(BaseModel):
    """Output schema for Output Node."""
    final_value: Any = Field(..., description="The exported value")

@register_node(
    category=NodeCategory.STRUCTURE,
    name="structure.output",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.TAIL
)
class OutputNode(BaseNode):
    """
    Sub-graph Output Collector.
    
    Collects a result from the sub-graph logic and exposes it as an output 
    of the parent Composite Node.
    """
    description = "Defines an output port for a Sub-Graph"
    InputSchema = OutputNodeInput
    OutputSchema = OutputNodeOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # The executor will read this node's output to populate the composite node's result
        return {
            "final_value": params.value
        }
