from enum import Enum, unique

@unique
class NodeCategory(str, Enum):
    TRIGGER = "trigger"
    DATA = "data"
    INDICATOR = "indicator"
    LOGIC = "logic"  # Indicators and conditional logic
    STRATEGY = "strategy"
    EXECUTION = "execution"
    ACCOUNT = "account"
    NOTIFICATION = "notification"
    FLOW = "flow"
    TESTING = "testing"
    AI = "ai"
    UTILITY = "utility"
    STRUCTURE = "structure"  # Composite, Input, Output nodes
    # New category for tools created by users
    USER_DEFINED = "user_defined"


@unique
class NodeScope(str, Enum):
    STRATEGY = "strategy"
    WORKFLOW = "workflow"
    TOOL = "tool"

@unique
class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@unique
class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


@unique
class NodeRole(str, Enum):
    """
    Node role in a strategy graph.
    
    - HEAD: Data source nodes (typically start a graph)
    - MIDDLE: Processing/logic nodes
    - TAIL: Output nodes (signals, actions)
    """
    HEAD = "head"
    MIDDLE = "middle"
    TAIL = "tail"
