from typing import Dict, Any, Optional
from sqlmodel import Field, JSON
import sqlalchemy as sa
from app.models.base import DBModel

class Workflow(DBModel, table=True):
    __tablename__ = "workflows"
    
    name: str = Field(index=True, nullable=False)
    description: Optional[str] = Field(default=None)
    
    # Store graph topological structure (Nodes & Edges)
    # Using JSONB in Postgres for efficient querying if needed
    graph_data: Dict[str, Any] = Field(
        default={}, 
        sa_column=sa.Column(JSON, nullable=False)
    )
    
    # Versioning for future proofing
    version: int = Field(default=1)
    
    # Is this a template?
    is_template: bool = Field(default=False)
