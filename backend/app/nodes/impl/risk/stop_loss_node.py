"""
StopLossNode - Configures stop loss parameters for a trade.

This node outputs stop loss configuration that the BacktestRunner uses.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class StopLossInput(BaseModel):
    """Input schema for StopLossNode."""
    type: str = Field(
        default="percentage",
        description="Stop loss type: 'percentage', 'fixed', 'atr'"
    )
    value: float = Field(
        default=0.02,
        ge=0,
        description="Stop loss value (0.02 = 2% for percentage, price units for fixed, multiplier for ATR)"
    )
    atr_value: Optional[float] = Field(
        default=None,
        description="ATR value for ATR-based stop loss (from indicator.atr node)"
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Entry price for calculating stop price"
    )


class StopLossOutput(BaseModel):
    """Output schema for StopLossNode."""
    stop_type: str = Field(description="Stop loss type used")
    stop_value: float = Field(description="Stop loss value")
    stop_price: Optional[float] = Field(
        default=None,
        description="Calculated stop price (if entry_price provided)"
    )
    enabled: bool = Field(default=True, description="Whether stop loss is enabled")


@register_node(
    category=NodeCategory.EXECUTION,
    name="risk.stop_loss",
    scopes=[NodeScope.STRATEGY, NodeScope.WORKFLOW]
)
class StopLossNode(BaseNode):
    """
    Stop Loss Node - Configures stop loss for trades.
    
    Supports three stop loss types:
    - percentage: Stop at X% below entry (e.g., 0.02 = 2%)
    - fixed: Stop at fixed price distance from entry
    - atr: Stop at N * ATR below entry (requires ATR input)
    
    NOTE: The actual stop loss execution is handled by BacktestRunner.
    This node outputs the CONFIGURATION for stop loss.
    
    示例 (For LLM):
    ```python
    # 百分比止损 (2%)
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    ma_fast = indicator.ma(source=data, period=10)
    ma_slow = indicator.ma(source=data, period=20)
    cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)
    
    # 设置止损
    stop = risk.stop_loss(type="percentage", value=0.02)
    
    if cross == 1:
        signal.buy(quantity=1.0, reason="金叉买入", stop_loss=stop)
    if cross == -1:
        signal.sell(quantity=1.0, reason="死叉卖出")
    ```
    
    ATR动态止损示例:
    ```python
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="4h")
    atr = indicator.atr(source=data, period=14)
    
    # 2倍ATR止损
    stop = risk.stop_loss(type="atr", value=2.0, atr_value=atr.current_value)
    
    ma_cross = indicator.crossover(...)
    if ma_cross == 1:
        signal.buy(quantity=1.0, stop_loss=stop)
    ```
    """
    description = "止损配置 (percentage/fixed/atr)"
    InputSchema = StopLossInput
    OutputSchema = StopLossOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        stop_price = None
        
        # Calculate stop price if we have entry price
        if params.entry_price is not None:
            if params.type == "percentage":
                stop_price = params.entry_price * (1 - params.value)
            elif params.type == "fixed":
                stop_price = params.entry_price - params.value
            elif params.type == "atr" and params.atr_value is not None:
                stop_price = params.entry_price - (params.value * params.atr_value)
        
        return {
            "stop_type": params.type,
            "stop_value": params.value,
            "stop_price": stop_price,
            "enabled": True
        }
