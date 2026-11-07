from typing import Dict, Any, List, Union
from pydantic import BaseModel, Field
import json
import copy
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole

class StructureBuilderInput(BaseModel):
    template: Any = Field(description="The structure template (Dict/List). Strings in format '${var_name}' will be replaced.")
    variables: Dict[str, Any] = Field(description="Variables to inject")

class StructureBuilderOutput(BaseModel):
    result: Any = Field(description="Constructed structure")

@register_node(
    category=NodeCategory.UTILITY,
    name="utility.structure_builder",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class StructureBuilderNode(BaseNode):
    """
    Constructs complex data structures (Lists, Dicts) from inputs.
    Supports simple string substitution for values: "${variable_name}".
    
    Example:
    template: [{"role": "system", "content": "${sys_prompt}"}, {"role": "user", "content": "${user_msg}"}]
    variables: {"sys_prompt": "You are AI", "user_msg": "Hi"}
    output: [{"role": "system", "content": "You are AI"}, {"role": "user", "content": "Hi"}]
    """
    description = "根据模板和变量构建复杂数据结构 (List/Dict)"
    InputSchema = StructureBuilderInput
    OutputSchema = StructureBuilderOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        import re
        
        # Regex to find ${variable_name}
        pattern = re.compile(r'\$\{([a-zA-Z0-9_]+)\}')

        def recursive_replace(obj, vars):
            if isinstance(obj, str):
                # Check for exact Match first (to preserve type if variable is not string)
                # E.g. "${number}" -> 123 (int), not "123" (str)
                if obj.startswith("${") and obj.endswith("}"):
                    clean_var = obj[2:-1]
                    if clean_var in vars:
                        return vars[clean_var]
                
                # Partial replacement (always returns string)
                def replace_match(match):
                    key = match.group(1)
                    return str(vars.get(key, match.group(0))) # Default to original if not found
                
                return pattern.sub(replace_match, obj)
                
            elif isinstance(obj, list):
                return [recursive_replace(item, vars) for item in obj]
            elif isinstance(obj, dict):
                return {k: recursive_replace(v, vars) for k, v in obj.items()}
            else:
                return obj
                
        # Deep copy template to avoid modification
        result = recursive_replace(copy.deepcopy(params.template), params.variables)
        
        return {"result": result}
