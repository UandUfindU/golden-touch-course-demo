import logging
import networkx as nx
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node, registry, NodeRegistry  # Fix imports
from app.core.enums import NodeCategory, NodeScope, NodeRole
# Removed NodeFactory import

logger = logging.getLogger(__name__)

class GraphExecutorInput(BaseModel):
    """Input schema for Graph Executor."""
    graph: Dict[str, Any] = Field(..., description="DAG definition (nodes, edges)")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Inputs for the graph's InputNodes")

class GraphExecutorOutput(BaseModel):
    """Output schema for Graph Executor."""
    outputs: Dict[str, Any] = Field(..., description="Results from the graph's OutputNodes")
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step execution log")

@register_node(
    category=NodeCategory.STRUCTURE,
    name="engine.graph_executor",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class GraphExecutorNode(BaseNode):
    """
    Generic Graph Execution Engine.
    
    Takes a JSON DAG definition, topologically sorts it, and executes nodes sequentially.
    Handles data transfer between nodes based on edges.
    """
    InputSchema = GraphExecutorInput
    OutputSchema = GraphExecutorOutput
    
    def _build_nx_graph(self, graph_def: Dict[str, Any]) -> nx.MultiDiGraph:
        """Convert JSON graph to NetworkX MultiDiGraph.
        
        Uses MultiDiGraph to support multiple edges between the same pair of nodes,
        which is required when a node has multiple output ports connected to the same target.
        """
        G = nx.MultiDiGraph()
        
        for node in graph_def.get("nodes", []):
            G.add_node(node["id"], **node)
            
        for edge in graph_def.get("edges", []):
            G.add_edge(edge["source"], edge["target"], **edge)
            
        return G
    
    def _validate_graph(self, G: nx.DiGraph) -> None:
        """Validate graph structure."""
        if not nx.is_directed_acyclic_graph(G):
            # Find cycles for better error message
            try:
                cycles = list(nx.simple_cycles(G))
                raise ValueError(f"Graph contains cycles: {cycles}")
            except Exception:
                raise ValueError("Graph contains cycles (not a DAG)")
                
        # Check for isolated nodes? Optional. 
        # For now, we allow them but they might be useless.
        
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        graph_def = params.graph
        external_inputs = params.inputs
        
        # 1. Build and Validate NetworkX Graph
        G = self._build_nx_graph(graph_def)
        self._validate_graph(G)
        
        # 2. Topological Sort
        try:
            execution_order = list(nx.topological_sort(G))
        except Exception as e:
            raise ValueError(f"Topological sort failed: {str(e)}")
            
        logger.info(f"Graph execution order: {execution_order}")
        
        # 3. Execution State
        node_outputs: Dict[str, Dict[str, Any]] = {} # node_id -> output_dict
        trace: List[Dict[str, Any]] = []
        final_outputs: Dict[str, Any] = {}
        
        # 4. Instantiate all nodes first (optimization: or JIT)
        # We need instances to run them.
        node_instances: Dict[str, BaseNode] = {}
        node_map = {n["id"]: n for n in graph_def.get("nodes", [])}
        
        for node_id in execution_order:
            node_data = node_map.get(node_id)
            if not node_data:
                continue
                
            node_type = node_data.get("type")
            try:
                node_cls = NodeRegistry.get_node(node_type)
                node_instances[node_id] = node_cls() # Instantiate the node
            except ValueError:
                raise ValueError(f"Unknown node type '{node_type}' for node '{node_id}'")

        # 5. Execution Loop
        for node_id in execution_order:
            node_data = node_map[node_id]
            node_type = node_data["type"]
            node_instance = node_instances[node_id]
            
            # 5.1 Gather Inputs
            # Start with static configuration data
            current_inputs = node_data.get("data", {}).copy()
            
            # Inject external inputs if it's an InputNode
            if node_type == "structure.input":
                # Special handling: Map 'value' from external_inputs
                # The InputNode expects 'name' in its data.
                input_name = current_inputs.get("name")
                if input_name and input_name in external_inputs:
                    current_inputs["value"] = external_inputs[input_name]
            
            # Resolving incoming edges (Data Flow)
            # For MultiDiGraph, use keys=True to get all edges including duplicates
            in_edges = G.in_edges(node_id, data=True, keys=True)
            for src_id, _, edge_key, edge_attr in in_edges:
                source_port = edge_attr.get("source_port")
                target_port = edge_attr.get("target_port")
                
                # Get value from source node's previous output
                source_output = node_outputs.get(src_id, {})
                if source_port in source_output:
                    # Overwrite/Set input parameter
                    current_inputs[target_port] = source_output[source_port]
                    # [DEBUG] Log successful edge resolution
                    val = source_output[source_port]
                    val_len = len(str(val)) if val else 0
                    # print(f"[GraphExec] Edge: {src_id}.{source_port} -> {node_id}.{target_port} (len={val_len})")
                else:
                    # [DEBUG] Log missing port
                    # print(f"[GraphExec] MISSING: {src_id}.{source_port} not found! Available: {list(source_output.keys())}")
                    pass  # Commented out debug print
            
            # 5.2 Execute Node
            try:
                # Create a sub-context
                sub_ctx = Context(
                    run_id=ctx.run_id,
                    workflow_id=ctx.workflow_id,
                    node_id=f"{ctx.node_id}_{node_id}", # Hierarchical ID
                    inputs=current_inputs,
                    # Pass specific handlers if needed (e.g. status updates?)
                    on_status_update=ctx.on_status_update 
                )
                
                logger.debug(f"Executing node {node_id} ({node_type})...")
                result = node_instance.run(sub_ctx)
                node_outputs[node_id] = result
                
                trace.append({
                    "node_id": node_id,
                    "type": node_type,
                    "status": "success",
                    "inputs": str(current_inputs)[:200], # Trucate for log
                    "outputs": str(result)[:200]
                })
                
                # Check output handlers
                if node_type == "structure.output":
                    output_name = current_inputs.get("name", "result")
                    final_value = result.get("final_value")
                    final_outputs[output_name] = final_value
                    
            except Exception as e:
                import traceback
                traceback.print_exc() # FORCE PRINT TO STDOUT
                logger.error(f"Error executing node {node_id}: {str(e)}")
                trace.append({
                    "node_id": node_id,
                    "type": node_type,
                    "status": "failed",
                    "error": str(e)
                })
                raise RuntimeError(f"Execution failed at node '{node_id}' ({node_type}): {str(e)}")
        
        return {
            "outputs": final_outputs,
            "execution_trace": trace
        }
