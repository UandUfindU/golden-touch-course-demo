"""
ATRNode - Average True Range Indicator

A volatility indicator that measures price movement range.
Essential for position sizing and trailing stop calculations.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class ATRInput(BaseModel):
    """Input schema for ATRNode."""
    source: Union[List[Dict[str, Any]], List[float]] = Field(
        description="OHLCV data (must have high, low, close fields)"
    )
    period: int = Field(
        default=14,
        ge=1,
        le=100,
        description="ATR period (default: 14)"
    )
    mode: str = Field(
        default="hybrid",
        description="Calculation mode: 'hybrid' (vectorized) or 'event' (step-by-step)"
    )
    current_index: Optional[int] = Field(
        default=None,
        description="Current bar index for event mode"
    )


class ATROutput(BaseModel):
    """Output schema for ATRNode."""
    values: List[Optional[float]] = Field(
        description="ATR values for each data point"
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current ATR value"
    )
    period: int = Field(description="Period used")


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.atr",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class ATRNode(BaseNode):
    """
    ATR Node - Average True Range.
    
    Measures market volatility by decomposing the entire range of an asset price.
    
    True Range = max(
        High - Low,
        |High - Previous Close|,
        |Low - Previous Close|
    )
    ATR = SMA of True Range over N periods
    
    Uses:
    - Volatility measurement
    - Position sizing (fixed risk models)
    - Trailing stop distance calculation
    - Breakout confirmation
    
    示例 (For LLM):
    ```python
    # ATR 用于波动率过滤
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    atr = indicator.atr(source=data, period=14)
    
    # 可以结合其他指标使用
    ma_fast = indicator.ma(source=data, period=10)
    ma_slow = indicator.ma(source=data, period=20)
    cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)
    
    # 只在低波动期入场 (ATR < 某阈值)
    if cross == 1:
        signal.buy(quantity=1.0, reason="金叉+低波动")
    if cross == -1:
        signal.sell(quantity=1.0, reason="死叉")
    ```
    
    止损距离计算示例:
    ```python
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="4h")
    atr = indicator.atr(source=data, period=14)
    
    # 止损距离 = 2倍ATR
    # stop_price = entry_price - (2 * atr.current_value)
    ```
    """
    description = "ATR波动率指标 (用于仓位计算和止损距离)"
    InputSchema = ATRInput
    OutputSchema = ATROutput
    
    def _extract_ohlc(self, data: Union[List[Dict[str, Any]], List[float]]) -> tuple:
        """Extract OHLC series from input data."""
        if not data:
            return [], [], []
        
        if isinstance(data[0], dict):
            high = [d.get('high', d.get('close', 0)) for d in data]
            low = [d.get('low', d.get('close', 0)) for d in data]
            close = [d.get('close', 0) for d in data]
            return high, low, close
        
        # If just a list of floats, assume it's close prices (limited functionality)
        return list(data), list(data), list(data)
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Calculate ATR using vectorized operations."""
        # Previous close
        prev_close = close.shift(1)
        
        # True Range components
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        # True Range = max of three components
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = SMA of True Range (Wilder's method uses EMA, but SMA is also common)
        # Using Wilder's smoothing for traditional ATR
        atr = true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        return atr
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        high, low, close = self._extract_ohlc(params.source)
        
        if len(close) < 2:
            return {
                "values": [None] * len(close),
                "current_value": None,
                "period": params.period
            }
        
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        close_s = pd.Series(close)
        
        atr_series = self._calculate_atr(high_s, low_s, close_s, params.period)
        
        # Convert to list, replacing NaN with None
        values = [None if pd.isna(v) else float(v) for v in atr_series]
        
        return {
            "values": values,
            "current_value": values[-1] if values else None,
            "period": params.period
        }
