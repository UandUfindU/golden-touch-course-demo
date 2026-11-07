
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../'))

from app.main import app
from app.models.session import LayerType

client = TestClient(app)

def test_session_lifecycle():
    session_id = "test_session_123"
    
    # 1. Get Session (should create new)
    response = client.get(f"/api/v1/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["active_layer"] == "offline" # Default
    assert "offline" in data["graphs"]
    
    # 2. Switch Layer to ONLINE
    response = client.post(f"/api/v1/session/{session_id}/switch", json={"layer": "online"})
    assert response.status_code == 200
    data = response.json()
    assert data["active_layer"] == "online"
    
    # 3. Update Graph (OFFLINE)
    offline_nodes = [{"id": "n1", "type": "logic.ma"}]
    edges = []
    payload = {"nodes": offline_nodes, "edges": edges}
    
    response = client.post(f"/api/v1/graph/{session_id}/offline", json=payload)
    assert response.status_code == 200
    
    # 4. Switch back to OFFLINE and Verify Persistence
    response = client.get(f"/api/v1/session/{session_id}")
    graph_data = response.json()["graphs"]["offline"]
    assert len(graph_data["nodes"]) == 1
    assert graph_data["nodes"][0]["id"] == "n1"
    
    # 5. Check Context Isolation (ONLINE should be empty)
    online_graph = response.json()["graphs"]["online"]
    assert len(online_graph["nodes"]) == 0

if __name__ == "__main__":
    test_session_lifecycle()
    print("Session Lifecycle Test Passed!")
