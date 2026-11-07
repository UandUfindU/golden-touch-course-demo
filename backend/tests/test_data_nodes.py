"""
Integration tests for Data Ingestion Nodes.

Tests FetchCryptoNode and FetchStockNode with real API calls (rate-limited).
"""
import pytest
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.nodes.base import Context
from app.nodes.impl.data import FetchCryptoNode, FetchStockNode, DataNormalizerNode, OHLCV



class TestFetchCryptoNode:
    """Test FetchCryptoNode with ccxt."""
    
    def test_fetch_btc_kraken(self):
        """Test fetching BTC/USDT from Kraken (globally accessible)."""
        node = FetchCryptoNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_crypto",
            inputs={
                "exchange": "kraken",
                "symbol": "BTC/USDT",
                "timeframe": "1d",
                "limit": 10
            }
        )
        
        result = node.run(ctx)
        
        assert "error" not in result or result.get("error") is None, f"Error: {result.get('error')}"
        assert result["count"] > 0, "Should return at least 1 candle"
        assert result["symbol"] == "BTC/USDT"
        assert result["exchange"] == "kraken"
        
        # Validate OHLCV structure
        if result["data"]:
            candle = result["data"][0]
            assert "timestamp" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle
            print(f"[Crypto] Fetched {result['count']} candles. Latest close: {result['data'][-1]['close']}")
    
    def test_fetch_eth_okx(self):
        """Test fetching ETH/USDT from OKX."""
        node = FetchCryptoNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_crypto",
            inputs={
                "exchange": "okx",
                "symbol": "ETH/USDT",
                "timeframe": "1h",
                "limit": 5
            }
        )
        
        result = node.run(ctx)
        
        assert "error" not in result or result.get("error") is None, f"Error: {result.get('error')}"
        assert result["count"] > 0
        print(f"[Crypto/OKX] Fetched {result['count']} hourly candles for ETH/USDT")
    
    def test_invalid_exchange(self):
        """Test error handling for invalid exchange."""
        node = FetchCryptoNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_crypto",
            inputs={
                "exchange": "invalid_exchange_xyz",
                "symbol": "BTC/USDT",
                "timeframe": "1d",
                "limit": 10
            }
        )
        
        result = node.run(ctx)
        
        assert "error" in result
        assert result["count"] == 0


class TestFetchStockNode:
    """Test FetchStockNode with YFinance and AkShare."""
    
    def test_fetch_aapl_us(self):
        """Test fetching AAPL from US market (YFinance)."""
        node = FetchStockNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_stock",
            inputs={
                "market": "us",
                "symbol": "AAPL",
                "timeframe": "1d",
                "limit": 10
            }
        )
        
        result = node.run(ctx)
        
        assert "error" not in result or result.get("error") is None, f"Error: {result.get('error')}"
        assert result["count"] > 0, "Should return at least 1 candle"
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us"
        
        if result["data"]:
            print(f"[Stock/US] Fetched {result['count']} candles for AAPL. Latest close: ${result['data'][-1]['close']:.2f}")
    
    def test_fetch_msft_weekly(self):
        """Test fetching MSFT weekly data."""
        node = FetchStockNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_stock",
            inputs={
                "market": "us",
                "symbol": "MSFT",
                "timeframe": "1wk",
                "limit": 5
            }
        )
        
        result = node.run(ctx)
        
        assert "error" not in result or result.get("error") is None
        print(f"[Stock/US] Fetched {result['count']} weekly candles for MSFT")
    
    @pytest.mark.skip(reason="AkShare may fail in certain network environments")
    def test_fetch_pingan_cn(self):
        """Test fetching 000001 (Ping An Bank) from A-shares (AkShare)."""
        node = FetchStockNode()
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="fetch_stock",
            inputs={
                "market": "cn",
                "symbol": "000001",
                "timeframe": "1d",
                "limit": 10,
                "adjust": "qfq"
            }
        )
        
        result = node.run(ctx)
        
        assert "error" not in result or result.get("error") is None, f"Error: {result.get('error')}"
        assert result["count"] > 0
        print(f"[Stock/CN] Fetched {result['count']} candles for 000001 (Ping An Bank)")


class TestOHLCVSchema:
    """Test OHLCV schema utilities."""
    
    def test_ohlcv_datetime_property(self):
        """Test datetime conversion from timestamp."""
        ohlcv = OHLCV(
            timestamp=1704067200000,  # 2024-01-01 00:00:00 UTC
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000000.0
        )
        
        dt = ohlcv.datetime
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

class TestDataNormalizerNode:
    """Test DataNormalizerNode."""
    
    def test_normalize_clean_data(self):
        """Test normalizing already clean data."""
        node = DataNormalizerNode()
        clean_data = [
            {"timestamp": 1000, "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"timestamp": 2000, "open": 103, "high": 110, "low": 102, "close": 108, "volume": 1200},
            {"timestamp": 3000, "open": 108, "high": 112, "low": 106, "close": 110, "volume": 800},
        ]
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="normalizer",
            inputs={"data": clean_data}
        )
        
        result = node.run(ctx)
        
        assert result["original_count"] == 3
        assert result["final_count"] == 3
        assert result["dropped_count"] == 0
        print(f"[Normalizer] Clean data: {result['final_count']} rows, issues: {result['issues']}")
    
    def test_normalize_with_missing_values(self):
        """Test forward filling missing values."""
        node = DataNormalizerNode()
        data_with_nan = [
            {"timestamp": 1000, "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"timestamp": 2000, "open": None, "high": 110, "low": 102, "close": None, "volume": 1200},
            {"timestamp": 3000, "open": 108, "high": 112, "low": 106, "close": 110, "volume": 800},
        ]
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="normalizer",
            inputs={"data": data_with_nan, "fill_method": "ffill"}
        )
        
        result = node.run(ctx)
        
        assert result["final_count"] == 3
        assert result["filled_count"] > 0
        # Check that NaN was filled
        assert result["data"][1]["open"] == 100  # forward filled from row 0
        print(f"[Normalizer] Filled {result['filled_count']} missing values")
    
    def test_normalize_with_duplicates(self):
        """Test removing duplicate timestamps."""
        node = DataNormalizerNode()
        data_with_dups = [
            {"timestamp": 1000, "open": 100, "high": 105, "low": 99, "close": 103, "volume": 1000},
            {"timestamp": 1000, "open": 101, "high": 106, "low": 100, "close": 104, "volume": 1100},  # duplicate
            {"timestamp": 2000, "open": 108, "high": 112, "low": 106, "close": 110, "volume": 800},
        ]
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="normalizer",
            inputs={"data": data_with_dups, "remove_duplicates": True}
        )
        
        result = node.run(ctx)
        
        assert result["final_count"] == 2
        assert "duplicate" in str(result["issues"]).lower()
        print(f"[Normalizer] Removed duplicates: {result['original_count']} -> {result['final_count']}")
    
    def test_validate_invalid_ohlcv(self):
        """Test validation detects invalid OHLCV data."""
        node = DataNormalizerNode()
        invalid_data = [
            {"timestamp": 1000, "open": 100, "high": 95, "low": 99, "close": 103, "volume": 1000},  # high < open!
        ]
        ctx = Context(
            run_id="test", workflow_id="wf_test", node_id="normalizer",
            inputs={"data": invalid_data, "validate": True}
        )
        
        result = node.run(ctx)
        
        assert len(result["issues"]) > 0
        print(f"[Normalizer] Validation issues found: {result['issues']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
