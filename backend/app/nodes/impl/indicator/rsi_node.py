"""
RSINode - Relative Strength Index Indicator

Supports:
- Hybrid Mode: Vectorized pre-calculation using pandas
- Pure Event Mode: Step-by-step calculation
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class RSIInput(BaseModel):
    """Input schema for RSINode."""
    source: Union[List[float], List[Dict[str, Any]]] = Field(
        description="Price data - either list of floats or list of OHLCV dicts"
    )
    period: int = Field(
        default=14,
        ge=2,
        le=100,
        description="RSI period"
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


class RSIOutput(BaseModel):
    """Output schema for RSINode."""
    values: List[Optional[float]] = Field(
        description="RSI values (0-100) for each data point"
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current RSI value"
    )
    result: List[Optional[float]] = Field(default=None, description="Alias for values (LLM convenience)")
    period: int = Field(description="Period used")


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.rsi",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class RSINode(BaseNode):
    """
    RSI Node - Calculates Relative Strength Index.
    
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss (over period)
    """
    description = "Calculate Relative Strength Index indicator"
    InputSchema = RSIInput
    OutputSchema = RSIOutput
    
    def _extract_prices(self, data: Union[List[float], List[Dict[str, Any]]], 
                        price_field: str) -> List[float]:
        """Extract price series from input data."""
        if not data:
            return []
        
        if isinstance(data[0], dict):
            return [d.get(price_field, d.get('close', 0)) for d in data]
        return list(data)
    
    def _calculate_rsi_vectorized(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using vectorized operations (Wilder's smoothing)."""
        delta = prices.diff()
        
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        
        # Wilder's smoothing (exponential-like)
        avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_single(self, prices: List[float], index: int, period: int) -> Optional[float]:
        """Calculate RSI for a single index (event mode)."""
        if index < period:
            return None
        
        # Calculate using all available data up to index
        window = prices[:index + 1]
        series = pd.Series(window)
        rsi_series = self._calculate_rsi_vectorized(series, period)
        
        return float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        prices = self._extract_prices(params.source, params.price_field)
        
        if len(prices) < 2:
            return {
                "values": [None] * len(prices),
                "current_value": None,
                "period": params.period
            }
        
        # Event mode: calculate single value
        if params.mode == "event" and params.current_index is not None:
            current_value = self._calculate_single(prices, params.current_index, params.period)
            return {
                "values": [],
                "current_value": current_value,
                "period": params.period
            }
        
        # Hybrid mode: calculate entire series
        series = pd.Series(prices)
        rsi_series = self._calculate_rsi_vectorized(series, params.period)
        
        # Convert to list, replacing NaN with None, clamp to 0-100
        values = []
        for v in rsi_series:
            if pd.isna(v):
                values.append(None)
            else:
                values.append(float(max(0, min(100, v))))
        
        return {
            "values": values,
            "result": values, # Alias for LLM compatibility
            "current_value": values[-1] if values else None,
            "period": params.period
        }
