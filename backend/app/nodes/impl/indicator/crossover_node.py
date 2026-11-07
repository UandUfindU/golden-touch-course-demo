"""
CrossOverNode - Signal generation for line crossovers.

Detects:
- fast > slow (Bullish/Golden Cross)
- fast < slow (Bearish/Death Cross)

Supports:
- Hybrid Mode: Vectorized using pandas shift comparison
- Pure Event Mode: Stateful comparison of current vs prev values
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class CrossOverInput(BaseModel):
    """Input schema for CrossOverNode."""
    fast_line: Optional[Union[List[float], List[Optional[float]], List[Dict[str, Any]], str]] = Field(
        default=None,
        description="Fast line values or column name in context"
    )
    slow_line: Optional[Union[List[float], List[Optional[float]], List[Dict[str, Any]], str]] = Field(
        default=None,
        description="Slow line values or column name in context"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context containing line data (if input is str column name)"
    )
    mode: str = Field(
        default="hybrid",
        description="Calculation mode: 'hybrid' (vectorized) or 'event' (step-by-step)"
    )
    current_index: Optional[int] = Field(
        default=None,
        description="Current index for event mode"
    )


class CrossOverOutput(BaseModel):
    """Output schema for CrossOverNode."""
    crossover: List[int] = Field(
        description="1 (Gold Cross), -1 (Death Cross), 0 (None) for each point"
    )
    current_signal: int = Field(
        default=0,
        description="Signal at current index: 1, -1, or 0"
    )


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.crossover",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class CrossOverNode(BaseNode):
    """
    CrossOver Node - Detects when two series cross.
    
    Output:
    - 1: Fast line crosses above Slow line (Golden Cross)
    - -1: Fast line crosses below Slow line (Death Cross)
    - 0: No cross
    """
    description = "Detect crossover signals between two lines"
    InputSchema = CrossOverInput
    OutputSchema = CrossOverOutput
    
    def _get_series(self, source: Union[List[float], List[Dict[str, Any]], str], context: Dict[str, Any]) -> List[float]:
        """Extract series from direct list or context."""
        if isinstance(source, str):
            return context.get(source, [])
        if not source:
            return []
        
        # Handle List[Dict] (e.g. OHLCV)
        if isinstance(source[0], dict):
             # Default to 'close' price
            return [d.get('close', d.get('value', 0)) for d in source]
            
        return source
    
    def _calculate_hybrid(self, fast: List[float], slow: List[float]) -> List[int]:
        """Vectorized crossover detection."""
        if len(fast) != len(slow) or len(fast) < 2:
            return [0] * len(fast)
        
        # Convert None to NaN for pandas handling
        f = pd.Series([np.nan if x is None else float(x) for x in fast])
        s = pd.Series([np.nan if x is None else float(x) for x in slow])
        
        # Logic:
        # CrossUp: (Fast[t] > Slow[t]) AND (Fast[t-1] <= Slow[t-1])
        # CrossDown: (Fast[t] < Slow[t]) AND (Fast[t-1] >= Slow[t-1])
        
        prev_f = f.shift(1)
        prev_s = s.shift(1)
        
        # Conditions
        bullish = (f > s) & (prev_f <= prev_s)
        bearish = (f < s) & (prev_f >= prev_s)
        
        # Map to 1, -1, 0
        signals = pd.Series(0, index=f.index)
        signals[bullish] = 1
        signals[bearish] = -1
        
        return signals.tolist()
    
    def _calculate_event(self, fast: List[float], slow: List[float], idx: int) -> int:
        """Single point crossover detection."""
        if idx < 1:
            return 0
        
        curr_f, curr_s = fast[idx], slow[idx]
        prev_f, prev_s = fast[idx-1], slow[idx-1]
        
        if any(x is None for x in [curr_f, curr_s, prev_f, prev_s]):
            return 0
            
        # Golden Cross
        if curr_f > curr_s and prev_f <= prev_s:
            return 1
        # Death Cross
        elif curr_f < curr_s and prev_f >= prev_s:
            return -1
            
        return 0
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute node."""
        params = self.validate_inputs(ctx.inputs)
        
        fast = self._get_series(params.fast_line, params.context)
        slow = self._get_series(params.slow_line, params.context)
        
        if not fast or not slow:
            return {"crossover": [], "current_signal": 0}
        
        if params.mode == "event" and params.current_index is not None:
            signal = self._calculate_event(fast, slow, params.current_index)
            return {
                "crossover": [],
                "current_signal": signal
            }
        
        # Hybrid mode
        signals = self._calculate_hybrid(fast, slow)
        return {
            "crossover": signals,
            "current_signal": signals[-1] if signals else 0
        }
