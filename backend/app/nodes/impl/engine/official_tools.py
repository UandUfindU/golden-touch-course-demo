"""
Official Meta-Graphs - Standard tools packaged as CompositeNodes.

These are registered at startup and available to users/LLM as high-level tools.
"""
from typing import Dict, Any
from app.nodes.impl.engine.composite import create_composite_node
from app.core.enums import NodeScope


# =============================================================================
# Standard.BuildStrategy (Fast Mode)
# =============================================================================
# This subgraph takes a user query and generates a complete strategy DAG.
# Pipeline: ToolRetriever -> PromptBuilder -> LLM -> Parser -> CodeToDAG -> Validate

BUILD_STRATEGY_GRAPH: Dict[str, Any] = {
    "nodes": [
        {
            "id": "input",
            "type": "core.input",
            "data": {"fields": ["query", "session_id", "scope"]}
        },
        {
            "id": "retriever",
            "type": "llm.tool_retriever",
            "data": {"top_k": 50, "scenario": "strategy_building"}
        },
        {
            "id": "prompt",
            "type": "llm.prompt_builder",
            "data": {"template_name": "dag_generator"}
        },
        {
            "id": "llm",
            "type": "llm.chat",
            "data": {"model": "glm-4-flash", "provider": "glm", "temperature": 0.1}
        },
        {
            "id": "parser",
            "type": "llm.response_parser",
            "data": {"parse_mode": "code"}
        },
        {
            "id": "dag_converter",
            "type": "llm.code_to_dag",
            "data": {}
        },
        {
            "id": "output",
            "type": "core.output",
            "data": {}
        }
    ],
    "edges": [
        # Input -> Retriever
        {"source": "input", "target": "retriever", "source_port": "query", "target_port": "query"},
        {"source": "input", "target": "retriever", "source_port": "scope", "target_port": "scope"},
        
        # Retriever -> PromptBuilder
        {"source": "retriever", "target": "prompt", "source_port": "tools", "target_port": "tools"},
        {"source": "input", "target": "prompt", "source_port": "query", "target_port": "query"},
        
        # PromptBuilder -> LLM
        {"source": "prompt", "target": "llm", "source_port": "messages", "target_port": "messages"},
        
        # LLM -> Parser
        {"source": "llm", "target": "parser", "source_port": "response", "target_port": "llm_output"},
        
        # Parser -> CodeToDAG
        {"source": "parser", "target": "dag_converter", "source_port": "parsed", "target_port": "code"},
        
        # CodeToDAG -> Output
        {"source": "dag_converter", "target": "output", "source_port": "dag", "target_port": "dag"},
        {"source": "dag_converter", "target": "output", "source_port": "success", "target_port": "success"}
    ]
}


def register_official_tools():
    """
    Register all official meta-graphs as CompositeNodes.
    
    Called at application startup to make tools available.
    """
    try:
        # Note: CompositeNode validation requires all referenced node types to be registered.
        # For now, we skip validation during registration (subgraph will be validated at runtime).
        # In production, you'd ensure all nodes are registered first.
        
        # Standard.BuildStrategy
        # We can't use create_composite_node directly because it validates the graph,
        # and the nodes in the graph (llm.tool_retriever, etc.) need to be registered first.
        # Instead, we store the graph definition and create on-demand.
        
        print("Official meta-graphs definitions loaded (deferred registration).")
        
    except Exception as e:
        print(f"Warning: Could not register official tools: {e}")


# Export graph definitions for manual use
OFFICIAL_GRAPHS = {
    "standard.build_strategy": {
        "name": "standard.build_strategy",
        "description": "Generate a complete strategy DAG from natural language (Fast Mode)",
        "graph": BUILD_STRATEGY_GRAPH,
        "scopes": [NodeScope.TOOL, NodeScope.WORKFLOW]
    }
}
