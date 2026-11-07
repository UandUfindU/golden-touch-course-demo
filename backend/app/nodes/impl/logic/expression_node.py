"""
LogicExpressionNode - General purpose expression evaluator.

Enables calculation of arbitrary Python expressions within the graph.
Critical for 'Node-only' architecture where all variables are node outputs.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class LogicExpressionInput(BaseModel):
    """Input schema for LogicExpressionNode."""
    expr: str = Field(
        description="Python expression to evaluate, e.g., 'high - low' or 'ma20 * 1.05'"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables available for expression evaluation"
    )

class LogicExpressionOutput(BaseModel):
    """Output schema for LogicExpressionNode."""
    value: Any = Field(description="Result of the evaluation")
    error: Optional[str] = Field(default=None, description="Error message if failed")


SAFE_BUILTINS = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'len': len,
    'sum': sum,
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,
    'list': list,
    'dict': dict,
    'True': True,
    'False': False,
    'None': None,
}

@register_node(
    category=NodeCategory.LOGIC,
    name="logic.expression",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class LogicExpressionNode(BaseNode):
    """
    Logic Expression Node - Evaluate arbitrary Python expressions.
    
    Used for intermediate calculations, variable assignments, and formula evaluation.
    Outputs the raw result (number, string, list, etc.).
    """
    description = "Evaluate arbitrary Python expression"
    InputSchema = LogicExpressionInput
    OutputSchema = LogicExpressionOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        try:
            # Build safe evaluation context
            eval_globals = {"__builtins__": SAFE_BUILTINS}
            eval_locals = dict(params.context)
            
            result = eval(params.expr, eval_globals, eval_locals)
            
            return {
                "value": result,
                "error": None
            }
            
        except Exception as e:
            return {
                "value": None,
                "error": f"Expression error: {str(e)}"
            }
