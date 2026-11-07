"""
Hold Signal Node - Outputs a HOLD trading signal.

This is a TAIL node that represents the decision to maintain current position.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class HoldSignalInput(BaseModel):
    """Input schema for HoldSignalNode."""
    condition: Optional[bool] = Field(
        default=True,
        description="条件是否满足 (从上游节点传入)"
    )
    reason: Optional[str] = Field(
        default=None,
        description="持有理由 (用于日志/回溯)"
    )


class HoldSignalOutput(BaseModel):
    """Output schema for HoldSignalNode."""
    signal: str = Field(description="信号类型: 'hold'")
    triggered: bool = Field(description="信号是否触发")
    reason: Optional[str] = Field(description="持有理由")


@register_node(
    category=NodeCategory.EXECUTION,
    name="signal.hold",
    scopes=[NodeScope.STRATEGY, NodeScope.WORKFLOW]
)
class HoldSignalNode(BaseNode):
    """
    Hold Signal Node - 输出持有信号。
    
    作为策略图的 TAIL 节点，表示保持当前仓位不变的决策。
    
    用法:
    - 通常作为条件分支的 else 分支
    - 表示"不操作"
    
    示例:
    ```python
    cross = indicator.crossover(fast_line=ma5, slow_line=ma20)
    if cross == 1:
        signal.buy()
    else:
        signal.hold(reason="等待信号")
    ```
    """
    description = "输出持有信号 (TAIL 节点)"
    InputSchema = HoldSignalInput
    OutputSchema = HoldSignalOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        triggered = bool(params.condition)
        
        return {
            "signal": "hold",
            "triggered": triggered,
            "reason": params.reason
        }
