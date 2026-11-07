"""
Tool Retriever Node - Retrieves and formats node documentation for LLM context.

This is the SINGLE SOURCE OF TRUTH for node information injection into LLMs.
Responsibilities:
1. Retrieve nodes from registry based on scope/scenario
2. Annotate nodes with roles (HEAD/MIDDLE/TAIL)
3. Format documentation with input/output schemas
4. Support future: vector search, custom session nodes, layer filtering
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


# =============================================================================
# NODE ROLE DEFINITIONS
# =============================================================================

# Role hints help LLM understand graph topology
NODE_ROLES = {
    # HEAD nodes - typically start a graph (data sources)
    "data.fetch_crypto": "HEAD",
    "data.fetch_stock": "HEAD",
    "data.fetch_kline": "HEAD",
    
    # TAIL nodes - typically end a graph (signals, actions)
    "signal.buy": "TAIL",
    "signal.sell": "TAIL",
    "signal.hold": "TAIL",
    "backtest.runner": "TAIL",
    
    # MIDDLE nodes - processing/indicators
    "indicator.ma": "MIDDLE",
    "indicator.rsi": "MIDDLE",
    "indicator.crossover": "MIDDLE",
    "logic.condition": "MIDDLE",  # Renamed from logic.if (Python reserved keyword)
    "data.normalizer": "MIDDLE",
}

ROLE_DESCRIPTIONS = {
    "HEAD": "🟢 Data Source Node - Usually the starting point of the graph",
    "MIDDLE": "🟡 Processing Node - Used for calculations and logic",
    "TAIL": "🔴 Output Node - Usually the end point (Signal/Backtest)",
}


# =============================================================================
# INPUT/OUTPUT SCHEMAS
# =============================================================================

class ToolRetrieverInput(BaseModel):
    """ToolRetriever node input"""
    query: Optional[str] = Field(
        default=None,
        description="Natural language query to match tools (for future vector search)"
    )
    scenario: Optional[str] = Field(
        default=None,
        description="Scenario context: 'strategy_building', 'analysis', 'node_creation'"
    )
    scope: str = Field(
        default="strategy",
        description="Scope to filter tools: strategy, workflow, tool"
    )
    top_k: int = Field(
        default=100,
        description="Maximum number of tools to return (default high for full injection)"
    )
    output_format: Literal["list", "documentation"] = Field(
        default="documentation",
        description="Output format: 'list' (raw metadata) or 'documentation' (formatted for LLM)"
    )
    include_roles: bool = Field(
        default=True,
        description="Include HEAD/MIDDLE/TAIL role annotations"
    )


class ToolRetrieverOutput(BaseModel):
    """ToolRetriever node output"""
    tools: List[Dict[str, Any]] = Field(description="Retrieved tool metadata list")
    documentation: str = Field(description="Formatted documentation for LLM injection")
    example_code: str = Field(default="", description="Dynamic example code using registered node names")
    count: int = Field(description="Number of tools retrieved")
    head_count: int = Field(description="Number of HEAD (data source) nodes")
    tail_count: int = Field(description="Number of TAIL (output) nodes")


@register_node(
    category=NodeCategory.AI,
    name="tool.llm.tool_retriever",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class ToolRetrieverNode(BaseNode):
    """
    Tool Retriever Node - Central hub for node information.
    
    This node is the ONLY place that:
    1. Accesses the node registry
    2. Determines node roles (HEAD/MIDDLE/TAIL)
    3. Formats documentation for LLM consumption
    
    For future optimization:
    - Add vector embedding search
    - Include session-scoped custom nodes
    - Filter by layer (Online/Offline/Tool)
    """
    description = "Retrieve and format node documentation for LLM"
    InputSchema = ToolRetrieverInput
    OutputSchema = ToolRetrieverOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        from app.nodes.registry import registry
        
        all_metadata = registry.get_all_metadata()
        
        # --- STEP 1: Filter nodes ---
        scope_filter = params.scope.lower()
        scenario_filter = params.scenario.lower() if params.scenario else None
        
        filtered = []
        
        for meta in all_metadata:
            # Scope check
            node_scopes = [s.lower() if isinstance(s, str) else s.value.lower() 
                          for s in meta.get("scopes", [])]
            
            # Include if matches scope OR is a core strategy node
            category = str(meta.get("category", "")).lower()
            core_categories = ["data", "indicator", "logic", "signal", "flow"]
            
            if scope_filter in node_scopes or category in core_categories:
                # Scenario filtering
                if scenario_filter == 'strategy_building':
                    # Exclude system/engine nodes for strategy building
                    if "tool" in category or "system" in category or "engine" in category:
                        if meta.get("name") not in ["backtest.runner"]:  # Keep backtest
                            continue
                
                # Attach role
                name = meta.get("name", "")
                role = NODE_ROLES.get(name, "MIDDLE")
                meta_copy = dict(meta)
                meta_copy["role"] = role
                filtered.append(meta_copy)
        
        # Limit to top_k
        result_tools = filtered[:params.top_k]
        
        # --- STEP 2: Group by role ---
        head_nodes = [m for m in result_tools if m.get("role") == "HEAD"]
        middle_nodes = [m for m in result_tools if m.get("role") == "MIDDLE"]
        tail_nodes = [m for m in result_tools if m.get("role") == "TAIL"]
        
        # --- STEP 3: Format documentation ---
        if params.output_format == "documentation":
            doc = self._format_documentation(head_nodes, middle_nodes, tail_nodes, params.include_roles)
        else:
            doc = ""
        
        # --- STEP 4: Generate example code ---
        example_code = self._generate_example_code(head_nodes, middle_nodes, tail_nodes)
        
        # [DEBUG] Print retrieval stats - Enhanced for debugging empty doc issue
        # print(f"[ToolRetriever] Found {len(result_tools)} tools.")
        # print(f"[ToolRetriever] Head: {len(head_nodes)}, Middle: {len(middle_nodes)}, Tail: {len(tail_nodes)}")
        # print(f"[ToolRetriever] Doc length: {len(doc)}")
        # print(f"[ToolRetriever] Doc preview (first 200 chars): {doc[:200] if doc else '(EMPTY)'}...")
        
        return {
            "tools": result_tools,
            "documentation": doc,
            "example_code": example_code,
            "count": len(result_tools),
            "head_count": len(head_nodes),
            "tail_count": len(tail_nodes)
        }
    
    def _format_documentation(
        self, 
        head_nodes: List[Dict], 
        middle_nodes: List[Dict], 
        tail_nodes: List[Dict],
        include_roles: bool
    ) -> str:
        """Format nodes into LLM-readable documentation."""
        lines = []
        
        # --- HEAD NODES ---
        if include_roles:
            lines.append("## 🟢 Data Source Nodes (HEAD)")
            lines.append("> Start here to fetch market data.")
            lines.append("")
        
        for node in head_nodes:
            lines.extend(self._format_single_node(node, "HEAD" if include_roles else None))
        
        if not head_nodes:
            lines.append("*No data source nodes available*\n")
        
        # --- MIDDLE NODES ---
        if include_roles:
            lines.append("## 🟡 Processing Nodes (MIDDLE)")
            lines.append("> Intermediate nodes for indicators and logic.")
            lines.append("")
        
        # Sub-group by category
        categories = {}
        for meta in middle_nodes:
            cat = str(meta.get("category", "OTHER"))
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(meta)
        
        for cat_name, nodes in sorted(categories.items()):
            lines.append(f"### {cat_name}")
            for node in nodes:
                lines.extend(self._format_single_node(node, "MIDDLE" if include_roles else None))
        
        if not middle_nodes:
            lines.append("*No processing nodes available*\n")
        
        # --- TAIL NODES ---
        if include_roles:
            lines.append("## 🔴 Output Nodes (TAIL)")
            lines.append("> End points for signals or actions.")
            lines.append("")
        
        for node in tail_nodes:
            lines.extend(self._format_single_node(node, "TAIL" if include_roles else None))
        
        if not tail_nodes:
            lines.append("*No output nodes available*\n")
        
        return "\n".join(lines)
    
    def _format_single_node(self, meta: Dict[str, Any], role: Optional[str]) -> List[str]:
        """Format a single node's documentation."""
        lines = []
        
        name = meta.get("name", "unknown")
        desc = meta.get("description", "No description")
        
        # Role emoji
        if role:
            emoji = {"HEAD": "🟢", "MIDDLE": "🟡", "TAIL": "🔴"}.get(role, "⚪")
            lines.append(f"**{emoji} `{name}`**")
        else:
            lines.append(f"**`{name}`**")
        
        lines.append(f"  {desc}")
        
        # Input params
        input_schema = meta.get("input_schema", {})
        props = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        if props:
            lines.append("  **Inputs:**")
            for pname, pdef in list(props.items())[:5]:
                ptype = pdef.get("type", "any")
                pdesc = pdef.get("description", "")[:40]
                req_mark = "(Required)" if pname in required else ""
                lines.append(f"    - `{pname}` ({ptype}) {req_mark}: {pdesc}")
            
            if len(props) > 5:
                lines.append(f"    - *... Total {len(props)} parameters*")
        
        # Output
        output_schema = meta.get("output_schema", {})
        out_props = output_schema.get("properties", {})
        if out_props:
            # Filter out current_* helper fields
            main_outputs = [k for k in out_props.keys() if not k.startswith("current_")]
            out_names = [f"`{k}`" for k in main_outputs[:4]]
            lines.append(f"  **Outputs:** {', '.join(out_names)}")
            
            # For multi-output nodes, show tuple unpacking usage
            if len(main_outputs) >= 2:
                var_names = ', '.join(main_outputs[:4])
                node_name = name.split('.')[-1]  # e.g., bollinger_bands
                lines.append(f"  **Usage:** `{var_names} = {name}(source=data, ...)`")
        
        lines.append("")
        return lines
    
    def _generate_example_code(
        self, 
        head_nodes: List[Dict], 
        middle_nodes: List[Dict], 
        tail_nodes: List[Dict]
    ) -> str:
        """
        Generate example code dynamically based on registered nodes.
        
        This ensures the prompt always uses correct, up-to-date node names
        instead of hardcoded values that may become stale.
        """
        # Find specific nodes for example (prefer common ones)
        data_node = next(
            (m["name"] for m in head_nodes if "fetch" in m["name"]), 
            head_nodes[0]["name"] if head_nodes else "data.fetch_crypto"
        )
        ma_node = next(
            (m["name"] for m in middle_nodes if m["name"] == "indicator.ma"),
            next(
                (m["name"] for m in middle_nodes if "indicator" in m["name"] and "ma" in m["name"].lower()),
                next(
                    (m["name"] for m in middle_nodes if m["name"].endswith(".ma")),
                    "indicator.ma"
                )
            )
        )
        crossover_node = next(
            (m["name"] for m in middle_nodes if "crossover" in m["name"].lower()), 
            None
        )
        buy_node = next(
            (m["name"] for m in tail_nodes if "buy" in m["name"].lower()), 
            tail_nodes[0]["name"] if tail_nodes else "signal.buy"
        )
        hold_node = next(
            (m["name"] for m in tail_nodes if "hold" in m["name"].lower()), 
            None
        )
        
        # Build example code - keep it MINIMAL to avoid LLM mimicking verbose style
        lines = [
            "```python",
            "# Example 1: Golden Cross Strategy",
            f'data = data.fetch_stock(symbol="AAPL", market="us", timeframe="1d")',
            f"ma5 = {ma_node}(source=data, period=5)",
            f"ma20 = {ma_node}(source=data, period=20)",
            f"signal.buy(condition=ma5 > ma20)",
            f"signal.sell(condition=ma5 < ma20)",
            "",
            "# Example 2: Bollinger Bands + RSI (MUST use tuple unpacking!)",
            f"upper, middle, lower = indicator.bollinger_bands(source=data, period=20)",
            f"rsi = indicator.rsi(source=data, period=14)",
            f"signal.buy(condition=close < lower and rsi < 30)",
            f"signal.sell(condition=close > upper and rsi > 70)",
            "```"
        ]
        return "\n".join(lines)
