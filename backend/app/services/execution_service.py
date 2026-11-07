from typing import Dict, Any, Optional, AsyncGenerator, List
import json
import logging
from datetime import datetime
import uuid

from app.core.session_manager import get_session_manager
from app.nodes.impl.backtest.result import BacktestResult
from app.nodes.impl.backtest.runner import BacktestRunnerNode
from app.nodes.impl.engine.graph_validator import validate_graph
from app.nodes.impl.data.fetch_crypto import FetchCryptoNode
from app.nodes.base import Context

logger = logging.getLogger(__name__)

class ExecutionService:
    """
    Service to handle strategy execution and backtesting.
    Enforces 'Validate -> Execute' lifecycle.
    """
    def __init__(self):
        self.session_manager = get_session_manager()

    def _fetch_data_from_graph(
        self,
        graph_json: Dict[str, Any],
        config_override: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Scan graph for data source nodes and fetch OHLCV data.
        Returns the historical data as a list of bars.
        """
        nodes = graph_json.get("nodes", [])
        
        # Determine data source from graph
        fetch_stock_node = next((n for n in nodes if n.get("type") == "data.fetch_stock"), None)
        fetch_crypto_node = next((n for n in nodes if n.get("type") == "data.fetch_crypto"), None)
        
        if not fetch_stock_node and not fetch_crypto_node:
            raise ValueError("Graph must contain a 'data.fetch_stock' or 'data.fetch_crypto' node for backtesting.")
        
        # Logic for Fetch Stock
        if fetch_stock_node:
            from app.nodes.impl.data.fetch_stock import FetchStockNode
            
            node_data = fetch_stock_node.get("data", {})
            
            symbol = config_override.get("symbol") if config_override else None
            symbol = symbol or node_data.get("symbol")
            
            if not symbol:
                raise ValueError(f"Missing 'symbol' in data.fetch_stock node. Node data: {node_data}")
            
            market = config_override.get("market") if config_override else None
            market = market or node_data.get("market", "us")
            
            timeframe = config_override.get("timeframe") if config_override else None
            timeframe = timeframe or node_data.get("timeframe", "1d")
            
            limit = config_override.get("limit") if config_override else None
            limit = limit or node_data.get("limit", 100)
            
            fetch_node = FetchStockNode()
            ctx = Context(
                run_id="data_fetch", workflow_id="backtest_prep", node_id="fetch",
                inputs={"symbol": symbol, "market": market, "timeframe": timeframe, "limit": limit}
            )
            result = fetch_node.run(ctx)
            if result.get("error"):
                raise ValueError(f"Stock Data fetch failed: {result.get('error')}")
            return result.get("data", []), {"symbol": symbol, "timeframe": timeframe}
            
        # Logic for Fetch Crypto
        else:
            data_node_def = fetch_crypto_node
            node_data = data_node_def.get("data", {})
            
            symbol = config_override.get("symbol") if config_override else None
            symbol = symbol or node_data.get("symbol", "BTC/USDT")
            
            timeframe = config_override.get("timeframe") if config_override else None
            timeframe = timeframe or node_data.get("timeframe", "1h")
            
            limit = config_override.get("limit") if config_override else None
            limit = limit or node_data.get("limit", 500)
            
            exchange = config_override.get("exchange") if config_override else None
            exchange = exchange or node_data.get("exchange", "binance")
            
            fetch_node = FetchCryptoNode()
            ctx = Context(
                run_id="data_fetch", workflow_id="backtest_prep", node_id="fetch",
                inputs={"symbol": symbol, "timeframe": timeframe, "limit": limit, "exchange": exchange}
            )
            result = fetch_node.run(ctx)
            
            if result.get("error"):
                raise ValueError(f"Crypto Data fetch failed: {result.get('error')}")
            
            return result.get("data", []), {"symbol": symbol, "timeframe": timeframe}

    async def execute_backtest(
        self,
        session_id: str,
        graph_json: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run a backtest for the given graph.
        Data is fetched automatically from graph's data source nodes.
        Returns streaming events (log, result).
        """
        import asyncio
        
        run_id = f"bt_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:4]}"
        
        yield {"type": "log", "content": f"Starting Backtest Run: {run_id}"}
        
        # 1. Validation Logic
        yield {"type": "log", "content": "Validating graph structure..."}
        validation = validate_graph(graph_json)
        
        if not validation.valid:
            error_msg = f"Graph Validation Failed: {validation.summary}"
            logger.warning(error_msg)
            yield {"type": "error", "content": error_msg}
            return

        yield {"type": "log", "content": "Graph validated successfully."}
        
        yield {"type": "status", "content": "正在获取历史行情"}
        try:
            loop = asyncio.get_running_loop()
            historical_data, market_info = await loop.run_in_executor(
                None, self._fetch_data_from_graph, graph_json, config
            )
            if not historical_data:
                raise ValueError("该标的没有返回历史行情")
            yield {"type": "log", "content": f"Loaded {len(historical_data)} bars of OHLCV data."}
        except Exception as e:
            yield {"type": "error", "content": f"历史行情获取失败：{e}"}
            return

        yield {"type": "status", "content": "正在模拟历史交易"}
        backtest_config = {
            "initial_capital": config.get("initial_capital", 10000.0) if config else 10000.0,
            "commission_rate": config.get("commission_rate", 0.001) if config else 0.001
        }

        runner = BacktestRunnerNode()
        
        # Setup Streaming Queue
        log_queue = asyncio.Queue()
        
        def on_log_callback(msg: str):
            loop.call_soon_threadsafe(log_queue.put_nowait, {"type": "log", "content": msg})
        
        ctx = Context(
            run_id=run_id,
            workflow_id="backtest_op",
            node_id="runner",
            inputs={
                "strategy_dag": graph_json,
                "data": historical_data,
                "config": backtest_config,
                "on_log": on_log_callback  # Pass callback
            }
        )
        
        try:
            run_future = loop.run_in_executor(None, runner.run, ctx)

            # Consume Queue while Runner runs
            while not run_future.done():
                try:
                    # Wait for log or timeout to check done status
                    # We use a short timeout to keep checking run_future status
                    event = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    continue
            
            # Clear remaining logs
            while not log_queue.empty():
                yield await log_queue.get()
            
            execution_output = await run_future
            result = BacktestResult.model_validate(execution_output["result"])
            if not result.success or result.metrics is None:
                yield {"type": "error", "content": result.error or "回测未生成有效指标"}
                return

            # Convert non-finite metrics to null before storing or streaming JSON.
            result_data = json.loads(result.model_dump_json())
            await self.session_manager.log_backtest_result(
                session_id=session_id,
                layer="offline",
                graph=graph_json,
                result=result_data
            )

            yield {"type": "result", "run_id": run_id, **result_data, **market_info}
            yield {"type": "log", "content": f"Backtest Finished. Sharpe: {result.metrics.sharpe_ratio:.2f}"}

        except Exception as e:
            logger.error(f"Backtest execution failed: {e}", exc_info=True)
            yield {"type": "error", "content": f"Runtime Error: {str(e)}"}

execution_service = ExecutionService()
