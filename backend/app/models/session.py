from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class LayerType(str, Enum):
    """
    Defines the active operational layer of the application.
    Different layers expose different tools and context to the LLM.
    """
    ONLINE = "online"   # Integration & Deployment (Workflow Editor)
    OFFLINE = "offline" # Strategy Logic Development (Strategy Lab)
    TOOL = "tool"       # Custom Component Building (Node Builder)

class GraphSnapshot(BaseModel):
    """Snapshot of a graph in a specific layer."""
    layer: LayerType
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SessionState(BaseModel):
    """
    Holds the state of a user's interaction session.
    """
    session_id: str = Field(description="Unique session identifier")
    user_id: Optional[str] = Field(default="default_user", description="User identifier")
    title: Optional[str] = Field(default="New Session", description="Session display name")
    
    # State
    active_layer: LayerType = Field(default=LayerType.OFFLINE, description="Currently active view/layer")
    
    # Data Storage (In-Memory for MVP)
    # Maps LayerType -> Graph Data (dict or GraphSnapshot)
    graphs: Dict[LayerType, GraphSnapshot] = Field(default_factory=dict, description="Graphs for each layer")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
