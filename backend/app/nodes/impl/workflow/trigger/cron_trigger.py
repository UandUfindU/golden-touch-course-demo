"""
Cron Trigger Node - Entry point for scheduled workflows.

Part of workflow/trigger nodes, SCOPE_WORKFLOW only.
Uses cron expressions to define schedule.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class CronTriggerInput(BaseModel):
    """Cron trigger configuration - stored in node config, not runtime input"""
    cron_expression: str = Field(
        default="0 * * * *",  # Every hour by default
        description="Cron expression (minute hour day month weekday)"
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for cron schedule"
    )


class CronTriggerOutput(BaseModel):
    triggered: bool = Field(description="Always True when executed")
    trigger_time: str = Field(description="ISO timestamp when triggered")
    scheduled_time: str = Field(description="The scheduled time this was meant to run")
    next_run: Optional[str] = Field(description="Next scheduled execution time")


@register_node(
    category=NodeCategory.TRIGGER,
    name="trigger.cron",
    scopes=[NodeScope.WORKFLOW]
)
class CronTriggerNode(BaseNode):
    """
    Cron Trigger Node - Entry point for scheduled workflows.
    
    This node is the starting point for workflows that run on a schedule.
    The actual scheduling is handled by an external scheduler (e.g., APScheduler,
    Celery Beat) that calls the workflow execution API at the scheduled times.
    
    When this node runs, it means the scheduler has triggered it.
    The node just records the trigger metadata and passes through.
    """
    description = "Scheduled workflow trigger (cron)"
    InputSchema = CronTriggerInput
    OutputSchema = CronTriggerOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        from datetime import datetime, timezone
        
        params = self.validate_inputs(ctx.inputs)
        
        # In a real implementation, the scheduler would inject
        # the actual scheduled_time and calculate next_run using croniter.
        # For now, we just record current time.
        
        now = datetime.now(timezone.utc)
        
        return {
            "triggered": True,
            "trigger_time": now.isoformat(),
            "scheduled_time": ctx.inputs.get("_scheduled_time", now.isoformat()),
            "next_run": ctx.inputs.get("_next_run")
        }
