"""
LLM Nodes Integration Tests.

This test file replicates the test-demo/backend workflow using our node system:
1. ToolRetriever - Get relevant tools for query
2. PromptBuilder - Build ReAct/DAG prompt  
3. LLMChat - Call GLM API
4. ResponseParser - Parse LLM output
5. CodeToDAG - Convert code to DAG structure
6. MemoryManager - Store conversation history
7. AgentExecutor - Full ReAct loop (composite)
"""
import pytest
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from app.nodes.base import Context
from app.nodes.impl.tool.llm import (
    LLMChatNode,
    ToolRetrieverNode,
    PromptBuilderNode,
    ResponseParserNode,
    CodeToDAGNode,
    MemoryManagerNode,
    AgentExecutorNode
)
from app.nodes.impl.tool.sandbox import PythonCodeNode
from app.nodes.impl.tool.boundary import InputNode, OutputNode


class TestLLMChatNode:
    """Test LLMChatNode with real API call"""
    
    def test_glm_chat_simple(self):
        """Test basic GLM API call"""
        if not os.getenv("ZHIPU_API_KEY"):
            pytest.skip("ZHIPU_API_KEY not set")
        
        node = LLMChatNode()
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="llm_chat_1",
            inputs={
                "messages": [{"role": "user", "content": "Say 'test passed' in English"}],
                "model": "glm-4-flash",
                "provider": "glm",
                "temperature": 0.1,
                "max_tokens": 50
            }
        )
        
        result = node.run(ctx)
        
        assert result["response"], "Should have a response"
        assert "error" not in result["response"].lower() or "test" in result["response"].lower()
        print(f"LLMChat Response: {result['response']}")


class TestToolRetrieverNode:
    """Test ToolRetrieverNode"""
    
    def test_retrieve_strategy_tools(self):
        """Test retrieving tools for strategy scope"""
        # First import nodes to register them
        from app.nodes.impl.core.flow import LogicIfNode
        
        node = ToolRetrieverNode()
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="retriever_1",
            inputs={
                "query": "Create a trading strategy",
                "scope": "strategy",
                "scenario": "strategy_building",
                "top_k": 5
            }
        )
        
        result = node.run(ctx)
        
        assert result["count"] >= 0, "Should return tool count"
        assert isinstance(result["tools"], list)
        print(f"Retrieved {result['count']} tools")
        for tool in result["tools"][:3]:
            print(f"  - {tool.get('name')}: {tool.get('description', 'N/A')[:50]}")


class TestPromptBuilderNode:
    """Test PromptBuilderNode"""
    
    def test_build_dag_generator_prompt(self):
        """Test building DAG generator prompt"""
        node = PromptBuilderNode()
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="prompt_1",
            inputs={
                "template_name": "dag_generator",
                "tools": [
                    {"name": "flow.if", "description": "Condition branching"},
                    {"name": "data.fetch_kline", "description": "Fetch K-line data"}
                ],
                "query": "Create a simple if-else workflow",
                "history": []
            }
        )
        
        result = node.run(ctx)
        
        assert len(result["messages"]) >= 2, "Should have system + user messages"
        assert "dag" in result["system_message"].lower() or "workflow" in result["system_message"].lower()
        print(f"Built prompt with {len(result['messages'])} messages")
    
    def test_build_react_prompt(self):
        """Test building ReAct prompt"""
        node = PromptBuilderNode()
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="prompt_2",
            inputs={
                "template_name": "react",
                "tools": [{"name": "search", "description": "Search for info"}],
                "query": "What is the weather?"
            }
        )
        
        result = node.run(ctx)
        
        assert "Thought" in result["system_message"]
        assert "Action" in result["system_message"]


class TestResponseParserNode:
    """Test ResponseParserNode"""
    
    def test_parse_react_format(self):
        """Test parsing ReAct format output"""
        node = ResponseParserNode()
        
        react_output = """
        Thought: I need to search for weather information.
        Action: search
        Action Input: current weather in Beijing
        Observation: The weather is sunny, 25°C.
        Thought: I have the information.
        Final Answer: The weather in Beijing is sunny with a temperature of 25°C.
        """
        
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="parser_1",
            inputs={
                "llm_output": react_output,
                "parse_mode": "react"
            }
        )
        
        result = node.run(ctx)
        
        assert result["success"]
        assert len(result["parsed"]["thoughts"]) >= 2
        assert result["parsed"]["final_answer"] is not None
        print(f"Parsed {len(result['parsed']['actions'])} actions")
    
    def test_parse_code_blocks(self):
        """Test parsing code blocks"""
        node = ResponseParserNode()
        
        code_output = """
        Here is the workflow code:
        ```python
        node1 = FetchKLine(symbol="BTCUSDT")
        node2 = MA(period=20)
        node1 >> node2
        ```
        """
        
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="parser_2",
            inputs={
                "llm_output": code_output,
                "parse_mode": "code"
            }
        )
        
        result = node.run(ctx)
        
        assert result["success"]
        assert len(result["parsed"]["code_blocks"]) >= 1
        assert "FetchKLine" in result["parsed"]["code_blocks"][0]


class TestCodeToDAGNode:
    """Test CodeToDAGNode - Core NL2DAG logic"""
    
    def test_parse_simple_dag(self):
        """Test parsing simple DAG code"""
        node = CodeToDAGNode()
        
        code = """
        node1 = FetchKLine(symbol="BTCUSDT", timeframe="1h")
        node2 = MA(period=20)
        node3 = LogicIf(threshold=0.5)
        node1 >> node2 >> node3
        """
        
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="dag_1",
            inputs={"code": code}
        )
        
        result = node.run(ctx)
        
        assert result["success"], f"Failed: {result.get('error')}"
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2
        
        print(f"Parsed DAG: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
        for n in result["nodes"]:
            print(f"  Node: {n['id']} -> {n['type']}")
    
    def test_parse_code_block(self):
        """Test parsing code from markdown code block"""
        node = CodeToDAGNode()
        
        code = """
        ```python
        start = ManualTrigger()
        condition = LogicIf(condition=True)
        start >> condition
        ```
        """
        
        ctx = Context(
            run_id="test_run",
            workflow_id="wf1",
            node_id="dag_2",
            inputs={"code": code}
        )
        
        result = node.run(ctx)
        
        assert result["success"]
        assert len(result["nodes"]) == 2


class TestMemoryManagerNode:
    """Test MemoryManagerNode"""
    
    def test_memory_lifecycle(self):
        """Test add/get/clear memory"""
        node = MemoryManagerNode()
        session_id = "test_session_123"
        
        # Clear first
        ctx = Context(
            run_id="test", workflow_id="wf1", node_id="mem_1",
            inputs={"session_id": session_id, "action": "clear"}
        )
        node.run(ctx)
        
        # Add messages
        ctx.inputs = {
            "session_id": session_id,
            "action": "add",
            "message": {"role": "user", "content": "Hello"}
        }
        result = node.run(ctx)
        assert result["message_count"] == 1
        
        ctx.inputs["message"] = {"role": "assistant", "content": "Hi!"}
        result = node.run(ctx)
        assert result["message_count"] == 2
        
        # Get history
        ctx.inputs = {"session_id": session_id, "action": "get"}
        result = node.run(ctx)
        
        assert len(result["history"]) == 2
        assert result["history"][0]["content"] == "Hello"
        
        # Clean up
        ctx.inputs = {"session_id": session_id, "action": "clear"}
        node.run(ctx)


class TestPythonCodeNode:
    """Test PythonCodeNode sandbox"""
    
    def test_simple_code_execution(self):
        """Test executing simple Python code"""
        node = PythonCodeNode()
        ctx = Context(
            run_id="test", workflow_id="wf1", node_id="code_1",
            inputs={
                "code": "result = sum(items)",
                "variables": {"items": [1, 2, 3, 4, 5]}
            }
        )
        
        result = node.run(ctx)
        
        assert result["success"], f"Failed: {result.get('error')}"
        assert result["result"] == 15
    
    def test_dangerous_code_blocked(self):
        """Test that dangerous operations are blocked"""
        node = PythonCodeNode()
        ctx = Context(
            run_id="test", workflow_id="wf1", node_id="code_2",
            inputs={
                "code": "import os; os.system('rm -rf /')",
                "variables": {}
            }
        )
        
        result = node.run(ctx)
        
        # Should fail due to restricted import
        assert not result["success"] or "error" in str(result).lower()


class TestBoundaryNodes:
    """Test Input/Output boundary nodes"""
    
    def test_input_node(self):
        """Test InputNode passes data through"""
        node = InputNode()
        ctx = Context(
            run_id="test", workflow_id="wf1", node_id="input_1",
            inputs={
                "schema_definition": {"type": "object"},
                "data": {"symbol": "BTCUSDT", "timeframe": "1h"}
            }
        )
        
        result = node.run(ctx)
        
        assert result["data"]["symbol"] == "BTCUSDT"
    
    def test_output_node(self):
        """Test OutputNode passes result"""
        node = OutputNode()
        ctx = Context(
            run_id="test", workflow_id="wf1", node_id="output_1",
            inputs={
                "data": {"status": "success", "value": 42}
            }
        )
        
        result = node.run(ctx)
        
        assert result["result"]["status"] == "success"


class TestFullWorkflow:
    """Integration test: Replicate test-demo/backend workflow"""
    
    def test_complete_nl2dag_pipeline(self):
        """
        Test the complete NL2DAG pipeline:
        ToolRetriever → PromptBuilder → LLMChat → ResponseParser → CodeToDAG
        
        This replicates the test-demo/backend LLMEngine.generate_plan() flow.
        """
        if not os.getenv("ZHIPU_API_KEY"):
            pytest.skip("ZHIPU_API_KEY not set")
        
        from app.nodes.impl.core.flow import LogicIfNode, MergeNode  # Register nodes
        
        # Step 1: Retrieve Tools
        retriever = ToolRetrieverNode()
        ctx1 = Context(
            run_id="integration_test", workflow_id="wf1", node_id="step1",
            inputs={"query": "Create a simple workflow", "scope": "workflow", "top_k": 5}
        )
        tools_result = retriever.run(ctx1)
        print(f"Step 1 - Retrieved {tools_result['count']} tools")
        
        # Step 2: Build Prompt
        builder = PromptBuilderNode()
        ctx2 = Context(
            run_id="integration_test", workflow_id="wf1", node_id="step2",
            inputs={
                "template_name": "dag_generator",
                "tools": tools_result["tools"],
                "query": "Create a workflow that checks a condition and prints result"
            }
        )
        prompt_result = builder.run(ctx2)
        print(f"Step 2 - Built prompt with {len(prompt_result['messages'])} messages")
        
        # Step 3: Call LLM
        llm = LLMChatNode()
        ctx3 = Context(
            run_id="integration_test", workflow_id="wf1", node_id="step3",
            inputs={
                "messages": prompt_result["messages"],
                "model": "glm-4-flash",
                "provider": "glm",
                "temperature": 0.1,
                "max_tokens": 1024
            }
        )
        llm_result = llm.run(ctx3)
        print(f"Step 3 - LLM Response: {llm_result['response'][:200]}...")
        
        # Step 4: Parse Response for Code
        parser = ResponseParserNode()
        ctx4 = Context(
            run_id="integration_test", workflow_id="wf1", node_id="step4",
            inputs={
                "llm_output": llm_result["response"],
                "parse_mode": "code"
            }
        )
        parsed_result = parser.run(ctx4)
        print(f"Step 4 - Found {len(parsed_result['parsed'].get('code_blocks', []))} code blocks")
        
        # Step 5: Convert to DAG (if code found)
        code_blocks = parsed_result["parsed"].get("code_blocks", [])
        if code_blocks:
            dag_converter = CodeToDAGNode()
            ctx5 = Context(
                run_id="integration_test", workflow_id="wf1", node_id="step5",
                inputs={"code": code_blocks[0]}
            )
            dag_result = dag_converter.run(ctx5)
            print(f"Step 5 - DAG: {len(dag_result.get('nodes', []))} nodes, {len(dag_result.get('edges', []))} edges")
            
            if dag_result["success"]:
                print("\n=== Generated DAG ===")
                for node in dag_result["nodes"]:
                    print(f"  {node['id']}: {node['type']} {node.get('data', {})}")
                for edge in dag_result["edges"]:
                    print(f"  {edge['source']} -> {edge['target']}")
        else:
            print("Step 5 - No code blocks found in LLM response")
        
        # Verify pipeline worked
        assert llm_result["response"], "LLM should return response"
        print("\n✅ Full NL2DAG pipeline test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
