"""
FetchStockNode - Fetch stock OHLCV data via AkShare (primary) and YFinance (fallback).

Supports A股 (via AkShare) and US Stocks (via AkShare with YFinance fallback).
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import time

from app.core.config import settings
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
from .base import BaseDataFetcher, OHLCV


class FetchStockInput(BaseModel):
    """Input schema for FetchStockNode."""
    market: str = Field(
        default="us",
        description="Market type: 'us' for US stocks, 'cn' for A-shares"
    )
    symbol: str = Field(
        description="Stock symbol (e.g., AAPL for US, 000001 for A-shares)"
    )
    timeframe: str = Field(
        default="1d",
        description="Candle timeframe (1d, 1wk, 1mo for US; daily/weekly for CN)"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=2000,
        description="Number of candles to fetch (max 2000)"
    )
    adjust: str = Field(
        default="qfq",
        description="Adjustment type for A-shares: qfq (forward), hfq (backward), or empty"
    )


class FetchStockOutput(BaseModel):
    """Output schema for FetchStockNode."""
    data: List[OHLCV] = Field(description="List of OHLCV candles")
    symbol: str = Field(description="Symbol fetched")
    market: str = Field(description="Market type (us/cn)")
    count: int = Field(description="Number of candles returned")


@register_node(
    category=NodeCategory.DATA,
    name="data.fetch_stock",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class FetchStockNode(BaseNode, BaseDataFetcher):
    """
    Fetch stock OHLCV data from various markets.
    
    - US Stocks: AkShare (东财) as primary, YFinance as fallback
    - A-Shares (China): AkShare (free, no API key required)
    """
    description = "Fetch stock OHLCV data from US or China markets"
    InputSchema = FetchStockInput
    OutputSchema = FetchStockOutput
    
    # Common US stock -> Exchange mapping (NASDAQ=105, NYSE=106, AMEX=107)
    _EXCHANGE_MAP = {
        # NASDAQ tech giants
        'AAPL': '105', 'MSFT': '105', 'AMZN': '105', 'GOOGL': '105', 'GOOG': '105',
        'META': '105', 'NVDA': '105', 'TSLA': '105', 'NFLX': '105', 'AMD': '105',
        'INTC': '105', 'QCOM': '105', 'AVGO': '105', 'TXN': '105', 'CSCO': '105',
        # NYSE blue chips
        'JPM': '106', 'V': '106', 'JNJ': '106', 'WMT': '106', 'PG': '106',
        'UNH': '106', 'HD': '106', 'BAC': '106', 'XOM': '106', 'CVX': '106',
        'KO': '106', 'PEP': '106', 'DIS': '106', 'VZ': '106', 'T': '106',
        'USAU': '107',  # AMEX for gold stocks
    }
    
    # Cache for US symbol codes
    _us_symbol_cache: Dict[str, str] = {}
    
    def _get_us_symbol_code(self, symbol: str) -> str:
        """
        获取美股的东财代码格式 (如 105.TSLA, 106.AAPL)
        105 = NASDAQ, 106 = NYSE, 107 = AMEX
        使用静态映射，避免网络请求验证
        """
        symbol_upper = symbol.upper()
        
        # Check cache first
        if symbol_upper in self._us_symbol_cache:
            return self._us_symbol_cache[symbol_upper]
        
        # Use static mapping, default to NASDAQ (105)
        exchange = self._EXCHANGE_MAP.get(symbol_upper, '105')
        full_symbol = f"{exchange}.{symbol_upper}"
        
        self._us_symbol_cache[symbol_upper] = full_symbol
        return full_symbol
    
    def _fetch_us_stock_ak(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> List[OHLCV]:
        """Fetch US stock data via AkShare (东财)."""
        import akshare as ak
        
        # Get EastMoney format symbol code
        full_symbol = self._get_us_symbol_code(symbol)
        
        # Map timeframe to period
        period_map = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}
        period = period_map.get(timeframe, "daily")
        
        # Retry logic for network instability
        df = None
        last_error = None
        for attempt in range(3):
            try:
                print(f"  [AkShare] Attempt {attempt+1}/3 fetching {full_symbol}...")
                df = ak.stock_us_hist(
                    symbol=full_symbol,
                    period=period,
                    start_date=(datetime.now() - timedelta(days=limit * 3)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                    adjust=""
                )
                if df is not None and not df.empty:
                    print(f"  [AkShare] Success! Got {len(df)} rows.")
                    break
            except Exception as e:
                last_error = e
                print(f"  [AkShare] Attempt {attempt+1} failed: {str(e)[:80]}")
                time.sleep(1 * (attempt + 1))
        
        if df is None or df.empty:
            error_msg = f"AkShare returned no data for US symbol: {symbol}"
            if last_error:
                error_msg += f" ({last_error})"
            raise ValueError(error_msg)
        
        df = df.tail(limit)
        
        ohlcv_list = []
        for _, row in df.iterrows():
            try:
                # stock_us_hist returns Chinese column names
                date_str = str(row['日期'])
                if ' ' in date_str:
                    date_str = date_str.split(' ')[0]
                ts = datetime.strptime(date_str, "%Y-%m-%d")
                
                ohlcv_list.append(OHLCV(
                    timestamp=int(ts.timestamp() * 1000),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=float(row['成交量'])
                ))
            except Exception:
                continue
                
        return ohlcv_list
    
    def _fetch_us_stock_yf(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> List[OHLCV]:
        """Fetch US stock data via YFinance (fallback, single attempt)."""
        import yfinance as yf
        
        print(f"  [YFinance] Fallback attempt for {symbol}...")
        
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "1d": "1d", "1wk": "1wk", "1mo": "1mo"
        }
        interval = interval_map.get(timeframe, "1d")
        
        period_map = {
            "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
            "1h": "730d", "1d": "max", "1wk": "max", "1mo": "max"
        }
        period = period_map.get(timeframe, "1y")
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df is None or df.empty:
                raise ValueError(f"YFinance returned no data for symbol '{symbol}'")
            
            print(f"  [YFinance] Success! Got {len(df)} rows.")
            
        except Exception as e:
            print(f"  [YFinance] Failed: {str(e)[:80]}")
            raise ValueError(f"YFinance fetch failed for '{symbol}': {str(e)}")
        
        df = df.tail(limit)
        
        ohlcv_list = []
        for idx, row in df.iterrows():
            ohlcv_list.append(OHLCV(
                timestamp=int(idx.timestamp() * 1000),
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                volume=row['Volume']
            ))
        
        return ohlcv_list
    
    def _fetch_us_stock(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> List[OHLCV]:
        """
        Fetch US stock data.
        Primary: AkShare (3 retries) -> Fallback: YFinance (1 retry)
        Total: 4 attempts max
        """
        if settings.US_STOCK_DATA_PROVIDER == "yfinance":
            return self._fetch_us_stock_yf(symbol, timeframe, limit)

        ak_error = None
        
        # Try AkShare first (3 attempts)
        print(f"  [Data] Fetching US stock {symbol} (AkShare primary, YFinance fallback)")
        try:
            return self._fetch_us_stock_ak(symbol, timeframe, limit)
        except Exception as e:
            ak_error = str(e)[:100]
            print(f"  [Data] AkShare failed after 3 attempts, trying YFinance...")
        
        # Fallback to YFinance (1 attempt)
        try:
            return self._fetch_us_stock_yf(symbol, timeframe, limit)
        except Exception as yf_error:
            error_msg = (
                f"Data fetch failed for '{symbol}' after 4 attempts. "
                f"Network or proxy issue likely. "
                f"AkShare: {ak_error}, YFinance: {str(yf_error)[:100]}"
            )
            print(f"  [Data] {error_msg}")
            raise ValueError(error_msg)
    
    def _fetch_cn_stock(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        adjust: str
    ) -> List[OHLCV]:
        """Fetch A-share stock data via AkShare."""
        import akshare as ak
        
        period_map = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}
        period = period_map.get(timeframe, "daily")
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                adjust=adjust,
                start_date=(datetime.now() - timedelta(days=limit * 2)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d")
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch A-share data for {symbol}: {e}")
        
        df = df.tail(limit)
        
        ohlcv_list = []
        for _, row in df.iterrows():
            try:
                # AkShare A-share columns: 日期, 开盘, 收盘, 最高, 最低, 成交量
                ts = datetime.strptime(str(row['日期']), "%Y-%m-%d")
                ohlcv_list.append(OHLCV(
                    timestamp=int(ts.timestamp() * 1000),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=float(row['成交量'])
                ))
            except (KeyError, ValueError):
                # Try English column names as fallback
                ts = datetime.strptime(str(row.get('date', row.name)), "%Y-%m-%d")
                ohlcv_list.append(OHLCV(
                    timestamp=int(ts.timestamp() * 1000),
                    open=float(row.get('open', row.get('Open', 0))),
                    high=float(row.get('high', row.get('High', 0))),
                    low=float(row.get('low', row.get('Low', 0))),
                    close=float(row.get('close', row.get('Close', 0))),
                    volume=float(row.get('volume', row.get('Volume', 0)))
                ))
        
        return ohlcv_list
    
    def fetch_history(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100,
        start: Optional[int] = None,
        end: Optional[int] = None,
        market: str = "us",
        adjust: str = "qfq"
    ) -> List[OHLCV]:
        """Fetch historical OHLCV data from stock markets."""
        if market == "us":
            return self._fetch_us_stock(symbol, timeframe, limit)
        elif market == "cn":
            return self._fetch_cn_stock(symbol, timeframe, limit, adjust)
        else:
            raise ValueError(f"Unknown market: {market}. Supported: us, cn")
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node: Fetch stock data."""
        params = self.validate_inputs(ctx.inputs)
        
        try:
            data = self.fetch_history(
                symbol=params.symbol,
                timeframe=params.timeframe,
                limit=params.limit,
                market=params.market,
                adjust=params.adjust
            )
            
            return {
                "data": [d.model_dump() for d in data],
                "symbol": params.symbol,
                "market": params.market,
                "count": len(data)
            }
        except Exception as e:
            return {
                "data": [],
                "symbol": params.symbol,
                "market": params.market,
                "count": 0,
                "error": str(e)
            }
