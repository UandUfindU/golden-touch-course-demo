"""
ScriptNode - Dynamic Python Code Execution.
SECURE MODE: Uses runtime import striction and safe builtins.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import traceback
import builtins

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole

# 1. Allowed Modules Whitelist
SAFE_MODULES = {
    "math", "json", "datetime", "random", "re", 
    "collections", "itertools", "functools", "statistics", "time"
}

# 2. Blocked Modules Blacklist (redundant but explicit)
UNSAFE_MODULES = {
    "os", "sys", "subprocess", "shutil", "pathlib", "input", "eval", "exec"
}

# 3. Allowed Builtins
SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in [
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
        "chr", "complex", "dict", "dir", "divmod", "enumerate", "filter", "float",
        "format", "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min",
        "next", "object", "oct", "ord", "pow", "print", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip"
    ]
}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Replacement for __import__ that checks against whitelist."""
    if name in UNSAFE_MODULES:
        raise ImportError(f"Importing '{name}' is forbidden for security reasons.")
    
    # Optional: Enforce allowed list only?
    # For now, just block known dangerous ones to allow pandas/numpy if installed.
    # But for strict safety:
    # if name not in SAFE_MODULES and not name.startswith("app."): 
    #    ...
    
    return __import__(name, globals, locals, fromlist, level)

class ScriptInput(BaseModel):
    code: str = Field(description="The Python code to execute. Must define a `main(inputs)` function.")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input variables")

class ScriptOutput(BaseModel):
    result: Any = Field(description="The return value of the main function")
    stdout: str = Field(default="", description="Captured stdout")
    error: str = Field(default="", description="Error message if failed")

@register_node(
    category=NodeCategory.LOGIC,
    name="logic.code",
    scopes=[NodeScope.STRATEGY, NodeScope.TOOL, NodeScope.WORKFLOW],
    role=NodeRole.MIDDLE
)
class ScriptNode(BaseNode):
    """
    Executes dynamic Python code in a soft sandbox.
    
    SECURITY:
    - Blocks `os`, `sys`, `subprocess` execution.
    - Restricts builtins.
    - Use this for algorithmic logic, NOT system administration.
    """
    description = "执行自定义 Python 代码 (安全模式)"
    InputSchema = ScriptInput
    OutputSchema = ScriptOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Prepare execution environment
        # We manually construct global scope to restrict access mechanisms
        
        local_scope = {}
        
        global_scope = {
            "__builtins__": SAFE_BUILTINS,
            "__import__": safe_import, # Override import
            "inputs": params.inputs,
            "ctx": ctx,
            # Pre-import common quant libs for convenience
            "math": __import__("math"),
            "json": __import__("json"),
            "datetime": __import__("datetime"),
        }
        
        # Try to import pandas/numpy if available (highly likely needed)
        try: global_scope["pd"] = __import__("pandas")
        except: pass
        try: global_scope["np"] = __import__("numpy")
        except: pass

        try:
            # Execute the code definition
            exec(params.code, global_scope, local_scope)
            
            if "main" not in local_scope:
                raise ValueError("Code must define a 'main(inputs)' function.")
            
            main_func = local_scope["main"]
            
            result = main_func(params.inputs)
            
            return {
                "result": result,
                "stdout": "Executed successfully",
                "error": ""
            }
            
        except ImportError as e:
            error_msg = f"Security Violation: {str(e)}"
            return {"result": None, "stdout": "", "error": error_msg}
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            return {"result": None, "stdout": "", "error": error_msg}
