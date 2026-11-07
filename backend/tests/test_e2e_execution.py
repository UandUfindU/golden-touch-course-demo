import sys
import os
import json
import logging
from dotenv import load_dotenv

# Setup Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Load Env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
load_dotenv(env_path)

from app.nodes.base import Context
from app.nodes.registry import NodeRegistry, register_node
from app.core.enums import NodeCategory, NodeScope
from app.nodes.impl.structure.composite_node import CompositeNode
from app.core.graph_persistence import GraphBundle

# Import all nodes to ensure registry is populated
import app.nodes.impl.data.fetch_crypto
import app.nodes.impl.indicator.ma_node
import app.nodes.impl.indicator.bollinger_node
import app.nodes.impl.logic.script_node
import app.nodes.impl.logic.graph_validator
import app.nodes.impl.tool.llm.llm_chat_node
import app.nodes.impl.tool.llm.response_parser_node
import app.nodes.impl.tool.llm.code_to_dag_node
import app.nodes.impl.tool.llm.tool_retriever_node
import app.nodes.impl.engine.graph_executor 
import app.nodes.impl.engine.dag_to_python
import app.nodes.impl.logic.prompt_formatter
import app.nodes.impl.flow.retry_node
import app.nodes.impl.structure.io_nodes
import app.nodes.impl.logic.structure_builder
import app.nodes.impl.logic.dict_builder

# Configure Logging
logging.basicConfig(level=logging.WARNING, format='%(message)s')

def load_standard_graphs():
    graphs_dir = os.path.join(os.path.dirname(__file__), '../graphs/standard')
    build_path = os.path.join(graphs_dir, 'build_strategy')
    if os.path.exists(build_path):
        try:
            NodeRegistry.get_node("standard.build_strategy")
        except ValueError:
            graph_def = GraphBundle.load(build_path)
            @register_node(category=NodeCategory.AI, name="standard.build_strategy", scopes=[NodeScope.TOOL])
            class BuildStrategyGraph(CompositeNode):
                 def __init__(self, **kwargs):
                    super().__init__(graph_definition=graph_def, **kwargs)

def main():
    print("==========================================")
    print("      E2E Test: Generate & Execute        ")
    print("==========================================")
    
    load_standard_graphs()
    
    # 1. GENERATE
    print("\n[Phase 1] Generatng Strategy...")
    prompt = "Create a simple strategy: Buy BTC/USDT if SMA(5) > SMA(20), otherwise Hold. Use 1h interval."
    print(f"Prompt: {prompt}")
    
    builder = NodeRegistry.get_node("standard.build_strategy")() # Compile/Instantiate
    
    ctx = Context(
        run_id="e2e_test", workflow_id="test", node_id="builder",
        inputs={
            "prompt": prompt,
            "current_graph": {"nodes": []}
        },
        on_status_update=lambda m: print(f"  [Build] {m}")
    )
    
    res = builder.run(ctx)
    success = res.get("success", False)
    dag = res.get("dag")
    
    if not success or not dag:
        print("❌ Generation Failed.")
        return

    print("✅ Generation Success!")
    node_count = len(dag.get("nodes", []))
    print(f"Generated DAG with {node_count} nodes.")
    
    # 2. EXECUTE
    print("\n[Phase 2] Executing Strategy...")
    
    try:
        # Instantiate the generated graph as a CompositeNode
        strategy_node = CompositeNode(graph_definition=dag)
        
        # Determine inputs? 
        # Usually strategy nodes might need inputs defined in the graph's 'structure.input'.
        # If the generated graph has inputs (e.g. data), we need to provide them.
        # But our strategies usually self-contain FETCH nodes (HEAD nodes).
        # Let's check input requirements.
        required_inputs = strategy_node.InputSchema.model_fields.keys() if hasattr(strategy_node, "InputSchema") else []
        print(f"Strategy requires inputs: {list(required_inputs)}")
        
        exec_ctx = Context(
            run_id="e2e_exec", workflow_id="test", node_id="strategy",
            inputs={}, # Assuming logic is self-contained or defaults
            on_status_update=lambda m: print(f"  [Exec] {m}")
        )
        
        exec_res = strategy_node.run(exec_ctx)
        
        print("\n✅ Execution Complete!")
        print("--- Result ---")
        print(json.dumps(exec_res, indent=2, default=str)[:1000] + "...") # Truncate
        
    except Exception as e:
        print(f"❌ Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
