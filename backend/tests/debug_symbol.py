import sys
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

# ==========================================
# 1. 模拟环境 (Mock Context & Base Classes)
# ==========================================
class NodeCategory:
    DATA = "DATA"

class NodeScope:
    STRATEGY = "STRATEGY"
    TOOL = "TOOL"

class Context:
    def __init__(self, inputs: Dict[str, Any]):
        self.inputs = inputs

class OHLCV(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class BaseNode:
    InputSchema = None
    OutputSchema = None
    
    def validate_inputs(self, inputs: Dict[str, Any]):
        if self.InputSchema:
            return self.InputSchema(**inputs)
        return inputs

class BaseDataFetcher:
    pass

def register_node(category, name, scopes):
    def decorator(cls):
        return cls
    return decorator

# ==========================================
# 2. 您的核心代码 (FetchStockNode)
# ==========================================

class FetchStockInput(BaseModel):
    """Input schema for FetchStockNode."""
    market: str = Field(
        default="us",
        description="Market type: 'us' (YFinance), 'cn' (AkShare), 'us_ak' (US via AkShare)"
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
        le=500,
        description="Number of candles to fetch"
    )
    adjust: str = Field(
        default="qfq",
        description="Adjustment type for A-shares: qfq (forward), hfq (backward), or empty"
    )


class FetchStockOutput(BaseModel):
    """Output schema for FetchStockNode."""
    data: List[OHLCV] = Field(description="List of OHLCV candles")
    symbol: str = Field(description="Symbol fetched")
    market: str = Field(description="Market type (us/cn/us_ak)")
    count: int = Field(description="Number of candles returned")


@register_node(
    category=NodeCategory.DATA,
    name="data.fetch_stock",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class FetchStockNode(BaseNode, BaseDataFetcher):
    """
    Fetch stock OHLCV data from various markets.
    """
    description = "Fetch stock OHLCV data from US or China markets"
    InputSchema = FetchStockInput
    OutputSchema = FetchStockOutput
    
    # -------------------------------------------------------
    # 原有逻辑：YFinance (US)
    # -------------------------------------------------------
    def _fetch_us_stock(self, symbol: str, timeframe: str, limit: int) -> List[OHLCV]:
        """Fetch US stock data via YFinance."""
        import yfinance as yf
        
        print(f"DEBUG: yfinance version: {yf.__version__}")

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
            
            df = None
            last_error = None
            for attempt in range(3):
                try:
                    print(f"DEBUG: Attempt {attempt+1} fetching {symbol} via YFinance...")
                    df = ticker.history(period=period, interval=interval)
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    last_error = e
                    import time
                    print(f"DEBUG: Error on attempt {attempt+1}: {e}")
                    time.sleep(0.5 * (attempt + 1))
            
            if df is None or df.empty:
                error_msg = f"YFinance returned no data for symbol '{symbol}' after 3 retries."
                if last_error:
                    error_msg += f" Last error: {last_error}"
                raise ValueError(error_msg)
            
        except ValueError:
            raise
        except Exception as e:
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
    
    # -------------------------------------------------------
    # 新增逻辑：AkShare (US Stock)
    # -------------------------------------------------------
    def _get_us_symbol_code(self, symbol: str) -> str:
        """
        获取美股的东财代码格式 (如 105.TSLA, 106.AAPL)
        通过 stock_us_spot_em 获取实时行情表，查找对应的代码
        """
        import akshare as ak
        
        # 直接尝试常见的交易所前缀
        # 105 = NASDAQ, 106 = NYSE, 107 = AMEX
        prefixes = ["105", "106", "107"]
        
        for prefix in prefixes:
            full_symbol = f"{prefix}.{symbol.upper()}"
            try:
                # 尝试用这个代码获取数据，如果成功就返回
                df = ak.stock_us_hist(
                    symbol=full_symbol, 
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=10)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                    adjust=""
                )
                if df is not None and not df.empty:
                    print(f"DEBUG: Found valid symbol code: {full_symbol}")
                    return full_symbol
            except:
                continue
        
        # 如果都失败了，尝试从实时行情表中查找
        try:
            spot_df = ak.stock_us_spot_em()
            # 在代码列中查找匹配的symbol
            matched = spot_df[spot_df['代码'].str.endswith(f'.{symbol.upper()}')]
            if not matched.empty:
                return matched.iloc[0]['代码']
        except Exception as e:
            print(f"WARN: Failed to lookup symbol from spot data: {e}")
        
        # 默认返回 NASDAQ 前缀
        return f"105.{symbol.upper()}"
    
    def _fetch_us_stock_ak(self, symbol: str, limit: int) -> List[OHLCV]:
        """Fetch US stock data via AkShare (东方财富)."""
        import akshare as ak
        
        print(f"DEBUG: Fetching US Stock '{symbol}' via AkShare (东财)...")
        
        try:
            # 获取东财格式的股票代码
            full_symbol = self._get_us_symbol_code(symbol)
            print(f"DEBUG: Using symbol code: {full_symbol}")
            
            # 使用 stock_us_hist 接口（东财历史数据）
            # 添加重试机制应对网络不稳定
            import time
            df = None
            last_error = None
            for attempt in range(3):
                try:
                    print(f"DEBUG: Attempt {attempt+1} fetching via stock_us_hist...")
                    df = ak.stock_us_hist(
                        symbol=full_symbol,
                        period="daily",
                        start_date=(datetime.now() - timedelta(days=limit * 3)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                        adjust=""
                    )
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    last_error = e
                    print(f"DEBUG: Error on attempt {attempt+1}: {e}")
                    time.sleep(1 * (attempt + 1))  # 递增等待
            
            if df is None or df.empty:
                error_msg = f"AkShare returned empty data for US symbol: {symbol}"
                if last_error:
                    error_msg += f" Last error: {last_error}"
                raise ValueError(error_msg)

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"AkShare (US) fetch failed for {symbol}: {e}")
        
        # AkShare 返回的 DataFrame 通常是按照日期升序排列的
        df = df.tail(limit)
        
        ohlcv_list = []
        for _, row in df.iterrows():
            try:
                # stock_us_hist 返回的列名是中文
                # 格式: 日期, 开盘, 收盘, 最高, 最低, 成交量
                date_str = str(row['日期'])
                # 处理可能包含时间的日期格式
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
            except Exception as e:
                print(f"WARN: Error parsing AkShare US row: {e}")
                continue
                
        return ohlcv_list

    # -------------------------------------------------------
    # 原有逻辑：AkShare (CN A-Share)
    # -------------------------------------------------------
    def _fetch_cn_stock(self, symbol: str, timeframe: str, limit: int, adjust: str) -> List[OHLCV]:
        """Fetch A-share stock data via AkShare."""
        import akshare as ak
        
        period_map = {"1d": "daily", "1wk": "weekly", "1mo": "monthly"}
        period = period_map.get(timeframe, "daily")
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                adjust=adjust,
                start_date=(datetime.now() - timedelta(days=limit * 3)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d")
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch A-share data for {symbol}: {e}")
        
        df = df.tail(limit)
        
        ohlcv_list = []
        for _, row in df.iterrows():
            try:
                ts = datetime.strptime(str(row['日期']), "%Y-%m-%d")
                ohlcv_list.append(OHLCV(
                    timestamp=int(ts.timestamp() * 1000),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=float(row['成交量'])
                ))
            except Exception as e:
                print(f"WARN: Error parsing row: {e}")
                continue
        
        return ohlcv_list
    
    # -------------------------------------------------------
    # Main Dispatcher
    # -------------------------------------------------------
    def fetch_history(self, symbol: str, timeframe: str = "1d", limit: int = 100,
                      start: Optional[int] = None, end: Optional[int] = None,
                      market: str = "us", adjust: str = "qfq") -> List[OHLCV]:
        
        if market == "us":
            return self._fetch_us_stock(symbol, timeframe, limit)
        elif market == "cn":
            return self._fetch_cn_stock(symbol, timeframe, limit, adjust)
        elif market == "us_ak":  # <--- 新增的分支
            return self._fetch_us_stock_ak(symbol, limit)
        else:
            raise ValueError(f"Unknown market: {market}")
    
    def run(self, ctx: Context) -> Dict[str, Any]:
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

# ==========================================
# 3. 执行测试 (Main Execution)
# ==========================================
if __name__ == "__main__":
    node = FetchStockNode()

    # # --- TEST 1: YFinance (Expected to fail locally without Proxy/VPN) ---
    # print("="*50)
    # print("TEST 1: Fetching US Stock via YFinance (Tesla - TSLA)")
    # print("="*50)
    
    # ctx_us = Context(inputs={
    #     "market": "us",
    #     "symbol": "TSLA",
    #     "timeframe": "1d",
    #     "limit": 5
    # })
    
    # result_us = node.run(ctx_us)
    
    # if "error" in result_us:
    #     print(f"❌ [Expected Failure] YFinance Fetch Failed: {result_us['error']}")
    # else:
    #     print(f"✅ YFinance Fetch Success! Got {result_us['count']} records.")
    #     if result_us['data']:
    #         print(f"Last record: {result_us['data'][-1]}")

    # # --- TEST 2: AkShare A-Share (Should Success) ---
    # print("\n" + "="*50)
    # print("TEST 2: Fetching CN Stock via AkShare (Moutai - 600519)")
    # print("="*50)

    # ctx_cn = Context(inputs={
    #     "market": "cn",
    #     "symbol": "600519",
    #     "timeframe": "1d",
    #     "limit": 5,
    #     "adjust": "qfq"
    # })

    # result_cn = node.run(ctx_cn)

    # if "error" in result_cn:
    #     print(f"❌ CN Fetch Failed: {result_cn['error']}")
    # else:
    #     print(f"✅ CN Fetch Success! Got {result_cn['count']} records.")
    #     if result_cn['data']:
    #         print(f"Last record: {result_cn['data'][-1]}")

    # --- TEST 3: AkShare US Stock (Should Success & Solve your problem) ---
    print("\n" + "="*50)
    print("TEST 3: Fetching US Stock via AkShare (Tesla - TSLA)")
    print("="*50)
    
    ctx_us_ak = Context(inputs={
        "market": "us_ak",  # <--- 使用新增的 market 类型
        "symbol": "TSLA",
        "timeframe": "1d",
        "limit": 5
    })
    
    result_us_ak = node.run(ctx_us_ak)
    
    if "error" in result_us_ak:
        print(f"❌ AkShare US Fetch Failed: {result_us_ak['error']}")
    else:
        print(f"✅ AkShare US Fetch Success! Got {result_us_ak['count']} records.")
        if result_us_ak['data']:
            print(f"Last record: {result_us_ak['data'][-1]}")