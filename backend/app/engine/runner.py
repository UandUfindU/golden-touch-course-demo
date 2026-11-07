from typing import Dict, Any, List
from uuid import UUID
import networkx as nx
from redis.asyncio import Redis

from app.models.workflow import Workflow
from app.models.run import WorkflowRun
from app.engine.context import ContextManager
from app.nodes.registry import registry
from app.nodes.base import Context
from app.core.enums import RunStatus

class GraphRunner:
    """
    Executes a Workflow DAG.
    """
    def __init__(self, workflow: Workflow, run_id: UUID, redis: Redis):
        self.workflow = workflow
        self.run_id = str(run_id)
        self.redis = redis
        self.context_mgr = ContextManager(self.run_id, redis)
        self.graph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        """Parse workflow.graph_data into a NetworkX graph"""
        G = nx.DiGraph()
        data = self.workflow.graph_data
        
        # Add Nodes
        for node in data.get("nodes", []):
            G.add_node(node["id"], **node)
            
        # Add Edges
        for edge in data.get("edges", []):
            G.add_edge(edge["source"], edge["target"], **edge)
            
        return G

    async def execute(self):
        """Execute the graph"""
        # 1. Initialize Context
        # TODO: Load initial inputs if any
        
        # 2. Update Run Status
        await self.context_mgr.set_var("_status", RunStatus.RUNNING)
        
        # 3. Topological Sort (for DAGs)
        # TODO: Handle Cycles (Event-Loop) later. For v0.0.1 assume DAG.
        try:
            execution_order = list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # Cycle detected
            await self.context_mgr.set_var("_error", "Cycle detected in DAG")
            await self.context_mgr.set_var("_status", RunStatus.FAILED)
            raise ValueError("Cycle detected in Workflow Graph")

        # 4. Execute Nodes
        for node_id in execution_order:
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type") # e.g. "logic.if" or unique_key
            
            # Instantiate Node
            try:
                node_instance = registry.get_node(node_type)
            except Exception as e:
                # Node not found
                print(f"Error instantiating node {node_type}: {e}")
                continue

            # Prepare Inputs
            # TODO: Resolve inputs from upstream outputs based on edges
            # For v0.0.1, we'll assume a global context passing or simple key matching
            current_context = await self.context_mgr.get_context()
            
            # Construct Execution Context
            ctx = Context(
                run_id=self.run_id,
                workflow_id=str(self.workflow.id),
                node_id=node_id,
                inputs=current_context, # Inject full state for now
                services={"redis": self.redis}
            )
            
            # Run Node
            print(f"Executing Node: {node_id} ({node_type})")
            try:
                outputs = node_instance.run(ctx)
                # Update Context with outputs
                await self.context_mgr.update_context(outputs)
            except Exception as e:
                print(f"Error executing node {node_id}: {e}")
                await self.context_mgr.set_var("_error", str(e))
                await self.context_mgr.set_var("_status", RunStatus.FAILED)
                raise e

        # 5. Complete
        await self.context_mgr.set_var("_status", RunStatus.COMPLETED)
        print("Workflow Execution Completed")
