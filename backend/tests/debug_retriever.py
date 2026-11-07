
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.nodes.impl.tool.llm.tool_retriever_node import ToolRetrieverNode
from app.nodes.base import Context

def test_retriever():
    node = ToolRetrieverNode()
    ctx = Context(
        run_id="test", workflow_id="test", node_id="retriever",
        inputs={"scope": "strategy", "output_format": "documentation"}
    )
    result = node.run(ctx)
    print("--- DOCUMENTATION ---")
    print(result['documentation'])
    print("\n--- EXAMPLE CODE ---")
    print(result['example_code'])

if __name__ == "__main__":
    test_retriever()
