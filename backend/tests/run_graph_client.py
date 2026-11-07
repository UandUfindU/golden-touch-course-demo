import sys
import os
import logging
import json
import asyncio
from dotenv import load_dotenv

# Setup Path: Add 'backend' to sys.path so 'app' can be imported
# Current file: backend/tests/run_graph_client.py
# Target: backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Load .env from backend/
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(env_path)
print(f"Loaded environment from {env_path}")

from app.nodes.base import Context
from app.nodes.registry import NodeRegistry, register_node
from app.core.enums import NodeCategory, NodeScope
from app.nodes.impl.structure.composite_node import CompositeNode
from app.core.graph_persistence import GraphBundle

# Import standard nodes to ensure registry population
import app.nodes.impl.logic.prompt_formatter
import app.nodes.impl.flow.retry_node
import app.nodes.impl.structure.io_nodes
import app.nodes.impl.logic.structure_builder
import app.nodes.impl.logic.dict_builder
import app.nodes.impl.logic.graph_validator
import app.nodes.impl.engine.graph_executor 
import app.nodes.impl.engine.dag_to_python
import app.nodes.impl.tool.llm.tool_retriever_node
import app.nodes.impl.tool.llm.llm_chat_node # Fixed Import
import app.nodes.impl.tool.llm.response_parser_node
import app.nodes.impl.tool.llm.code_to_dag_node
import app.nodes.impl.indicator.bollinger_node # Register Bollinger Bands
import app.nodes.impl.logic.script_node # Register Script Node

# Configure Logging (Hide Debug)
logging.basicConfig(level=logging.WARNING, format='%(message)s')

def load_standard_graphs():
    """Register standard graphs from bundles."""
    # graphs_dir is relative to backend root, or check relative to this script
    # backend/tests/../graphs/standard -> backend/graphs/standard
    graphs_dir = os.path.join(os.path.dirname(__file__), '../graphs/standard')
    
    # 1. Build Strategy
    build_path = os.path.join(graphs_dir, 'build_strategy')
    if os.path.exists(build_path):
        # Check if already registered to avoid warning
        try:
            NodeRegistry.get_node("standard.build_strategy")
            # print("ℹ️  standard.build_strategy already loaded.")
        except ValueError:
            graph_def = GraphBundle.load(build_path)
            @register_node(category=NodeCategory.AI, name="standard.build_strategy", scopes=[NodeScope.TOOL])
            class BuildStrategyGraph(CompositeNode):
                 def __init__(self, **kwargs):
                    super().__init__(graph_definition=graph_def, **kwargs)
            print("✅ Loaded standard.build_strategy")
    else:
        print(f"⚠️ Build Bundle not found at {build_path}")

    # 2. Analyze Strategy
    analyze_path = os.path.join(graphs_dir, 'analyze_strategy')
    if os.path.exists(analyze_path):
        try:
            NodeRegistry.get_node("standard.analyze_strategy")
        except ValueError:
            graph_def = GraphBundle.load(analyze_path)
            @register_node(category=NodeCategory.AI, name="standard.analyze_strategy", scopes=[NodeScope.TOOL])
            class AnalyzeStrategyGraph(CompositeNode):
                 def __init__(self, **kwargs):
                    super().__init__(graph_definition=graph_def, **kwargs)
            print("✅ Loaded standard.analyze_strategy")
    else:
        print(f"⚠️ Analyze Bundle not found at {analyze_path}")

def main():
    print("==========================================")
    print("      Golden Touch Graph Client (CLI)     ")
    print("==========================================")
    
    # Initialize
    load_standard_graphs()
    
    while True:
        print("\nSelect Mode:")
        print("1. Fast Mode (Direct Build)")
        print("2. Think Mode (Analysis + Build)")
        print("q. Quit")
        
        choice = input("Choice > ").strip().lower()
        if choice == 'q':
            break
            
        target_node = ""
        if choice == '1':
            target_node = "standard.build_strategy"
        elif choice == '2':
            target_node = "standard.analyze_strategy"
        else:
            print("Invalid choice.")
            continue
            
        prompt = input("\nEnter Strategy Description: ").strip()
        if not prompt:
            print("Prompt cannot be empty.")
            continue
            
        print(f"\n🚀 Launching {target_node}...")
        
        # Instantiate Node
        try:
            node_cls = NodeRegistry.get_node(target_node)
            node_instance = node_cls() # CompositeNode
        except Exception as e:
            print(f"❌ Error loading node: {e}")
            continue
            
        # Helper for status printing
        def _print_status(msg: str):
            # If message contains newlines (like validation errors), handle gracefully
            if "\n" in msg:
                lines = msg.split('\n')
                print(f"  [Status] {lines[0]}")
                for line in lines[1:]:
                    if line.strip():
                        print(f"           {line}")
            else:
                print(f"  [Status] {msg}")

        # Prepare Context
        ctx = Context(
            run_id="cli_run", workflow_id="cli", node_id="main",
            inputs={
                "prompt": prompt,
                "current_graph": {"nodes": []} # Assume empty start
            },
            on_status_update=_print_status
        )
        
        # Run
        try:
            res = node_instance.run(ctx)
            print("\n✅ Execution Complete!")
            print("--- Output ---")
            
            generated_dag = None
            if "dag" in res:
                generated_dag = res.get("dag")
                if generated_dag and isinstance(generated_dag, dict) and "nodes" in generated_dag:
                    node_count = len(generated_dag.get("nodes", []))
                    print(f"DAG Generated: {node_count} nodes.")
                else:
                    print(f"DAG Generated: None (Failed)")
            
            if "success" in res:
                print(f"Success: {res['success']}")

            # === Backtest Section ===
            if generated_dag:
                do_backtest = input("\nRun Backtest on this strategy? (y/n) > ").strip().lower()
                if do_backtest == 'y':
                    # Debug: Print DAG structure
                    import json
                    print("\n🔍 Generated DAG Structure (First 3 nodes + edges):")
                    nodes_preview = generated_dag.get('nodes', [])[:3]
                    edges_preview = generated_dag.get('edges', [])[:5]
                    print(f"  Nodes ({len(generated_dag.get('nodes', []))} total):")
                    for n in nodes_preview:
                        print(f"    - {n.get('id')}: {n.get('type')} | data: {n.get('data', {})}")
                    print(f"  Edges ({len(generated_dag.get('edges', []))} total): {edges_preview[:3]}...")
                    
                    print("\n📉 Preparing Backtest...")
                    try:
                        from app.nodes.impl.backtest.runner import BacktestRunnerNode
                        
                        # 1. Fetch Data (Synthetic or Real)
                        # For CLI demo, let's try to fetch real data using internal usage of FetchCryptoNode
                        # or just mock it if we don't want to depend on CCXT keys being perfectly set up
                        # Let's try to use CCXT via FetchCryptoNode if available
                        print("  [Data] Fetching 500 bars of BTC/USDT (1h)...")
                        from app.nodes.impl.data.fetch_crypto import FetchCryptoNode
                        data_node = FetchCryptoNode()
                        data_ctx = Context(run_id="data", workflow_id="cli", node_id="data", inputs={
                            "symbol": "BTC/USDT",
                            "timeframe": "1h",
                            "limit": 500,
                            "exchange": "binance"
                        })
                        data_res = data_node.run(data_ctx)
                        historical_data = data_res.get("data", [])
                        print(f"  [Data] {len(historical_data)} bars loaded.")
                        if data_res.get("error"):
                            print(f"  [Data] ⚠️ Fetch Error: {data_res.get('error')}")

                        # 2. Run Backtest
                        print("  [Backtest] Running simulation...")
                        runner = BacktestRunnerNode()
                        
                        bt_ctx = Context(
                            run_id="bt_run", workflow_id="cli", node_id="bt",
                            inputs={
                                "data": historical_data,
                                "strategy_dag": generated_dag,
                                "config": {
                                    "initial_capital": 10000.0,
                                    "commission_rate": 0.001
                                }
                            }
                        )
                        bt_res = runner.run(bt_ctx)
                        result = bt_res.get("result", {})
                        
                        if result.get("success"):
                            metrics = result.get("metrics", {})
                            print("\n📊 Backtest Results:")
                            print(f"  Return: {metrics.get('total_return', 0):.2f}%")
                            print(f"  Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
                            print(f"  Trades: {metrics.get('total_trades', 0)} ({metrics.get('win_rate', 0):.1f}% Win)")
                            print(f"  Max DD: {metrics.get('max_drawdown', 0):.2f}%")
                            print(f"  Final Equity: ${result.get('final_equity', 0):.2f}")
                        else:
                            print(f"\n❌ Backtest Failed: {result.get('error')}")

                    except Exception as bt_e:
                        print(f"\n❌ Backtest Error: {bt_e}")
                        import traceback
                        traceback.print_exc()

        except Exception as e:
            print(f"\n❌ Execution Failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
