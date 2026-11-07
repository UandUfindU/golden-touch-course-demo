
"""
Integration Test & Client Simulation: Robust Strategy Generation.

This script verifies the full NL2DAG pipeline using the robust `AgentExecutorNode`.
It supports:
1.  **Global Retry Mechanism**: Automatically feeding parsing errors back to the LLM.
2.  **Client Simulation**: Interactive CLI mode to select scenarios and view detailed logs.

Scenarios:
1. Basic Strategy (MA Crossover)
2. Multi-Output Strategy (Data Splitting)
3. Branching Strategy (If/Else Logic)
"""
import pytest
import os
import sys
import json
import uuid
from dotenv import load_dotenv

# Add backend to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(os.path.join(backend_dir, "backend"))

from app.nodes.base import Context
from app.nodes.registry import register_node, registry
from app.core.enums import NodeCategory, NodeScope
from app.nodes.impl.tool.llm import AgentExecutorNode, MemoryManagerNode

# --- Pydantic & Mock Nodes (Required for Registry) ---
from app.nodes.base import BaseNode
from pydantic import BaseModel

class EmptySchema(BaseModel):
    pass

class DataInput(BaseModel):
    symbol: str
    timeframe: str = "1h"

class AlgoInput(BaseModel):
    data: dict
    period: int = 20

@register_node(category=NodeCategory.DATA, name="data.fetch_kline", scopes=[NodeScope.STRATEGY])
class FetchKLine(BaseNode):
    description = "Fetch historical K-Line data for a symbol."
    InputSchema = DataInput
    OutputSchema = EmptySchema
    def run(self, ctx): return {"data": []}

@register_node(category=NodeCategory.INDICATOR, name="indicator.ma", scopes=[NodeScope.STRATEGY])
class MA(BaseNode):
    description = "Calculate Moving Average."
    InputSchema = AlgoInput
    OutputSchema = EmptySchema
    def run(self, ctx): return {"value": []}

@register_node(category=NodeCategory.INDICATOR, name="indicator.rsi", scopes=[NodeScope.STRATEGY])
class RSI(BaseNode):
    description = "Calculate Relative Strength Index."
    InputSchema = EmptySchema
    OutputSchema = EmptySchema
    def run(self, ctx): return {"value": []}

@register_node(category=NodeCategory.FLOW, name="flow.split_data", scopes=[NodeScope.STRATEGY])
class SplitData(BaseNode):
    description = "Split data into training and testing sets."
    InputSchema = EmptySchema
    OutputSchema = EmptySchema
    def run(self, ctx): return {"train": [], "test": []}

@register_node(category=NodeCategory.FLOW, name="flow.if", scopes=[NodeScope.STRATEGY])
class LogicIf(BaseNode):
    description = "Condition branching."
    InputSchema = EmptySchema
    OutputSchema = EmptySchema
    def run(self, ctx): return {}

@register_node(category=NodeCategory.EXECUTION, name="tool.buy", scopes=[NodeScope.STRATEGY])
class Buy(BaseNode):
    description = "Execute Buy Order."
    InputSchema = EmptySchema
    OutputSchema = EmptySchema
    def run(self, ctx): return {}

@register_node(category=NodeCategory.EXECUTION, name="tool.sell", scopes=[NodeScope.STRATEGY])
class Sell(BaseNode):
    description = "Execute Sell Order."
    InputSchema = EmptySchema
    OutputSchema = EmptySchema
    def run(self, ctx): return {}


class TestStrategyGeneration:
    
    def setup_class(self):
        load_dotenv()
        if not os.getenv("ZHIPU_API_KEY"):
            pytest.skip("ZHIPU_API_KEY not set", allow_module_level=True)
            
    def run_agent(self, scenario_name: str, query: str):
        print(f"\n{'='*20} Testing Scenario: {scenario_name} {'='*20}")
        print(f"User Query: {query}")
        
        agent = AgentExecutorNode()
        session_id = str(uuid.uuid4())
        
        ctx = Context(
            run_id="test_run",
            workflow_id="wf_test",
            node_id="agent",
            inputs={
                "query": query,
                "session_id": session_id,
                "scope": "strategy",
                "max_retries": 3,
                # Inject scenario hint if supported by context passing logic (ToolRetriever picks it up)
                "scenario": "strategy_building" 
            }
        )
        
        result = agent.run(ctx)
        
        print(f"\n--- Execution Result ---")
        print(f"Success: {result['success']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Thought Process:")
        for step in result['thought_process']:
            print(f"  > {step}")
            
        if not result['success']:
            print(f"Final Answer (Error): {result['final_answer']}")
            pytest.fail(f"Agent failed: {result['final_answer']}")
            
        dag = result['dag']
        print(f"\n[DAG Stats] Nodes: {len(dag['nodes'])}, Edges: {len(dag['edges'])}")
        return dag

    def test_basic_strategy(self):
        """Test 1: Basic MA Strategy"""
        query = "Create a strategy that buys when price closes above MA20"
        dag = self.run_agent("Basic Strategy", query)
        node_types = [n['type'] for n in dag['nodes']]
        assert "data.fetch_kline" in node_types
        assert "indicator.ma" in node_types

    def test_multi_output(self):
        """Test 2: Multi-Output (Data Splitting)"""
        query = "Fetch BTC data, split it into train and test sets"
        dag = self.run_agent("Multi-Output", query)
        node_types = [n['type'] for n in dag['nodes']]
        assert "flow.split_data" in node_types

    def test_branching_logic(self):
        """Test 3: If/Else Branching"""
        query = "Calculate RSI. If RSI > 70 sell, otherwise buy."
        dag = self.run_agent("Branching Logic", query)
        node_types = [n['type'] for n in dag['nodes']]
        assert "flow.if" in node_types


def interactive_mode():
    """Client Simulation Mode"""
    load_dotenv()
    print("\n" + "="*50)
    print("Welcome to NL2DAG Client Simulation")
    print("="*50)
    
    scenarios = {
        "1": ("Basic Strategy", "Create a strategy that buys when price closes above MA20"),
        "2": ("Multi-Output", "Fetch BTC data, split it into train and test sets"),
        "3": ("Branching Logic", "Calculate RSI. If RSI > 70 sell, otherwise buy.")
    }
    
    while True:
        print("\nAvailable Scenarios:")
        for k, v in scenarios.items():
            print(f"{k}. {v[0]}: \"{v[1]}\"")
        print("4. Custom Query")
        print("q. Quit")
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == 'q':
            break
            
        query = ""
        name = ""
        
        if choice in scenarios:
            name, query = scenarios[choice]
        elif choice == '4':
            name = "Custom"
            query = input("Enter your strategy description: ")
        else:
            print("Invalid choice.")
            continue
            
        print(f"\n[Client] Initializing Agent for: {name}")
        
        # Instantiate Agent manually for simulation
        agent = AgentExecutorNode()
        session_id = str(uuid.uuid4())
        
        ctx = Context(
            run_id="sim_run",
            workflow_id="wf_sim",
            node_id="agent",
            inputs={
                "query": query,
                "session_id": session_id,
                "scope": "strategy",
                "max_retries": 3,
                "scenario": "strategy_building"
            }
        )
        
        print("[Client] Sending request to Agent...")
        result = agent.run(ctx)
        
        print("\n" + "-"*30 + " AGENT LOGS " + "-"*30)
        for log in result['thought_process']:
            print(f"🤖 {log}")
        print("-"*72)
        
        if result['success']:
            print(f"\n✅ SUCCESS! Generated DAG with {len(result['dag']['nodes'])} nodes / {len(result['dag']['edges'])} edges.")
            print("\n📝 [LLM Final Answer / Generated Code]:")
            print("="*40)
            print(result['final_answer'])
            print("="*40)
            
            print("\n📊 [DAG Structure]:")
            for node in result['dag']['nodes']:
                print(f"   - ID: {node['id']:<5} | Type: {node['type']:<20} | Params: {node['data']}")
            print("\n🔗 [Edges]:")
            for edge in result['dag']['edges']:
                print(f"   - {edge['source']} -> {edge['target']} ({edge.get('type', 'data')})")
        else:
            print(f"\n❌ FAILED. Final Answer: {result['final_answer']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "client":
        interactive_mode()
    else:
        pytest.main([__file__, "-v", "-s"])
