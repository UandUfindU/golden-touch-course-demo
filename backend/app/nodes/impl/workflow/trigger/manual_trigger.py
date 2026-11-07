"""
Manual Trigger Node - Entry point for manually started workflows.

Part of workflow/trigger nodes, SCOPE_WORKFLOW only.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class ManualTriggerInput(BaseModel):
    """Manual trigger can accept initial input data"""
    initial_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Initial data passed when manually triggering the workflow"
    )


class ManualTriggerOutput(BaseModel):
    triggered: bool = Field(description="Always True for manual trigger")
    trigger_time: str = Field(description="ISO timestamp when triggered")
    initial_data: Dict[str, Any] = Field(description="Passed through initial data")


@register_node(
    category=NodeCategory.TRIGGER,
    name="trigger.manual",
    scopes=[NodeScope.WORKFLOW]
)
class ManualTriggerNode(BaseNode):
    """
    Manual Trigger Node - Entry point for user-initiated workflows.
    
    This node serves as the starting point for workflows that are
    triggered manually by a user (e.g., clicking "Run" in the UI).
    
    It passes through any initial data provided by the user.
    """
    description = "Manual workflow trigger"
    InputSchema = ManualTriggerInput
    OutputSchema = ManualTriggerOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        from datetime import datetime, timezone
        
        params = self.validate_inputs(ctx.inputs)
        
        return {
            "triggered": True,
            "trigger_time": datetime.now(timezone.utc).isoformat(),
            "initial_data": params.initial_data or {}
        }
