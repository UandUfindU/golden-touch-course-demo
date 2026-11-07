"""
Precompute Registry for BacktestRunner.

Handles vectorized precomputation of indicators to keep the runner clean.
"""
from typing import Dict, Any, List, Optional, Callable, Union
import pandas as pd
import numpy as np

# Simple type for cleaner signatures
PrecomputerHandler = Callable[[Dict[str, Any], List[Dict[str, Any]], Dict[str, List[float]]], None]

class PrecomputerRegistry:
    """Registry for indicator precomputation handlers."""
    
    _handlers: Dict[str, PrecomputerHandler] = {}
    
    @classmethod
    def register(cls, node_types: Union[str, List[str]]):
        """Decorator to register a handler for specific node types."""
        def decorator(func: PrecomputerHandler):
            types = [node_types] if isinstance(node_types, str) else node_types
            for t in types:
                cls._handlers[t] = func
            return func
        return decorator

    @classmethod
    def get_handler(cls, node_type: str) -> Optional[PrecomputerHandler]:
        """Get handler for a specific node type."""
        # Exact match
        if node_type in cls._handlers:
            return cls._handlers[node_type]
        
        # Partial match (e.g. 'indicator.ma' handles 'logic.ma') - optional flexibility
        for key, handler in cls._handlers.items():
            if key in node_type: 
                return handler
        
        return None

    @classmethod
    def execute(cls, node_type: str, node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], dag: Dict = None, node_id: str = None) -> bool:
        """
        Execute precomputation if handler exists.
        Returns True if handled, False otherwise.
        """
        handler = cls.get_handler(node_type)
        if handler:
            # We pass extended context naturally via kw args if we wanted, 
            # but for now let's stick to a robust signature or kwargs
            try:
                # Check signature or just pass standardized args
                handler(node_data, data, indicators, dag=dag, node_id=node_id)
                return True
            except TypeError as e:
                # Fallback for handlers that might simple signature
                handler(node_data, data, indicators)
                return True
        return False

# ==============================================================================
# Helper Functions
# ==============================================================================

def extract_prices(data: List[Dict[str, Any]], field: str = 'close') -> List[float]:
    """Extract price series from data."""
    return [d.get(field, d.get('close', 0.0)) for d in data]

def to_list(series: pd.Series) -> List[Optional[float]]:
    """Convert pandas series to list of floats/None."""
    return [None if pd.isna(v) else float(v) for v in series]

# ==============================================================================
# Handlers Implementation
# ==============================================================================

@PrecomputerRegistry.register(["indicator.ma", "indicator.ema", "indicator.sma", "ma"])
def compute_ma(node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], **kwargs):
    period = node_data.get('period', node_data.get('window', 20))
    ma_type = node_data.get('ma_type', 'sma')
    price_field = node_data.get('price_field', 'close')
    prices = extract_prices(data, price_field)
    
    series = pd.Series(prices)
    if ma_type == 'ema':
        ma_series = series.ewm(span=period, adjust=False, min_periods=period).mean()
    else: 
        ma_series = series.rolling(window=period, min_periods=period).mean()
    
    col_name = node_data.get('output_name', f'ma{period}')
    indicators[col_name] = to_list(ma_series)

@PrecomputerRegistry.register(["indicator.rsi", "rsi"])
def compute_rsi(node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], **kwargs):
    period = node_data.get('period', 14)
    price_field = node_data.get('price_field', 'close')
    prices = extract_prices(data, price_field)
    
    series = pd.Series(prices)
    delta = series.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    
    col_name = node_data.get('output_name', 'rsi')
    indicators[col_name] = to_list(rsi_series)

@PrecomputerRegistry.register(["indicator.bollinger_bands", "bollinger"])
def compute_bollinger(node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], **kwargs):
    period = node_data.get('period', 20)
    std_dev = node_data.get('std_dev', 2.0)
    price_field = node_data.get('price_field', 'close')
    prices = extract_prices(data, price_field)
    
    series = pd.Series(prices)
    middle = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    upper_vals = middle + (std * std_dev)
    lower_vals = middle - (std * std_dev)
    
    # Check for tuple unpacking: {"upper": "user_var", "middle": "user_var2", ...}
    tuple_outputs = node_data.get('tuple_outputs')
    if tuple_outputs:
        # Use user-defined variable names directly
        indicators[tuple_outputs.get('upper', 'upper')] = to_list(upper_vals)
        indicators[tuple_outputs.get('middle', 'middle')] = to_list(middle)
        indicators[tuple_outputs.get('lower', 'lower')] = to_list(lower_vals)
    else:
        # Legacy: use {base_name}_{field} pattern
        base_name = node_data.get('output_name', 'bb')
        indicators[f'{base_name}_upper'] = to_list(upper_vals)
        indicators[f'{base_name}_middle'] = to_list(middle)
        indicators[f'{base_name}_lower'] = to_list(lower_vals)

@PrecomputerRegistry.register(["indicator.macd", "macd"])
def compute_macd(node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], **kwargs):
    fast_period = node_data.get('fast_period', 12)
    slow_period = node_data.get('slow_period', 26)
    signal_period = node_data.get('signal_period', 9)
    price_field = node_data.get('price_field', 'close')
    prices = extract_prices(data, price_field)
    
    series = pd.Series(prices)
    ema_fast = series.ewm(span=fast_period, adjust=False, min_periods=fast_period).mean()
    ema_slow = series.ewm(span=slow_period, adjust=False, min_periods=slow_period).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
    histogram = macd_line - signal_line
    
    # Check for tuple unpacking
    tuple_outputs = node_data.get('tuple_outputs')
    if tuple_outputs:
        # Use user-defined variable names directly
        indicators[tuple_outputs.get('line', 'line')] = to_list(macd_line)
        indicators[tuple_outputs.get('signal', 'signal')] = to_list(signal_line)
        indicators[tuple_outputs.get('histogram', 'histogram')] = to_list(histogram)
    else:
        # Legacy: use {base_name}_{field} pattern
        base_name = node_data.get('output_name', 'macd')
        indicators[f'{base_name}_line'] = to_list(macd_line)
        indicators[f'{base_name}_signal'] = to_list(signal_line)
        indicators[f'{base_name}_histogram'] = to_list(histogram)
        
        # Aliases if base_name is default
        if base_name == 'macd':
            indicators['macd_line'] = indicators[f'{base_name}_line']
            indicators['signal_line'] = indicators[f'{base_name}_signal']

@PrecomputerRegistry.register(["indicator.crossover", "crossover"])
def compute_crossover(node_data: Dict[str, Any], data: List[Dict[str, Any]], indicators: Dict[str, List[float]], **kwargs):
    dag = kwargs.get('dag')
    node_id = kwargs.get('node_id')
    
    if not dag or not node_id:
        print("[WARN] Crossover precomputation missing dag/node_id")
        return

    # Try to get fast/slow from node data first
    fast_name = node_data.get('fast_line')
    slow_name = node_data.get('slow_line')
    
    # Strip ${} edge reference wrapper
    def resolve_ref(name):
        if name and isinstance(name, str):
            if name.startswith('${') and name.endswith('}'):
                return name[2:-1]
        return name
    
    fast_name = resolve_ref(fast_name)
    slow_name = resolve_ref(slow_name)
    
    fallback_used = False
    
    # FALLBACK 1: Resolve from incoming EDGES
    if not fast_name or not slow_name:
        element_nodes = dag.get('nodes', [])
        nodes_map = {n['id']: n for n in element_nodes}
        edges = dag.get('edges', [])
        incoming_edges = [e for e in edges if e.get('target') == node_id]
        
        for edge in incoming_edges:
            source_id = edge.get('source')
            target_port = edge.get('target_port', '')
            source_port = edge.get('source_port', '')
            source_node = nodes_map.get(source_id, {})
            source_type = source_node.get('type', '')
            
            # Determine indicator name logic (same as before)
            indicator_name = None
            if 'macd' in source_type.lower() and source_port:
                indicator_name = source_port
            elif source_port == 'values':
                indicator_name = source_node.get('data', {}).get('output_name')
            elif source_port:
                indicator_name = source_port
            else:
                indicator_name = source_node.get('data', {}).get('output_name')
            
            if not indicator_name:
                continue
            
            if 'fast' in target_port.lower():
                fast_name = indicator_name
                fallback_used = True
            elif 'slow' in target_port.lower():
                slow_name = indicator_name
                fallback_used = True
            elif not fast_name:
                fast_name = indicator_name
                fallback_used = True
            elif not slow_name:
                slow_name = indicator_name
                fallback_used = True
        
        if fallback_used:
            # print(f"  [DEBUG] CrossOver '{node_id}': Resolved via edges - fast='{fast_name}', slow='{slow_name}'")
            pass

    # FALLBACK 2: Only when EXACTLY 2 MA nodes exist
    if not fast_name or not slow_name:
        element_nodes = dag.get('nodes', [])
        ma_nodes = [(n['id'], n.get('data', {}).get('output_name'), n.get('data', {}).get('period', 0)) 
                    for n in element_nodes if 'ma' in n.get('type', '').lower() and 'macd' not in n.get('type', '').lower() and n.get('data', {}).get('output_name')]
        
        if len(ma_nodes) == 2:
            ma_nodes.sort(key=lambda x: x[2] if x[2] else 999)
            fast_name = ma_nodes[0][1]
            slow_name = ma_nodes[1][1]
            print(f"  [WARN] CrossOver '{node_id}': Auto-inferred fast='{fast_name}', slow='{slow_name}'")

    if not fast_name or not slow_name:
        print(f"  [ERROR] CrossOver '{node_id}' SKIPPED: Unable to resolve lines")
        return

    def get_series(name):
        if name and name in indicators: 
            return indicators[name]
        return [d.get(name, 0.0) for d in data] if name else [0.0] * len(data)

    fast_series = get_series(fast_name)
    slow_series = get_series(slow_name)
    
    f = pd.Series([np.nan if x is None else float(x) for x in fast_series])
    s = pd.Series([np.nan if x is None else float(x) for x in slow_series])
    
    prev_f = f.shift(1)
    prev_s = s.shift(1)
    
    bullish = (f > s) & (prev_f <= prev_s)
    bearish = (f < s) & (prev_f >= prev_s)
    
    signals = pd.Series(0, index=f.index)
    signals[bullish] = 1
    signals[bearish] = -1
    
    col_name = node_data.get('output_name', 'crossover')
    indicators[col_name] = to_list(signals)

