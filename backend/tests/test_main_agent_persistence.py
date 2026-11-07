
import pytest
import os
import sys
import uuid
import asyncio
from dotenv import load_dotenv

# Add backend to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
if backend_dir not in sys.path:
    sys.path.append(os.path.join(backend_dir, "backend"))

from app.nodes.base import Context
from app.core.session_manager import session_manager, LayerType
from app.nodes.impl.agent.main_router import MainRouterNode
from app.models.sql import ChatMessage

class TestMainAgentPersistence:
    
    @classmethod
    def setup_class(cls):
        load_dotenv()
        # Ensure we have a DB URL
        pass

    @pytest.mark.asyncio
    async def test_chat_persistence_flow(self):
        """
        Simulate a user talking to MainRouter, verify responses and DB persistence.
        """
        print("\n>>> Starting MainRouter Persistence Test...")
        
        # 1. Setup Session
        session_id = f"test_flow_{uuid.uuid4().hex[:8]}"
        print(f"Session ID: {session_id}")
        
        # Initialize session in DB (via save_session which lazily creates)
        # Or just let the router/manager handle it? 
        # In our logic, manager.save_session creates the session if invalid. 
        # But MainRouter logic: `sess = session_manager.get_session()` -> Gets in-memory.
        # It doesn't explicitly save session metadata yet unless we added that.
        # Let's ensure session exists in DB first to be safe, simulating a "Session Start" API call.
        await session_manager.save_session(session_id)
        
        # 2. Simulate Input (User: "Hello, I want to create a strategy")
        user_msg = "Hello, I want to create a strategy for BTC"
        
        # We manually persist USER message (simulating API layer)
        await session_manager.add_chat_message(session_id, "user", user_msg, source="user")
        
        # 3. Call MainRouterNode
        router = MainRouterNode()
        ctx = Context(
            run_id="test_run_1",
            workflow_id="wf_1",
            node_id="main_router",
            inputs={
                "message": user_msg,
                "session_id": session_id,
                "model": "glm-4-flash",
                "provider": "glm"
            }
        )
        
        result = router.run(ctx)
        print(f"Router Output: {result}")
        
        assert result["source"] == "tool:build_strategy" or result["source"] == "main_agent"
        if "BTC" in user_msg:
             # Default is offline, so it maps to build_strategy
             assert result["source"] == "tool:build_strategy"
        
        # 4. Test Online Layer Routing
        print("\nTesting Online Layer Routing...")
        online_ctx = Context(
            run_id="test_run_online",
            workflow_id="wf_online",
            node_id="main_router",
            inputs={
                "message": "Create a new workflow with Data Loader",
                "session_id": session_id,
                "layer": "online",
                "client_context": {"node_count": 0}
            }
        )
        online_res = router.run(online_ctx)
        print(f"Online Router Output: {online_res}")
        assert online_res["source"] == "tool:build_workflow"

        # 5. Persist Assistant Response
        # Again, simulating API layer doing the persistence
        await session_manager.add_chat_message(session_id, "assistant", result["response"], source=result["source"])
        
        # 6. Verify DB Persistence
        print("\nVerifying DB History...")
        history = await session_manager.get_chat_history(session_id)
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[0].content == user_msg
        assert history[1].role == "assistant"
        assert history[1].content == result["response"]
        assert history[1].source == result["source"]
        
        print(f"✅ Verified {len(history)} messages in DB.")

    @pytest.mark.asyncio
    async def test_general_chat_flow(self):
        """Simulate general chat trigger."""
        session_id = f"test_chat_{uuid.uuid4().hex[:8]}"
        await session_manager.save_session(session_id)
        
        user_msg = "What is the capital of France? Just chatting."
        await session_manager.add_chat_message(session_id, "user", user_msg)
        
        router = MainRouterNode()
        # Mock LLMChatNode to avoid real API call if desired? 
        # Or let it hit the API to verify integration.
        # Assuming ZHIPU_API_KEY is validated by setup.
        
        if not os.getenv("ZHIPU_API_KEY"):
            print("Skipping LLM call due to missing API Key")
            return

        ctx = Context(
            run_id="test_run_2",
            workflow_id="wf_2",
            node_id="main_router",
            inputs={
                "message": user_msg,
                "session_id": session_id
            }
        )
        
        result = router.run(ctx)
        print(f"Chat Response: {result['response'][:50]}...")
        
        assert result["source"] == "main_agent"
        assert len(result["response"]) > 0
        
        await session_manager.add_chat_message(session_id, "assistant", result["response"], source=result["source"])
        
        history = await session_manager.get_chat_history(session_id)
        assert len(history) == 2

if __name__ == "__main__":
    # Allow running directly
    sys.exit(pytest.main([__file__, "-v", "-s"]))
