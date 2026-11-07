"""
Prompt Builder Node - Constructs prompts from templates.

Uses LangChain's ChatPromptTemplate for standardized prompt construction.
Supports ReAct, CoT, Plan-and-Execute templates.
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


# Predefined prompt templates
TEMPLATES = {
    "react": '''You are an intelligent assistant that can use tools to help users.

Available Tools:
{tools}

When responding, follow this format:
Thought: [your reasoning about what to do]
Action: [the tool to use]
Action Input: [the input to the tool]
Observation: [what you observed]
... (repeat Thought/Action/Observation as needed)
Thought: I have enough information to answer
Final Answer: [your final response]

User Query: {query}
''',
    
    "cot": '''You are an intelligent assistant. Think step by step.

Problem: {query}

Let's solve this step by step:
1. First, I need to understand...
2. Then, I should consider...
3. Finally, I can conclude...
''',
    
    "dag_generator": '''You are an expert at creating workflow DAGs for quantitative trading.

Available Nodes:
{tools}

Based on the user's request, generate a DAG (Directed Acyclic Graph) as valid Python code.

RULES:
1. Instantiate nodes as classes: `variable_name = NodeType(param=value)`
2. Connect nodes by passing variables as arguments: `ma = indicator.ma(data=kline_node)`
3. For multiple outputs, use tuple unpacking: `train, test = flow.split_data(data=source)`
4. For logic branching, use native Python `if/else`:
   ```python
   rsi = indicator.rsi(data=source)
   if rsi > 70:
       res = tool.sell()
   else:
       res = tool.buy()
   ```

User Request: {query}

Generate the DAG code:
```python
# Create workflow
''',

    "custom": "{prompt}"
}


class PromptBuilderInput(BaseModel):
    """PromptBuilder node input"""
    template_name: Literal["react", "cot", "dag_generator", "custom"] = Field(
        default="react",
        description="Name of the prompt template to use"
    )
    tools: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of tool schemas to include in prompt"
    )
    query: str = Field(
        description="User query to include"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context variables"
    )
    history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Conversation history"
    )
    custom_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt template (for template_name='custom')"
    )


class PromptBuilderOutput(BaseModel):
    messages: List[Dict[str, str]] = Field(description="Formatted messages for LLM")
    system_message: str = Field(description="System message content")


@register_node(
    category=NodeCategory.AI,
    name="llm.prompt_builder",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class PromptBuilderNode(BaseNode):
    """
    Prompt Builder Node - Constructs prompts from templates.
    
    Uses LangChain's ChatPromptTemplate for standardized construction.
    Supports predefined templates (ReAct, CoT, DAG Generator) and custom.
    """
    description = "Build prompts from templates"
    InputSchema = PromptBuilderInput
    OutputSchema = PromptBuilderOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Get template
        if params.template_name == "custom" and params.custom_prompt:
            template = params.custom_prompt
        else:
            template = TEMPLATES.get(params.template_name, TEMPLATES["react"])
        
        # Format tools as string
        tools_str = ""
        if params.tools:
            for tool in params.tools:
                tools_str += f"- {tool.get('name')}: {tool.get('description', 'No description')}\n"
                if tool.get('input_schema'):
                    props = tool['input_schema'].get('properties', {})
                    tools_str += f"  Inputs: {list(props.keys())}\n"
        
        # Build system message
        system_content = template.format(
            tools=tools_str or "No tools available",
            query=params.query,
            prompt=params.custom_prompt or "",
            **(params.context or {})
        )
        
        # Build messages
        messages = [{"role": "system", "content": system_content}]
        
        # Add history
        if params.history:
            messages.extend(params.history)
        
        # Add current query as user message
        messages.append({"role": "user", "content": params.query})
        
        return {
            "messages": messages,
            "system_message": system_content
        }
