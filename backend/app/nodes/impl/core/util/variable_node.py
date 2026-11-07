"""
Variable Nodes - Get and Set context variables for cross-node state sharing.

Part of core/util nodes, available in all scopes.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


# --- SetVariable ---

class SetVariableInput(BaseModel):
    """SetVariable input"""
    name: str = Field(description="Variable name to set")
    value: Any = Field(description="Value to store")


class SetVariableOutput(BaseModel):
    name: str = Field(description="Variable name that was set")
    success: bool = Field(description="Whether the variable was set successfully")


@register_node(
    category=NodeCategory.UTILITY,
    name="util.set_variable",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class SetVariableNode(BaseNode):
    """
    SetVariable Node - Stores a value in the run context.
    
    This allows sharing state across different nodes in the same run.
    Variables are stored in the ContextManager and persist for the run's lifetime.
    """
    description = "Set a context variable"
    InputSchema = SetVariableInput
    OutputSchema = SetVariableOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # The value is returned in output with a special key prefix
        # that the ContextManager recognizes for variable storage.
        return {
            "name": params.name,
            "success": True,
            "_set_variable": {params.name: params.value}  # Signal to ContextManager
        }


# --- GetVariable ---

class GetVariableInput(BaseModel):
    """GetVariable input"""
    name: str = Field(description="Variable name to retrieve")
    default: Optional[Any] = Field(
        default=None,
        description="Default value if variable not found"
    )


class GetVariableOutput(BaseModel):
    name: str = Field(description="Variable name")
    value: Any = Field(description="Retrieved value")
    found: bool = Field(description="Whether the variable was found")


@register_node(
    category=NodeCategory.UTILITY,
    name="util.get_variable",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class GetVariableNode(BaseNode):
    """
    GetVariable Node - Retrieves a value from the run context.
    
    Reads a variable that was previously set by SetVariableNode.
    Returns the default value if the variable doesn't exist.
    """
    description = "Get a context variable"
    InputSchema = GetVariableInput
    OutputSchema = GetVariableOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Check if the variable exists in the context inputs
        # (ContextManager should inject variables into inputs)
        var_key = f"_var_{params.name}"
        
        if var_key in ctx.inputs:
            return {
                "name": params.name,
                "value": ctx.inputs[var_key],
                "found": True
            }
        else:
            return {
                "name": params.name,
                "value": params.default,
                "found": False
            }
