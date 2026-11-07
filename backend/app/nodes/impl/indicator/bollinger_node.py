"""
BollingerBandsNode - Bollinger Bands Indicator

Supports:
- Hybrid Mode: Vectorized using pandas
- Event Mode: Step-by-step
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope

class BBInput(BaseModel):
    source: Union[List[float], List[Dict[str, Any]]] = Field(description="Price data")
    period: int = Field(default=20, ge=2, description="MA period")
    std_dev: float = Field(default=2.0, ge=0.1, description="Standard Deviations")
    price_field: str = Field(default="close", description="Field to use if dict input")
    mode: str = Field(default="hybrid", description="'hybrid' or 'event'")
    current_index: Optional[int] = Field(default=None, description="Current index for event mode")

class BBOutput(BaseModel):
    upper: List[Optional[float]] = Field(description="Upper Band")
    middle: List[Optional[float]] = Field(description="Middle Band (MA)")
    lower: List[Optional[float]] = Field(description="Lower Band")
    current_upper: Optional[float] = Field(default=None)
    current_middle: Optional[float] = Field(default=None)
    current_lower: Optional[float] = Field(default=None)

@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.bollinger_bands", # Standard name
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class BollingerBandsNode(BaseNode):
    """
    Bollinger Bands Node.
    Returns Upper, Middle, and Lower bands.
    """
    description = "Calculate Bollinger Bands (Upper, Middle, Lower)"
    InputSchema = BBInput
    OutputSchema = BBOutput

    def _extract_prices(self, data: Union[List[float], List[Dict[str, Any]]], price_field: str) -> List[float]:
        if not data: return []
        if isinstance(data[0], dict):
            return [d.get(price_field, d.get('close', 0)) for d in data]
        return list(data)

    def _calculate_vectorized(self, prices: List[float], period: int, std_dev: float) -> Dict[str, pd.Series]:
        series = pd.Series(prices)
        middle = series.rolling(window=period, min_periods=period).mean()
        std = series.rolling(window=period, min_periods=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return {"upper": upper, "middle": middle, "lower": lower}

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        prices = self._extract_prices(params.source, params.price_field)
        
        if not prices:
             return {k: [] for k in ["upper", "middle", "lower"]} | {k: None for k in ["current_upper", "current_middle", "current_lower"]}

        # Hybrid Logic (simplification: always calc full series for checking)
        # Optimization: for Event mode, strict window calculation
        results = self._calculate_vectorized(prices, params.period, params.std_dev)
        
        def to_list(series):
            return [None if pd.isna(v) else float(v) for v in series]

        upper_list = to_list(results["upper"])
        middle_list = to_list(results["middle"])
        lower_list = to_list(results["lower"])

        curr_u, curr_m, curr_l = None, None, None
        if params.mode == "event" and params.current_index is not None:
             idx = params.current_index
             if idx < len(upper_list):
                 curr_u = upper_list[idx]
                 curr_m = middle_list[idx]
                 curr_l = lower_list[idx]
        else:
             if upper_list:
                 curr_u = upper_list[-1]
                 curr_m = middle_list[-1]
                 curr_l = lower_list[-1]

        return {
            "upper": upper_list,
            "middle": middle_list,
            "lower": lower_list,
            "current_upper": curr_u,
            "current_middle": curr_m,
            "current_lower": curr_l
        }
