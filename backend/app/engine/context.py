from typing import Dict, Any, Optional
import json
from redis.asyncio import Redis
from app.core.config import settings

class ContextManager:
    """
    Manages the execution context of a workflow run.
    Persists state to Redis for stateless execution and recovery.
    """
    def __init__(self, run_id: str, redis: Redis):
        self.run_id = run_id
        self.redis = redis
        self._prefix = f"run:{run_id}"

    @property
    def state_key(self) -> str:
        return f"{self._prefix}:state"

    async def get_context(self) -> Dict[str, Any]:
        """Retrieve full context state from Redis"""
        data = await self.redis.get(self.state_key)
        if not data:
            return {}
        return json.loads(data)

    async def update_context(self, updates: Dict[str, Any]):
        """Update context with new variables"""
        # Optimistic locking or atomic operations needed for high concurrency
        # For now, simple GET-SET-MERGE
        current = await self.get_context()
        current.update(updates)
        await self.redis.set(self.state_key, json.dumps(current))
        
    async def get_var(self, key: str) -> Any:
        ctx = await self.get_context()
        return ctx.get(key)
    
    async def set_var(self, key: str, value: Any):
        await self.update_context({key: value})

    async def clear(self):
        await self.redis.delete(self.state_key)
