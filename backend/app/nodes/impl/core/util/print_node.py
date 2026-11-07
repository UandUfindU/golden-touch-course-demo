"""
Print Node - Outputs a message to the frontend display panel.

Part of core/util nodes, available in all scopes.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class PrintInput(BaseModel):
    """Print node input"""
    message: str = Field(description="Message to display")
    level: str = Field(
        default="info",
        description="Log level: info, warning, error, debug"
    )


class PrintOutput(BaseModel):
    printed: bool = Field(description="Whether the message was printed")
    message: str = Field(description="The printed message")


@register_node(
    category=NodeCategory.UTILITY,
    name="util.print",
    scopes=[NodeScope.WORKFLOW, NodeScope.STRATEGY, NodeScope.TOOL]
)
class PrintNode(BaseNode):
    """
    Print Node - Outputs a message for user display.
    
    Unlike debug logging (which is controlled by node's `debug` attribute),
    this node explicitly outputs a message to the user-facing panel.
    
    The message is stored in the run context and pushed to the frontend
    via WebSocket for real-time display.
    """
    description = "Print a message to the output panel"
    InputSchema = PrintInput
    OutputSchema = PrintOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # In production, this would:
        # 1. Log to run-specific log stream
        # 2. Push to WebSocket for real-time display
        # For now, we just return the message to be captured in context
        
        import logging
        logger = logging.getLogger(f"node.print.{ctx.node_id}")
        
        log_method = getattr(logger, params.level, logger.info)
        log_method(f"[{ctx.run_id}] {params.message}")
        
        return {
            "printed": True,
            "message": params.message
        }
