import sys
import os
import unittest
# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from app.nodes.impl.tool.llm.code_to_dag_node import CodeToDAGNode
from app.nodes.base import Context
from app.nodes.impl.logic.logic_if_node import LogicIfNode

class TestParsing(unittest.TestCase):
    def test_bool_op_parsing(self):
        code = """
# Logic
# Test simple comparison
cond1 = logic.condition(arg_0=10, arg_1=">", arg_2=5)

# Test python comparison
cond2 = 20 > 10

# Test Boolean And
final_cond = cond1 and cond2

# Test If usage
if final_cond:
    signal.buy()
"""
        node = CodeToDAGNode()
        ctx = Context(run_id="test", workflow_id="test", node_id="test", inputs={"code": code})
        result = node.run(ctx)
        
        print("\n--- DAG Nodes ---")
        for n in result['dag']['nodes']:
            print(f"ID: {n['id']}, Type: {n['type']}, Data: {n['data']}")
        
        print("\n--- DAG Edges ---")
        for e in result['edges']:
             print(f"{e['source']} -> {e['target']} [{e['source_port']} -> {e['target_port']}]")

        # Verify logic.condition nodes created
        logic_nodes = [n for n in result['dag']['nodes'] if n['type'] == 'logic.condition']
        self.assertTrue(len(logic_nodes) >= 3, "Should have at least 3 logic conditions (cond1, cond2, final_cond)")
        
        # Check operator mapping
        ops = [n['data'].get("operator") for n in logic_nodes]
        print(f"Operators found: {ops}")
        self.assertIn(">", ops) 
        self.assertIn("and", ops)

    def test_logic_if_node_execution(self):
        # Test 1: Expression
        node = LogicIfNode()
        ctx1 = Context(run_id="t1", workflow_id="w", node_id="n1", inputs={
            "condition_expr": "10 > 5"
        })
        res1 = node.run(ctx1)
        self.assertTrue(res1['result'])
        
        # Test 2: Structured (Positional Aliases from CodeToDag)
        ctx2 = Context(run_id="t2", workflow_id="w", node_id="n1", inputs={
            "arg_0": 10,
            "arg_1": ">",
            "arg_2": 5
        })
        res2 = node.run(ctx2)
        print(f"Structured Result: {res2}")
        self.assertTrue(res2['result'])
        
        # Test 3: Structured (Named)
        ctx3 = Context(run_id="t3", workflow_id="w", node_id="n1", inputs={
            "left": True,
            "operator": "and",
            "right": True
        })
        res3 = node.run(ctx3)
        self.assertTrue(res3['result'])

if __name__ == '__main__':
    unittest.main()
