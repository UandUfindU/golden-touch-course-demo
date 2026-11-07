"""
DAGtoPythonNode - Converts DAG JSON to Python pseudo-code.

Used for Context Injection - making the graph readable by LLM.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class DAGtoPythonInput(BaseModel):
    """Input schema for DAGtoPythonNode."""
    dag: Dict[str, Any] = Field(
        description="DAG definition with 'nodes' and 'edges' keys"
    )


class DAGtoPythonOutput(BaseModel):
    """Output schema for DAGtoPythonNode."""
    python_code: str = Field(description="Python pseudo-code representation")
    node_count: int = Field(description="Number of nodes in graph")


@register_node(
    category=NodeCategory.FLOW,
    name="engine.dag_to_python",
    scopes=[NodeScope.WORKFLOW, NodeScope.TOOL]
)
class DAGtoPythonNode(BaseNode):
    """
    DAG to Python Node - Converts graph JSON to readable Python code.
    
    Output format:
    ```python
    # Node: n1 (data.fetch_kline)
    data = fetch_kline(symbol="BTC/USDT", interval="1d")
    
    # Node: n2 (logic.ma)
    ma20 = ma(source=data, period=20)
    ```
    """
    description = "Convert DAG JSON to Python pseudo-code"
    InputSchema = DAGtoPythonInput
    OutputSchema = DAGtoPythonOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        dag = params.dag
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])
        
        if not nodes:
            return {"python_code": "# Empty graph", "node_count": 0}
        
        # Build edge mapping: target_node -> list of (source_node, source_port, target_port)
        edge_map: Dict[str, List[tuple]] = {n["id"]: [] for n in nodes}
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            src_port = edge.get("source_port", "output")
            tgt_port = edge.get("target_port", "input")
            if tgt in edge_map:
                edge_map[tgt].append((src, src_port, tgt_port))
        
        # Build node output variable names
        node_vars: Dict[str, str] = {}
        for node in nodes:
            nid = node.get("id")
            node_type = node.get("type", "unknown")
            # Generate variable name from node type
            var_name = node_type.split(".")[-1]  # e.g., "logic.ma" -> "ma"
            # Handle duplicates
            base_var = var_name
            counter = 1
            while var_name in node_vars.values():
                var_name = f"{base_var}_{counter}"
                counter += 1
            node_vars[nid] = var_name
        
        # Generate code
        lines = ["# Auto-generated from DAG", ""]
        
        # Sort by topological order (simple: by number of incoming edges)
        sorted_nodes = sorted(nodes, key=lambda n: len(edge_map[n["id"]]))
        
        for node in sorted_nodes:
            nid = node.get("id")
            node_type = node.get("type", "unknown")
            node_data = node.get("data", {})
            var_name = node_vars[nid]
            
            # Skip input/output nodes
            if node_type in ("core.input", "core.output"):
                lines.append(f"# {node_type}: {nid}")
                continue
            
            # Build function call
            func_name = node_type.split(".")[-1]
            
            # Collect arguments
            args = []
            
            # 1. Arguments from edges (upstream connections)
            for src_id, src_port, tgt_port in edge_map[nid]:
                src_var = node_vars.get(src_id, src_id)
                if src_port != "output":
                    args.append(f"{tgt_port}={src_var}['{src_port}']")
                else:
                    args.append(f"{tgt_port}={src_var}")
            
            # 2. Static arguments from node data
            for key, value in node_data.items():
                if isinstance(value, str):
                    args.append(f'{key}="{value}"')
                else:
                    args.append(f"{key}={value}")
            
            args_str = ", ".join(args)
            lines.append(f"# Node: {nid} ({node_type})")
            lines.append(f"{var_name} = {func_name}({args_str})")
            lines.append("")
        
        python_code = "\n".join(lines)
        
        return {
            "python_code": python_code,
            "node_count": len(nodes)
        }
