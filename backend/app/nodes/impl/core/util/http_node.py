"""
HttpRequest Node - Makes HTTP requests to external APIs.

Part of core/util nodes, available in all scopes.
"""
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope
import httpx


class HttpRequestInput(BaseModel):
    """HttpRequest input"""
    url: str = Field(description="URL to request")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET",
        description="HTTP method"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Request headers"
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Request body (for POST/PUT/PATCH)"
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )


class HttpRequestOutput(BaseModel):
    status_code: int = Field(description="HTTP status code")
    response_body: Any = Field(description="Response body (parsed as JSON if possible)")
    headers: Dict[str, str] = Field(description="Response headers")
    success: bool = Field(description="Whether request was successful (2xx)")


@register_node(
    category=NodeCategory.UTILITY,
    name="util.http_request",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class HttpRequestNode(BaseNode):
    """
    HttpRequest Node - Makes HTTP requests to external APIs.
    
    Supports all common HTTP methods with configurable headers and body.
    Responses are automatically parsed as JSON when possible.
    """
    description = "Make an HTTP request"
    InputSchema = HttpRequestInput
    OutputSchema = HttpRequestOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        try:
            with httpx.Client(timeout=params.timeout) as client:
                response = client.request(
                    method=params.method,
                    url=params.url,
                    headers=params.headers,
                    json=params.body if params.method in ["POST", "PUT", "PATCH"] else None
                )
                
                # Try to parse response as JSON
                try:
                    response_body = response.json()
                except Exception:
                    response_body = response.text
                
                return {
                    "status_code": response.status_code,
                    "response_body": response_body,
                    "headers": dict(response.headers),
                    "success": 200 <= response.status_code < 300
                }
                
        except httpx.TimeoutException:
            return {
                "status_code": 0,
                "response_body": {"error": "Request timed out"},
                "headers": {},
                "success": False
            }
        except httpx.RequestError as e:
            return {
                "status_code": 0,
                "response_body": {"error": str(e)},
                "headers": {},
                "success": False
            }
