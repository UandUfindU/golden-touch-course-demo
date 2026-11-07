# Risk management nodes
# DISABLED: These nodes are not yet integrated with signal.buy/sell and BacktestRunner.
# Exposing them causes LLM to generate dead code (unused nodes).
# Re-enable after implementing:
#   1. stop_loss/take_profit params in signal.buy/sell InputSchema
#   2. Stop-loss/take-profit execution logic in BacktestRunner
#
# from .stop_loss_node import StopLossNode
# from .take_profit_node import TakeProfitNode

__all__ = []  # No exports until integration complete
