"""
GraphValidator - Validates graph structure and type compatibility.

This is a UTILITY/MECHANISM, not a node. Called by the execution pipeline
to validate graphs before execution or when LLM generates code.

Checks:
1. No cycles (must be DAG).
2. No orphan nodes (except Input/Output).
3. Required parameters are provided.
4. Type compatibility between connected ports.
"""
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field
from collections import deque

from app.nodes.registry import registry


class GraphValidationError(Exception):
    """Exception raised when graph validation fails."""
    def __init__(self, message: str, issues: List[Dict[str, Any]] = None):
        super().__init__(message)
        self.issues = issues or []


class ValidationResult(BaseModel):
    """Result of graph validation."""
    valid: bool = Field(description="Whether the graph is valid")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="List of issues found")
    summary: str = Field(description="Human-readable summary for LLM feedback")


def _generate_node_usage_hint(node_type: str, required_fields: List[str], properties: Dict[str, Any]) -> str:
    """
    Generate a usage hint string for a node type based on its InputSchema.
    
    Example output:
      "Usage: indicator.bollinger_bands(source=<data>, period=<int>, std_dev=<float>)"
    """
    param_hints = []
    for field in required_fields:
        prop = properties.get(field, {})
        field_type = prop.get("type", "value")
        # Simplify type hints for readability
        if field_type == "array":
            field_type = "data"
        elif field_type == "integer":
            field_type = "int"
        elif field_type == "number":
            field_type = "float"
        param_hints.append(f"{field}=<{field_type}>")
    
    # Add common optional params for indicators
    if node_type.startswith("indicator."):
        if "period" not in required_fields and "period" in properties:
            default = properties["period"].get("default", 20)
            param_hints.append(f"period={default}")
    
    return f"\n  Correct Usage: {node_type}({', '.join(param_hints)})"


def validate_graph(dag: Dict[str, Any], strict_types: bool = False) -> ValidationResult:
    """
    Validate a DAG structure.
    
    Args:
        dag: DAG definition with 'nodes' and 'edges' keys
        strict_types: If True, enforce strict type checking on ports
        
    Returns:
        ValidationResult with valid flag, issues list, and summary for LLM feedback
    """
    nodes = dag.get("nodes", [])
    edges = dag.get("edges", [])
    
    issues: List[Dict[str, Any]] = []
    
    if not nodes:
        return ValidationResult(
            valid=False,
            issues=[{"severity": "error", "node_id": None, "message": "Empty graph - no strategy nodes were generated"}],
            summary="Error: Empty graph. The LLM did not generate any valid strategy code. Please try again."
        )
    
    node_map = {n["id"]: n for n in nodes}
    node_ids = set(node_map.keys())
    
    # Also collect output_name values as valid variable names
    # This handles: cross = indicator.crossover(...) -> output_name='cross'
    output_name_to_node = {}
    for n in nodes:
        output_name = n.get("data", {}).get("output_name")
        if output_name:
            node_ids.add(output_name)
            output_name_to_node[output_name] = n["id"]
    
    
    # --- Check 0: Port Existence (Semantic Check) ---
    # Strictly validate that source_port exists on the source node
    for edge in edges:
        src_id = edge.get("source")
        src_port = edge.get("source_port")
        
        # Skip if src node doesn't exist (handled by Check 1)
        if src_id not in node_map:
            continue
            
        src_node = node_map[src_id]
        src_type = src_node.get("type", "")
        
        # Get node schema from registry
        try:
            all_meta = registry.get_all_metadata()
            node_meta = next((m for m in all_meta if m.get("name") == src_type), None)
            
            if node_meta:
                output_schema = node_meta.get("output_schema", {})
                properties = output_schema.get("properties", {})
                valid_ports = list(properties.keys())
                
                # Check if port exists
                # Note: valid_ports might be empty if schema is loose (e.g. Any), but usually specified
                if valid_ports and src_port not in properties:
                    # Fuzzy match for suggestion
                    from difflib import get_close_matches
                    matches = get_close_matches(src_port, valid_ports, n=1, cutoff=0.6)
                    suggestion = f" Did you mean '{matches[0]}'?" if matches else ""
                    
                    issues.append({
                        "severity": "error",
                        "node_id": src_id,
                        "message": f"Invalid Port: Node '{src_type}' has no output named '{src_port}'. Available outputs: {valid_ports}.{suggestion}"
                    })
        except Exception:
            pass # Registry lookup failed, skip check

    # --- Check 1: Edge references valid nodes ---
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src not in node_ids:
            issues.append({
                "severity": "error",
                "node_id": src,
                "message": f"Edge references non-existent source node: '{src}'"
            })
        if tgt not in node_ids:
            issues.append({
                "severity": "error",
                "node_id": tgt,
                "message": f"Edge references non-existent target node: '{tgt}'"
            })
    
    # --- Check 2: Cycle detection ---
    # Use only real node IDs (not output_name aliases) for cycle detection
    real_node_ids = set(node_map.keys())
    in_edges: Dict[str, List[str]] = {nid: [] for nid in real_node_ids}
    out_edges: Dict[str, List[str]] = {nid: [] for nid in real_node_ids}
    
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in real_node_ids and tgt in real_node_ids:
            in_edges[tgt].append(src)
            out_edges[src].append(tgt)
    
    # Kahn's algorithm for cycle detection
    in_degree = {nid: len(in_edges[nid]) for nid in real_node_ids}
    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    visited_count = 0
    
    while queue:
        nid = queue.popleft()
        visited_count += 1
        for neighbor in out_edges[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if visited_count != len(nodes):
        issues.append({
            "severity": "error",
            "node_id": None,
            "message": "Graph contains cycles - it must be a Directed Acyclic Graph (DAG)."
        })
    
    # --- Check 3: Orphan nodes and Dead Ends ---
    # Special types that are allowed to have no connections
    special_types = {"core.input", "core.output", "structure.input", "structure.output"}
    # Terminal types that are allowed to have no outgoing edges
    terminal_types = {"signal.buy", "signal.sell", "structure.output", "core.output"}
    
    for nid, node_def in node_map.items():
        node_type = node_def.get("type", "")
        if node_type in special_types:
            continue  # Input/Output can be orphans
            
        has_in = len(in_edges[nid]) > 0
        has_out = len(out_edges[nid]) > 0
        
        # Check 3a: Completely orphaned (no connections at all)
        if not has_in and not has_out:
            issues.append({
                "severity": "warning",
                "node_id": nid,
                "message": f"Orphaned Node: '{nid}' ({node_type}) has no connections at all."
            })
        # Check 3b: Dead end (has inputs but no outputs, except for terminal nodes)
        elif has_in and not has_out and node_type not in terminal_types:
            issues.append({
                "severity": "warning",
                "node_id": nid,
                "message": f"Dead End: '{nid}' ({node_type}) receives data but doesn't output to anything. Connect it to a signal or remove it."
            })
    
    # --- Check 4: Required parameters ---
    for nid, node_def in node_map.items():
        node_type = node_def.get("type", "")
        node_data = node_def.get("data", {})
        
        # Try to get node schema from registry
        try:
            all_meta = registry.get_all_metadata()
            node_meta = next((m for m in all_meta if m.get("name") == node_type), None)
            
            if node_meta:
                input_schema = node_meta.get("input_schema", {})
                required_fields = input_schema.get("required", [])
                properties = input_schema.get("properties", {})
                
                # Check which inputs come from edges
                edge_inputs = set()
                for src, src_port, tgt_port in [(e.get("source"), e.get("source_port", "output"), e.get("target_port", "input")) 
                                                 for e in edges if e.get("target") == nid]:
                    edge_inputs.add(tgt_port)
                
                for field in required_fields:
                    # Field is required if: not in node_data AND not coming from edge AND no default
                    has_default = properties.get(field, {}).get("default") is not None
                    if field not in node_data and field not in edge_inputs and not has_default:
                        # Generate usage hint from InputSchema
                        usage_hint = _generate_node_usage_hint(node_type, required_fields, properties)
                        issues.append({
                            "severity": "error",
                            "node_id": nid,
                            "message": f"Node '{nid}' ({node_type}) missing required parameter: '{field}'{usage_hint}"
                        })
        except Exception:
            pass  # Skip if registry lookup fails
    
    # --- Check 5: Unknown node types ---
    try:
        known_types = set(m.get("name") for m in registry.get_all_metadata())
    except Exception:
        known_types = set()
    known_types.update(special_types)  # core.input/output may not be registered
    
    for nid, node_def in node_map.items():
        node_type = node_def.get("type", "")
        if node_type and node_type not in known_types:
            if node_type.startswith("custom."):
                # Custom Node: Allow as Warning (Schema-less placeholder)
                issues.append({
                    "severity": "warning",
                    "node_id": nid,
                    "message": f"Custom node type '{node_type}' is not registered. It will be treated as a placeholder. Ensure you implement/register it before production execution."
                })
            else:
                # Fuzzy match suggestion
                from difflib import get_close_matches
                matches = get_close_matches(node_type, list(known_types), n=1, cutoff=0.6)
                suggestion = f" Did you mean '{matches[0]}'?" if matches else ""
                
                issues.append({
                    "severity": "error",
                    "node_id": nid,
                    "message": f"Unknown node type: '{node_type}'.{suggestion} Available types: {sorted(known_types)[:5]}..."
                })
    
    # --- Check 6: Logic Flow Validation ---
    signal_nodes_found = False
    
    for nid, node_def in node_map.items():
        node_type = node_def.get("type", "").lower()
        node_data = node_def.get("data", {})
        
        # Check 6a: Disconnected Condition Nodes (Dead Ends)
        # Condition nodes usually should connect to something (another condition or signal)
        if ('condition' in node_type or 'if' in node_type) and 'output' not in node_type:
             if len(out_edges[nid]) == 0:
                 # Extract details for better error message
                 expr = node_data.get('condition_expr', '??')
                 output_name = node_data.get('output_name', nid)
                 
                 issues.append({
                    "severity": "error",
                    "node_id": nid,
                    "message": f"Logic Dead End: Condition '{nid}' (expr='{expr}') has NO outgoing connections. It computes '{output_name}' but triggers nothing. Fix: Connect it to a 'signal.buy' or 'signal.sell' node."
                 })
        
        # Check 6b: Signal Nodes
        if 'signal.buy' in node_type or 'signal.sell' in node_type:
            signal_nodes_found = True
            if len(in_edges[nid]) == 0:
                 issues.append({
                    "severity": "error",
                    "node_id": nid,
                    "message": f"Unreachable Signal: '{nid}' ({node_type}) has NO incoming triggers. No condition will ever activate this signal. Fix: Connect a condition node to this signal."
                 })

    # --- Check 7: Static Analysis of Logic Expressions ---
    # Parse condition expressions to ensure all referenced variables exist
    import ast
    
    # helper to find variable usage in expression
    def extract_names(expr_str):
        try:
            tree = ast.parse(expr_str, mode='eval')
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
            return names, None
        except SyntaxError as e:
            return set(), str(e)

    # Collect all available output variable names (from node IDs or explicit output names)
    # In this simplified DAG model, node ID is often used as the variable name in generated code
    # But strictly speaking, we should track what "variable" each node produces.
    # LLM Graph Generator usually produces: variable = Node(...) 
    # The 'id' in the JSON graph IS the variable name.
    available_vars = set(node_ids)
    
    # Add common data columns that are always available after data fetch
    available_vars.update(['close', 'open', 'high', 'low', 'volume', 'data'])
    
    # Collect output_name and multi-output indicator variables dynamically from OutputSchema
    all_meta = registry.get_all_metadata()
    
    for nid, node_def in node_map.items():
        node_data = node_def.get("data", {})
        node_type = node_def.get("type", "")
        output_name = node_data.get("output_name")
        
        # Handle tuple unpacking: {"upper": "user_upper_var", "middle": "user_mid_var", ...}
        tuple_outputs = node_data.get("tuple_outputs")
        if tuple_outputs:
            # Add all user-defined variable names from tuple unpacking
            available_vars.update(tuple_outputs.values())
        
        if output_name:
            available_vars.add(output_name)
            
            # Dynamically extract output fields from node's OutputSchema
            node_meta = next((m for m in all_meta if m.get("name") == node_type), None)
            if node_meta:
                output_schema = node_meta.get("output_schema", {})
                output_fields = output_schema.get("properties", {}).keys()
                
                # Generate {output_name}_{field} for each output field
                # Skip fields starting with 'current_' (event-mode helpers)
                for field in output_fields:
                    if not field.startswith("current_"):
                        available_vars.add(f"{output_name}_{field}")
    
    for nid, node_def in node_map.items():
        node_data = node_def.get("data", {})
        
        # Check 'condition' parameter in Signals or 'condition_expr' in Logic nodes
        expr = None
        if 'condition' in node_data:
            expr = str(node_data['condition'])
        elif 'condition_expr' in node_data:  # logic.condition
            expr = str(node_data['condition_expr'])
            
        if expr:
            # Skip boolean constants or simple values if handled elsewhere, but ast parser handles "True"/"1" fine.
            # However, if 'condition' refers to an EDGE (upstream node), it might be just a node ID string.
            # If it's a complex expression "ma5 > ma10", we need to check vars.
            
            referenced_names, syntax_err = extract_names(expr)
            if syntax_err:
                issues.append({
                    "severity": "error",
                    "node_id": nid,
                    "message": f"Syntax Error in condition '{expr}': {syntax_err}"
                })
                continue
                
            for name in referenced_names:
                # Ignore Python keywords/builtins likely to be used
                if name in ['True', 'False', 'None', 'and', 'or', 'not', 'abs', 'len', 'int', 'float']:
                    continue
                    
                # The referenced name MUST be a Node ID (which serves as variable) 
                # OR it must be an output of a node connected via edge?
                # Actually, our Graph Generator maps:
                #   ma5 = indicator.ma(...) -> Node ID "ma5"
                #   if ma5 > ma10: ... -> Condition uses "ma5" and "ma10"
                # So we simply check if 'name' exists in node_ids
                
                if name not in node_ids and name not in available_vars:
                    # NEW: Check if name is defined via 'output_name' in any node (Unified Graph Model)
                    # This replaces the need for 'expressions' dict
                    found_in_nodes = False
                    for node in nodes:
                        if node.get("data", {}).get("output_name") == name:
                            found_in_nodes = True
                            break
                    
                    if found_in_nodes:
                        continue

                    # Special Case: 'data' columns access? e.g. data.close
                    # ast.Name only catches 'data'. Attribute access 'data.close' -> Name 'data'
                    # So if 'data' is a node, 'data.close' is valid usage of 'data'.
                    # We only flag if the ROOT name is missing.
                    
                    # Legacy: Check if name is a user-defined constant or expression (Backward Compatibility)
                    constants = dag.get('constants', {})
                    expressions = dag.get('expressions', {})
                    if name in constants or name in expressions:
                        continue  # Valid: user-defined intermediate variable
                    
                    # NEW: Check OHLCV columns (always available at runtime)
                    ohlcv_columns = {'close', 'open', 'high', 'low', 'volume', 'data'}
                    if name in ohlcv_columns:
                        continue  # Valid: built-in data column
                    
                    issues.append({
                        "severity": "error",
                        "node_id": nid,
                        "message": f"Undefined Variable: Condition '{expr}' references '{name}', but no node exists with this name. Did you forget to define '{name}' or use the wrong variable name?"
                    })

    # Check 6c: Missing Signals
    if not signal_nodes_found and len(nodes) > 0:
         issues.append({
            "severity": "error",
            "node_id": None,
            "message": "Strategy Incomplete: No 'signal.buy' or 'signal.sell' nodes found. A strategy must generate actions to be valid."
         })
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    
    if errors:
        summary = f"Graph INVALID: {len(errors)} error(s), {len(warnings)} warning(s).\n"
        for err in errors[:5]:  # Limit to first 5 for LLM context
            summary += f"  - ERROR: {err['message']}\n"
    elif warnings:
        summary = f"Graph valid with {len(warnings)} warning(s)."
    else:
        summary = "Graph is valid."
    
    return ValidationResult(
        valid=len(errors) == 0,
        issues=issues,
        summary=summary
    )

