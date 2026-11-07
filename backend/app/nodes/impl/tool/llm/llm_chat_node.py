"""
LLM Chat Node - Base LLM calling node (Custom implementation).

Supports multiple providers (GLM, OpenAI, Local) with streaming.
This is a custom implementation for full control over streaming format.
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
import os


class LLMChatInput(BaseModel):
    """LLMChat node input"""
    messages: List[Dict[str, str]] = Field(
        description="List of message dicts (role, content)"
    )
    model: str = Field(
        default="glm-4.5-flash",
        description="Model name to use"
    )
    provider: Literal["glm", "openai", "local"] = Field(
        default="glm",
        description="LLM provider"
    )
    temperature: float = Field(
        default=0.1,
        description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=8192,
        description="Maximum tokens to generate"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response"
    )


class LLMChatOutput(BaseModel):
    response: str = Field(description="LLM response content")
    model: str = Field(description="Model used")
    usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage")


@register_node(
    category=NodeCategory.AI,
    name="tool.llm.chat",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class LLMChatNode(BaseNode):
    """
    LLM Chat Node - Call an LLM with messages.
    
    Custom implementation (not using LangChain) for full control over:
    - Streaming format and token-by-token output
    - Provider-specific handling
    - Error handling and retries
    
    Supports: GLM (Zhipu), OpenAI, Local (placeholder)
    """
    description = "Call an LLM with chat messages"
    InputSchema = LLMChatInput
    OutputSchema = LLMChatOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Handle "provider/model" format in model field
        if "/" in params.model:
            parts = params.model.split("/", 1)
            provider_candidate = parts[0].lower()
            if provider_candidate in ["cerebras", "zai", "openai", "glm"]:
                params.provider = provider_candidate
                params.model = parts[1]
                # Map 'zai' to 'glm' for internal logic if needed, or keep distinct
                if params.provider == "zai":
                    params.provider = "glm"

        if params.provider == "glm":
            return self._call_glm(params, ctx)
        elif params.provider == "openai":
            return self._call_openai(params, ctx)
        elif params.provider == "cerebras":
            return self._call_cerebras(params, ctx)
        elif params.provider == "local":
            return self._call_local(params, ctx)
        else:
            return {
                "response": f"Unknown provider: {params.provider}",
                "model": params.model,
                "usage": None
            }
    
    def _call_glm(self, params: LLMChatInput, ctx: Context = None) -> Dict[str, Any]:
        """Call Zhipu GLM API"""
        try:
            from zhipuai import ZhipuAI
            
            # Prefer ZAI_API_KEY, fallback to ZHIPU_API_KEY
            api_key = os.getenv("ZAI_API_KEY") or os.getenv("ZHIPU_API_KEY")
            if not api_key:
                return {
                    "response": "Error: ZAI_API_KEY not set",
                    "model": params.model,
                    "usage": None
                }
            
            client = ZhipuAI(api_key=api_key)
            
            if ctx:
                ctx.emit_status(f"🤖 Calling ZhipuAI ({params.model})...")
            
            # [DEBUG] Print full prompt for E2E testing
            print(f"\n[LLM_INPUT] Model: {params.model}")
            for msg in params.messages:
                print(f"--- Role: {msg['role']} ---")
                print(msg['content'])
            print("--------------------------------\n")
            
            response = client.chat.completions.create(
                model=params.model,
                messages=params.messages,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                stream=False,  # TODO: Implement GLM streaming if reasoning needed
                timeout=60
            )
            
            if response.choices:
                content = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
                return {
                    "response": content,
                    "model": params.model,
                    "usage": usage
                }
            
            return {
                "response": "",
                "model": params.model,
                "usage": None
            }
            
        except Exception as e:
            return {
                "response": f"Error calling GLM: {e}",
                "model": params.model,
                "usage": None
            }
    
    def _call_openai(self, params: LLMChatInput, ctx: Context = None) -> Dict[str, Any]:
        """Call OpenAI API"""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
            
            if not api_key:
                return {
                    "response": "Error: OPENAI_API_KEY not set",
                    "model": params.model,
                    "usage": None
                }
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            if ctx:
                ctx.emit_status(f"🤖 Calling OpenAI ({params.model})...")

            response = client.chat.completions.create(
                model=params.model,
                messages=params.messages,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                timeout=60
            )
            
            if response.choices:
                content = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
                return {
                    "response": content,
                    "model": params.model,
                    "usage": usage
                }
            
            return {
                "response": "",
                "model": params.model,
                "usage": None
            }
            
        except Exception as e:
            return {
                "response": f"Error calling OpenAI: {e}",
                "model": params.model,
                "usage": None
            }

    def _call_cerebras(self, params: LLMChatInput, ctx: Context = None) -> Dict[str, Any]:
        """Call Cerebras API (via OpenAI SDK)"""
        try:
            from openai import OpenAI
            
            api_key = os.getenv("CEREBRAS_API_KEY")
            base_url = "https://api.cerebras.ai/v1"
            
            if not api_key:
                return {
                    "response": "Error: CEREBRAS_API_KEY not set",
                    "model": params.model,
                    "usage": None
                }
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            if ctx:
                ctx.emit_status(f"🧠 Calling Cerebras ({params.model})...")

            # Force stream=True if we want to capture reasoning/thinking
            # Even if params.stream is False, we might stream internally to capture reasoning
            should_stream = True 
            
            completion = client.chat.completions.create(
                model=params.model,
                messages=params.messages,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                stream=should_stream,
                timeout=60
            )
            
            full_content = []
            
            for chunk in completion:
                delta = chunk.choices[0].delta
                
                # Check for reasoning content (Cerebras/DeepSeek style)
                # Note: Adjust field name based on actual provider API (e.g. 'reasoning_content' or similar)
                # For now assume 'reasoning_content' or check standard delta
                reasoning = getattr(delta, 'reasoning_content', None)
                content = delta.content
                
                if reasoning and ctx:
                    # Emit reasoning event
                    # We send a dict, ChatService will need to handle it
                    ctx.emit_status({"type": "think", "content": reasoning})
                
                if content:
                    full_content.append(content)
            
            response_text = "".join(full_content)
            
            return {
                "response": response_text,
                "model": params.model,
                "usage": None # Usage is tricky with streaming in some providers
            }
            
        except Exception as e:
            return {
                "response": f"Error calling Cerebras: {e}",
                "model": params.model,
                "usage": None
            }

    def _call_local(self, params: LLMChatInput, ctx: Context = None) -> Dict[str, Any]:
        """Placeholder for local LLM (Ollama, vLLM, etc.)"""
        return {
            "response": "Local LLM not implemented yet",
            "model": params.model,
            "usage": None
        }
