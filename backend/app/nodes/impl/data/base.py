"""
Base Data Fetcher - Abstract base class for all data fetcher nodes.

Defines the standard OHLCV schema and the interface for fetching historical data.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class OHLCV(BaseModel):
    """Standardized OHLCV (Open-High-Low-Close-Volume) data schema."""
    timestamp: int = Field(description="Unix timestamp in milliseconds")
    open: float = Field(description="Opening price")
    high: float = Field(description="Highest price")
    low: float = Field(description="Lowest price")
    close: float = Field(description="Closing price")
    volume: float = Field(description="Trading volume")
    
    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object."""
        return datetime.fromtimestamp(self.timestamp / 1000)


class BaseDataFetcher(ABC):
    """
    Abstract base class for data fetcher nodes.
    
    All data sources (Crypto, Stock, etc.) must implement this interface
    to ensure consistent data format for downstream nodes and backtesting.
    """
    
    @abstractmethod
    def fetch_history(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100,
        start: Optional[int] = None,
        end: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch historical OHLCV data.
        
        Args:
            symbol: Trading pair or stock symbol (e.g., "BTC/USDT", "AAPL")
            timeframe: Candle timeframe (e.g., "1m", "1h", "1d")
            limit: Maximum number of candles to fetch
            start: Start timestamp in milliseconds (optional)
            end: End timestamp in milliseconds (optional)
            
        Returns:
            List of OHLCV objects, sorted by timestamp ascending.
        """
        pass
    
    @staticmethod
    def validate_timeframe(timeframe: str) -> bool:
        """Validate timeframe format."""
        valid_timeframes = [
            "1m", "3m", "5m", "15m", "30m",
            "1h", "2h", "4h", "6h", "8h", "12h",
            "1d", "3d", "1w", "1M"
        ]
        return timeframe in valid_timeframes
