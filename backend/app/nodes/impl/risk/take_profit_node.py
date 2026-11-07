"""
TakeProfitNode - Configures take profit parameters for a trade.

This node outputs take profit configuration that the BacktestRunner uses.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class TakeProfitInput(BaseModel):
    """Input schema for TakeProfitNode."""
    type: str = Field(
        default="percentage",
        description="Take profit type: 'percentage', 'fixed', 'atr', 'rr_ratio'"
    )
    value: float = Field(
        default=0.04,
        ge=0,
        description="Take profit value (0.04 = 4% for percentage, price units for fixed, multiplier for ATR/RR)"
    )
    atr_value: Optional[float] = Field(
        default=None,
        description="ATR value for ATR-based take profit"
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Entry price for calculating target price"
    )
    stop_distance: Optional[float] = Field(
        default=None,
        description="Stop distance for Risk/Reward ratio calculation"
    )


class TakeProfitOutput(BaseModel):
    """Output schema for TakeProfitNode."""
    tp_type: str = Field(description="Take profit type used")
    tp_value: float = Field(description="Take profit value")
    target_price: Optional[float] = Field(
        default=None,
        description="Calculated target price (if entry_price provided)"
    )
    enabled: bool = Field(default=True, description="Whether take profit is enabled")


@register_node(
    category=NodeCategory.EXECUTION,
    name="risk.take_profit",
    scopes=[NodeScope.STRATEGY, NodeScope.WORKFLOW]
)
class TakeProfitNode(BaseNode):
    """
    Take Profit Node - Configures take profit for trades.
    
    Supports take profit types:
    - percentage: Take profit at X% above entry (e.g., 0.04 = 4%)
    - fixed: Take profit at fixed price distance from entry
    - atr: Take profit at N * ATR above entry
    - rr_ratio: Take profit at N * stop_distance (e.g., 2.0 = 1:2 risk/reward)
    
    NOTE: The actual take profit execution is handled by BacktestRunner.
    This node outputs the CONFIGURATION for take profit.
    
    示例 (For LLM):
    ```python
    # 百分比止盈 (4%)
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    ma_cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)
    
    # 设置止损和止盈
    stop = risk.stop_loss(type="percentage", value=0.02)
    profit = risk.take_profit(type="percentage", value=0.04)
    
    if ma_cross == 1:
        signal.buy(quantity=1.0, stop_loss=stop, take_profit=profit)
    ```
    
    风险回报比止盈 (1:2):
    ```python
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="4h")
    atr = indicator.atr(source=data, period=14)
    
    # 止损2倍ATR，止盈按1:2风险回报
    stop = risk.stop_loss(type="atr", value=2.0, atr_value=atr.current_value)
    profit = risk.take_profit(type="rr_ratio", value=2.0, stop_distance=stop.stop_value * atr.current_value)
    
    if cross == 1:
        signal.buy(quantity=1.0, stop_loss=stop, take_profit=profit)
    ```
    """
    description = "止盈配置 (percentage/fixed/atr/rr_ratio)"
    InputSchema = TakeProfitInput
    OutputSchema = TakeProfitOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        target_price = None
        
        # Calculate target price if we have entry price
        if params.entry_price is not None:
            if params.type == "percentage":
                target_price = params.entry_price * (1 + params.value)
            elif params.type == "fixed":
                target_price = params.entry_price + params.value
            elif params.type == "atr" and params.atr_value is not None:
                target_price = params.entry_price + (params.value * params.atr_value)
            elif params.type == "rr_ratio" and params.stop_distance is not None:
                target_price = params.entry_price + (params.value * params.stop_distance)
        
        return {
            "tp_type": params.type,
            "tp_value": params.value,
            "target_price": target_price,
            "enabled": True
        }
