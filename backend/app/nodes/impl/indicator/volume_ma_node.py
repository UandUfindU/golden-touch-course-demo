"""
VolumeMANode - Volume Moving Average Indicator

Calculates moving average of trading volume for volume analysis.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import pandas as pd

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class VolumeMAInput(BaseModel):
    """Input schema for VolumeMANode."""
    source: Union[List[Dict[str, Any]], List[float]] = Field(
        description="OHLCV data (must have volume field) or list of volume values"
    )
    period: int = Field(
        default=20,
        ge=1,
        le=200,
        description="MA period for volume (default: 20)"
    )
    ma_type: str = Field(
        default="sma",
        description="MA type: 'sma' (simple), 'ema' (exponential)"
    )
    volume_field: str = Field(
        default="volume",
        description="Field name for volume in OHLCV data"
    )


class VolumeMAOutput(BaseModel):
    """Output schema for VolumeMANode."""
    values: List[Optional[float]] = Field(
        description="Volume MA values for each data point"
    )
    current_value: Optional[float] = Field(
        default=None,
        description="Current Volume MA value"
    )
    current_volume: Optional[float] = Field(
        default=None,
        description="Current raw volume"
    )
    volume_ratio: Optional[float] = Field(
        default=None,
        description="Current volume / Volume MA ratio"
    )


@register_node(
    category=NodeCategory.LOGIC,
    name="indicator.volume_ma",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class VolumeMANode(BaseNode):
    """
    Volume MA Node - Volume Moving Average.
    
    Calculates moving average of trading volume to identify:
    - High volume breakouts (volume > MA)
    - Low volume consolidation (volume < MA)
    - Volume confirmation of price moves
    
    Output includes volume_ratio:
    - ratio > 1.5: High volume (strong move confirmation)
    - ratio < 0.5: Low volume (weak move, possible reversal)
    
    示例 (For LLM):
    ```python
    # 放量突破策略
    data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")
    vol_ma = indicator.volume_ma(source=data, period=20)
    ma_fast = indicator.ma(source=data, period=10)
    ma_slow = indicator.ma(source=data, period=20)
    cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)
    
    # 只在放量时买入 (成交量 > 均量1.5倍)
    if cross == 1:
        signal.buy(condition=vol_ma.volume_ratio > 1.5, quantity=1.0, reason="放量金叉")
    if cross == -1:
        signal.sell(quantity=1.0, reason="死叉卖出")
    ```
    
    单独使用成交量分析:
    ```python
    data = data.fetch_crypto(symbol="ETH/USDT", timeframe="1h")
    vol_ma = indicator.volume_ma(source=data, period=20)
    
    # 成交量异常放大 (超过均量2倍)
    signal.buy(condition=vol_ma.volume_ratio > 2.0, quantity=0.5, reason="成交量异常")
    ```
    """
    description = "成交量均线 (含volume_ratio放量/缩量比)"
    InputSchema = VolumeMAInput
    OutputSchema = VolumeMAOutput
    
    def _extract_volume(self, data: Union[List[Dict[str, Any]], List[float]], 
                        volume_field: str) -> List[float]:
        """Extract volume series from input data."""
        if not data:
            return []
        
        if isinstance(data[0], dict):
            return [d.get(volume_field, d.get('volume', 0)) for d in data]
        return list(data)
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node."""
        params = self.validate_inputs(ctx.inputs)
        
        volumes = self._extract_volume(params.source, params.volume_field)
        
        if not volumes:
            return {
                "values": [],
                "current_value": None,
                "current_volume": None,
                "volume_ratio": None
            }
        
        series = pd.Series(volumes)
        
        if params.ma_type == "ema":
            ma_series = series.ewm(span=params.period, adjust=False, min_periods=params.period).mean()
        else:
            ma_series = series.rolling(window=params.period, min_periods=params.period).mean()
        
        # Convert to list, replacing NaN with None
        values = [None if pd.isna(v) else float(v) for v in ma_series]
        
        current_vol = volumes[-1] if volumes else None
        current_ma = values[-1] if values else None
        
        # Calculate volume ratio
        vol_ratio = None
        if current_vol is not None and current_ma is not None and current_ma > 0:
            vol_ratio = float(current_vol / current_ma)
        
        return {
            "values": values,
            "current_value": current_ma,
            "current_volume": current_vol,
            "volume_ratio": vol_ratio
        }
