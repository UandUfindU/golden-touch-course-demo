"""
CompositeNode - Wraps a subgraph as a single node.

A CompositeNode stores a DAG JSON internally and executes it when run.
This enables:
1. Reusable workflow components
2. Official meta-tools as subgraphs
3. User-defined custom tools
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class CompositeNodeInput(BaseModel):
    """Input for CompositeNode - passed to the internal Input node."""
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inputs to pass to the subgraph's InputNode"
    )


class CompositeNodeOutput(BaseModel):
    """Output from CompositeNode - from the internal Output node."""
    outputs: Dict[str, Any] = Field(description="Outputs from the subgraph")
    success: bool = Field(description="Whether execution succeeded")
    error: Optional[str] = Field(default=None, description="Error if failed")


class CompositeNodeFactory:
    """
    Factory to create CompositeNode classes from subgraph JSON.
    
    Each created node class has the subgraph embedded and validates
    before registration.
    """
    
    @staticmethod
    def create(
        name: str,
        description: str,
        sub_graph: Dict[str, Any],
        scopes: List[NodeScope] = None
    ) -> type:
        """
        Create a new CompositeNode class from a subgraph definition.
        
        Args:
            name: Node name (e.g., "standard.build_strategy")
            description: Human-readable description
            sub_graph: DAG JSON with nodes and edges
            scopes: NodeScope list for registration
            
        Returns:
            A new BaseNode subclass that executes the subgraph
            
        Raises:
            ValueError: If the subgraph fails validation
        """
        from app.nodes.impl.engine.graph_validator import validate_graph
        
        # Validate before allowing creation
        validation = validate_graph(sub_graph)
        if not validation.valid:
            raise ValueError(f"Cannot create CompositeNode '{name}': {validation.summary}")
        
        # Create the class dynamically
        class _CompositeNode(BaseNode):
            _sub_graph = sub_graph
            _composite_name = name
            
            InputSchema = CompositeNodeInput
            OutputSchema = CompositeNodeOutput
            
            def run(self, ctx: Context) -> Dict[str, Any]:
                from app.nodes.impl.engine.graph_executor import GraphExecutorNode
                
                params = self.validate_inputs(ctx.inputs)
                
                executor = GraphExecutorNode()
                exec_ctx = Context(
                    run_id=ctx.run_id,
                    workflow_id=ctx.workflow_id,
                    node_id=f"{ctx.node_id}_exec",
                    inputs={
                        "dag": self._sub_graph,
                        "inputs": params.inputs
                    }
                )
                
                result = executor.run(exec_ctx)
                
                return {
                    "outputs": result.get("outputs", {}),
                    "success": result.get("success", False),
                    "error": result.get("error")
                }
        
        # Set class attributes
        _CompositeNode.description = description
        _CompositeNode.__name__ = name.replace(".", "_").title().replace("_", "")
        
        # Register if scopes provided
        if scopes:
            register_node(
                category=NodeCategory.COMPOSITE,
                name=name,
                scopes=scopes
            )(_CompositeNode)
        
        return _CompositeNode


# Convenience function
def create_composite_node(
    name: str,
    description: str,
    sub_graph: Dict[str, Any],
    scopes: List[NodeScope] = None
) -> type:
    """Create and optionally register a CompositeNode from a subgraph."""
    return CompositeNodeFactory.create(name, description, sub_graph, scopes)
