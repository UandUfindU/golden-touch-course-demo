# Node implementations
from . import core
from . import tool
from . import workflow
from . import data        # Data ingestion nodes (ccxt, akshare, etc.)
from . import backtest    # Backtesting engine
from . import logic       # Conditional logic nodes (if)
from . import indicator   # Technical indicators (ma, rsi, crossover, macd, atr)
from . import signal      # Trading signals (buy, sell, hold)
from . import risk        # Risk management (stop_loss, take_profit)

