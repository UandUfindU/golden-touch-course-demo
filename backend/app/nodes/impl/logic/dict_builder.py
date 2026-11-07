from typing import Dict, Any
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole

class DictBuilderInput(BaseModel):
    # Flexible input: accepts any keys
    pass

class DictBuilderOutput(BaseModel):
    result: Dict[str, Any] = Field(description="The aggregated dictionary")

@register_node(
    category=NodeCategory.UTILITY,
    name="utility.dict_builder",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class DictBuilderNode(BaseNode):
    """
    Aggregates all provided inputs into a single dictionary.
    Used to prepare 'variables' for templates.
    
    Example:
    Inputs: key1="value1", key2=10
    Output: {"result": {"key1": "value1", "key2": 10}}
    """
    description = "将所有输入合并为一个字典"
    InputSchema = DictBuilderInput
    OutputSchema = DictBuilderOutput
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> BaseModel:
        # Override to allow dynamic inputs without validation error
        # We don't use strict Pydantic validation for InputSchema here because it's dynamic
        return DictBuilderInput() 

    def run(self, ctx: Context) -> Dict[str, Any]:
        # Directly use ctx.inputs as the result
        # Filter out system keys if any? 
        return {"result": ctx.inputs}
