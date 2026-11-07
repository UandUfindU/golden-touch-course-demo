from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import jinja2

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole

class PromptFormatterInput(BaseModel):
    template: str = Field(description="Jinja2 template string")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables to inject into the template")

class PromptFormatterOutput(BaseModel):
    prompt: str = Field(description="Formatted string")

@register_node(
    category=NodeCategory.LOGIC,
    name="logic.prompt_formatter",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class PromptFormatterNode(BaseNode):
    """
    Renders a text string (prompt) using Jinja2 template and input variables.
    
    Example:
    template: "Hello {{ name }}, today is {{ day }}."
    variables: {"name": "Alice", "day": "Monday"}
    output: "Hello Alice, today is Monday."
    """
    description = "格式化字符串模板 (Jinja2)"
    InputSchema = PromptFormatterInput
    OutputSchema = PromptFormatterOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        try:
            # [DEBUG] Print variable stats
            # print(f"[PromptFormatter] Variables received: {list(params.variables.keys())}")
            # for k, v in params.variables.items():
            #     val_len = len(str(v)) if v else 0
            #     print(f"  - {k}: length={val_len}")
            
            # Create a Jinja2 environment (sandboxed ideally, but minimal here)
            env = jinja2.Environment(autoescape=False)
            template = env.from_string(params.template)
            result = template.render(**params.variables)
            
            return {"prompt": result}
        except Exception as e:
            # Fallback for simple f-string style if Jinja fails or simply raise?
            # Raising is safer so user knows template is broken.
            raise ValueError(f"Template rendering failed: {str(e)}")
