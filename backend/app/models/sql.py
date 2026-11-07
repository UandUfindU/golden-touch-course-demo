from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON

class ChatSession(SQLModel, table=True):
    """
    Represents a user's conversation session.
    """
    __tablename__ = "chat_sessions"
    
    id: Optional[str] = Field(default=None, primary_key=True)  # UUID string
    user_id: str = Field(index=True)
    title: Optional[str] = Field(default="Untitled Session")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    messages: List["ChatMessage"] = Relationship(back_populates="session")
    snapshots: List["GraphSnapshot"] = Relationship(back_populates="session")
    logs: List["GenerationLog"] = Relationship(back_populates="session")


class ChatMessage(SQLModel, table=True):
    """
    A single message in the chat history.
    Flat structure: 'source' field distinguishes MainAgent vs Tool outputs.
    """
    __tablename__ = "chat_messages"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.id", index=True)
    
    role: str = Field(description="user / assistant / system")
    content: str = Field(description="The message text")
    
    # improved flat design: source identifies the generator
    source: str = Field(default="user", description="e.g. user, main_agent, tool:build_strategy")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    session: ChatSession = Relationship(back_populates="messages")


class GraphSnapshot(SQLModel, table=True):
    """
    A versioned snapshot of the strategy graph.
    Saved whenever a successful modification occurs.
    """
    __tablename__ = "graph_snapshots"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.id", index=True)
    
    layer: str = Field(description="online / offline / tool")
    version: int = Field(default=1)
    
    # Use SA JSON type for JSON storage
    graph_json: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: ChatSession = Relationship(back_populates="snapshots")
    backtests: List["BacktestRecord"] = Relationship(back_populates="snapshot")


class GenerationLog(SQLModel, table=True):
    """
    The 'Gold Mine': Records the internal 'Thinking & Fixing' trace of LLM tools.
    Used for future fine-tuning.
    """
    __tablename__ = "generation_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.id", index=True)
    
    prompt: str = Field(description="The original user request trigger")
    final_success: bool = Field(default=False)
    
    # Stores the detailed RetryNode trace: [{attempt:1, error:..., fix:...}, ...]
    trace_data: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    session: ChatSession = Relationship(back_populates="logs")


class BacktestRecord(SQLModel, table=True):
    """
    Results of a backtest run.
    """
    __tablename__ = "backtest_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="graph_snapshots.id", index=True)
    
    # Key Metrics
    sharpe: float = Field(default=0.0)
    pnl: float = Field(default=0.0)
    max_dd: float = Field(default=0.0)
    
    # Detailed Data
    metrics: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    trades: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    snapshot: GraphSnapshot = Relationship(back_populates="backtests")
