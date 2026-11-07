"""
FetchCryptoNode - Fetch cryptocurrency OHLCV data via CCXT.

Supports 100+ exchanges via a unified interface.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import ccxt

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
from .base import BaseDataFetcher, OHLCV


class FetchCryptoInput(BaseModel):
    """Input schema for FetchCryptoNode."""
    exchange: str = Field(
        default="binance",
        description="Exchange ID (e.g., binance, okx, coinbase, bybit)"
    )
    symbol: str = Field(
        description="Trading pair symbol (e.g., BTC/USDT, ETH/USDT)"
    )
    timeframe: str = Field(
        default="1d",
        description="Candle timeframe (e.g., 1m, 1h, 1d)"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Number of candles to fetch (max 1000)"
    )
    since: Optional[int] = Field(
        default=None,
        description="Start timestamp in milliseconds (optional)"
    )


class FetchCryptoOutput(BaseModel):
    """Output schema for FetchCryptoNode."""
    data: List[OHLCV] = Field(description="List of OHLCV candles")
    symbol: str = Field(description="Symbol fetched")
    exchange: str = Field(description="Exchange used")
    count: int = Field(description="Number of candles returned")


@register_node(
    category=NodeCategory.DATA,
    name="data.fetch_crypto",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class FetchCryptoNode(BaseNode, BaseDataFetcher):
    """
    Fetch cryptocurrency OHLCV data from 100+ exchanges via CCXT.
    
    Supports: Binance, OKX, Bybit, Coinbase, Kraken, Huobi, etc.
    """
    description = "Fetch crypto OHLCV data from various exchanges"
    InputSchema = FetchCryptoInput
    OutputSchema = FetchCryptoOutput
    
    # Cache exchange instances for performance
    _exchange_cache: Dict[str, ccxt.Exchange] = {}
    
    def _get_exchange(self, exchange_id: str) -> ccxt.Exchange:
        """Get or create exchange instance."""
        if exchange_id not in self._exchange_cache:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                self._exchange_cache[exchange_id] = exchange_class({
                    'enableRateLimit': True,  # Important: Respect rate limits
                })
            except AttributeError:
                raise ValueError(f"Unknown exchange: {exchange_id}. Supported: {', '.join(ccxt.exchanges[:10])}...")
        return self._exchange_cache[exchange_id]
    
    def fetch_history(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100,
        start: Optional[int] = None,
        end: Optional[int] = None,
        exchange_id: str = "binance"
    ) -> List[OHLCV]:
        """
        Fetch historical OHLCV data from a crypto exchange.
        
        This method implements the BaseDataFetcher interface.
        """
        exchange = self._get_exchange(exchange_id)
        
        # Fetch OHLCV data
        # ccxt returns: [[timestamp, open, high, low, close, volume], ...]
        raw_data = exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=start,
            limit=limit
        )
        
        # Convert to OHLCV objects
        ohlcv_list = []
        for candle in raw_data:
            ohlcv_list.append(OHLCV(
                timestamp=candle[0],
                open=candle[1],
                high=candle[2],
                low=candle[3],
                close=candle[4],
                volume=candle[5] if len(candle) > 5 else 0.0
            ))
        
        return ohlcv_list

    def _generate_mock_data(self, symbol: str, limit: int) -> List[OHLCV]:
        """Generate mock data for testing/fallback."""
        import random
        from datetime import datetime, timedelta
        
        base_price = 50000.0 if "BTC" in symbol else 3000.0
        data = []
        now = datetime.utcnow()
        
        for i in range(limit):
            dt = now - timedelta(hours=limit-i)
            ts = int(dt.timestamp() * 1000)
            
            change = (random.random() - 0.5) * (base_price * 0.02)
            close = base_price + change
            open_p = close + (random.random() - 0.5) * (base_price * 0.005)
            high = max(open_p, close) + random.random() * (base_price * 0.005)
            low = min(open_p, close) - random.random() * (base_price * 0.005)
            vol = random.random() * 1000
            
            data.append(OHLCV(
                timestamp=ts, open=open_p, high=high, low=low, close=close, volume=vol
            ))
            base_price = close
            
        return data

    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node: Fetch crypto data."""
        params = self.validate_inputs(ctx.inputs)
        
        # Validate timeframe
        if not self.validate_timeframe(params.timeframe):
            return {
                "data": [],
                "symbol": params.symbol,
                "exchange": params.exchange,
                "count": 0,
                "error": f"Invalid timeframe: {params.timeframe}"
            }
        
        try:
            data = self.fetch_history(
                symbol=params.symbol,
                timeframe=params.timeframe,
                limit=params.limit,
                start=params.since,
                exchange_id=params.exchange
            )
            
            return {
                "data": [d.model_dump() for d in data],
                "symbol": params.symbol,
                "exchange": params.exchange,
                "count": len(data)
            }
        except Exception as e:
            # Fallback for testing/geo-block
            if "451" in str(e) or "Network Error" in str(e) or "Connection refused" in str(e):
                print(f"[WARN] FetchCryptoNode failed ({e}). Using Mock Data.")
                mock_data = self._generate_mock_data(params.symbol, params.limit)
                return {
                    "data": [d.model_dump() for d in mock_data],
                    "symbol": params.symbol,
                    "exchange": "mock",
                    "count": len(mock_data),
                    "note": "Mock Data (Fetch Failed)"
                }
                
            return {
                "data": [],
                "symbol": params.symbol,
                "exchange": params.exchange,
                "count": 0,
                "error": str(e)
            }
