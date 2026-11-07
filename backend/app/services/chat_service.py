from typing import AsyncGenerator, Dict, Any, List, Optional
import json
import logging
import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.core.session_manager import get_session_manager
from app.nodes.impl.agent.main_router import MainRouterNode
from app.nodes.base import Context
from app.nodes.impl.tool.llm.agent_executor_node import AgentExecutorNode
from app.nodes.impl.tool.storage.save_strategy_node import SaveStrategyNode
# Import other tools as needed

logger = logging.getLogger(__name__)

class ChatService:
    """
    Service to handle chat interactions, routing, and tool execution.
    Designed for Streaming (SSE) with async wrappers for sync nodes.
    """
    def __init__(self):
        self.session_manager = get_session_manager()
        self.router = MainRouterNode()
        self.executor_pool = ThreadPoolExecutor(max_workers=4)

    async def _run_sync_node_streaming(self, node, ctx: Context) -> AsyncGenerator[Dict[str, Any], Any]:
        """
        Run a synchronous node in a thread, capturing status updates via queue.
        Yields {"type": "status", "content": ...} events.
        Returns result as the return value of the generator (not yielded).
        """
        q = queue.SimpleQueue()
        
        def status_callback(msg):
            q.put(msg)
            
        ctx.on_status_update = status_callback
        
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self.executor_pool, node.run, ctx)
        
        while not future.done():
            # Drain queue
            while not q.empty():
                msg = q.get()
                if isinstance(msg, dict) and msg.get("type") in ["think", "status", "token"]:
                    yield msg
                else:
                    yield {"type": "status", "content": msg}
            await asyncio.sleep(0.05)
            
        # Drain remaining
        while not q.empty():
             msg = q.get()
             if isinstance(msg, dict) and msg.get("type") in ["think", "status", "token"]:
                 yield msg
             else:
                 yield {"type": "status", "content": msg}
             
        # Return result (to be caught by caller)
        # Note: In async generators, 'return' is only accessible via StopAsyncIteration.value
        # But here we are yielding dicts. We need a way to pass the final result.
        # We will yield a special internal event for result, or changing signature.
        # Let's change strategy: This method yields status events, and lastly yields the result wrapped.
        
        try:
            result = await future
            yield {"type": "__internal_result__", "data": result}
        except Exception as e:
            logger.error(f"Node execution failed: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}

    async def process_message(
        self, 
        session_id: str, 
        user_message: str, 
        layer: str = "offline",
        mode: str = "auto",
        model: str = "glm-4-flash",
        client_context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message:
        1. Persist User Msg.
        2. Run MainRouterNode.
        3. Persist System Response.
        4. If Tool Call -> Execute Tool and stream progress.
        """
        if client_context is None:
            client_context = {}

        # 1. Persist User Message
        await self.session_manager.add_chat_message(session_id, "user", user_message)
        yield {"type": "status", "content": "Thinking..."}

        # 2. Prepare Context (History)
        raw_history = await self.session_manager.get_chat_history(session_id, limit=20)
        formatted_history = [{"role": m.role, "content": m.content} for m in raw_history]

        # 3. Execution Context
        # Note: We create a unique run_id for this interaction
        run_id = f"run_{int(datetime.utcnow().timestamp())}"
        
        ctx = Context(
            run_id=run_id,
            workflow_id=f"chat_{session_id}",
            node_id="main_router",
            inputs={
                "message": user_message,
                "session_id": session_id,
                "layer": layer,
                "mode": mode,
                "model": model, # Pass model to router (for future use/logging)
                "client_context": client_context,
                "history": formatted_history
            }
        )

        try:
            # 4. Run Router (Async Execution with Streaming)
            # We use _run_sync_node_streaming to offload to thread and capture status/thinking
            result = None
            async for event in self._run_sync_node_streaming(self.router, ctx):
                if event["type"] == "__internal_result__":
                    result = event["data"]
                else:
                    yield event
            
            # Defensive check: router.run should always return a dict
            if result is None:
                logger.error("MainRouterNode.run returned None! Possible internal error.")
                yield {"type": "error", "content": "Internal error: Router returned no response. Check backend logs."}
                return
            
            response_text = result.get("response", "")
            source = result.get("source", "unknown")
            tool_args = result.get("tool_args", {})

            # 5. Persist Assistant Response
            await self.session_manager.add_chat_message(session_id, "assistant", response_text, source=source)
            
            # Yield Initial Response
            yield {
                "type": "message", 
                "source": source, 
                "content": response_text
            }

            # 6. Tool Execution Logic
            if source.startswith("tool:"):
                tool_name = source.split(":")[1]
                yield {"type": "tool_call", "name": tool_name, "args": tool_args}
                
                if tool_name.startswith("build_"):
                   async for event in self._handle_build_tool(session_id, tool_name, tool_args, mode, model, client_context):
                       yield event
                       
                elif tool_name == "run_backtest":
                   async for event in self._handle_run_backtest_tool(session_id, tool_args, client_context):
                       yield event

                elif tool_name == "save_strategy":
                   async for event in self._handle_save_tool(session_id, tool_args, client_context):
                       yield event
                

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            yield {"type": "error", "content": str(e)}

    async def _handle_build_tool(self, session_id, tool_name, tool_args, mode, model, client_context):
        """Handle build_strategy / build_workflow using Graph Executor."""
        instruction = tool_args.get("instruction", "Generate default")
        
        # 1. Determine Graph to Run
        graph_name = "build_strategy"
        if tool_name == "build_workflow":
            graph_name = "build_workflow"
        elif mode == "think" and tool_name == "build_strategy":
            graph_name = "analyze_strategy"
            yield {"type": "status", "content": f"🧠 Think Mode: Switching to {graph_name}..."}
        
        yield {"type": "status", "content": f"Loading Graph: {graph_name}..."}

        try:
            # 2. Load Graph Definition
            from app.core.graph_loader import GraphLoader
            graph_def = GraphLoader.load_graph(graph_name)
            
            # 3. Instantiate Graph Executor
            from app.nodes.impl.engine.graph_executor import GraphExecutorNode
            executor = GraphExecutorNode()
            
            # 4. Prepare Inputs
            # Map standard inputs expected by the graph's structure.input nodes
            asset_type = tool_args.get("asset_type", "us_stock")  # Default to US stocks
            graph_inputs = {
                "prompt": instruction,
                "current_graph": client_context.get("current_graph_dag", client_context.get("last_graph_dag", {})), # Injected context
                "session_id": session_id,
                "model": model,  # Maybe passed to internal nodes via some config?
                "asset_type": asset_type,  # Pass asset type for data source selection
                "backtest_results": client_context.get("backtest_results"),  # For optimization mode
                # Note: valid graph.yaml uses ${sys_prompt} etc via `init_msgs` variables, which get data from inputs?
                # Let's check graph.yaml: 
                #   - in_prompt (structure.input) -> inputs['prompt']
                #   - in_graph (structure.input) -> inputs['current_graph']
            }
            
            tool_ctx = Context(
                run_id=f"graph_{int(datetime.utcnow().timestamp())}",
                workflow_id=f"wf_{graph_name}",
                node_id="graph_exec",
                inputs={
                    "graph": graph_def,
                    "inputs": graph_inputs
                }
            )
            
            # 5. Run with Streaming
            res = {}
            async for event in self._run_sync_node_streaming(executor, tool_ctx):
                if event["type"] == "__internal_result__":
                    res = event["data"] # GraphExecutorOutput(outputs=..., trace=...)
                else:
                    yield event
            
            # 6. Process Outputs
            # GraphExecutor returns {"outputs": {...}, "execution_trace": [...]}
            outputs = res.get("outputs", {})  # From structure.output nodes
            
            if outputs.get("success"):
                dag = outputs.get("dag", {})
                feedback = outputs.get("feedback", "")
                
                # Log for Fine-tuning
                await self.session_manager.log_generation_trace(
                    session_id, instruction, True, res.get("execution_trace", [])
                )
                
                yield {
                    "type": "graph_generated",
                    "dag": dag,
                    "final_answer": feedback or "Strategy generated successfully via GraphExecutor."
                }
            else:
                # If explicit failure output or exception caught in trace
                error_msg = outputs.get("feedback") or "Execution failed without feedback."
                yield {"type": "error", "content": f"Graph execution failed: {error_msg}"}
                
        except Exception as e:
             logger.error(f"Graph execution error: {e}", exc_info=True)
             yield {"type": "error", "content": f"Executor failed: {str(e)}"}

    async def _handle_run_backtest_tool(self, session_id, tool_args, client_context):
        """Handle run_backtest request"""
        yield {"type": "status", "content": "Initializing Backtest Engine..."}
        
        # 1. Get Strategy Graph
        dag = client_context.get("current_graph_dag")
        if not dag or not dag.get("nodes"):
            yield {"type": "error", "content": "No strategy graph found to backtest."}
            return

        # 2. Fetch Historical Data (Auto-detected from graph or default)
        # 2. Fetch Historical Data (Auto-detected from graph or default)
        nodes = dag.get("nodes", [])
        
        # Determine data source from graph
        fetch_stock_node = next((n for n in nodes if n["type"] == "data.fetch_stock"), None)
        fetch_crypto_node = next((n for n in nodes if n["type"] == "data.fetch_crypto"), None)
        
        # Default to BTC/USDT if no node found
        symbol = "BTC/USDT"
        market = "crypto" # internal flag
        timeframe = "1h"
        limit = 1000
        
        if fetch_stock_node:
            symbol = fetch_stock_node.get("data", {}).get("symbol", "AAPL")
            market = fetch_stock_node.get("data", {}).get("market", "us")
            timeframe = fetch_stock_node.get("data", {}).get("timeframe", "1d")
            limit = fetch_stock_node.get("data", {}).get("limit", limit)
        elif fetch_crypto_node:
            symbol = fetch_crypto_node.get("data", {}).get("symbol", symbol)
            # market implicitly crypto or exchange id
            timeframe = fetch_crypto_node.get("data", {}).get("timeframe", timeframe)
            limit = fetch_crypto_node.get("data", {}).get("limit", limit)
            
        yield {"type": "status", "content": f"Fetching historical data for {symbol} ({timeframe})..."}
        
        # 3. Fetch Data
        try:
            data = []
            if fetch_stock_node:
                from app.nodes.impl.data.fetch_stock import FetchStockNode
                fetcher = FetchStockNode()
                fetch_ctx = Context(
                    run_id="fetch_data", workflow_id="bt", node_id="fetcher",
                    inputs={"symbol": symbol, "market": market, "timeframe": timeframe, "limit": limit}
                )
                fetch_out = fetcher.run(fetch_ctx)
                data = fetch_out.get("data", [])
            else:
                # Default to Crypto logic
                from app.nodes.impl.data.fetch_crypto import FetchCryptoNode
                fetcher = FetchCryptoNode()
                fetch_ctx = Context(
                    run_id="fetch_data", workflow_id="bt", node_id="fetcher",
                    inputs={"symbol": symbol, "timeframe": timeframe, "limit": limit}
                )
                fetch_out = fetcher.run(fetch_ctx)
                data = fetch_out.get("data", [])
            
            if not data:
                yield {"type": "error", "content": f"Failed to fetch data for {symbol}"}
                return
                
            yield {"type": "status", "content": f"Loaded {len(data)} bars. Running Simulation..."}
            
            # 4. Run Backtest
            from app.nodes.impl.backtest.result import BacktestResult
            from app.nodes.impl.backtest.runner import BacktestRunnerNode, BacktestConfig
            
            runner = BacktestRunnerNode()
            config = BacktestConfig(initial_capital=10000.0)
            
            # Filter out fetch nodes from DAG for execution (runner assumes input data is passed)
            # Actually runner handles it, but safer to keep strategy logic only
            # logic nodes, indicators etc.
            
            run_ctx = Context(
                run_id=f"bt_{int(datetime.utcnow().timestamp())}", 
                workflow_id="bt", 
                node_id="runner",
                inputs={
                    "data": data,
                    "strategy_dag": dag,
                    "config": config
                }
            )
            
            result = runner.run(run_ctx)
            bt_result = result.get("result", {})
            
            if bt_result.get("success"):
                bt_result = json.loads(BacktestResult.model_validate(bt_result).model_dump_json())
                metrics = bt_result.get("metrics", {})
                ret = metrics.get("total_return", 0)
                yield {
                    "type": "result", # TODO: Use a specific "backtest_result" event?
                    "content": f"Backtest Completed. Return: {ret:.2f}%",
                    "data": bt_result # Frontend expects this in 'data' field
                }
                # Also yield final answer text
                yield {
                    "type": "message",
                    "source": "tool:run_backtest",
                    "content": f"Backtest completed successfully.\n\n**Results:**\n- Total Return: {ret:.2f}%\n- Trades: {metrics.get('total_trades')}\n- Win Rate: {metrics.get('win_rate', 0):.1f}%\n"
                }
            else:
                yield {"type": "error", "content": f"Backtest failed: {bt_result.get('error')}"}

        except Exception as e:
            logger.error(f"Backtest error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Backtest execution error: {str(e)}"}

    async def _handle_save_tool(self, session_id, tool_args, client_context):
        """Handle save_strategy request"""
        # Note: In API mode, Client Context must contain the graph to save
        # Because Backend is stateless.
        # Use `client_context.get('last_graph_dag')` if passed.
        # IF client didn't pass it, we can't save.
        
        graph_data = client_context.get("last_graph_dag") or client_context.get("current_graph_dag")
        code = client_context.get("current_graph_code")
        name = tool_args.get("name", "Untitled")

        if not graph_data:
            yield {"type": "error", "content": "Cannot save: No graph data provided in client context."}
            return

        saver = SaveStrategyNode()
        save_ctx = Context(
            run_id=f"save_{int(datetime.utcnow().timestamp())}", 
            workflow_id="ops", 
            node_id="saver",
            inputs={"name": name, "graph_data": graph_data, "code": code}
        )
        
        res = saver.run(save_ctx)
        if res.get("success"):
            yield {
                "type": "result", 
                "content": f"Saved {name} (ID: {res.get('strategy_id')})",
                "data": res
            }
        else:
            yield {"type": "error", "content": res.get("message")}

chat_service = ChatService()
