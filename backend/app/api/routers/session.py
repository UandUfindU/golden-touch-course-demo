from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List

from app.core.session_manager import get_session_manager, SessionManager
from app.models.session import SessionState, LayerType

router = APIRouter(tags=["session"])

@router.get("/session/{session_id}", response_model=SessionState)
async def get_session_info(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    """Get current session state."""
    return manager.get_session(session_id)

@router.post("/session/{session_id}/switch")
async def switch_layer(
    session_id: str,
    layer: LayerType = Body(..., embed=True),
    manager: SessionManager = Depends(get_session_manager)
):
    """Switch active layer (Online/Offline/Tool)."""
    return manager.switch_layer(session_id, layer)

@router.get("/graph/{session_id}/{layer}")
async def get_layer_graph(
    session_id: str,
    layer: LayerType,
    manager: SessionManager = Depends(get_session_manager)
):
    """Get graph data for a specific layer."""
    session = manager.get_session(session_id)
    if layer not in session.graphs:
        return {"nodes": [], "edges": []}
    return session.graphs[layer]

@router.post("/graph/{session_id}/{layer}")
async def update_layer_graph(
    session_id: str,
    layer: LayerType,
    data: Dict[str, List[Any]] = Body(...),
    manager: SessionManager = Depends(get_session_manager)
):
    """Update graph data (Autosave)."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    manager.update_graph(session_id, layer, nodes, edges)
    return {"status": "ok", "updated_layer": layer}
