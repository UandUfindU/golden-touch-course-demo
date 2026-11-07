from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import logging

from app.services.execution_service import execution_service
from app.core.config import settings

router = APIRouter(prefix="/backtest", tags=["Execution"])
logger = logging.getLogger(__name__)

class BacktestRunRequest(BaseModel):
    session_id: str
    graph_json: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None  # Optional overrides (symbol, timeframe, limit)

class OptimizeRequest(BaseModel):
    """Request for strategy optimization based on backtest results."""
    session_id: str
    graph_json: Dict[str, Any]  # Current strategy graph (will be converted to Python)
    backtest_results: Dict[str, Any]  # Complete backtest metrics
    optimization_prompt: Optional[str] = "请根据回测结果优化这个策略"
    model: str = settings.LLM_DEFAULT_MODEL  # LLM model to use

@router.post("/run")
async def run_backtest(req: BacktestRunRequest):
    """
    Execute a backtest. Returns SSE stream with progress and results.
    """
    async def event_generator():
        try:
            async for event in execution_service.execute_backtest(
                session_id=req.session_id,
                graph_json=req.graph_json,
                config=req.config
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Backtest Stream Error: {e}")
            err_event = {"type": "error", "content": "Internal Execution Error"}
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/optimize")
async def optimize_strategy(req: OptimizeRequest):
    """
    Optimize strategy based on backtest results.
    Directly executes the 'build_strategy' graph with an ENRICHED prompt containing backtest context.
    """
    async def event_generator():
        try:
            from app.core.graph_loader import GraphLoader
            from app.nodes.impl.engine.graph_executor import GraphExecutorNode
            from app.nodes.base import Context
            from starlette.concurrency import run_in_threadpool
            import time
            
            # --- 1. Construct Enriched Prompt (Non-Invasive) ---
            bt = req.backtest_results or {}
            
            # Format metrics into a clear table/list
            metrics_summary = f"""
## Previous Backtest Analysis
| Metric | Value | Evaluation |
|--------|-------|------------|
| Sharpe Ratio | {bt.get('sharpe_ratio', 0):.2f} | {'⚠️ Low' if bt.get('sharpe_ratio', 0) < 1.0 else '✅ Good'} |
| Max Drawdown | {bt.get('max_drawdown', 0):.1f}% | {'⚠️ High' if bt.get('max_drawdown', 0) > 20 else '✅ Acceptable'} |
| Win Rate | {bt.get('win_rate', 0):.1f}% | {'⚠️ Low' if bt.get('win_rate', 0) < 50 else '✅ Good'} |
| Total Trades | {bt.get('total_trades', 0)} | {'⚠️ Too Few' if bt.get('total_trades', 0) < 5 else '✅ Normal'} |
| Buy Signals | {bt.get('buy_signals_count', 0)} | - |
| Sell Signals | {bt.get('sell_signals_count', 0)} | {'⚠️ None' if bt.get('sell_signals_count', 0) == 0 else '-'} |
"""
            
            optimization_suggestions = []
            if bt.get('sharpe_ratio', 0) < 1.0:
                optimization_suggestions.append("- Low Sharpe Ratio: Adjust entry threshold for higher precision.")
            if bt.get('max_drawdown', 0) > 20:
                optimization_suggestions.append("- High Drawdown: Add stop-loss conditions (e.g., price < entry * 0.95).")
            if bt.get('win_rate', 0) < 50:
                optimization_suggestions.append("- Low Win Rate: Add filter conditions (e.g., trend confirmation).")
            if bt.get('total_trades', 0) < 5:
                optimization_suggestions.append("- Too Few Trades: Relax entry conditions.")
            if bt.get('sell_signals_count', 0) == 0:
                optimization_suggestions.append("- No Sell Signals: Ensure signal.sell() conditions are reachable.")

            suggestions_text = "\n".join(optimization_suggestions) if optimization_suggestions else "- Strategy looks good. consider fine-tuning parameters."

            # Combine into a single rich prompt with STRICT constraints
            enriched_prompt = f"""
{req.optimization_prompt}

{metrics_summary}

## Optimization Suggestions
Based on the metrics above, please rewrite the strategy code:
{suggestions_text}

## ⚠️ MANDATORY RULES
1. Output ONLY the Strategy DSL code (data.*, indicator.*, signal.*).
2. DO NOT output JSON, Dictionary, or raw Python functions.
3. DO NOT use 'engine.graph_executor' or any external libraries.
4. **NO UNDEFINED VARIABLES**: If you use `trend_condition = ma20 > ma50`, you MUST define `ma20 = indicator.ma(...)` and `ma50 = indicator.ma(...)` BEFORE using them.
5. Ensure all conditions connect to `signal.buy` or `signal.sell`.
6. **REMOVE UNUSED CODE**: Do not define variables or conditions that are never used. Unused nodes cause validation errors.
"""
            
            # --- 2. Load Graph & Prepare Inputs ---
            graph_def = GraphLoader.load_graph("build_strategy")
            
            graph_inputs = {
                "prompt": enriched_prompt,  # Pass enriched prompt here
                "current_graph": req.graph_json,
                "asset_type": "us_stock",
                "model": req.model  # Pass model to graph
            }
            
            ctx = Context(
                run_id=f"opt_{int(time.time())}",
                workflow_id="wf_optimize",
                node_id="graph_exec",
                inputs={
                    "graph": graph_def,
                    "inputs": graph_inputs
                }
            )
            
            yield f"data: {json.dumps({'type': 'status', 'content': 'Starting optimization with backtest context...'})}\n\n"
            
            # --- 3. Execute Graph ---
            executor = GraphExecutorNode()
            result = await run_in_threadpool(executor.run, ctx)
            
            # --- 4. Handle Output ---
            outputs = result.get("outputs", {})
            
            if outputs.get("success"):
                dag = outputs.get("dag", {})
                yield f"data: {json.dumps({'type': 'graph_generated', 'dag': dag})}\n\n"
                yield f"data: {json.dumps({'type': 'message', 'content': 'Strategy optimized successfully.'})}\n\n"
            else:
                feedback = outputs.get("feedback") or "Optimization failed."
                yield f"data: {json.dumps({'type': 'error', 'content': feedback})}\n\n"
                
        except Exception as e:
            logger.error(f"Optimization Error: {e}", exc_info=True)
            err_event = {"type": "error", "content": f"Optimization failed: {str(e)}"}
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
