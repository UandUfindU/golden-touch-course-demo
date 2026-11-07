"""
MACDNode - Moving Average Convergence Divergence Indicator

A trend-following momentum indicator that shows the relationship between two EMAs.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class MACDInput(BaseModel):
    """Input schema for MACDNode."""
    source: Union[List[float], List[Dict[str, Any]]] = Field(
        description="Price data - either list of floats or list of OHLCV dicts"
    )
    fast_period: int = Field(
        default=12,
        ge=2,
        le=100,
        description="Fast EMA period (default: 12)"
    )
    slow_period: int = Field(
        default=26,
        ge=5,
        le=200,
        description="Slow EMA period (default: 26)"
    )
    signal_period: int = Field(
        default=9,
        ge=2,
        le=50,
        description="Signal line EMA period (default: 9)"
    )
    price_field: str = Field(
        default="close",
        description="Price field to use if data is OHLCV dicts"
    )
    mode: str = Field(
        default="hybrid",
        description="Calculation mode: 'hybrid' (vectorized) or 'event' (step-by-step)"
    )
    current_index: Optional[int] = Field(
        default=None,
        description="Current bar index for event mode"
    )


class MACDOutput(BaseModel):
    """Output schema for MACDNode."""
    macd_line: List[Optional[float]] = Field(
        description="MACD Line (Fast EMA - Slow EMA)"
    )
    signal_line: List[Optional[float]] = Field(
        description="Signal Line (EMA of MACD Line)"
    )
    histogram: List[Optional[float]] = Field(
        description="Histogram (MACD Line - Signal Line)"
    )
    current_macd: Optional[float] = Field(
        default=None,
        description="Current MACD value"
    )
    current_signal: Optional[float] = Field(
        default=None,
        description="Current Signal value"
    )
    current_histogram: Optional[float] = Field(
        default=None,
        description="Current Histogram value"
    )


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.macd",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class MACDNode(BaseNode):
    """
    MACD Node - Moving Average Convergence Divergence.
    
    Calculates:
    - MACD Line = Fast EMA (12) - Slow EMA (26)
    - Signal Line = 9-period EMA of MACD Line
    - Histogram = MACD Line - Signal Line
    
    Trading signals:
    - Bullish: MACD crosses above Signal Line (histogram turns positive)
    - Bearish: MACD crosses below Signal Line (histogram turns negative)
    
    示例 (For LLM):
    ```python
    # MACD 策略
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    macd_result = indicator.macd(source=data, fast_period=12, slow_period=26, signal_period=9)
    
    # 检测 MACD 金叉/死叉 (使用 histogram)
    cross = indicator.crossover(fast_line=macd_result.macd_line, slow_line=macd_result.signal_line)
    
    if cross == 1:
        signal.buy(quantity=1.0, reason="MACD金叉")
    if cross == -1:
        signal.sell(quantity=1.0, reason="MACD死叉")
    ```
    
    或者直接使用 histogram:
    ```python
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="4h")
    macd = indicator.macd(source=data)
    
    # histogram > 0 表示 MACD 在 Signal 上方
    signal.buy(condition=macd.histogram > 0, quantity=1.0, reason="MACD多头")
    signal.sell(condition=macd.histogram < 0, quantity=1.0, reason="MACD空头")
    ```
    """
    description = "MACD指标 (macd_line, signal_line, histogram)"
    InputSchema = MACDInput
    OutputSchema = MACDOutput
    
    def _extract_prices(self, data: Union[List[float], List[Dict[str, Any]]], 
                        price_field: str) -> List[float]:
        """Extract price series from input data."""
        if not data:
            return []
        
        if isinstance(data[0], dict):
            return [d.get(price_field, d.get('close', 0)) for d in data]
        return list(data)
    
    def _calculate_macd(self, prices: pd.Series, fast: int, slow: int, signal: int) -> Dict[str, pd.Series]:
        """Calculate MACD components using vectorized operations."""
        # EMA calculations
        ema_fast = prices.ewm(span=fast, adjust=False, min_periods=fast).mean()
        ema_slow = prices.ewm(span=slow, adjust=False, min_periods=slow).mean()
        
        # MACD Line
        macd_line = ema_fast - ema_slow
        
        # Signal Line
        signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram
        }
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        prices = self._extract_prices(params.source, params.price_field)
        
        if len(prices) < params.slow_period:
            return {
                "macd_line": [None] * len(prices),
                "signal_line": [None] * len(prices),
                "histogram": [None] * len(prices),
                "current_macd": None,
                "current_signal": None,
                "current_histogram": None
            }
        
        series = pd.Series(prices)
        result = self._calculate_macd(series, params.fast_period, params.slow_period, params.signal_period)
        
        # Convert to lists, replacing NaN with None
        def to_list(s):
            return [None if pd.isna(v) else float(v) for v in s]
        
        macd_list = to_list(result["macd_line"])
        signal_list = to_list(result["signal_line"])
        hist_list = to_list(result["histogram"])
        
        return {
            "macd_line": macd_list,
            "signal_line": signal_list,
            "histogram": hist_list,
            "current_macd": macd_list[-1] if macd_list else None,
            "current_signal": signal_list[-1] if signal_list else None,
            "current_histogram": hist_list[-1] if hist_list else None
        }
