# Graph Architecture

This directory contains two types of graph definitions with different purposes and executors.

## Graph Types Overview

| Type | Format | Executor | Purpose |
|------|--------|----------|---------|
| **Workflow Graphs** | `graph.yaml` | `CompositeNode` + `GraphExecutor` | LLM pipelines, meta-workflows |
| **Strategy Graphs** | `*.json` | `BacktestRunnerNode` | Trading strategies for backtesting |

---

## 1. Workflow Graphs (YAML)

**Location**: `build_strategy/`, `analyze_strategy/`, `build_workflow/`

### Loading Flow

```
GraphBundle.load(path) → Parse YAML → Wrap as CompositeNode → Register to NodeRegistry
                                              ↓
                                   CompositeNode.run() → GraphExecutor executes
```

### Components

- **`GraphBundle`** (`app/core/graph_persistence.py`) - Loads YAML bundles
- **`CompositeNode`** - Wraps entire graph as a single executable node
- Contains complex flow control: `flow.retry`, `tool.llm.chat`, `structure.input/output`

### Example Usage

```python
from app.core.graph_persistence import GraphBundle
from app.nodes.impl.structure.composite_node import CompositeNode

# Load graph definition
graph_def = GraphBundle.load("graphs/standard/build_strategy")

# Create and run
node = CompositeNode(graph_definition=graph_def)
result = node.run(ctx)
```

---

## 2. Strategy Graphs (JSON)

**Location**: `classic_strategies/`

### Loading Flow

```
json.load() → Pass to BacktestRunnerNode
                     ↓
              BacktestRunner parses nodes/edges internally
              Instantiates nodes from NodeRegistry
              Topological sort → Execute bar-by-bar
```

### Components

- **`BacktestRunnerNode`** - Parses and executes strategy DAGs
- Contains trading logic only: `indicator.*`, `signal.*`, `logic.condition`

### Example Usage

```python
import json
from app.nodes.impl.backtest.runner import BacktestRunnerNode
from app.nodes.base import Context

# Load strategy
with open("classic_strategies/ma_crossover.json") as f:
    strategy = json.load(f)

# Run backtest
runner = BacktestRunnerNode()
ctx = Context(
    run_id="test", workflow_id="wf", node_id="bt",
    inputs={
        "data": ohlcv_data,
        "strategy_dag": strategy,
        "config": {"initial_capital": 10000}
    }
)
result = runner.run(ctx)
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      NodeRegistry                           │
│            (Central registry for all node types)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌───────────────────┐       ┌────────────────────┐
│   CompositeNode   │       │  BacktestRunner    │
│  (Executes YAML)  │       │  (Executes JSON)   │
│  - Meta workflows │       │  - Trading logic   │
│  - LLM pipelines  │       │  - Backtest sim    │
└───────┬───────────┘       └────────┬───────────┘
        │                            │
        ▼                            ▼
   graph.yaml                  strategy.json
   (build_strategy)            (ma_crossover)
```

---

## Key Difference

| Aspect | Workflow (YAML) | Strategy (JSON) |
|--------|-----------------|-----------------|
| **Nodes** | LLM, Retry, I/O | Indicators, Signals |
| **Execution** | Single run | Bar-by-bar loop |
| **Output** | Generated DAG | Trade signals, metrics |
| **Use Case** | Generate strategies | Execute strategies |
