from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope, NodeRole
from app.nodes.impl.engine.graph_validator import validate_graph

class GraphValidatorInput(BaseModel):
    graph: Dict[str, Any] = Field(description="The DAG (nodes, edges) to validate")

class GraphValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if valid")
    error: str = Field(description="Error message if invalid, or 'OK'")
    summary: str = Field(description="Validation summary")

@register_node(
    category=NodeCategory.UTILITY,
    name="utility.graph_validator",
    scopes=[NodeScope.TOOL, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class GraphValidatorNode(BaseNode):
    """
    Validates a Strategy Graph using the standard validation logic.
    Checks for:
    - Cycles
    - Disconnected nodes
    - Missing required parameters
    """
    description = "Validates a Strategy Graph using the standard validation logic."
    InputSchema = GraphValidatorInput
    OutputSchema = GraphValidatorOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Use existing validator utility
        # Note: validate_graph returns a ValidationResult object
        validation = validate_graph(params.graph)
        
        error_msg = ""
        if not validation.valid:
             # Combine errors into a string
             error_msg = validation.summary
             
             # Append Correct Usage Guide
             error_msg += "\n\n[CORRECT USAGE PATTERNS]\n"
             error_msg += "```python\n"
             error_msg += "# 1. Data (Choose ONE based on user request)\n"
             error_msg += '# Option A: US Stock (Default)\n'
             error_msg += 'data = data.fetch_stock(symbol="AAPL", market="us", timeframe="1d")\n'
             error_msg += '# Option B: A-Share\n'
             error_msg += '# data = data.fetch_stock(symbol="600519", market="cn", timeframe="1d")\n'
             error_msg += '# Option C: Crypto\n'
             error_msg += '# data = data.fetch_crypto(symbol="BTC/USDT", timeframe="1h")\n'
             error_msg += "\n"
             error_msg += "# 2. Indicators (ALL use 'source' to receive data!)\n"
             error_msg += "ma_fast = indicator.ma(source=data, period=10)\n"
             error_msg += "ma_slow = indicator.ma(source=data, period=20)\n"
             error_msg += "rsi = indicator.rsi(source=data, period=14)\n"
             error_msg += "bb = indicator.bollinger_bands(source=data, period=20, std_dev=2)\n"
             error_msg += "\n"
             error_msg += "# 3. Signal Logic (Must connect to signal.buy/sell)\n"
             error_msg += "cross = indicator.crossover(fast_line=ma_fast, slow_line=ma_slow)\n"
             error_msg += "if cross == 1:\n"
             error_msg += "    signal.buy()  # Must be last step\n"
             error_msg += "if cross == -1:\n"
             error_msg += "    signal.sell() # Must be last step\n"
             error_msg += "```\n"
             error_msg += "[CRITICAL GUIDE] 1. Logic Dead Ends: Conditions MUST connect to signal.buy/sell. - Wrong: \"c = logic.cond(...) # unused\" - Right: \"if c: signal.buy()\" OR \"signal.buy(condition=c)\" 2. Missing Inputs: Indicators usually need \"source\" input.\n"
             error_msg += "Please regenerate the code."
        else:
            error_msg = "OK"

        return {
            "is_valid": validation.valid,
            "error": error_msg,
            "summary": validation.summary
        }
