from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.nodes.registry import registry

router = APIRouter(prefix="/nodes", tags=["nodes"])

@router.get("/", response_model=List[Dict[str, Any]])
async def list_nodes():
    """
    List all available nodes with metadata.
    Used by Frontend Node Palette.
    """
    return registry.get_all_metadata()

@router.get("/{unique_key}")
async def get_node_details(unique_key: str):
    """
    Get detailed schema for a specific node type.
    """
    meta = next((m for m in registry.get_all_metadata() if m["name"] == unique_key), None)
    # Note: registry uses unique_key concept but in registry.py we used name as key temporary. 
    # Should align.
    
    # In registry.py: unique_key = name. 
    # And cls._metadata keys are unique_key.
    
    # Let's check registry.py implementation:
    # cls._metadata[unique_key] = ...
    # So we can just lookup
    
    # Actually registry didn't expose get_metadata_by_key, but we can iterate or add method.
    # Iteration is fine for now.
    if not meta:
        raise HTTPException(status_code=404, detail="Node not found")
    return meta
