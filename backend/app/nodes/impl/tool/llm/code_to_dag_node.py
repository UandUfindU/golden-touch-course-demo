"""
Code to DAG Node - Parses LLM-generated code into DAG structure.

Core NL2DAG logic - custom implementation using Python AST.
"""
from typing import Dict, Any, Optional, List, Union, Tuple
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
import ast
import re

# print("DEBUG: [Importing CodeToDAGNode.py] File has been loaded!")

class CodeToDAGInput(BaseModel):
    """CodeToDAG node input"""
    code: str = Field(
        description="Python-like code representing a DAG"
    )


class CodeToDAGOutput(BaseModel):
    dag: Dict[str, Any] = Field(description="DAG structure with nodes and edges")
    nodes: List[Dict[str, Any]] = Field(description="List of nodes")
    edges: List[Dict[str, str]] = Field(description="List of edges")
    constants: Dict[str, Any] = Field(default_factory=dict, description="Extracted constants")
    expressions: Dict[str, str] = Field(default_factory=dict, description="[DEPRECATED] Extracted expressions. Now represented as logic.expression nodes.")
    success: bool = Field(description="Whether parsing succeeded")
    error: Optional[str] = Field(default=None, description="Error if parsing failed")


class DAGVisitor(ast.NodeVisitor):
    """AST Visitor to build DAG from Python code"""
    
    def __init__(self):
        self.nodes = []
        self.edges = []
        self.node_vars = {}  # Map var_name -> (node_id, output_index_or_name)
        self.constants = {}  # Map var_name -> value (for constant assignments like threshold = 30)
        self.expressions = {}  # Map var_name -> expression_string (for expr aliases)
        self.node_counter = 0
        self.control_stack = []  # Stack of (node_id, port) for control flow dep
        self.errors = []

    def _get_next_id(self):
        self.node_counter += 1
        return f"n{self.node_counter}"

    def _convert_node_type(self, class_name: str) -> str:
        """
        Convert class name to registered node type using dynamic registry lookup.
        
        Lookup order:
        1. Exact match in registry (e.g., "data.fetch_crypto")
        2. Try common prefixes (indicator, signal, data, logic, flow, ...)
        3. Fallback to custom.{snake_case}
        """
        from app.nodes.registry import registry
        
        # 1. Exact match (handles already qualified names like "data.fetch_crypto")
        if '.' in class_name:
            parts = class_name.split('.')
            candidate = f"{parts[0]}.{self._to_snake(parts[1])}"
            all_meta = registry.get_all_metadata()
            if any(m.get("name") == candidate for m in all_meta):
                return candidate
            # Also try exact as-is
            if any(m.get("name") == class_name for m in all_meta):
                return class_name
        
        # 2. Try common prefixes in priority order
        prefixes = [
            "indicator",  # ma, rsi, crossover, macd
            "signal",     # buy, sell, hold
            "data",       # fetch_crypto, normalizer
            "logic",      # if
            "flow",       # loop, merge, wait
            "backtest",   # runner
            "llm",        # chat
            "util",       # print, http_request
            "trigger",    # manual, cron
            "tool",       # python_code, input, output
            "engine",     # graph_executor
        ]
        
        snake_name = self._to_snake(class_name)
        all_meta = registry.get_all_metadata()
        registered_names = {m.get("name") for m in all_meta}
        
        for prefix in prefixes:
            candidate = f"{prefix}.{snake_name}"
            if candidate in registered_names:
                return candidate
        
        # 3. Fallback to custom namespace
        return f"custom.{snake_name}"


    def _to_snake(self, name: str) -> str:
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _parse_arg_value(self, arg_node):
        """Parse argument value, detecting variables"""
        if isinstance(arg_node, ast.Constant):
            return arg_node.value
        elif isinstance(arg_node, ast.Name):
            # Variable reference - DO NOT return value, return reference marker
            # We handle edges in the caller, but here we process the value if it's a known constant?
            # No, strictly strictly speaking this is an input connection.
            # For parameters that expect static values (like symbol="BTC"), this might be tricky.
            # But in this system, *everything* coming from a var is an edge.
            return f"${{{arg_node.id}}}" 
        elif isinstance(arg_node, ast.List):
            return [self._parse_arg_value(elt) for elt in arg_node.elts]
        elif isinstance(arg_node, ast.Dict):
            return {
                self._parse_arg_value(k): self._parse_arg_value(v) 
                for k, v in zip(arg_node.keys, arg_node.values)
            }
        # print(f"[DEBUG] Parsing node: {type(arg_node)}")
        try:
            return ast.unparse(arg_node)
        except Exception as e:
            # print(f"[DEBUG] Unparse failed: {e}")
            return str(arg_node)

    def visit_BoolOp(self, node):
        """Handle boolean operations: a and b"""
        # We need to turn this into a Node!
        # logic.condition(left=a, operator='and', right=b)
        
        # BoolOp can have multiple values (a and b and c)
        # We process them sequentially: (a and b) -> res, (res and c) -> final
        
        values = node.values
        op_symbol = 'and' if isinstance(node.op, ast.And) else 'or'
        
        current_left_var = None
        
        for i, val_node in enumerate(values):
            # Parse the value to get a variable or constant
            # If it's a nested expression (BinOp/BoolOp), we need to visit it first?
            # AST visit pattern: self.visit(val_node) usually doesn't return value.
            # But we need the result variable name.
            
            # Helper to extract/generate variable for a node
            val_var = self._process_expression_to_var(val_node)
            
            if i == 0:
                current_left_var = val_var
                continue
                
            # Create node combining current_left and this val
            node_id = self._get_next_id()
            params = {
                "operator": op_symbol
            }
            
            # Map edges
            self._add_edge(current_left_var, node_id, "left")
            self._add_edge(val_var, node_id, "right")
            
            self.nodes.append({
                "id": node_id,
                "type": "logic.condition",
                "data": params
            })
            
            # The output of this node becomes the left operand for next
            # Default output for logic.condition is 'result'
            out_var = f"boolop_{node_id}"
            self.node_vars[out_var] = (node_id, "result")
            current_left_var = out_var
            
        # The result of the entire BoolOp is the last variable
        # We need to map this result to the parent assignment?
        # Since visit_BoolOp doesn't return, strict AST visitors maintain state.
        # But we can store it in a temporary 'last_expr_var' attribute on self
        self.last_expr_var = current_left_var

    def visit_Compare(self, node):
        """Handle comparisons: a > b"""
        # Python compare: left, ops, comparators
        # a > b > c is (a>b) and (b>c)
        # Simplify: assume single comparison for now: a > b
        
        left_var = self._process_expression_to_var(node.left)
        
        current_left = left_var
        final_var = None
        
        for op, comparator in zip(node.ops, node.comparators):
            right_var = self._process_expression_to_var(comparator)
            
            # Determine operator symbol
            op_symbol = '=='
            if isinstance(op, ast.Eq): op_symbol = '=='
            elif isinstance(op, ast.NotEq): op_symbol = '!='
            elif isinstance(op, ast.Lt): op_symbol = '<'
            elif isinstance(op, ast.LtE): op_symbol = '<='
            elif isinstance(op, ast.Gt): op_symbol = '>'
            elif isinstance(op, ast.GtE): op_symbol = '>='
            # ... others
            
            node_id = self._get_next_id()
            params = {"operator": op_symbol}
            
            self._add_edge(current_left, node_id, "left")
            self._add_edge(right_var, node_id, "right")
            
            self.nodes.append({
                "id": node_id,
                "type": "logic.condition",
                "data": params
            })
            
            out_var = f"cmp_{node_id}"
            self.node_vars[out_var] = (node_id, "result")
            
            # If multiple ops (chained), logic is complex (and relation).
            # For now assume single op usually.
            final_var = out_var
            current_left = right_var # Chained? No, python chain is a>b and b>c. 
            # Ignoring chain logic correctness for a>b>c, assuming a>b structure.
            
        self.last_expr_var = final_var

    def _process_expression_to_var(self, node):
        """Helper to process a sub-expression and return a variable name representing it"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            # Pass constant value? We need an edge source.
            # If constant, we can't make an edge unless we wrap it in a Literal Node?
            # Or we can return a marker so usage knows it's a constant param.
            # BUT _add_edge checks self.node_vars.
            # If we return a literal string, _add_edge won't find it and skip.
            # So parameters need to be handled. 
            # But visit_BoolOp creates params={"operator"...} but edges for left/right.
            # If left is constant, we want to put it in params["left"]!
            # Complex. 
            # FIX: Return a Tuple (value, is_var=False) or string.
            # Let's return raw value if constant.
            return node.value 
        elif isinstance(node, ast.Call):
            # Visit call to generate node
            # visit_Call isn't standard in NodeVisitor? generic_visit calling visit_Expr?
            # Assign captures Call. 
            # If we have logic.crossover(...) inside an expression?
            # We need to manually process it.
            
            # Trick: Generate a temp var assignment
            temp_var = f"tmp_{self._get_next_id()}"
            # Mock assignment
            # call _process_call directly, but target is temp_var
            # _process_call is designed for Assign...
            pass
            # Too complex to refactor _process_call now. 
            # LLM usually assigns `cross = logic.crossover(...)` then uses `cross` in next line.
            # If nested: `logic.and(logic.crossover(...), ...)`
            # We assume LLM flattens or uses variables.
            # If not, naive parser fails. This is acceptable for now.
            return f"EXP_complex_{type(node)}" 
            
        # Recurse for BoolOp/Compare nested
        self.visit(node)
        if hasattr(self, 'last_expr_var'):
            return self.last_expr_var
            
        return "UNKNOWN_EXPR"

    def _is_expression_param(self, param_name: str, value_node) -> bool:
        """
        Determine if a parameter should be stored as a string expression.
        
        Returns True for:
        - 'condition' params (always need string for eval)
        - Complex expressions (BoolOp, Compare, BinOp) that need runtime eval
        """
        # Explicit expression params
        if param_name in ("condition", "condition_expr", "expr"):
            return True
        
        # Complex expression types that need unparsing
        expression_types = (ast.BoolOp, ast.Compare, ast.BinOp, ast.UnaryOp, ast.IfExp)
        return isinstance(value_node, expression_types)
    
    def _extract_and_create_edges(self, value_node, target_node_id: str, param_name: str):
        """
        Recursively extract variable references from an expression and create edges.
        
        This enables graph connectivity for visualization and dependency tracking.
        """
        # Direct variable reference
        if isinstance(value_node, ast.Name):
            var_name = value_node.id
            if var_name in self.node_vars:
                self._add_edge(var_name, target_node_id, param_name)
            return
        
        # Subscript access: data['close'] -> data
        if isinstance(value_node, ast.Subscript):
            if isinstance(value_node.value, ast.Name):
                var_name = value_node.value.id
                if var_name in self.node_vars:
                    self._add_edge(var_name, target_node_id, param_name)
            return
        
        # BoolOp: a and b -> recurse on values
        if isinstance(value_node, ast.BoolOp):
            for sub_value in value_node.values:
                self._extract_and_create_edges(sub_value, target_node_id, param_name)
            return
        
        if isinstance(value_node, ast.Compare):
            self._extract_and_create_edges(value_node.left, target_node_id, param_name)
            for comp in value_node.comparators:
                self._extract_and_create_edges(comp, target_node_id, param_name)
            return
            
        # UnaryOp: not a -> recurse
        if isinstance(value_node, ast.UnaryOp):
            self._extract_and_create_edges(value_node.operand, target_node_id, param_name)
            return

        # NEW: Handle string constants that contain expressions
        # e.g. condition_expr="close < lower and oversold_rsi"
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            if self._is_expression_param(param_name, value_node):
                try:
                    # Parse the string content as an expression
                    parsed_expr = ast.parse(value_node.value, mode='eval')
                    # Recursively process the parsed expression body
                    # Use a dummy param name to avoid infinite recursion if logic is circular, 
                    # but importantly to just extract vars.
                    self._extract_and_create_edges(parsed_expr.body, target_node_id, param_name)
                except Exception:
                    # Not a valid Python expression, ignore
                    pass
            return
        
        # BinOp: a + b -> recurse on left and right
        if isinstance(value_node, ast.BinOp):
            self._extract_and_create_edges(value_node.left, target_node_id, param_name)
            self._extract_and_create_edges(value_node.right, target_node_id, param_name)
            return
        
        # Dict: {key: value} -> recurse on values
        if isinstance(value_node, ast.Dict):
            for val in value_node.values:
                if val:  # None for **kwargs
                    self._extract_and_create_edges(val, target_node_id, f"context:{param_name}")
            return

    def _add_edge(self, source_var, target_node_id: str, target_param: str = None):
        """Create edge from variable to node"""
        # Support constants passed as source_var
        if not isinstance(source_var, str) and not isinstance(source_var, float) and not isinstance(source_var, int):
             # Maybe raw object? 
             pass
             
        # Check if it's a variable reference
        if isinstance(source_var, str) and source_var in self.node_vars:
            source_id, source_port = self.node_vars[source_var]
            edge = {
                "source": source_id,
                "target": target_node_id,
                "type": "data"
            }
            if source_port:
                edge["source_port"] = str(source_port) 
            if target_param:
                edge["target_port"] = target_param 
            self.edges.append(edge)
        else:
            # It's a constant value!
            # We should inject it into the node's data!
            # But node is already created? 
            # No, usually logical nodes data is params.
            # We need to find the node and update its data.
            # Linear scan of self.nodes?
            for node in self.nodes:
                if node["id"] == target_node_id:
                    node["data"][target_param] = source_var
                    # print(f"[DEBUG] Injected constant param: {target_param}={source_var}")
                    break

    def visit_Assign(self, node):
        """
        Handle assignments with clean priority order:
        1. Constant assignments: threshold = 30
        2. Expression aliases: my_condition = (close < lower and rsi < 30)
        3. Variable aliases: alias = existing_var
        4. Node calls: ma = indicator.ma(...)
        """
        target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not target_names:
            # Tuple unpacking handled via _process_call
            if isinstance(node.value, ast.Call):
                self._process_call(node.value, node.targets)
            return
        
        value = node.value
        
        # === Priority 1: Constant assignments ===
        # Examples: threshold = 30, symbol = "AAPL"
        if isinstance(value, ast.Constant):
            for name in target_names:
                self.constants[name] = value.value
            return
        
        # === Priority 2: Expression aliases ===
        # Examples: buy_cond = (close < lower and rsi < 30)
        # === Priority 2: Expression aliases ===
        # Examples: buy_cond = (close < lower and rsi < 30)
        # Strategy: Try to visit() to see if implicit logic nodes (like logic.if) are created.
        # If yes, use them. If no, FALL THROUGH to Fallback (logic.expression).
        if isinstance(value, (ast.BoolOp, ast.Compare, ast.BinOp, ast.UnaryOp)):
            # Track nodes before visit
            count_before = len(self.nodes)
            self.visit(value)
            count_after = len(self.nodes)
            
            # If a new logic node was created, attribute it to this variable!
            if count_after > count_before:
                # The last node created corresponds to this expression
                last_node = self.nodes[-1]
                
                # Inject output_name for strict validation (unified graph model)
                if target_names:
                    # Use the first target name as the canonical output name
                    primary_name = target_names[0]
                    last_node["data"]["output_name"] = primary_name
                    
                    # Also register this node for all target names
                    for name in target_names:
                        # Assuming logic nodes output 'result' default port
                        self.node_vars[name] = (last_node["id"], "result")
                        
                # Success! Return.
                return
            
            # If NO node was created (e.g. simple Compare not converting to logic.condition),
            # FALL THROUGH to create a logic.expression node.
            pass
        
        # === Priority 3: Variable aliases ===
        # Examples: data2 = data, my_ma = ma
        if isinstance(value, ast.Name):
            ref_name = value.id
            # Check if it references a node output
            if ref_name in self.node_vars:
                for name in target_names:
                    self.node_vars[name] = self.node_vars[ref_name]
            # Check if it references a constant
            elif ref_name in self.constants:
                for name in target_names:
                    self.constants[name] = self.constants[ref_name]
            # Check if it references an expression
            elif ref_name in self.expressions:
                for name in target_names:
                    self.expressions[name] = self.expressions[ref_name]
            return
        
        # === Priority 4: Node calls ===
        # Examples: ma = indicator.ma(source=data, period=20)
        if isinstance(value, ast.Call):
            self._process_call(value, node.targets)
            return
        
        # Fallback: Create a explicit logic.expression node
        # This converts 'x = a + b' into a Node, eliminating the 'expressions' sidecar dict.
        try:
            expr_str = ast.unparse(value)
            
            # Create LogicExpressionNode
            node_id = self._get_next_id()
            self.nodes.append({
                "id": node_id,
                "type": "logic.expression",
                "data": {
                    "expr": expr_str,
                    # Inject output_name to primary variable
                    "output_name": target_names[0] if target_names else None
                }
            })
            
            # Extract dependencies from the expression string
            # Now we parse the expr_str (which we just unparsed) to find variable refs
            # Reuse _extract_and_create_edges logic by passing parsed value
            self._extract_and_create_edges(value, node_id, "expr")
            
            # Register outputs
            for name in target_names:
                self.node_vars[name] = (node_id, "value") # logic.expression outputs 'value'
                
        except Exception:
            pass

    def visit_Expr(self, node):
        """Handle standalone calls: Node(...) - CRITICAL for signal.buy/sell inside if blocks"""
        if isinstance(node.value, ast.Call):
            self._process_call(node.value, [])
        elif isinstance(node.value, ast.BinOp):
            # Handle >> operator: a >> b
            if isinstance(node.value.op, ast.RShift):
                self._process_rshift(node.value)

    def _process_rshift(self, node):
        """Handle a >> b recursively (legacy operator style)"""
        pass

    def _process_call(self, call_node, targets):
        """Create node from function call"""
        # print(f"[DEBUG] Processing Call: {ast.dump(call_node)}")
        # Get node type
        node_type_name = ""
        if isinstance(call_node.func, ast.Name):
            node_type_name = call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            # e.g. flow.if
            if isinstance(call_node.func.value, ast.Name):
                 node_type_name = f"{call_node.func.value.id}.{call_node.func.attr}"
            else:
                return # Too complex
        
        node_id = self._get_next_id()
        real_node_type = self._convert_node_type(node_type_name)
        
        # Parse arguments (inputs)
        params = {}
        
        # 1. Positional args (heuristic map to 'input', 'data' etc? Or just index?)
        # For safety, best to force keyword args in prompt. 
        # But if positional, map to arg_0, arg_1...
        for i, arg in enumerate(call_node.args):
            val = self._parse_arg_value(arg)
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                var_name = val[2:-1]
                self._add_edge(var_name, node_id, f"arg_{i}")
            else:
                params[f"arg_{i}"] = val
        
        # 2. Keyword args - Clean two-phase approach:
        #    Phase 1: Store ALL values as params (for node data / runtime eval)
        #    Phase 2: Create edges for variable dependencies (for graph connectivity)
        
        for kw in call_node.keywords:
            param_name = kw.arg
            
            # === PHASE 1: Always store the param value ===
            # Use ast.unparse for expressions (condition, etc.) or _parse_arg_value for literals
            if self._is_expression_param(param_name, kw.value):
                # Complex expressions: store as string for runtime eval
                try:
                    params[param_name] = ast.unparse(kw.value)
                except Exception:
                    params[param_name] = str(kw.value)
            else:
                # Simple values: parse normally
                val = self._parse_arg_value(kw.value)
                if not (isinstance(val, str) and val.startswith("${") and val.endswith("}")):
                    params[param_name] = val
            
            # === PHASE 2: Create edges for variable dependencies ===
            self._extract_and_create_edges(kw.value, node_id, param_name)

        # Add control flow dependency if inside If/Loop
        if self.control_stack:
            ctrl_source, ctrl_port = self.control_stack[-1]
            
            # Determine target port based on node type
            target_port = "trigger" # Default
            if "signal" in real_node_type:
                target_port = "condition"
            elif "condition" in real_node_type:
                target_port = "condition_input" # Chained conditions?
            
            edge = {
                "source": ctrl_source,
                "target": node_id,
                "source_port": str(ctrl_port), # Fix: Use source_port, not sourceHandle
                "target_port": target_port,    # Fix: Explicit target port
                "type": "control"
            }
            self.edges.append(edge)
            # print(f"[DEBUG] Added Control Edge: {edge}")

        # Create Node
        self.nodes.append({
            "id": node_id,
            "type": real_node_type,
            "data": params
        })

        # Register Outputs
        # Handle tuple unpacking: x, y = Node()
        if len(targets) == 1 and isinstance(targets[0], ast.Tuple):
            # Multi-output - use actual OutputSchema field names when available
            output_fields = self._get_output_fields(real_node_type)
            
            # Build mapping: {schema_field: user_variable_name}
            tuple_outputs = {}
            
            for i, elt in enumerate(targets[0].elts):
                if isinstance(elt, ast.Name):
                    # Use actual field name if available, fallback to output_i
                    if i < len(output_fields):
                        field_name = output_fields[i]
                    else:
                        field_name = f"output_{i}"
                    self.node_vars[elt.id] = (node_id, field_name)
                    tuple_outputs[field_name] = elt.id  # e.g., {"upper": "my_upper_var"}
            
            # PERSIST tuple outputs in node data for validator and precompute
            self.nodes[-1]["data"]["tuple_outputs"] = tuple_outputs
                    
        elif len(targets) == 1 and isinstance(targets[0], ast.Name):
            # Single output - Resolve default port name
            default_port = self._resolve_default_output(real_node_type)
            var_name = targets[0].id
            self.node_vars[var_name] = (node_id, default_port)
            
            # INJECT output_name for BacktestRunner compatibility
            # This ensures 'ma_5 = MA()' results in data['output_name'] = 'ma_5'
            # So BacktestRunner calculates indicators['ma_5'] instead of 'ma5'
            self.nodes[-1]["data"]["output_name"] = var_name

    def _resolve_default_output(self, node_type: str) -> str:
        """Resolve the primary output field name for a node type."""
        from app.nodes.registry import NodeRegistry
        
        try:
            node_cls = NodeRegistry.get_node(node_type)
            # Inspect OutputSchema
            schema = node_cls.OutputSchema
            fields = schema.model_fields.keys()
            
            # Heuristics for primary output (order matters: most common first)
            if "value" in fields: return "value"      # indicator.ma, etc.
            if "values" in fields: return "values"    # Batch outputs (rare)
            if "crossover" in fields: return "crossover"  # logic.crossover
            if "crossunder" in fields: return "crossunder" # logic.crossunder
            if "data" in fields: return "data"        # data nodes
            if "series" in fields: return "series"
            if "signal" in fields: return "signal"
            if "result" in fields: return "result"    # logic.condition
            
            # Fallback: return first field
            if fields:
                return list(fields)[0]
                
        except Exception:
            pass
            
        return "default"

    def _get_output_fields(self, node_type: str) -> list:
        """Get list of output field names from node's OutputSchema.
        
        Returns field names in declaration order, filtering out 'current_*' helper fields.
        This enables tuple unpacking like: upper, middle, lower = bollinger_bands(...)
        """
        from app.nodes.registry import NodeRegistry
        
        try:
            node_cls = NodeRegistry.get_node(node_type)
            schema = node_cls.OutputSchema
            # Get fields in declaration order, filter out current_* (event-mode helpers)
            return [f for f in schema.model_fields.keys() if not f.startswith("current_")]
        except Exception:
            return []

    def visit_If(self, node):
        """Handle if statements -> LogicIf"""
        # Create LogicIf Node
        if_id = self._get_next_id()
        
        # Parse condition
        # This is hard to do perfectly, but we can extract variables from the test
        # e.g. if len(df) > 100
        # For now, treat 'test' as a parameter string? Or try to find dependencies?
        # Simple approach: Convert the test expression to string
        test_source = ast.unparse(node.test)
        
        # Find dependencies in test
        # Walk the test node to find Names
        test_deps = [n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)]
        
        params = {"condition_expr": test_source}
        
        self.nodes.append({
            "id": if_id,
            "type": "logic.condition",  # Cannot use 'logic.if' - Python reserved keyword
            "data": params
        })
        
        # Add edges for condition dependencies
        for dep in test_deps:
            if dep in self.node_vars:
                # Resolve smart port for boolean usage
                # If 'if crossover_node:' used, we want to listen to 'crossover' port, not 'true'
                dep_node_id, dep_default_port = self.node_vars[dep]
                
                # Check node type for smart mapping
                dep_node = next((n for n in self.nodes if n["id"] == dep_node_id), None)
                source_port = "result" # Default for boolean nodes - logic.condition outputs 'result'
                
                if dep_node:
                    n_type = dep_node.get("type", "")
                    if "crossover" in n_type:
                        source_port = "crossover"
                    elif "crossunder" in n_type:
                        source_port = "crossunder"
                    elif "logic.condition" in n_type:
                        source_port = "result" # logic.condition outputs 'result', not 'true'
                    else:
                        # Fallback: Use the default port (likely 'value', 'data' or 'result')
                        # But 'if' implies a boolean signal? 
                        # If a raw boolean value is passed (e.g. from a tool), it might be 'result'
                        # For now, default to 'result' to maintain compatibility
                        # Registry check:
                        if dep_default_port in ["result", "success", "is_valid"]:
                            source_port = dep_default_port


                # Manually add edge with resolved source_port (skip generic _add_edge)
                edge = {
                    "source": dep_node_id,
                    "target": if_id,
                    "source_port": source_port,
                    "target_port": "condition_input",
                    "type": "data"
                }
                self.edges.append(edge)

        # Process Body (True branch) - use 'result' port (not 'true' which doesn't exist)
        self.control_stack.append((if_id, "result"))
        for stmt in node.body:
            self.visit(stmt)
        self.control_stack.pop()
        
        # Process Else (False branch) - also use 'result' (inverted semantics handled elsewhere)
        if node.orelse:
            self.control_stack.append((if_id, "result"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.control_stack.pop()


@register_node(
    category=NodeCategory.AI,
    name="tool.llm.code_to_dag",
    scopes=[NodeScope.TOOL]
)
class CodeToDAGNode(BaseNode):
    """
    Code to DAG Node - Parse code into workflow DAG structure.
    
    Uses AST parsing to support:
    - Variable-as-Edge
    - Multi-Output (Tuple unpacking)
    - Native Control Flow (if/else)
    """
    description = "Convert Python code to DAG structure"
    InputSchema = CodeToDAGInput
    OutputSchema = CodeToDAGOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        try:
            nodes, edges, constants, expressions = self._parse_dag_ast(params.code)
            
            # Unified Graph Model: 'expressions' sidecar is deprecated.
            # All variables are now Nodes (logic.expression or other nodes with output_name).
            # We return empty dict for expressions to maintain Pydantic schema compatibility for now,
            # or we could remove it if we update schema.
            # Let's keep constants for now if they are truly global constants, but ideally they're nodes too.
            
            dag = {
                "nodes": nodes,
                "edges": edges,
                "constants": constants,      
                "expressions": {}   # DEPRECATED: All expressions are now Nodes.
            }
            
            return {
                "dag": dag,
                "nodes": nodes,
                "edges": edges,
                "success": True,
                "error": None
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "dag": {"nodes": [], "edges": []},
                "nodes": [],
                "edges": [],
                "success": False,
                "error": f"Failed to parse DAG: {e}"
            }
    
    def _attempt_syntax_fix(self, code: str, error: SyntaxError) -> Optional[str]:
        """Attempt to fix common LLM syntax errors, specifically mixed quotes."""
        try:
            lines = code.split('\n')
            if error.lineno is None:
                return None
                
            # Line index is 1-based in error
            idx = error.lineno - 1
            if idx < 0 or idx >= len(lines):
                return None
                
            line = lines[idx]
            
            # Fix 1: Mixed quotes (starts with ' ends with " or vice versa)
            # Example: reason='Analysis complete"
            # Heuristic: Check for params passed to signal.buy/sell or indicator
            
            # Pattern: key='value" or key="value'
            # We look for simple assignment-like patterns inside function calls
            # This is a basic heuristic
            
            # Case A: starts single, has double, no end single
            if "'" in line and '"' in line:
                # Naive fix: if it smells like a quote mismatch at the end
                stripped = line.strip()
                if stripped.endswith('"}') or stripped.endswith('",') or stripped.endswith('")'):
                    # Check if it started with single quote
                    # key='value... -> we want key="value... or key='value...
                    # Let's just try to enforce double quotes if mixed
                    # This is tricky without a full tokenizer.
                    pass
                
                # Regex for: identifier='[^']+"   (starts single, hits double, no closing single)
                import re
                # Fix: key='value" -> key="value"
                # Look for: (\w+)\s*=\s*'([^']+)"
                match_mixed_1 = re.search(r"(\w+)\s*=\s*'([^']+)\"", line)
                if match_mixed_1:
                    # Replace with double quotes
                    key, val = match_mixed_1.groups()
                    new_line = line.replace(f"{key}='{val}\"", f'{key}="{val}"')
                    lines[idx] = new_line
                    return '\n'.join(lines)

                # Fix: key="value' -> key="value"
                match_mixed_2 = re.search(r"(\w+)\s*=\s*\"([^\"]+)'", line)
                if match_mixed_2:
                    # Replace with double quotes
                    key, val = match_mixed_2.groups()
                    new_line = line.replace(f'{key}="{val}\'', f'{key}="{val}"')
                    lines[idx] = new_line
                    return '\n'.join(lines)
            
            return None
        except Exception:
            return None

    def _parse_dag_ast(self, code: str) -> tuple:
        """Parse Python code using AST"""
        # Extract code block if needed
        code_block_match = re.search(r"```(?:python)?\n?(.*?)```", code, re.DOTALL)
        if code_block_match:
            code = code_block_match.group(1)
            
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # Try to recover from known LLM quirks
            if "unterminated string literal" in str(e) or "EOL while scanning string literal" in str(e):
                fixed_code = self._attempt_syntax_fix(code, e)
                if fixed_code:
                    try:
                        tree = ast.parse(fixed_code)
                        print(f"[WARN] SyntaxError fixed automatically at line {e.lineno}")
                    except SyntaxError:
                        raise e
                else:
                    raise e
            else:
                raise e
            
        visitor = DAGVisitor()
        visitor.visit(tree)
        
        # Auto-add 'structure.output' for 'signal' variable if present
        if "signal" in visitor.node_vars:
            source_id, source_port = visitor.node_vars["signal"]
            output_id = visitor._get_next_id()
            
            # Add Output Node
            visitor.nodes.append({
                "id": output_id,
                "type": "structure.output",
                "data": {"name": "signal"}
            })
            
            # Add Edge
            visitor.edges.append({
                "source": source_id,
                "target": output_id,
                "source_port": str(source_port),
                "target_port": "value", # MUST match OutputNodeInput.value field
                "type": "data"
            })
        
        # Return all parsing results (backwards-compatible tuple expansion)
        return visitor.nodes, visitor.edges, visitor.constants, visitor.expressions
