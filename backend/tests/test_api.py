"""
API Integration Tests for Golden Touch Backend.
Uses FastAPI's TestClient with mocked database session.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.main import app
from app.db.session import get_session

# --- Setup Mock Session ---
# AsyncMock simulates AsyncSession behavior
mock_session = AsyncMock()

# Override FastAPI dependency
# get_session is an async generator, but for testing we return a simple mock
async def override_get_session():
    return mock_session

app.dependency_overrides[get_session] = override_get_session

# Create sync TestClient
client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self):
        """Verify health endpoint returns ok status"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestNodesEndpoint:
    def test_list_nodes(self):
        """Verify nodes endpoint returns registered nodes"""
        # Import node implementations to trigger registration
        import app.nodes.impl.core.flow.if_node  # noqa: F401
        
        response = client.get("/api/v1/nodes/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Verify LogicIfNode is registered
        found = next((n for n in data if n["name"] == "logic.if"), None)
        assert found is not None, "LogicIfNode should be registered"
        assert found["category"] == "flow"


class TestWorkflowEndpoint:
    def setup_method(self):
        """Reset mock before each test"""
        mock_session.reset_mock()
        # Setup default mock behaviors
        mock_session.add = MagicMock()  # add() is synchronous
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.exec = AsyncMock()
        mock_session.get = AsyncMock()
        mock_session.delete = AsyncMock()

    def test_create_workflow(self):
        """Test workflow creation via POST"""
        # Workflow model has default_factory for id, so it will be auto-generated
        payload = {
            "name": "Test Workflow",
            "description": "Created via API test",
            "graph_data": {"nodes": [], "edges": []}
        }
        
        response = client.post("/api/v1/workflows/", json=payload)
        
        # Debug output if failed
        if response.status_code != 200:
            print(f"Create failed: {response.status_code} - {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert "id" in data  # ID should be auto-generated
        
        # Verify session methods were called
        assert mock_session.add.called
        assert mock_session.commit.called
