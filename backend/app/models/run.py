from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlmodel import Field, JSON
import sqlalchemy as sa
from app.models.base import DBModel
from app.core.enums import RunStatus

class WorkflowRun(DBModel, table=True):
    __tablename__ = "workflow_runs"
    
    workflow_id: UUID = Field(foreign_key="workflows.id", index=True, nullable=False)
    
    # Execution State
    status: RunStatus = Field(default=RunStatus.PENDING, index=True)
    
    # Context Snapshot (The state of all variables at the current moment)
    # Critical for resuming and debugging
    context_snapshot: Dict[str, Any] = Field(
        default={}, sa_column=sa.Column(JSON, nullable=False)
    )
    
    # Error tracking
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Performance metrics
    start_time: Optional[float] = None
    end_time: Optional[float] = None
