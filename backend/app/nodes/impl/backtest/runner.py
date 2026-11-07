"""
BacktestRunnerNode - Core backtesting engine.

Executes a strategy DAG on historical data, simulating trades and tracking equity.
Supports Hybrid Mode:
- Vectorized Precomputation for standard indicators (MA, RSI).
- Event-Driven Execution for custom logic logic/scripts.
"""
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import copy
import numpy as np

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node, NodeRegistry
from app.core.enums import NodeCategory, NodeScope
from .result import BacktestResult, Trade, EquityPoint, PerformanceMetrics


class BacktestConfig(BaseModel):
    """Backtest configuration."""
    initial_capital: float = Field(
        default=10000.0,
        ge=0,
        description="Initial capital"
    )
    commission_rate: float = Field(
        default=0.001,
        ge=0,
        le=0.1,
        description="Commission rate (0.001 = 0.1%)"
    )
    slippage: float = Field(
        default=0.0,
        ge=0,
        description="Slippage in price units"
    )
    position_size_pct: float = Field(
        default=1.0,
        ge=0,
        le=1.0,
        description="Position size as percentage of equity (1.0 = 100%)"
    )
    # Risk Management
    stop_loss_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=1.0,
        description="Stop loss percentage (0.02 = 2% stop loss, None = disabled)"
    )
    take_profit_pct: Optional[float] = Field(
        default=None,
        ge=0,
        description="Take profit percentage (0.04 = 4% take profit, None = disabled)"
    )


class BacktestRunnerInput(BaseModel):
    """Input schema for BacktestRunnerNode."""
    data: List[Dict[str, Any]] = Field(
        description="Historical OHLCV data (must have timestamp, open, high, low, close, volume)"
    )
    strategy_dag: Dict[str, Any] = Field(
        description="Strategy DAG definition with nodes and edges"
    )
    config: BacktestConfig = Field(
        default_factory=BacktestConfig,
        description="Backtest configuration"
    )


class BacktestRunnerOutput(BaseModel):
    """Output schema for BacktestRunnerNode."""
    result: BacktestResult = Field(description="Complete backtest result")


@register_node(
    category=NodeCategory.EXECUTION,
    name="backtest.runner",
    scopes=[NodeScope.WORKFLOW, NodeScope.TOOL]
)
class BacktestRunnerNode(BaseNode):
    """
    Backtest Runner Node - Executes strategy on historical data.
    
    This node simulates trading by:
    1. Precomputing vectorized indicators (MA, RSI) for speed.
    2. Iterating through historical data bar by bar.
    3. Executing remaining nodes (Logic, Script) dynamically.
    4. Evaluating conditions and executing trades.
    """
    description = "Run backtest on historical data with a strategy DAG"
    InputSchema = BacktestRunnerInput
    OutputSchema = BacktestRunnerOutput
    
    def _topological_sort(self, dag: Dict[str, Any]) -> List[str]:
        """Sort DAG nodes topologically for execution order."""
        nodes = {n['id']: n for n in dag.get('nodes', [])}
        edges = dag.get('edges', [])
        
        # Build adjacency list
        in_degree = {nid: 0 for nid in nodes}
        adj = {nid: [] for nid in nodes}
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source in nodes and target in nodes:
                adj[source].append(target)
                in_degree[target] += 1
        
        # Kahn's algorithm
        queue = [nid for nid, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def _instantiate_nodes(self, dag: Dict[str, Any]) -> Dict[str, Any]:
        """Instantiate node classes for runtime execution."""
        instances = {}
        for node in dag.get('nodes', []):
            try:
                node_type = node.get('type')
                node_cls = NodeRegistry.get_node(node_type)
                # We instantiate without args, params are passed in Context during run
                instances[node['id']] = node_cls()
            except Exception:
                # If node type not found, we skip instantiation (might be handled by precompute or just invalid)
                pass
        return instances

    def _execute_runtime_node(self, node_id: str, dag: Dict[str, Any], instances: Dict[str, Any], 
                              bar_context: Dict[str, Any], runtime_state: Dict[str, Any]) -> None:
        """
        Execute a single node at runtime (Bar-by-Bar).
        Updates runtime_state with the node's outputs.
        """
        if node_id not in instances:
            return

        node_def = next((n for n in dag.get('nodes', []) if n['id'] == node_id), None)
        if not node_def:
            return

        node_instance = instances[node_id]
        
        # 1. Resolve Inputs
        # Look at edges targeting this node
        inputs = copy.deepcopy(node_def.get('data', {}))
        
        # Context includes bar data (open, close, etc)
        # Some nodes might look for 'close' in inputs, others in context
        # We merge bar_context into inputs just in case, or rely on node usage logic
        # Ideally, inputs specific to the node come from edges
        
        # Resolve edges
        edges = dag.get('edges', [])
        for edge in edges:
            if edge.get('target') == node_id:
                source_id = edge.get('source')
                target_port = edge.get('target_port')
                source_port = edge.get('source_port', 'default')
                
                # Get value from runtime_state (outputs of previous nodes)
                if source_id in runtime_state:
                    val = runtime_state[source_id].get(source_port)
                    # If single output, maybe stored directly? No, assume dict output for now
                    # Or check checks logic to handle simple values
                    if val is None:
                         # Try 'default' or inferred
                         val = runtime_state[source_id].get('value') or runtime_state[source_id].get('output')
                    
                    if target_port:
                        inputs[target_port] = val
        
        # 2. Run Node
        # Context needs to be lightweight
        ctx = Context(
            run_id="bt_step", workflow_id="bt", node_id=node_id,
            inputs=inputs
        )
        
        # Inject bar data into context vars (hack for some nodes that read context direct)
        # But standard nodes read inputs. 
        # For ScriptNode, it might need 'close', 'open' etc available as variables?
        # ScriptNode usually puts inputs into locals. So we must have mapped Global Vars to inputs via edges.
        # IF the graph didn't put 'close' as an edge to ScriptNode, ScriptNode won't see it.
        # UNLESS ScriptNode reads from a global 'context' object?
        # Let's assume correct wiring for now.
        
        try:
            result = node_instance.run(ctx)
            # Store result
            runtime_state[node_id] = result
            
            # 3. Update Bar Context (Variable Injection)
            # If node has 'output_name', inject result into bar_context for Condition Eval
            output_name = node_def.get('data', {}).get('output_name')
            if output_name:
                # Assuming result has 'value' or 'data', or is the dict itself
                # We want a single scalar for eval context usually
                val = result.get('value') if isinstance(result, dict) else result
                if isinstance(result, dict) and len(result) == 1:
                     val = list(result.values())[0]
                
                bar_context[output_name] = val
                
        except Exception as e:
            # print(f"  [DEBUG] Runtime Error node {node_id} ({node_def['type']}): {e}")
            pass

    def _evaluate_conditions(self, dag: Dict[str, Any], bar: Dict[str, Any], 
                             indicators: Dict[str, Any]) -> Optional[str]:
        """
        Evaluate strategy conditions and return signal.
        
        Two-pass approach for intermediate variable support:
        1. Execute ALL condition nodes in topological order, storing results
        2. Check for buy/sell signal nodes and return appropriate action
        """
        nodes = {n['id']: n for n in dag.get('nodes', [])}
        edges = dag.get('edges', [])
        
        # Build execution order (topological sort for condition nodes only)
        condition_nodes = [n for n in dag.get('nodes', []) 
                          if 'condition' in n.get('type', '').lower() or 'if' in n.get('type', '').lower()]
        
        # Expression-based dependency analysis for proper topological sort
        def extract_variables(expr: str) -> set:
            """Extract variable names from expression using regex."""
            import re
            # Match valid Python identifiers, exclude keywords and operators
            tokens = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr)
            # Filter out Python keywords and common operators
            keywords = {'and', 'or', 'not', 'True', 'False', 'None', 'in', 'is', 'if', 'else'}
            return {t for t in tokens if t not in keywords}
        
        # Build output_name -> node mapping
        output_to_node = {}
        for node in condition_nodes:
            output_name = node.get('data', {}).get('output_name', node.get('id'))
            output_to_node[output_name] = node.get('id')
        
        # Build dependency graph: node_id -> set of node_ids it depends on
        dependencies = {}
        for node in condition_nodes:
            node_id = node.get('id')
            expr = node.get('data', {}).get('condition_expr', '')
            vars_in_expr = extract_variables(expr)
            
            # Find which condition nodes these variables come from
            deps = set()
            for var in vars_in_expr:
                if var in output_to_node and output_to_node[var] != node_id:
                    deps.add(output_to_node[var])
            dependencies[node_id] = deps
        
        # Topological sort using Kahn's algorithm
        def topo_sort(nodes_list, deps):
            in_degree = {n.get('id'): 0 for n in nodes_list}
            for node_id, dep_set in deps.items():
                for dep in dep_set:
                    if dep in in_degree:
                        in_degree[node_id] = in_degree.get(node_id, 0) + 1
            
            # Start with nodes that have no dependencies
            queue = [n for n in nodes_list if in_degree.get(n.get('id'), 0) == 0]
            sorted_nodes = []
            
            while queue:
                current = queue.pop(0)
                sorted_nodes.append(current)
                
                # Decrease in-degree for nodes that depend on current
                for node in nodes_list:
                    if current.get('id') in deps.get(node.get('id'), set()):
                        in_degree[node.get('id')] -= 1
                        if in_degree[node.get('id')] == 0:
                            queue.append(node)
            
            # Handle any remaining nodes (circular deps or disconnected)
            remaining = [n for n in nodes_list if n not in sorted_nodes]
            return sorted_nodes + remaining
        
        condition_nodes = topo_sort(condition_nodes, dependencies)
        
        # Debug: Print execution order (only once per backtest run)
        if not hasattr(self, '_debug_cond_printed'):
            self._debug_cond_printed = True
            # print(f"  [DEBUG] Condition execution order: {[n.get('data', {}).get('output_name', n.get('id')) for n in condition_nodes]}")
            # print(f"  [DEBUG] Dependencies: {[(k, list(v)) for k, v in dependencies.items()]}")
        
        # Pass 1: Evaluate all condition nodes, store results in shared context
        # Base context includes OHLCV + precomputed indicators
        eval_context = {
            'close': bar.get('close', 0),
            'open': bar.get('open', 0),
            'high': bar.get('high', 0),
            'low': bar.get('low', 0),
            'volume': bar.get('volume', 0),
            **{k: (v if v is not None else float('nan')) for k, v in indicators.items()}
        }
        
        # Inject user-defined constants from DSL (e.g., threshold = 30)
        constants = dag.get('constants', {})
        eval_context.update(constants)
        
        # Inject expression aliases from DSL (e.g., buy_cond = "close < lower")
        # These need to be evaluated once using current context
        expressions = dag.get('expressions', {})
        for expr_name, expr_str in expressions.items():
            try:
                eval_context[expr_name] = eval(expr_str, {"__builtins__": {}}, eval_context)
            except Exception:
                pass  # Expression may reference variables not yet available
        
        # Store condition results by output_name
        condition_results = {}
        
        # Debug: Print available context keys (once)
        if not hasattr(self, '_debug_ctx_printed'):
            self._debug_ctx_printed = True
            print(f"  [DEBUG] Initial context keys: {list(eval_context.keys())[:20]}... (total: {len(eval_context)})")
        
        for node in condition_nodes:
            node_id = node.get('id')
            node_data = node.get('data', {})
            # Support both 'condition_expr' (from if statements) and 'condition' (from logic.condition() calls)
            condition_expr = node_data.get('condition_expr') or node_data.get('condition', '')
            output_name = node_data.get('output_name', node_id)  # Fallback to node_id
            
            if not condition_expr:
                continue
                
            try:
                # Merge previous condition results into context
                current_context = {**eval_context, **condition_results}
                result = eval(condition_expr, {"__builtins__": {}}, current_context)
                condition_results[output_name] = result
                
                # Debug: Print first 3 condition evals
                if not hasattr(self, '_debug_eval_count'):
                    self._debug_eval_count = 0
                if self._debug_eval_count < 5:
                    self._debug_eval_count += 1
                    print(f"  [DEBUG] Eval '{output_name}' = '{condition_expr[:80]}' → {result}")
                    
            except Exception as e:
                # Log unique errors
                if not hasattr(self, '_logged_cond_errors'):
                    self._logged_cond_errors = set()
                err_key = f"{node_id}:{str(e)[:30]}"
                if err_key not in self._logged_cond_errors:
                    print(f"  [WARN] Condition '{node_id}' (output='{output_name}') eval failed: {e}")
                    self._logged_cond_errors.add(err_key)
                condition_results[output_name] = False  # Default to False on error
        
        # Pass 2: Check which conditions lead to buy/sell signals
        for node in condition_nodes:
            node_id = node.get('id')
            output_name = node.get('data', {}).get('output_name', node_id)
            result = condition_results.get(output_name, False)
            
            if result:
                # Check what action follows this condition via edges
                for edge in edges:
                    if edge.get('source') == node_id:
                        target = nodes.get(edge.get('target'), {})
                        target_type = target.get('type', '').lower()
                        if 'buy' in target_type:
                            print(f"  [DEBUG] BUY Signal triggered at bar {bar.get('timestamp')}")
                            return 'buy'
                        elif 'sell' in target_type:
                            print(f"  [DEBUG] SELL Signal triggered at bar {bar.get('timestamp')}")
                            return 'sell'
        
        # Pass 3: Evaluate explicit signal conditions before considering legacy fallbacks.
        has_explicit_signal = False
        for node_id, node in nodes.items():
            node_type = node.get('type', '').lower()
            node_data = node.get('data', {})
            
            if 'signal.buy' in node_type or 'signal.sell' in node_type:
                condition_expr = node_data.get('condition', '')
                # Print signal debug only on first bar
                if not hasattr(self, '_signal_debug_printed'):
                    self._signal_debug_printed = True
                    print(f"  [DEBUG] Signal node '{node_id}' ({node_type}): condition='{condition_expr}'")
                
                if condition_expr and isinstance(condition_expr, str):
                    has_explicit_signal = True
                    try:
                        # Evaluate condition expression using indicator context
                        current_context = {**eval_context, **condition_results}
                        result = eval(condition_expr, {"__builtins__": {}}, current_context)
                        
                        if result:
                            if 'buy' in node_type:
                                print(f"  [DEBUG] BUY Signal triggered (Direct) at bar {bar.get('timestamp')}: {condition_expr[:50]}")
                                return 'buy'
                            elif 'sell' in node_type:
                                print(f"  [DEBUG] SELL Signal triggered (Direct) at bar {bar.get('timestamp')}: {condition_expr[:50]}")
                                return 'sell'
                    except Exception as e:
                        # Log unique errors
                        if not hasattr(self, '_logged_signal_errors'):
                            self._logged_signal_errors = set()
                        err_key = f"{node_id}:{str(e)[:30]}"
                        if err_key not in self._logged_signal_errors:
                            print(f"  [WARN] Signal '{node_id}' condition eval failed: {e}")
                            print(f"         Expression: {condition_expr[:80]}")
                            print(f"         Available vars: {list(current_context.keys())[:10]}...")
                            self._logged_signal_errors.add(err_key)
        
        if has_explicit_signal:
            return None

        # Legacy strategies without explicit signal expressions.
        for node_id, node in nodes.items():
            node_type = node.get('type', '')

            if 'crossover' in node_type.lower():
                output_name = node.get('data', {}).get('output_name', 'crossover')
                signal_val = indicators.get(output_name, 0)

                if signal_val == 1:
                    print(f"  [DEBUG] BUY Signal triggered (CrossOver) at bar {bar.get('timestamp')}")
                    return 'buy'
                elif signal_val == -1:
                    print(f"  [DEBUG] SELL Signal triggered (CrossOver) at bar {bar.get('timestamp')}")
                    return 'sell'

        return None
    
    def _precompute_indicators(self, dag: Dict[str, Any], data: List[Dict[str, Any]]) -> tuple[Dict[str, List[Any]], List[str]]:
        """
        Pre-compute vectorizable indicators.
        Returns (indicators_map, list_of_precomputed_node_ids)
        """
        indicators: Dict[str, List[Any]] = {}
        precomputed_ids = []
        nodes = dag.get('nodes', [])
        
        for node in nodes:
            node_type = node.get('type', '').lower()
            node_data = node.get('data', {})
            node_id = node.get('id', '')
            
            # Delegate to Registry
            from .precompute import PrecomputerRegistry
            
            handled = PrecomputerRegistry.execute(
                node_type, 
                node_data, 
                data, 
                indicators, 
                dag=dag, 
                node_id=node_id
            )
            
            if handled:
                precomputed_ids.append(node_id)
            else:
                # Optional: warn if it looks like an indicator but wasn't handled
                if node_type.startswith("indicator."):
                     pass # or log warning
        
        return indicators, precomputed_ids
        
        return indicators, precomputed_ids
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        """Execute backtest."""
        params = self.validate_inputs(ctx.inputs)
        
        data = params.data
        dag = params.strategy_dag
        config = params.config
        
        if not data:
            return {
                "result": BacktestResult(
                    success=False,
                    error="Empty data provided",
                    initial_capital=config.initial_capital,
                    commission_rate=config.commission_rate
                ).model_dump()
            }
        
        # Initialize state
        cash = config.initial_capital
        position = 0.0
        position_price = 0.0
        trades: List[Trade] = []
        equity_curve: List[EquityPoint] = []
        
        # 1. Pre-compute indicators (Vectorized Speedup)
        precomputed, precomputed_ids = self._precompute_indicators(dag, data)
        
        # Debug: Show what was precomputed
        # if precomputed:
        #     print(f\"  [DEBUG] Precomputed indicators: {list(precomputed.keys())}\"）
        #     for name, values in precomputed.items():
        #         non_zero = sum(1 for v in values if v and v != 0)
        #         print(f\"    - {name}: {len(values)} values, {non_zero} non-zero/signal events\")
        
        # The runner receives the primary market history from its caller.
        # Keep the source node for graph wiring without fetching that series again on every bar.
        nodes_map = {node["id"]: node for node in dag.get("nodes", [])}
        stock_source = next((node for node in nodes_map.values() if node["type"] == "data.fetch_stock"), None)
        crypto_source = next((node for node in nodes_map.values() if node["type"] == "data.fetch_crypto"), None)
        market_source = stock_source or crypto_source
        market_source_id = market_source["id"] if market_source else None
        runtime_node_ids = [
            node_id for node_id in self._topological_sort(dag)
            if node_id not in precomputed_ids and node_id != market_source_id
        ]
        needs_market_history = market_source is not None and any(
            edge.get("source") == market_source_id and edge.get("target") in runtime_node_ids
            for edge in dag.get("edges", [])
        )
        node_instances = self._instantiate_nodes(dag)

        buy_signals_count = 0
        sell_signals_count = 0
        
        # Extract callback if provided in context
        on_log = ctx.inputs.get("on_log")
        
        try:
            if on_log: on_log(f"Starting bar-by-bar execution ({len(data)} bars)...")
            for i, bar in enumerate(data):
                # Progress logging every 20 bars
                if i > 0 and i % 20 == 0:
                    if on_log: on_log(f"Processing bar {i}/{len(data)}...")
                
                timestamp = bar.get('timestamp', i)
                close = bar.get('close', 0)
                
                # Equity Tracking
                position_value = position * close
                equity = cash + position_value
                regime = "Normal"
                
                equity_curve.append(EquityPoint(
                    timestamp=timestamp,
                    equity=equity,
                    cash=cash,
                    position_value=position_value,
                    regime=regime
                ))
                
                # ========== STOP-LOSS / TAKE-PROFIT CHECK ==========
                # Check BEFORE regular signal evaluation
                if position > 0 and position_price > 0:
                    high = bar.get('high', close)
                    low = bar.get('low', close)
                    
                    # Stop-Loss Check (uses low price to be conservative)
                    if config.stop_loss_pct is not None:
                        stop_price = position_price * (1 - config.stop_loss_pct)
                        if low <= stop_price:
                            # Stop-loss triggered
                            exit_price = stop_price  # Assume execution at stop price
                            pnl = (exit_price - position_price) * position
                            commission = position * exit_price * config.commission_rate
                            cash += position * exit_price - commission
                            if trades and not trades[-1].is_closed:
                                trades[-1].exit_time = timestamp
                                trades[-1].exit_price = exit_price
                                trades[-1].pnl = pnl - commission - abs(position) * position_price * config.commission_rate
                                trades[-1].is_closed = True
                            position = 0
                            position_price = 0
                            if on_log: on_log(f"STOP-LOSS triggered @ {exit_price:.2f}")
                            continue  # Skip rest of this bar's processing
                    
                    # Take-Profit Check (uses high price)
                    if config.take_profit_pct is not None:
                        tp_price = position_price * (1 + config.take_profit_pct)
                        if high >= tp_price:
                            # Take-profit triggered
                            exit_price = tp_price  # Assume execution at TP price
                            pnl = (exit_price - position_price) * position
                            commission = position * exit_price * config.commission_rate
                            cash += position * exit_price - commission
                            if trades and not trades[-1].is_closed:
                                trades[-1].exit_time = timestamp
                                trades[-1].exit_price = exit_price
                                trades[-1].pnl = pnl - commission - abs(position) * position_price * config.commission_rate
                                trades[-1].is_closed = True
                            position = 0
                            position_price = 0
                            if on_log: on_log(f"TAKE-PROFIT triggered @ {exit_price:.2f}")
                            continue  # Skip rest of this bar's processing
                # ===================================================
                
                # Build Context for this Bar
                # Start with precomputed values
                current_indicators = {
                    name: values[i] if i < len(values) else None
                    for name, values in precomputed.items()
                }
                
                # 3. Execute Runtime Nodes
                # We maintain a state of node_outputs for this bar to resolve dependencies
                runtime_state = {} 
                
                # Also seed runtime_state with precomputed values (if any runtime node depends on MA)
                for nid in precomputed_ids:
                    node = nodes_map.get(nid)
                    out_name = node.get('data', {}).get('output_name', 'default')
                    # Find value in precomputed indicators
                    # This relies on strict naming convention.
                    # If out_name used in indicators, grab it.
                    val = precomputed.get(out_name, [None]*len(data))[i]
                    runtime_state[nid] = {"value": val} # Fake node output format
                
                # Run each runtime node
                for nid in runtime_node_ids:
                    self._execute_runtime_node(nid, dag, node_instances, current_indicators, runtime_state)
                
                # 4. Evaluate Signal
                # Pass current_indicators (which contains runtime outputs now too)
                signal = self._evaluate_conditions(dag, bar, current_indicators)
                
                if signal == 'buy':
                    buy_signals_count += 1
                    if on_log: on_log(f"BUY Signal triggered at bar {timestamp}")
                elif signal == 'sell':
                    sell_signals_count += 1
                    if on_log: on_log(f"SELL Signal triggered at bar {timestamp}")
                
                # 5. Execute Trades (支持做多和做空)
                if signal == 'buy':
                    if position < 0:  # 平空仓
                        pnl = (position_price - close) * abs(position)
                        commission = abs(position) * close * config.commission_rate
                        cash -= abs(position) * close + commission
                        if trades and not trades[-1].is_closed:
                            trades[-1].exit_time = timestamp
                            trades[-1].exit_price = close
                            trades[-1].pnl = pnl - commission - abs(position) * position_price * config.commission_rate
                            trades[-1].is_closed = True
                        if on_log: on_log(f"EXECUTED BUY: Closed Short @ {close:.2f}, PnL: {pnl - commission:.2f}")
                        position = 0
                    
                    if position == 0 and cash > 0:  # 开多仓
                        target_equity = cash * config.position_size_pct
                        size = target_equity / (close * (1 + config.commission_rate))
                        cost = size * close
                        commission = cost * config.commission_rate
                        
                        if cash >= cost + commission - 0.001:
                            cash -= (cost + commission)
                            position = size
                            position_price = close

                            # Bulletproof sanitation
                            safe_entries = {}
                            for k, v in current_indicators.items():
                                try:
                                    if isinstance(v, (int, float)):
                                        safe_entries[k] = float(v)
                                    elif isinstance(v, str) and v.replace(".", "", 1).isdigit():
                                        safe_entries[k] = float(v)
                                except Exception:
                                    pass
                                    
                            trades.append(Trade(
                                entry_time=timestamp, direction='long', entry_price=close, quantity=size,
                                entry_context=safe_entries
                            ))
                            if on_log: on_log(f"EXECUTED BUY: Open Long {size:.4f} @ {close:.2f}")
                
                elif signal == 'sell':
                    if position > 0:  # 平多仓
                        pnl = (close - position_price) * position
                        commission = position * close * config.commission_rate
                        cash += position * close - commission
                        if trades and not trades[-1].is_closed:
                            trades[-1].exit_time = timestamp
                            trades[-1].exit_price = close
                            trades[-1].pnl = pnl - commission - abs(position) * position_price * config.commission_rate
                            trades[-1].is_closed = True
                        if on_log: on_log(f"EXECUTED SELL: Closed Long @ {close:.2f}, PnL: {pnl - commission:.2f}")
                        position = 0
                    
                    if position == 0 and cash > 0:  # 开空仓
                        target_equity = cash * config.position_size_pct
                        size = target_equity / (close * (1 + config.commission_rate))
                        # 开空仓：借入股票卖出，获得现金
                        proceeds = size * close
                        commission = proceeds * config.commission_rate
                        cash += proceeds - commission
                        position = -size  # 负数表示空仓
                        position_price = close

                        # Bulletproof sanitation
                        safe_entries = {}
                        for k, v in current_indicators.items():
                            try:
                                if isinstance(v, (int, float)):
                                    safe_entries[k] = float(v)
                                elif isinstance(v, str) and v.replace(".", "", 1).isdigit():
                                    safe_entries[k] = float(v)
                            except Exception:
                                pass
                                
                        trades.append(Trade(
                            entry_time=timestamp, direction='short', entry_price=close, quantity=size,
                            entry_context=safe_entries
                        ))
                        if on_log: on_log(f"EXECUTED SELL: Open Short {size:.4f} @ {close:.2f}")
            
            # Close final
            if position != 0:
                final_bar = data[-1]
                close = final_bar.get('close', 0)
                timestamp = final_bar.get('timestamp', len(data))
                if position > 0: pnl = (close - position_price) * position
                else: pnl = (position_price - close) * abs(position)
                commission = abs(position) * close * config.commission_rate
                cash += position * close - commission
                if trades and not trades[-1].is_closed:
                    trades[-1].exit_time = timestamp; trades[-1].exit_price = close; trades[-1].pnl = pnl - commission - abs(position) * position_price * config.commission_rate; trades[-1].is_closed = True

            final_equity = cash
            equity_curve[-1].cash = final_equity
            equity_curve[-1].equity = final_equity
            equity_curve[-1].position_value = 0.0
            metrics = BacktestResult.calculate_metrics(trades, equity_curve, config.initial_capital)
            metrics.buy_signals_count = buy_signals_count
            metrics.sell_signals_count = sell_signals_count
            
            # Log completion
            if on_log: 
                on_log(f"Execution complete! Buy signals: {buy_signals_count}, Sell signals: {sell_signals_count}, Trades: {len(trades)}")
            
            result = BacktestResult(
                success=True,
                initial_capital=config.initial_capital,
                commission_rate=config.commission_rate,
                final_equity=final_equity,
                trades=[t.model_dump() for t in trades],
                equity_curve=[e.model_dump() for e in equity_curve],
                metrics=metrics.model_dump(),
                start_time=equity_curve[0].timestamp,
                end_time=equity_curve[-1].timestamp,
                bars_processed=len(data)
            )
            return {"result": result.model_dump()}
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "result": BacktestResult(
                    success=False, error=str(e), initial_capital=config.initial_capital, commission_rate=config.commission_rate
                ).model_dump()
            }
