from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel

class Context(BaseModel):
    """Execution Context passed to every node run"""
    run_id: str
    workflow_id: str
    node_id: str
    # Access to previous node outputs
    inputs: Dict[str, Any] 
    # Global state (e.g., database session, redis client)
    # This will be injected by the runner
    services: Dict[str, Any] = {}
    
    # Optional callback for real-time status updates (e.g., streaming to frontend)
    # This allows nodes to "talk" during execution without async generators
    on_status_update: Optional[Any] = None 
    
    def emit_status(self, message: str):
        """Helper to emit status if callback is registered"""
        # Always log to stdout for debugging
        print(f"[Status] {message}")
        
        if self.on_status_update and callable(self.on_status_update):
            try:
                self.on_status_update(message)
            except Exception:
                pass # Suppress callback errors to avoid breaking execution

class BaseNode(ABC):
    """Abstract Base Class for all Workflow Nodes"""
    
    # Metadata to be defined by subclasses
    name: str = "Base Node"
    description: str = ""
    # Category and scopes will be populated by registry decorator
    category: str = "utility"
    
    # Schema Definitions (Pydantic Models)
    # Must be overridden by subclasses
    InputSchema: Type[BaseModel] = BaseModel
    OutputSchema: Type[BaseModel] = BaseModel

    def __init__(self):
        pass

    @abstractmethod
    def run(self, ctx: Context) -> Dict[str, Any]:
        """
        Core execution logic.
        Must return a dictionary matching OutputSchema.
        """
        pass

    @classmethod
    def get_input_schema_json(cls) -> Dict[str, Any]:
        if cls.InputSchema is BaseModel:
            return {}
        return cls.InputSchema.model_json_schema()

    @classmethod
    def get_output_schema_json(cls) -> Dict[str, Any]:
        if cls.OutputSchema is BaseModel:
            return {}
        return cls.OutputSchema.model_json_schema()

    def validate_inputs(self, inputs: Dict[str, Any]) -> BaseModel:
        """Validate raw dictionary against InputSchema"""
        return self.InputSchema(**inputs)
