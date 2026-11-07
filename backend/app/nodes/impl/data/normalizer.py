"""
DataNormalizerNode - Cleans and normalizes OHLCV data for backtesting.

Handles:
- Missing values (forward fill, interpolation)
- Timestamp alignment
- Data validation
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
from .base import OHLCV


class DataNormalizerInput(BaseModel):
    """Input schema for DataNormalizerNode."""
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of OHLCV data dictionaries"
    )
    source: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Alias for 'data' (common LLM usage)"
    )
    fill_method: str = Field(
        default="ffill",
        description="Method for filling missing values: 'ffill' (forward fill), 'bfill' (backward fill), 'interpolate', 'drop'"
    )
    validate_integrity: bool = Field(
        default=True,
        description="Whether to validate data integrity"
    )
    sort_by_time: bool = Field(
        default=True,
        description="Sort data by timestamp ascending"
    )
    remove_duplicates: bool = Field(
        default=True,
        description="Remove duplicate timestamps"
    )


class DataNormalizerOutput(BaseModel):
    """Output schema for DataNormalizerNode."""
    data: List[Dict[str, Any]] = Field(description="Cleaned OHLCV data")
    original_count: int = Field(description="Original row count")
    final_count: int = Field(description="Final row count after cleaning")
    dropped_count: int = Field(description="Number of rows dropped")
    filled_count: int = Field(description="Number of values filled")
    issues: List[str] = Field(description="List of data quality issues found")


@register_node(
    category=NodeCategory.DATA,
    name="data.normalizer",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL]
)
class DataNormalizerNode(BaseNode):
    """
    Data Normalizer Node - Cleans and validates OHLCV data.
    
    Ensures data quality before feeding into backtesting or analysis nodes.
    """
    description = "Clean and normalize OHLCV data"
    InputSchema = DataNormalizerInput
    OutputSchema = DataNormalizerOutput
    
    def _validate_ohlcv(self, df: pd.DataFrame) -> List[str]:
        """Validate OHLCV data integrity."""
        issues = []
        
        # Check for negative prices
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns and (df[col] < 0).any():
                issues.append(f"Negative values found in {col}")
        
        # Check high >= low
        if 'high' in df.columns and 'low' in df.columns:
            invalid_hl = df['high'] < df['low']
            if invalid_hl.any():
                issues.append(f"{invalid_hl.sum()} rows have high < low")
        
        # Check high >= open, close
        if all(c in df.columns for c in ['high', 'open', 'close']):
            invalid_ho = df['high'] < df['open']
            invalid_hc = df['high'] < df['close']
            if invalid_ho.any() or invalid_hc.any():
                issues.append("Some rows have high < open or high < close")
        
        # Check low <= open, close
        if all(c in df.columns for c in ['low', 'open', 'close']):
            invalid_lo = df['low'] > df['open']
            invalid_lc = df['low'] > df['close']
            if invalid_lo.any() or invalid_lc.any():
                issues.append("Some rows have low > open or low > close")
        
        # Check for zero volume (warning, not error)
        if 'volume' in df.columns and (df['volume'] == 0).any():
            zero_vol_count = (df['volume'] == 0).sum()
            issues.append(f"{zero_vol_count} rows have zero volume (may be valid)")
        
        return issues
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute the node: Clean and normalize data."""
        params = self.validate_inputs(ctx.inputs)
        
        # Handle 'source' alias for 'data'
        data_input = params.data
        if not data_input and params.source:
            data_input = params.source
            
        if not data_input:
            return {
                "data": [],
                "original_count": 0,
                "final_count": 0,
                "dropped_count": 0,
                "filled_count": 0,
                "issues": ["Empty input data"]
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(data_input)
        original_count = len(df)
        issues = []
        filled_count = 0
        
        # Ensure required columns exist
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")
            # Try to continue with available columns
        
        # Sort by timestamp
        if params.sort_by_time and 'timestamp' in df.columns:
            df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Remove duplicates
        if params.remove_duplicates and 'timestamp' in df.columns:
            before_dedup = len(df)
            df = df.drop_duplicates(subset=['timestamp'], keep='last')
            if len(df) < before_dedup:
                issues.append(f"Removed {before_dedup - len(df)} duplicate timestamps")
        
        # Handle missing values
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        available_numeric = [c for c in numeric_cols if c in df.columns]
        
        # Count missing before filling
        missing_before = df[available_numeric].isna().sum().sum()
        
        if params.fill_method == "ffill":
            df[available_numeric] = df[available_numeric].ffill()
        elif params.fill_method == "bfill":
            df[available_numeric] = df[available_numeric].bfill()
        elif params.fill_method == "interpolate":
            df[available_numeric] = df[available_numeric].interpolate(method='linear')
        elif params.fill_method == "drop":
            df = df.dropna(subset=available_numeric)
        
        # Count remaining missing (may still exist after ffill/bfill at edges)
        missing_after = df[available_numeric].isna().sum().sum()
        filled_count = int(missing_before - missing_after)
        
        # Drop any remaining NaN rows
        rows_with_nan = df[available_numeric].isna().any(axis=1).sum()
        if rows_with_nan > 0:
            df = df.dropna(subset=available_numeric)
            issues.append(f"Dropped {rows_with_nan} rows with unfillable NaN values")
        
        # Validate data integrity
        if params.validate_integrity:
            validation_issues = self._validate_ohlcv(df)
            issues.extend(validation_issues)
        
        final_count = len(df)
        dropped_count = original_count - final_count
        
        return {
            "data": df.to_dict(orient='records'),
            "original_count": original_count,
            "final_count": final_count,
            "dropped_count": dropped_count,
            "filled_count": filled_count,
            "issues": issues
        }
