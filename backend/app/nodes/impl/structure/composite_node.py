from typing import Dict, Any, Type, List
from pydantic import BaseModel, create_model

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole
from app.nodes.impl.engine.graph_executor import GraphExecutorNode

@register_node(
    category=NodeCategory.STRUCTURE,
    name="structure.composite",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class CompositeNode(BaseNode):
    """
    Composite Node Wrapper.
    
    Encapsulates a sub-graph (DAG) and presents it as a single node.
    Dynamically generates Input/Output Schema based on the sub-graph's 
    'structure.input' and 'structure.output' nodes.
    """
    description = "Wraps a sub-graph as a single node"
    
    def __init__(self, graph_definition: Dict[str, Any]):
        self.graph_definition = graph_definition
        
        # 1. Dynamic Schema Generation
        input_fields = {}
        output_fields = {}
        
        self.inputs_map = {} # name -> node_id (optional optimization)
        
        for node in graph_definition.get("nodes", []):
            if node["type"] == "structure.input":
                # 'data': {'name': 'query', 'default_value': ...}
                name = node.get("data", {}).get("name")
                default = node.get("data", {}).get("default_value", ...)
                desc = node.get("data", {}).get("description", "")
                if name:
                    input_fields[name] = (Any, default)
                    
            elif node["type"] == "structure.output":
                 # 'data': {'name': 'report'}
                name = node.get("data", {}).get("name")
                desc = node.get("data", {}).get("description", "")
                if name:
                    output_fields[name] = (Any, ...)

        # Create Pydantic models dynamically
        self.InputSchema = create_model(
            "CompositeInput",
            **input_fields
        )
        self.OutputSchema = create_model(
            "CompositeOutput",
            **output_fields
        )
        
        # 2. Strict Validation (Fail fast)
        self._validate_subgraph()
        
    def _validate_subgraph(self):
        """Perform strict validation on the internal graph."""
        executor = GraphExecutorNode()
        # Use executor's build & validate logic
        try:
            G = executor._build_nx_graph(self.graph_definition)
            executor._validate_graph(G)
        except ValueError as e:
             raise ValueError(f"Invalid Sub-Graph definition: {str(e)}")
             
        # Check inputs/outputs existence
        has_input = any(n["type"] == "structure.input" for n in self.graph_definition.get("nodes", []))
        has_output = any(n["type"] == "structure.output" for n in self.graph_definition.get("nodes", []))
        
        if not has_output:
            raise ValueError("Composite Node must have at least one Output node.")
            
        # has_input is optional (e.g. self-contained source nodes)

    def run(self, ctx: Context) -> Dict[str, Any]:
        # 1. Validate inputs using dynamic schema
        # Note: BaseNode.validate_inputs expects self.InputSchema to be set
        params = self.validate_inputs(ctx.inputs)
        
        # 2. Prepare execution
        executor = GraphExecutorNode()
        
        # 3. internal inputs = ctx.inputs (filtered by schema model effectively)
        # GraphExecutor expects inputs={ 'query': '...', ... } which matches params.dict()
        execution_ctx = Context(
            run_id=ctx.run_id,
            workflow_id=ctx.workflow_id,
            node_id=f"{ctx.node_id}_inner",
            inputs={
                "graph": self.graph_definition,
                "inputs": params.dict()
            },
            on_status_update=ctx.on_status_update
        )
        
        # 4. Execute
        result = executor.run(execution_ctx)
        
        # 5. Result: {'outputs': {'report': ...}, 'execution_trace': ...}
        # We return the outputs directly to match OutputSchema
        return result.get("outputs", {})
