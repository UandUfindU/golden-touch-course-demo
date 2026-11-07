"""
Sell Signal Node - Outputs a SELL trading signal.

This is a TAIL node that represents the decision to exit a position or go short.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class SellSignalInput(BaseModel):
    """Input schema for SellSignalNode."""
    condition: Optional[bool] = Field(
        default=True,
        description="条件是否满足 (从上游节点传入)"
    )
    price: Optional[float] = Field(
        default=None,
        description="出场价格 (可选)"
    )
    quantity: Optional[float] = Field(
        default=1.0,
        description="交易数量/仓位比例"
    )
    reason: Optional[str] = Field(
        default=None,
        description="卖出理由 (用于日志/回溯)"
    )


class SellSignalOutput(BaseModel):
    """Output schema for SellSignalNode."""
    signal: str = Field(description="信号类型: 'sell'")
    triggered: bool = Field(description="信号是否触发")
    price: Optional[float] = Field(description="出场价格")
    quantity: float = Field(description="交易数量")
    reason: Optional[str] = Field(description="卖出理由")


@register_node(
    category=NodeCategory.EXECUTION,
    name="signal.sell",
    scopes=[NodeScope.STRATEGY, NodeScope.WORKFLOW]
)
class SellSignalNode(BaseNode):
    """
    Sell Signal Node - 输出卖出信号。
    
    作为策略图的 TAIL 节点，表示平仓或做空的决策。
    
    用法:
    - 连接条件节点到 condition 输入
    - 可选指定出场价格和数量
    
    推荐示例 (直接使用条件):
    ```python
    # 方式1: 直接在参数中传入条件表达式 (推荐!)
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="1h")
    rsi = indicator.rsi(source=data, period=14)
    
    # RSI策略: 超卖买入，超买卖出
    signal.buy(condition=rsi < 30, quantity=1.0, reason="RSI超卖")
    signal.sell(condition=rsi > 70, quantity=1.0, reason="RSI超买")
    ```
    
    配合crossover使用:
    ```python
    # 方式2: 使用if语句配合均线交叉
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    ma_fast = indicator.ma(source=data, period=10)
    ma_slow = indicator.ma(source=data, period=20)
    cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)
    
    # 金叉买入 (crossover输出1表示金叉)
    if cross == 1:
        signal.buy(quantity=1.0, reason="金叉买入")
    # 死叉卖出 (crossover输出-1表示死叉)
    if cross == -1:
        signal.sell(quantity=1.0, reason="死叉卖出")
    ```
    
    注意: 每个策略应同时包含买入和卖出信号以形成完整交易闭环。
    """
    description = "输出卖出信号 (TAIL 节点)"
    InputSchema = SellSignalInput
    OutputSchema = SellSignalOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        triggered = bool(params.condition)
        
        return {
            "signal": "sell",
            "triggered": triggered,
            "price": params.price,
            "quantity": params.quantity if triggered else 0,
            "reason": params.reason
        }
