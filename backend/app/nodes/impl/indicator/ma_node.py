"""
MANode - Moving Average Indicator

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


class MAInput(BaseModel):
    """Input schema for MANode."""
    source: Union[List[float], List[Dict[str, Any]]] = Field(
        description="Price data - either list of floats or list of OHLCV dicts"
    )
    period: int = Field(
        default=20,
        ge=1,
        le=500,
        description="MA period (window size)"
    )
    ma_type: str = Field(
        default="sma",
        description="MA type: 'sma' (simple), 'ema' (exponential), 'wma' (weighted)"
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
        description="Current bar index for event mode (returns single value)"
    )


class MAOutput(BaseModel):
    """Output schema for MANode."""
    values: List[Optional[float]] = Field(
        description="MA values for each data point (None for insufficient data)"
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current MA value (for event mode)"
    )
    period: int = Field(description="Period used")
    ma_type: str = Field(description="MA type used")


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.ma",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class MANode(BaseNode):
    """
    Moving Average Node - Calculates simple, exponential, or weighted moving averages.
    
    Supports dual execution modes:
    - Hybrid: Pre-calculates entire series (fast, for backtesting)
    - Event: Calculates single value at current_index (for real-time)
    """
    description = "Calculate Moving Average indicator"
    InputSchema = MAInput
    OutputSchema = MAOutput
    
    def _extract_prices(self, data: Union[List[float], List[Dict[str, Any]]], 
                        price_field: str) -> List[float]:
        """Extract price series from input data."""
        if not data:
            return []
        
        if isinstance(data[0], dict):
            return [d.get(price_field, d.get('close', 0)) for d in data]
        return list(data)
    
    def _calculate_sma(self, prices: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return prices.rolling(window=period, min_periods=period).mean()
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return prices.ewm(span=period, adjust=False, min_periods=period).mean()
    
    def _calculate_wma(self, prices: pd.Series, period: int) -> pd.Series:
        """Weighted Moving Average."""
        weights = np.arange(1, period + 1)
        return prices.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    
    def _calculate_single(self, prices: List[float], index: int, 
                          period: int, ma_type: str) -> Optional[float]:
        """Calculate MA for a single index (event mode)."""
        if index < period - 1:
            return None
        
        window = prices[index - period + 1:index + 1]
        
        if ma_type == "sma":
            return sum(window) / period
        elif ma_type == "ema":
            # For single-point EMA, we need all previous data
            series = pd.Series(prices[:index + 1])
            ema = series.ewm(span=period, adjust=False, min_periods=period).mean()
            return ema.iloc[-1] if not pd.isna(ema.iloc[-1]) else None
        elif ma_type == "wma":
            weights = list(range(1, period + 1))
            return sum(w * p for w, p in zip(weights, window)) / sum(weights)
        
        return None
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        prices = self._extract_prices(params.source, params.price_field)
        
        if not prices:
            return {
                "values": [],
                "current_value": None,
                "period": params.period,
                "ma_type": params.ma_type
            }
        
        # Event mode: calculate single value
        if params.mode == "event" and params.current_index is not None:
            current_value = self._calculate_single(
                prices, params.current_index, params.period, params.ma_type
            )
            return {
                "values": [],
                "current_value": current_value,
                "period": params.period,
                "ma_type": params.ma_type
            }
        
        # Hybrid mode: calculate entire series
        series = pd.Series(prices)
        
        if params.ma_type == "sma":
            ma_series = self._calculate_sma(series, params.period)
        elif params.ma_type == "ema":
            ma_series = self._calculate_ema(series, params.period)
        elif params.ma_type == "wma":
            ma_series = self._calculate_wma(series, params.period)
        else:
            ma_series = self._calculate_sma(series, params.period)
        
        # Convert to list, replacing NaN with None
        values = [None if pd.isna(v) else float(v) for v in ma_series]
        
        return {
            "values": values,
            "current_value": values[-1] if values else None,
            "period": params.period,
            "ma_type": params.ma_type
        }
