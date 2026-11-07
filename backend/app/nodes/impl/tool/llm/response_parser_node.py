"""
Response Parser Node - Parses LLM responses into structured data.

Custom implementation for our specific DAG DSL format.
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
import re
import json


class ResponseParserInput(BaseModel):
    """ResponseParser node input"""
    llm_output: str = Field(
        description="Raw LLM output to parse"
    )
    parse_mode: Literal["code", "json", "steps", "react"] = Field(
        default="react",
        description="Parsing mode"
    )


class ResponseParserOutput(BaseModel):
    parsed: Dict[str, Any] = Field(description="Parsed structured data")
    first_code_block: Optional[str] = Field(default=None, description="First found code block (for convenience)")
    success: bool = Field(description="Whether parsing succeeded")
    error: Optional[str] = Field(default=None, description="Error if parsing failed")


@register_node(
    category=NodeCategory.AI,
    name="llm.response_parser",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class ResponseParserNode(BaseNode):
    """
    Response Parser Node - Extract structured data from LLM output.
    
    Custom implementation for parsing:
    - ReAct format (Thought/Action/Observation)
    - Code blocks (Python)
    - JSON blocks
    - Step-by-step reasoning
    """
    description = "Parse LLM responses into structured data"
    InputSchema = ResponseParserInput
    OutputSchema = ResponseParserOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        try:
            if params.parse_mode == "react":
                parsed = self._parse_react(params.llm_output)
            elif params.parse_mode == "code":
                parsed = self._parse_code(params.llm_output)
            elif params.parse_mode == "json":
                parsed = self._parse_json(params.llm_output)
            elif params.parse_mode == "steps":
                parsed = self._parse_steps(params.llm_output)
            else:
                parsed = {"raw": params.llm_output}
            
            first_code_block = None
            if params.parse_mode == "code" and parsed.get("code_blocks"):
                    first_code_block = parsed["code_blocks"][0]
            
            return {
                "parsed": parsed,
                "first_code_block": first_code_block,
                "success": True,
                "error": None
            }
        except Exception as e:
            return {
                "parsed": {"raw": params.llm_output},
                "success": False,
                "error": str(e)
            }
    
    def _parse_react(self, text: str) -> Dict[str, Any]:
        """Parse ReAct format (Thought/Action/ActionInput/Observation)"""
        result = {
            "thoughts": [],
            "actions": [],
            "final_answer": None,
            "raw": text
        }
        
        # Extract Thought blocks
        thought_pattern = r"Thought:\s*(.+?)(?=Action:|Observation:|Final Answer:|$)"
        thoughts = re.findall(thought_pattern, text, re.DOTALL | re.IGNORECASE)
        result["thoughts"] = [t.strip() for t in thoughts]
        
        # Extract Action blocks
        action_pattern = r"Action:\s*(.+?)(?=Action Input:|Observation:|Thought:|$)"
        actions = re.findall(action_pattern, text, re.DOTALL | re.IGNORECASE)
        
        action_input_pattern = r"Action Input:\s*(.+?)(?=Observation:|Thought:|Action:|$)"
        action_inputs = re.findall(action_input_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for i, action in enumerate(actions):
            action_data = {
                "action": action.strip(),
                "input": action_inputs[i].strip() if i < len(action_inputs) else ""
            }
            result["actions"].append(action_data)
        
        # Extract Final Answer
        final_pattern = r"Final Answer:\s*(.+?)$"
        final_match = re.search(final_pattern, text, re.DOTALL | re.IGNORECASE)
        if final_match:
            result["final_answer"] = final_match.group(1).strip()
        
        return result
    
    def _parse_code(self, text: str) -> Dict[str, Any]:
        """Extract code blocks from text"""
        result = {
            "code_blocks": [],
            "raw": text
        }
        
        # Match ```python or ``` code blocks
        code_pattern = r"```(?:python)?\n?(.*?)```"
        matches = re.findall(code_pattern, text, re.DOTALL)
        
        for match in matches:
            result["code_blocks"].append(match.strip())
        
        # If no blocks found, treat entire text as code (if it looks like code)
        if not result["code_blocks"] and ("def " in text or "import " in text or "=" in text):
            result["code_blocks"].append(text.strip())
        
        return result
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text"""
        # Try to find JSON in code blocks first
        json_pattern = r"```(?:json)?\n?(.*?)```"
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return {"data": json.loads(match.strip()), "raw": text}
            except json.JSONDecodeError:
                continue
        
        # Try to parse the whole text as JSON
        try:
            return {"data": json.loads(text.strip()), "raw": text}
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in text
        json_obj_pattern = r"\{[^{}]*\}"
        matches = re.findall(json_obj_pattern, text)
        for match in matches:
            try:
                return {"data": json.loads(match), "raw": text}
            except json.JSONDecodeError:
                continue
        
        return {"data": None, "raw": text, "error": "No valid JSON found"}
    
    def _parse_steps(self, text: str) -> Dict[str, Any]:
        """Parse numbered steps"""
        result = {
            "steps": [],
            "raw": text
        }
        
        # Match numbered steps (1., 2., etc.)
        step_pattern = r"(\d+)\.\s*([^\n]+(?:\n(?!\d+\.).*)*)"
        matches = re.findall(step_pattern, text)
        
        for num, content in matches:
            result["steps"].append({
                "number": int(num),
                "content": content.strip()
            })
        
        return result
