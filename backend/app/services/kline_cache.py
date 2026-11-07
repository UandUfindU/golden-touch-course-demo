"""
K-Line Cache Service - SQLite based caching for OHLCV data.

Supports both stock and crypto data with incremental updates.
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from app.nodes.impl.data.base import OHLCV


class KlineCacheService:
    """SQLite-based K-line data cache service."""
    
    # TTL settings (in seconds)
    TTL_MAP = {
        "1m": 60,           # 1 minute data: 1 min TTL
        "5m": 300,          # 5 minute data: 5 min TTL
        "15m": 900,         # 15 minute data: 15 min TTL
        "30m": 1800,        # 30 minute data: 30 min TTL
        "1h": 3600,         # 1 hour data: 1 hour TTL
        "4h": 14400,        # 4 hour data: 4 hour TTL
        "1d": 14400,        # Daily data: 4 hour TTL
        "daily": 14400,
        "1wk": 86400,       # Weekly data: 1 day TTL
        "weekly": 86400,
        "1mo": 604800,      # Monthly data: 1 week TTL
        "monthly": 604800,
    }
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize cache service with SQLite database."""
        if db_path is None:
            # Default to backend/data/kline_cache.db
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "kline_cache.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kline_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    data TEXT NOT NULL,
                    last_timestamp INTEGER NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_key ON kline_cache(cache_key)")
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _make_cache_key(
        self, 
        data_type: str, 
        symbol: str, 
        timeframe: str,
        market: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> str:
        """Generate cache key."""
        symbol_clean = symbol.replace("/", "_").upper()
        
        if data_type == "stock":
            return f"stock:{market or 'us'}:{symbol_clean}:{timeframe}"
        elif data_type == "crypto":
            return f"crypto:{exchange or 'binance'}:{symbol_clean}:{timeframe}"
        else:
            return f"other:{symbol_clean}:{timeframe}"
    
    def _get_ttl(self, timeframe: str) -> int:
        """Get TTL in seconds for a given timeframe."""
        return self.TTL_MAP.get(timeframe, 14400)  # Default 4 hours
    
    def _is_expired(self, updated_at: str, timeframe: str) -> bool:
        """Check if cache entry is expired."""
        try:
            # SQLite CURRENT_TIMESTAMP is UTC
            update_time = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
            ttl = self._get_ttl(timeframe)
            return datetime.utcnow() - update_time > timedelta(seconds=ttl)
        except:
            return True
    
    def get(
        self,
        data_type: str,
        symbol: str,
        timeframe: str,
        market: Optional[str] = None,
        exchange: Optional[str] = None,
        after: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached K-line data.
        
        Args:
            data_type: 'stock' or 'crypto'
            symbol: Stock symbol or trading pair
            timeframe: K-line timeframe
            market: Stock market (us/cn)
            exchange: Crypto exchange
            after: Return only data after this timestamp (for incremental)
        
        Returns:
            Dict with 'data', 'last_timestamp', 'expired' keys, or None if not found
        """
        cache_key = self._make_cache_key(data_type, symbol, timeframe, market, exchange)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT data, last_timestamp, updated_at FROM kline_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            data = json.loads(row["data"])
            expired = self._is_expired(row["updated_at"], timeframe)
            
            # Filter by 'after' timestamp if specified
            if after:
                data = [d for d in data if d.get("timestamp", 0) > after]
            
            return {
                "data": data,
                "last_timestamp": row["last_timestamp"],
                "expired": expired
            }
    
    def set(
        self,
        data_type: str,
        symbol: str,
        timeframe: str,
        data: List[Dict[str, Any]],
        market: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> bool:
        """
        Set K-line cache data.
        
        Args:
            data_type: 'stock' or 'crypto'
            symbol: Stock symbol or trading pair
            timeframe: K-line timeframe
            data: List of OHLCV dicts
            market: Stock market
            exchange: Crypto exchange
        
        Returns:
            True if successful
        """
        if not data:
            return False
        
        cache_key = self._make_cache_key(data_type, symbol, timeframe, market, exchange)
        
        # Get last timestamp
        last_timestamp = max(d.get("timestamp", 0) for d in data)
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO kline_cache (cache_key, data, last_timestamp, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (cache_key, json.dumps(data), last_timestamp))
            conn.commit()
        
        return True
    
    def update(
        self,
        data_type: str,
        symbol: str,
        timeframe: str,
        new_data: List[Dict[str, Any]],
        market: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> bool:
        """
        Update cache with new data (append/merge).
        
        Args:
            new_data: New OHLCV data to append
        
        Returns:
            True if successful
        """
        if not new_data:
            return False
        
        # Get existing data
        existing = self.get(data_type, symbol, timeframe, market, exchange)
        
        if existing and existing["data"]:
            # Merge: remove duplicates by timestamp
            existing_timestamps = {d.get("timestamp") for d in existing["data"]}
            merged = existing["data"] + [d for d in new_data if d.get("timestamp") not in existing_timestamps]
            # Sort by timestamp
            merged.sort(key=lambda x: x.get("timestamp", 0))
        else:
            merged = new_data
        
        return self.set(data_type, symbol, timeframe, merged, market, exchange)
    
    def clear(self, cache_key: Optional[str] = None):
        """Clear cache entries."""
        with self._get_connection() as conn:
            if cache_key:
                conn.execute("DELETE FROM kline_cache WHERE cache_key = ?", (cache_key,))
            else:
                conn.execute("DELETE FROM kline_cache")
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM kline_cache")
            count = cursor.fetchone()["count"]
            
            cursor = conn.execute("SELECT cache_key, last_timestamp, updated_at FROM kline_cache ORDER BY updated_at DESC LIMIT 10")
            recent = [dict(row) for row in cursor.fetchall()]
            
            return {
                "total_entries": count,
                "recent_entries": recent,
                "db_path": self.db_path
            }


# Global instance
_cache_instance: Optional[KlineCacheService] = None


def get_kline_cache() -> KlineCacheService:
    """Get global cache service instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = KlineCacheService()
    return _cache_instance
