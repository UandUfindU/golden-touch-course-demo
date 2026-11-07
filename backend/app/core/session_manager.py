from typing import Dict, Optional, Any, List
import logging
from datetime import datetime
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.session import SessionState, LayerType, GraphSnapshot
from app.models.sql import ChatSession, GraphSnapshot as GraphSnapshotSQL, ChatMessage, GenerationLog
from app.db.session import get_session as get_db_session

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions with hybrid persistence (Memory + DB).
    - API endpoints should call `load_session` before usage and `save_session` after updates.
    - Nodes access the in-memory `SessionState` synchronously.
    """
    
    def __init__(self):
        # Cache: session_id -> SessionState
        self._sessions: Dict[str, SessionState] = {}
        
    def get_session(self, session_id: str) -> SessionState:
        """
        Get session from memory. Creates new empty session if not found (lazy init).
        WARNING: Call `load_session` first to ensure data is synced from DB.
        """
        if session_id not in self._sessions:
            logger.info(f"Creating new in-memory session: {session_id}")
            session = SessionState(
                session_id=session_id,
                active_layer=LayerType.OFFLINE,
                graphs={
                    LayerType.ONLINE: GraphSnapshot(layer=LayerType.ONLINE),
                    LayerType.OFFLINE: GraphSnapshot(layer=LayerType.OFFLINE),
                    LayerType.TOOL: GraphSnapshot(layer=LayerType.TOOL),
                }
            )
            self._sessions[session_id] = session
        
        session = self._sessions[session_id]
        session.last_accessed = datetime.utcnow()
        return session
    
    async def load_session(self, session_id: str):
        """Load session from DB into memory."""
        async for db in get_db_session():
            statement = select(ChatSession).where(ChatSession.id == session_id).options(selectinload(ChatSession.snapshots))
            results = await db.exec(statement)
            db_session = results.first()
            
            if db_session:
                # Map DB -> Memory
                mem_session = self.get_session(session_id) # Get or create default
                mem_session.title = db_session.title
                
                # Load Graphs
                for snap in db_session.snapshots:
                    try:
                        layer = LayerType(snap.layer)
                        mem_session.graphs[layer] = GraphSnapshot(
                            layer=layer,
                            nodes=snap.graph_json.get("nodes", []),
                            edges=snap.graph_json.get("edges", []),
                            updated_at=snap.created_at
                        )
                    except ValueError:
                        continue
                logger.info(f"Loaded session {session_id} from DB")
            else:
                logger.info(f"Session {session_id} not found in DB, starting fresh.")

    async def save_session(self, session_id: str):
        """Persist in-memory session to DB."""
        session = self.get_session(session_id)
        
        async for db in get_db_session():
            # 1. Update/Create ChatSession
            statement = select(ChatSession).where(ChatSession.id == session_id)
            results = await db.exec(statement)
            db_session = results.first()
            
            if not db_session:
                db_session = ChatSession(
                    id=session_id, 
                    user_id=session.user_id or "default",
                    title="New Session"
                )
                db.add(db_session)
            
            db_session.updated_at = datetime.utcnow()
            
            # 2. Save Snapshots (Upsert-like: we just save latest state as a new snapshot if changed? 
            # Or just update the 'current' state? For MVP, let's just update the current 'latest' snapshot per layer)
            # Actually, User wants full history. But for now, let's at least save the current state.
            
            for layer, graph in session.graphs.items():
                if not graph.nodes: continue # Skip empty graphs
                
                # Check if we should save a snapshot (e.g. hash check? or just save on every explicit save?)
                # For Phase 3, we just save.
                snapshot = GraphSnapshotSQL(
                    session_id=session_id,
                    layer=layer if isinstance(layer, str) else layer.value,
                    version=1, # TODO: Versioning
                    graph_json={"nodes": graph.nodes, "edges": graph.edges}
                )
                db.add(snapshot)
            
            await db.commit()
            logger.info(f"Saved session {session_id} to DB")

    async def _ensure_chat_session(self, db, session_id: str):
        if await db.get(ChatSession, session_id) is not None:
            return

        try:
            async with db.begin_nested():
                db.add(ChatSession(id=session_id, user_id="default", title="New Session"))
                await db.flush()
        except IntegrityError:
            # Another request may have created this session while we were starting it.
            if await db.get(ChatSession, session_id) is None:
                raise

    async def add_chat_message(self, session_id: str, role: str, content: str, source: str = "user"):
        """Append a message to the session's chat history in DB."""
        async for db in get_db_session():
            await self._ensure_chat_session(db, session_id)
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                source=source,
                created_at=datetime.utcnow()
            )
            db.add(msg)
            await db.commit()
            # Optional: Emit via socket?
            
    async def get_chat_history(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        """Retrieve recent chat history from DB."""
        async for db in get_db_session():
            statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(limit)
            results = await db.exec(statement)
            # Reverse to chronological order
            return list(reversed(results.all()))
        return []

    def switch_layer(self, session_id: str, layer: LayerType) -> SessionState:
        """Switch the active layer for a session."""
        session = self.get_session(session_id)
        if session.active_layer != layer:
            logger.info(f"Session {session_id} switching layer: {session.active_layer} -> {layer}")
            session.active_layer = layer
            session.last_accessed = datetime.utcnow()
        return session
    
    def update_graph(self, session_id: str, layer: LayerType, nodes: list, edges: list) -> SessionState:
        """Update the graph data for a specific layer."""
        session = self.get_session(session_id)
        
        # Update specific graph
        session.graphs[layer] = GraphSnapshot(
            layer=layer,
            nodes=nodes,
            edges=edges,
            updated_at=datetime.utcnow()
        )
        session.last_accessed = datetime.utcnow()
        return session

    def get_active_context(self, session_id: str) -> Dict[str, Any]:
        """
        Retrives the context relevant to the ACTIVE layer.
        Used for injecting into LLM prompt.
        """
        session = self.get_session(session_id)
        layer = session.active_layer
        graph = session.graphs.get(layer)
        
        return {
            "session_id": session_id,
            "active_layer": layer,
            "graph_summary": {
                "node_count": len(graph.nodes) if graph else 0,
                "edge_count": len(graph.edges) if graph else 0
            },
            # We explicitly send the full graph schema for the LLM to 'see'
            "graph_data": graph.model_dump() if graph else None
        }

    async def log_generation_trace(self, session_id: str, prompt: str, success: bool, trace: List[Dict[str, Any]]):
        """
        Log an LLM generation trace for fine-tuning.
        """
        async for db in get_db_session():
            log_entry = GenerationLog(
                session_id=session_id,
                prompt=prompt,
                final_success=success,
                trace_data=trace
            )
            db.add(log_entry)
            await db.commit()
            
    async def log_backtest_result(self, session_id: str, layer: str, graph: Dict, result: Dict):
        """
        Log a backtest experiment. Encapsulates the graph snapshot + result.
        """
        from app.models.sql import BacktestRecord
        async for db in get_db_session():
            await self._ensure_chat_session(db, session_id)
            # 1. Snapshot
            snapshot = GraphSnapshotSQL(
                session_id=session_id,
                layer=layer,
                graph_json=graph,
                version=int(datetime.utcnow().timestamp()) 
            )
            db.add(snapshot)
            await db.flush()
            
            # 2. Result
            metrics = result.get("metrics", {})
            record = BacktestRecord(
                snapshot_id=snapshot.id,
                sharpe=metrics.get("sharpe_ratio", 0.0),
                pnl=metrics.get("total_pnl", 0.0),
                max_dd=metrics.get("max_drawdown", 0.0),
                metrics=metrics,
                trades=result.get("trades", [])
            )
            db.add(record)
            await db.commit()

# Global Instance
session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    return session_manager
