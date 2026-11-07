"""
LogicIfNode - Conditional logic for strategy flow control.

Evaluates expressions and outputs boolean results for signal routing.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class LogicIfInput(BaseModel):
    """Input schema for LogicIfNode."""
    condition_expr: Optional[str] = Field(
        default=None,
        description="Expression to evaluate, e.g., 'close > ma20' or 'rsi < 30'"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables available for expression evaluation"
    )
    # Structured inputs for direct comparison (LLM friendly)
    left: Optional[Any] = Field(default=None, description="Left operand")
    operator: Optional[str] = Field(default=None, description="Operator (>, <, ==, !=, >=, <=, and, or)")
    right: Optional[Any] = Field(default=None, description="Right operand")
    
    # Allow positional aliases from CodeToDag
    arg_0: Optional[Any] = Field(default=None, alias="left_alias")
    arg_1: Optional[str] = Field(default=None, alias="op_alias")
    arg_2: Optional[Any] = Field(default=None, alias="right_alias")


class LogicIfOutput(BaseModel):
    """Output schema for LogicIfNode."""
    result: bool = Field(description="Evaluation result")
    action: Optional[str] = Field(
        default=None,
        description="Suggested action based on result ('true_branch' or 'false_branch')"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if evaluation failed"
    )


# Safe builtins for expression evaluation
SAFE_BUILTINS = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'len': len,
    'sum': sum,
    'True': True,
    'False': False,
    'None': None,
}

OPERATORS = {
    '>': lambda x, y: x > y,
    '<': lambda x, y: x < y,
    '>=': lambda x, y: x >= y,
    '<=': lambda x, y: x <= y,
    '==': lambda x, y: x == y,
    '!=': lambda x, y: x != y,
    'and': lambda x, y: bool(x) and bool(y),
    'or': lambda x, y: bool(x) or bool(y),
}


@register_node(
    category=NodeCategory.LOGIC,
    name="logic.condition",  # Cannot use 'logic.if' - 'if' is Python reserved keyword
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class LogicIfNode(BaseNode):
    """
    Logic If Node - Evaluate conditional expressions for strategy flow control.
    
    Supports expressions like:
    - 'close > ma20'
    - Structured: left=rsi, operator='<', right=30
    """
    description = "Evaluate conditional expression"
    InputSchema = LogicIfInput
    OutputSchema = LogicIfOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        # Handle Positional Alias Fallback
        # CodeToDag maps first 3 args to arg_0, arg_1, arg_2
        left = params.left if params.left is not None else params.arg_0
        op = params.operator if params.operator is not None else params.arg_1
        right = params.right if params.right is not None else params.arg_2
        
        result_bool = False
        
        try:
            # Mode 1: Expression String
            if params.condition_expr:
                # Build safe evaluation context
                eval_globals = {"__builtins__": SAFE_BUILTINS}
                eval_locals = dict(params.context)
                
                # If structured inputs provided, add them to context too (optional)
                if left is not None: eval_locals['left'] = left
                if right is not None: eval_locals['right'] = right
                
                result = eval(params.condition_expr, eval_globals, eval_locals)
                result_bool = bool(result)
            
            # Mode 2: Structured Comparison
            elif op is not None:
                if op not in OPERATORS:
                     return {
                        "result": False,
                        "action": "false_branch",
                        "error": f"Unsupported operator: {op}"
                    }
                
                # Ensure we have operands (None checks if needed, but None might be valid like 'is None')
                # For simplified logic, assume values are ready (resolved from edges)
                result_bool = OPERATORS[op](left, right)
                
            else:
                 return {
                    "result": False,
                    "action": "false_branch",
                    "error": "Missing 'condition_expr' or 'operator'"
                }

            return {
                "result": result_bool,
                "action": "true_branch" if result_bool else "false_branch",
                "error": None
            }

        except Exception as e:
            return {
                "result": False,
                "action": "false_branch",
                "error": f"Evaluation error: {str(e)}"
            }
