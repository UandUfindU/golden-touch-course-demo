from typing import Dict, Any, List, Optional
from sqlmodel import Field, JSON
import sqlalchemy as sa
from app.models.base import DBModel
from app.core.enums import NodeCategory, NodeScope

class NodeDef(DBModel, table=True):
    __tablename__ = "node_defs"
    
    # Unique identifier for the node type, e.g., "pandas_ta.ma"
    unique_key: str = Field(unique=True, index=True, nullable=False)
    name: str = Field(nullable=False)
    description: Optional[str] = None
    
    # Taxonomy
    category: NodeCategory = Field(index=True)
    scopes: List[str] = Field(
        default=[NodeScope.STRATEGY],
        sa_column=sa.Column(JSON, nullable=False)
    )
    
    # Interface Definition (JSON Schema)
    input_schema: Dict[str, Any] = Field(
        default={}, sa_column=sa.Column(JSON, nullable=False)
    )
    output_schema: Dict[str, Any] = Field(
        default={}, sa_column=sa.Column(JSON, nullable=False)
    )
    
    # Implementation link
    class_path: str = Field(nullable=False, description="Full Python path to the implementation class")
    
    # Versioning
    version: str = Field(default="1.0.0")
