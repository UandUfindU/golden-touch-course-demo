
import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.graph_loader import GraphLoader
from app.nodes.impl.engine.graph_executor import GraphExecutorNode
from app.nodes.registry import registry

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_load_build_strategy():
    print("--- Testing GraphLoader: build_strategy ---")
    try:
        graph_def = GraphLoader.load_graph("build_strategy")
        print("✅ Graph loaded successfully.")
        
        # Check system prompt resolution
        nodes = graph_def.get("nodes", [])
        prompt_fmt_node = next((n for n in nodes if n["id"] == "prompt_fmt"), None)
        if prompt_fmt_node:
            tpl = prompt_fmt_node["data"].get("template", "")
            if "## STRICT SYNTAX RULES" in tpl:
                print("✅ System prompt resolved correctly (found strict rules).")
            else:
                print(f"❌ System prompt resolution failed. Content starts with: {tpl[:50]}...")
        else:
            print("❌ prompt_fmt node not found.")
            
        return graph_def
    except Exception as e:
        print(f"❌ Load failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_graph_validation(graph_def):
    print("\n--- Testing GraphExecutor: Validation ---")
    if not graph_def:
        return
        
    executor = GraphExecutorNode()
    try:
        G = executor._build_nx_graph(graph_def)
        print(f"✅ NetworkX Graph built. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
        
        executor._validate_graph(G)
        print("✅ Graph validation passed (DAG check).")
        
        # Check output mappings
        retry_node = next((n for n in graph_def["nodes"] if n["id"] == "retry"), None)
        if retry_node:
            print(f"✅ Retry Node found: {retry_node['type']}")
            # Check edges from retry
            retry_edges = [e for e in graph_def["edges"] if e["source"] == "retry"]
            for e in retry_edges:
                print(f"   Edge: retry[{e['source_port']}] -> {e['target']}[{e['target_port']}]")
                
            # Verify we have edges for dag, success, feedback
            ports = {e["source_port"] for e in retry_edges}
            expected = {"dag", "success", "feedback"}
            if expected.issubset(ports):
                 print("✅ Retry node outputs (dag, success, feedback) are all mapped.")
            else:
                 print(f"❌ Missing output mappings from retry node. Found: {ports}")
        else:
             print("❌ Retry node not found!")
             
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    g = test_load_build_strategy()
    test_graph_validation(g)
