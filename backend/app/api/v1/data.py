"""
Data API - K-line and market data endpoints.

Provides cached access to stock and crypto OHLCV data.
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.services.kline_cache import get_kline_cache
from app.nodes.base import Context

router = APIRouter(prefix="/data", tags=["Data"])


@router.get("/kline")
async def get_kline(
    type: str = Query(..., description="Data type: 'stock' or 'crypto'"),
    symbol: str = Query(..., description="Symbol (e.g., TSLA, BTC/USDT)"),
    market: Optional[str] = Query(None, description="Stock market: 'us' or 'cn'"),
    exchange: Optional[str] = Query(None, description="Crypto exchange (e.g., binance)"),
    timeframe: str = Query("1d", description="K-line timeframe (1d, 1h, etc.)"),
    limit: int = Query(100, ge=1, le=2000, description="Number of candles"),
    after: Optional[int] = Query(None, description="Return data after this timestamp (ms)")
):
    """
    Get K-line (OHLCV) data with caching.
    
    - **type**: 'stock' for stocks, 'crypto' for cryptocurrencies
    - **symbol**: Stock symbol (TSLA) or trading pair (BTC/USDT)
    - **market**: For stocks - 'us' (default) or 'cn'
    - **exchange**: For crypto - exchange name (default: binance)
    - **timeframe**: Candle period (1m, 5m, 15m, 1h, 4h, 1d, 1wk, 1mo)
    - **limit**: Number of candles (max 2000)
    - **after**: Incremental query - only return data after this timestamp
    """
    cache = get_kline_cache()
    
    # Validate type
    if type not in ["stock", "crypto"]:
        raise HTTPException(status_code=400, detail="type must be 'stock' or 'crypto'")
    
    # Set defaults
    if type == "stock" and not market:
        market = "us"
    if type == "crypto" and not exchange:
        exchange = "binance"
    
    # Check cache first
    cached = cache.get(
        data_type=type,
        symbol=symbol,
        timeframe=timeframe,
        market=market,
        exchange=exchange,
        after=after
    )
    
    # If cache hit and not expired (and has enough data), return it
    if cached and not cached["expired"] and len(cached["data"]) >= limit:
        return {
            "success": True,
            "type": type,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(cached["data"][-limit:]),
            "cached": True,
            "data": cached["data"][-limit:]
        }
    
    # Cache miss or expired - fetch fresh data
    try:
        if type == "stock":
            data = await _fetch_stock_data(symbol, market, timeframe, limit)
        else:
            data = await _fetch_crypto_data(symbol, exchange, timeframe, limit)
        
        # Update cache
        if data:
            cache.update(
                data_type=type,
                symbol=symbol,
                timeframe=timeframe,
                new_data=data,
                market=market,
                exchange=exchange
            )
        
        return {
            "success": True,
            "type": type,
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(data),
            "cached": False,
            "data": data
        }
        
    except Exception as e:
        # If fetch fails but we have stale cache, return it
        if cached and cached["data"]:
            return {
                "success": True,
                "type": type,
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(cached["data"][-limit:]),
                "cached": True,
                "stale": True,
                "data": cached["data"][-limit:],
                "warning": f"Using stale cache: {str(e)[:100]}"
            }
        
        raise HTTPException(status_code=500, detail=f"Data fetch failed: {str(e)}")


async def _fetch_stock_data(symbol: str, market: str, timeframe: str, limit: int):
    """Fetch stock data using FetchStockNode."""
    import asyncio
    from app.nodes.impl.data.fetch_stock import FetchStockNode
    
    node = FetchStockNode()
    ctx = Context(
        run_id="api_kline",
        workflow_id="data_api",
        node_id="fetch_stock",
        inputs={
            "symbol": symbol,
            "market": market,
            "timeframe": timeframe,
            "limit": limit
        }
    )
    
    # Run in executor to avoid blocking
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, node.run, ctx)
    
    if result.get("error"):
        raise ValueError(result["error"])
    
    return result.get("data", [])


async def _fetch_crypto_data(symbol: str, exchange: str, timeframe: str, limit: int):
    """Fetch crypto data using FetchCryptoNode."""
    import asyncio
    from app.nodes.impl.data.fetch_crypto import FetchCryptoNode
    
    node = FetchCryptoNode()
    ctx = Context(
        run_id="api_kline",
        workflow_id="data_api",
        node_id="fetch_crypto",
        inputs={
            "symbol": symbol,
            "exchange": exchange,
            "timeframe": timeframe,
            "limit": limit
        }
    )
    
    # Run in executor to avoid blocking
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, node.run, ctx)
    
    if result.get("error"):
        raise ValueError(result["error"])
    
    return result.get("data", [])


@router.get("/kline/stats")
async def get_cache_stats():
    """Get K-line cache statistics."""
    cache = get_kline_cache()
    return cache.get_stats()


@router.delete("/kline/cache")
async def clear_cache(cache_key: Optional[str] = None):
    """Clear K-line cache."""
    cache = get_kline_cache()
    cache.clear(cache_key)
    return {"success": True, "message": "Cache cleared"}
