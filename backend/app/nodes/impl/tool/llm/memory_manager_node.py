"""
Memory Manager Node - Manages conversation history.

Uses LangChain's ConversationBufferMemory with Redis backend.
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class MemoryManagerInput(BaseModel):
    """MemoryManager node input"""
    session_id: str = Field(
        description="Session/conversation ID"
    )
    action: Literal["get", "add", "clear"] = Field(
        default="get",
        description="Action to perform on memory"
    )
    message: Optional[Dict[str, str]] = Field(
        default=None,
        description="Message to add (for 'add' action): {role, content}"
    )
    max_history: int = Field(
        default=20,
        description="Maximum messages to keep in history"
    )


class MemoryManagerOutput(BaseModel):
    history: List[Dict[str, str]] = Field(description="Conversation history")
    success: bool = Field(description="Whether action succeeded")
    message_count: int = Field(description="Number of messages in history")


@register_node(
    category=NodeCategory.AI,
    name="llm.memory_manager",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class MemoryManagerNode(BaseNode):
    """
    Memory Manager Node - Store and retrieve conversation history.
    
    Uses Redis for persistence. For production, can integrate with
    LangChain's ConversationBufferMemory or Zep for advanced features.
    
    MVP: In-memory storage (context-based)
    Production: Redis + LangChain Memory
    """
    description = "Manage conversation memory"
    InputSchema = MemoryManagerInput
    OutputSchema = MemoryManagerOutput
    
    # In-memory storage for MVP (should be Redis in production)
    _memory_store: Dict[str, List[Dict[str, str]]] = {}

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        session_id = params.session_id
        
        if params.action == "get":
            return self._get_history(session_id)
        elif params.action == "add":
            return self._add_message(session_id, params.message, params.max_history)
        elif params.action == "clear":
            return self._clear_history(session_id)
        else:
            return {
                "history": [],
                "success": False,
                "message_count": 0
            }
    
    def _get_history(self, session_id: str) -> Dict[str, Any]:
        """Get conversation history for a session"""
        history = self._memory_store.get(session_id, [])
        return {
            "history": history,
            "success": True,
            "message_count": len(history)
        }
    
    def _add_message(self, session_id: str, message: Optional[Dict[str, str]], max_history: int) -> Dict[str, Any]:
        """Add a message to history"""
        if not message:
            return {
                "history": self._memory_store.get(session_id, []),
                "success": False,
                "message_count": len(self._memory_store.get(session_id, []))
            }
        
        if session_id not in self._memory_store:
            self._memory_store[session_id] = []
        
        self._memory_store[session_id].append(message)
        
        # Trim to max_history
        if len(self._memory_store[session_id]) > max_history:
            self._memory_store[session_id] = self._memory_store[session_id][-max_history:]
        
        return {
            "history": self._memory_store[session_id],
            "success": True,
            "message_count": len(self._memory_store[session_id])
        }
    
    def _clear_history(self, session_id: str) -> Dict[str, Any]:
        """Clear history for a session"""
        if session_id in self._memory_store:
            del self._memory_store[session_id]
        
        return {
            "history": [],
            "success": True,
            "message_count": 0
        }
