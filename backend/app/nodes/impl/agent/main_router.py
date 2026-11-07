from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import json

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
from app.core.session_manager import session_manager, LayerType

# Import schemas for internal nodes it calls
from app.nodes.impl.tool.llm.llm_chat_node import LLMChatInput, LLMChatNode

class MainRouterInput(BaseModel):
    """Input for Main Router."""
    message: str = Field(description="User's latest message")
    session_id: str = Field(description="Chat Session ID")
    # New Context Fields
    layer: str = Field(default="offline", description="Current Layer: offline/online")
    mode: str = Field(default="auto", description="Thinking Mode: auto/fast/executor")
    client_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Frontend Context")
    
    # History Injection (API Layer / Client handles async fetch)
    history: List[Dict[str, str]] = Field(default_factory=list, description="Recent Chat History")
    
    # Optional config overrides
    model: str = Field(default="glm-4-flash", description="Model to use")
    provider: str = Field(default="glm", description="LLM Provider")

class MainRouterOutput(BaseModel):
    """Unified output for Frontend."""
    response: str = Field(description="Final text response to user")
    source: str = Field(description="Who generated this? main_agent / tool:xyz")
    tool_args: Optional[Dict[str, Any]] = Field(default=None, description="Arguments for the tool call if source starts with tool:")

@register_node(
    category=NodeCategory.AI,
    name="agent.main_router",
    scopes=[NodeScope.WORKFLOW]
)
class MainRouterNode(BaseNode):
    """
    The 'Master Mind' Agent with Tool Calling capabilities.
    - Decides intent and optimizes prompt for sub-tools.
    """
    description = "Central Hub for user interaction"
    InputSchema = MainRouterInput
    OutputSchema = MainRouterOutput
    
    def _dag_to_dsl(self, dag: dict) -> str:
        """Convert DAG JSON to Python-like DSL for LLM readability"""
        try:
            if dag is None:
                return "# Empty Strategy"
                
            nodes = dag.get("nodes", [])
            edges = dag.get("edges", [])
            
            if not nodes:
                return "# Empty Strategy"
                
            lines = []
            
            # Map node IDs to variable names
            id_map = {}
            for n in nodes:
                # Use output_name if available, else derive from type and ID
                var_name = n.get("data", {}).get("output_name")
                if not var_name:
                    # Clean type name (e.g. indicator.ma -> ma)
                    type_suffix = n["type"].split(".")[-1]
                    var_name = f"{type_suffix}_{n['id']}"
                id_map[n["id"]] = var_name
            
            # Group nodes by category
            data_nodes = []
            indicator_nodes = []
            logic_nodes = []
            signal_nodes = []
            
            for n in nodes:
                node_type = n["type"]
                line = ""
                
                # Format arguments
                params = n.get("data", {})
                args = []
                
                # Check incoming edges to find input dependencies
                incoming = [e for e in edges if e["target"] == n["id"]]
                for inc in incoming:
                    src_var = id_map.get(inc["source"], inc["source"])
                    arg_name = inc.get("target_port", "source")
                    if arg_name == "default": arg_name = "source"
                    args.append(f"{arg_name}={src_var}")
                
                # Add scalar parameters (exclude internal fields)
                for k, v in params.items():
                    if k not in ["output_name", "nodeType", "label"] and not isinstance(v, (dict, list)):
                        if isinstance(v, str):
                            args.append(f'{k}="{v}"')
                        else:
                            args.append(f"{k}={v}")
                            
                args_str = ", ".join(args)
                var_name = id_map[n["id"]]
                
                # Construct line based on node type
                if "data" in node_type:
                    line = f"{var_name} = {node_type}({args_str})"
                    data_nodes.append(line)
                elif "indicator" in node_type:
                    line = f"{var_name} = {node_type}({args_str})"
                    indicator_nodes.append(line)
                elif "logic" in node_type or "condition" in node_type:
                    line = f"{var_name} = {node_type}({args_str})"
                    logic_nodes.append(line)
                elif "signal" in node_type:
                    # Signals are usually actions
                    if incoming:
                        # Find the condition causing this signal
                        condition_var = id_map.get(incoming[0]["source"], "True")
                        line = f"if {condition_var}:\n    {node_type}({args_str})"
                    else:
                        line = f"{node_type}({args_str})"
                    signal_nodes.append(line)
                else:
                    line = f"{var_name} = {node_type}({args_str})"
                    logic_nodes.append(line)

            # Assemble the script
            if data_nodes:
                lines.append("# 1. Data Loading")
                lines.extend(data_nodes)
                lines.append("")
                
            if indicator_nodes:
                lines.append("# 2. Indicators")
                lines.extend(indicator_nodes)
                lines.append("")
                
            if logic_nodes:
                lines.append("# 3. Logic & Conditions")
                lines.extend(logic_nodes)
                lines.append("")
                
            if signal_nodes:
                lines.append("# 4. Signals")
                lines.extend(signal_nodes)
                
            return "\n".join(lines)
            
        except Exception as e:
            return f"# Error converting graph to DSL: {str(e)}\n# Raw JSON: {json.dumps(dag)}"

    def run(self, ctx: Context) -> Dict[str, Any]:
        try:
            params = self.validate_inputs(ctx.inputs)
            # print(f"[DEBUG MainRouter] params validated: message='{params.message[:30]}...', layer={params.layer}")
        except Exception as e:
            print(f"[ERROR MainRouter] Validation failed: {e}")
            import traceback
            traceback.print_exc()
            return {"response": f"Input validation error: {e}", "source": "error", "tool_args": None}
        
        # --- 1. Define Tools ---
        all_tools = [
            {
                "name": "build_strategy",
                "layer": "offline",
                "description": "Create or modify a trading strategy graph. Preserve explicitly requested tickers, bar counts, timeframes, indicator parameters, and signal conditions in 'instruction'. IMPORTANT: You MUST specify 'asset_type' based on the user's request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "Optimized technical instruction for the builder agent."},
                        "asset_type": {
                            "type": "string",
                            "enum": ["us_stock", "crypto", "cn_stock"],
                            "description": "Asset type detected from user request. Use 'us_stock' for US stocks (AAPL, TSLA, 美股), 'crypto' for cryptocurrency (BTC, ETH, 比特币), 'cn_stock' for Chinese A-shares (600519, A股)."
                        }
                    },
                    "required": ["instruction", "asset_type"]
                }
            },
            {
                "name": "build_workflow",
                "layer": "online",
                "description": "Create or modify a quant workflow. Input 'instruction' should be a clear orchestration plan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "Optimized workflow instruction."}
                    },
                    "required": ["instruction"]
                }
            },
            {
                "name": "save_strategy",
                "layer": "offline",
                "description": "Save the current strategy graph to the database/registry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name for the strategy (optional, inferred if missing)"}
                    }
                }
            },
            {
                "name": "run_backtest",
                "layer": "offline",
                "description": "Run a backtest simulation on the current strategy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "params": {"type": "string", "description": "Backtest parameters (e.g. timeframe, dates)"}
                    }
                }
            }
        ]
        
        # Filter tools
        current_layer_tools = [t for t in all_tools if t["layer"] == params.layer]
        tools_def = [{k:v for k,v in t.items() if k != "layer"} for t in current_layer_tools]
        
        # --- 2. Construct System Prompt ---
        # Convert DAG JSON to Python DSL for better readability
        # Safety: client_context defaults to None in input param, ensure it's a dict
        c_ctx = params.client_context or {}
        current_dag = c_ctx.get("current_graph_dag", {})
        ctx_str = self._dag_to_dsl(current_dag) if current_dag and current_dag.get("nodes") else "Empty Canvas"
        
        role_desc = "You are a Quant AI Assistant."
        if params.layer == "online":
            role_desc = "You are a Quantitative Workflow Architect (Online Layer)."
        else:
            role_desc = "You are a Trading Strategy Designer (Offline Layer)."

        tool_instruction = f"""
## Tool Usage
You have access to the following tools:
{json.dumps(tools_def, indent=2, ensure_ascii=False)}

To call a tool, you MUST output a JSON block ONLY, with this format:
```json
{{
  "tool": "tool_name",
  "args": {{ "instruction": "...", "asset_type": "us_stock|crypto|cn_stock" }}
}}
```

## Asset Type Detection (CRITICAL for build_strategy)
When calling `build_strategy`, you MUST detect the asset type from the user's message:
- **"美股"、"US stocks"、"AAPL"、"TSLA"、"NVDA"** → `"asset_type": "us_stock"`
- **"A股"、"中国股票"、"600519"、"茅台"** → `"asset_type": "cn_stock"`
- **"比特币"、"BTC"、"ETH"、"crypto"、"加密货币"** → `"asset_type": "crypto"`
- If not specified, default to `"us_stock"`

Example: User says "帮我创建一个简单的美股均线交叉策略"
→ Output: `{{"tool": "build_strategy", "args": {{"instruction": "Create MA crossover strategy with 10-day and 20-day moving averages, buy when short MA crosses above long MA", "asset_type": "us_stock"}}}}`

IMPORTANT: 
- Do not just pass the user's raw message. You specifically optimze the 'instruction' to be more technical and precise for the tool.
- **Proactive Mode**: If the user's request is a **CREATION/MODIFICATION intent** but vague (e.g. "build a strategy", "draw a graph"), assume a default template and call the tool.
- **Status Queries**: If the user asks about the **CURRENT STATUS** (e.g. "what does the graph look like?", "current context?"), DO NOT call a tool. Just interpret the 'Current Canvas Context' (Python DSL) provided above and explain it to the user.
"""
        
        system_prompt = f"""{role_desc}
Current Canvas Context (Python DSL):
```python
{ctx_str}
```

{tool_instruction}

Answer the user's request. If they ask to create/modify something, USE A TOOL.
"""

        # --- 3. Call LLM ---
        messages = [{"role": "system", "content": system_prompt}]
        if params.history:
            messages.extend(params.history)
        messages.append({"role": "user", "content": params.message})
        
        # DEBUG LOGGING
        # print("="*50)
        # print("[DEBUG] MainRouter System Prompt:")
        # print(system_prompt) # Too noisy
        # print("-" * 20)
        # print(f"[DEBUG] User Message: {params.message}")
        # print("="*50)
        
        llm_node = LLMChatNode()
        
        llm_out = llm_node.run(Context(
            run_id=ctx.run_id,
            workflow_id=ctx.workflow_id,
            node_id=ctx.node_id + "_llm",
            inputs={
                "messages": messages,
                "model": params.model,
                "provider": params.provider,
                "stream": False 
            },
            on_status_update=ctx.on_status_update
        ))
        
        raw_response = llm_out["response"].strip()
        
        # --- 4. Parse Output ---
        import re
        
        source = "main_agent"
        response_text = raw_response
        tool_args = None
        tool_name = None
        
        # Pattern 1: Standard JSON block ```json { "tool": "...", "args": {...} } ```
        json_pattern = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if not json_pattern:
            # Pattern 2: Raw JSON { "tool": "...", "args": {...} }
            json_pattern = re.search(r"(\{.*\})", raw_response, re.DOTALL)
        
        if json_pattern:
            try:
                tool_call = json.loads(json_pattern.group(1))
                if "tool" in tool_call:
                    tool_name = tool_call["tool"]
                    tool_args = tool_call.get("args", {})
            except Exception:
                pass
        
        # Pattern 3: Fallback for "tool_name\n{json}" format (some LLMs produce this)
        if not tool_name:
            alt_pattern = re.match(r"^(build_strategy|save_strategy|run_backtest)\s*\n\s*(\{.*\})", raw_response, re.DOTALL)
            if alt_pattern:
                tool_name = alt_pattern.group(1)
                try:
                    tool_args = json.loads(alt_pattern.group(2))
                except Exception:
                    tool_args = {"instruction": alt_pattern.group(2)}
        
        if tool_name:
            source = f"tool:{tool_name}"
            response_text = f"Invoking {tool_name}..." 
            ctx.emit_status(f"🛠️ 正在调用工具: {tool_name}")
        
        return {
            "response": response_text,
            "source": source,
            "tool_args": tool_args
        }
