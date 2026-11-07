from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os
import time

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope

class SaveStrategyInput(BaseModel):
    name: str = Field(description="Name of the strategy")
    graph_data: Dict[str, Any] = Field(description="The graph definition (nodes, edges)")
    code: Optional[str] = Field(default=None, description="Generated Python code")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")

class SaveStrategyOutput(BaseModel):
    success: bool = Field(description="Whether save was successful")
    strategy_id: str = Field(description="ID of the saved strategy")
    message: str = Field(description="Status message")

@register_node(
    category=NodeCategory.UTILITY,
    name="tool.save_strategy",
    scopes=[NodeScope.STRATEGY, NodeScope.WORKFLOW]
)
class SaveStrategyNode(BaseNode):
    """
    Save Strategy Node - Persists the current strategy.
    
    In a real production system, this would write to a PostgreSQL/MongoDB 'strategies' table.
    For this prototype, it manages a 'strategies.json' file in the storage directory.
    """
    description = "Save current strategy to registry"
    InputSchema = SaveStrategyInput
    OutputSchema = SaveStrategyOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Simulate Persistence Layer
        storage_dir = "storage/strategies"
        os.makedirs(storage_dir, exist_ok=True)
        registry_file = os.path.join(storage_dir, "registry.json")
        
        # Load existing
        registry = {}
        if os.path.exists(registry_file):
            try:
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
            except:
                registry = {}
        
        # Generate ID (simple slug)
        strategy_id = params.name.lower().replace(" ", "_") + "_" + str(int(time.time()))
        
        # Create Record
        record = {
            "id": strategy_id,
            "name": params.name,
            "graph": params.graph_data,
            "code": params.code,
            "created_at": time.time(),
            "metadata": params.metadata
        }
        
        # Save to individual file (for clean versioning)
        strategy_path = os.path.join(storage_dir, f"{strategy_id}.json")
        with open(strategy_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            
        # Update Registry (Summary)
        registry[strategy_id] = {
            "name": params.name,
            "path": strategy_path,
            "updated_at": time.time()
        }
        
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
            
        return {
            "success": True,
            "strategy_id": strategy_id,
            "message": f"Strategy '{params.name}' saved successfully to {strategy_path}"
        }
