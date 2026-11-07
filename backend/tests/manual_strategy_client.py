"""
Interactive Test Client for Strategy ToolChain.

Tests both Fast Mode (BuildStrategy) and Think Mode (AnalyzeStrategy)
with full output at each step.

Usage:
    python test_strategy_client.py
    
Then enter your prompts interactively.
"""
import sys
import json
import uuid
import os
from datetime import datetime
from dotenv import load_dotenv

# Load .env file (Robust path handling)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir)) # golden_touch
backend_env = os.path.join(project_root, 'backend', '.env')

load_dotenv() # Try default (CWD)
if not os.getenv("ZHIPU_API_KEY"):
    load_dotenv(backend_env) # Try explicit backend/.env
    
if not os.getenv("ZHIPU_API_KEY"):
    print(f"⚠️ 警告: 未找到 ZHIPU_API_KEY (Checked CWD and {backend_env})")


# Adjust path to find the 'app' module
# Current file is in backend/tests/manual_strategy_client.py
# We need to add 'backend' (parent of app) to sys.path
# 'backend' is the parent of 'tests', which is the parent of this file.
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir)) # golden_touch
sys.path.insert(0, os.path.join(backend_dir, 'backend')) 
# Also allow loading from root for general imports if needed
sys.path.insert(0, backend_dir)

# Force import nodes to register them - BE COMPREHENSIVE
from app.nodes.impl.data import *
from app.nodes.impl.logic import *
from app.nodes.impl.indicator import *  # NEW: indicator nodes (ma, rsi, crossover)
from app.nodes.impl.signal import *     # NEW: signal nodes (buy, sell, hold)
from app.nodes.impl.core.flow import *
from app.nodes.impl.engine import *
from app.nodes.impl.backtest import *

from app.nodes.base import Context
from app.nodes.impl.engine.strategy_toolchain import BuildStrategyNode, AnalyzeStrategyNode
from app.nodes.impl.tool.llm.tool_retriever_node import ToolRetrieverNode


def show_injected_nodes():
    """显示注入给 LLM 的节点文档"""
    print_separator("注入节点文档预览")
    
    retriever = ToolRetrieverNode()
    ctx = Context(
        run_id="preview",
        workflow_id="preview",
        node_id="preview_retriever",
        inputs={
            "scope": "strategy",
            "scenario": "strategy_building",
            "output_format": "documentation",
            "include_roles": True
        }
    )
    result = retriever.run(ctx)
    
    print(f"📊 节点统计:")
    print(f"  - 总节点数: {result.get('count', 0)}")
    print(f"  - HEAD (数据源): {result.get('head_count', 0)}")
    print(f"  - TAIL (输出节点): {result.get('tail_count', 0)}")
    print()
    
    print("📝 注入的节点文档 (以下内容会作为 System Prompt 发送给 LLM):")
    print("-" * 60)
    doc = result.get("documentation", "")
    print(doc[:2000])  # Show first 2000 chars
    if len(doc) > 2000:
        print(f"\n... (共 {len(doc)} 字符, 已截断)")
    print("-" * 60)
    
    # Also show raw tool list
    print("\n📋 可用节点列表:")
    for tool in result.get("tools", []):
        role_emoji = {"HEAD": "🟢", "TAIL": "🔴"}.get(tool.get("role"), "🟡")
        print(f"  {role_emoji} {tool.get('name')}: {tool.get('description', '')[:40]}...")


def print_separator(title: str = ""):
    """Print a visual separator."""
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)
    print()


def print_step(step_num: int, title: str, content: str):
    """Print a numbered step with content."""
    print(f"\n【步骤 {step_num}】{title}")
    print("-" * 40)
    print(content[:500] + "..." if len(content) > 500 else content)


def test_fast_mode(prompt: str, current_graph: dict = None):
    """Test BuildStrategyNode (Fast Mode)."""
    print_separator("Fast Mode (BuildStrategy) 测试")
    
    node = BuildStrategyNode()
    ctx = Context(
        run_id=str(uuid.uuid4()),
        workflow_id="test_workflow",
        node_id="test_build_strategy",
        inputs={
            "current_graph": current_graph or {"nodes": [], "edges": []},
            "prompt": prompt
        }
    )
    
    print(f"📝 输入 Prompt: {prompt}")
    print(f"📊 当前图: {len((current_graph or {}).get('nodes', []))} 个节点")
    print("\n⏳ 正在生成策略...")
    
    start = datetime.now()
    result = node.run(ctx)
    elapsed = (datetime.now() - start).total_seconds()
    
    print(f"\n⏱️ 耗时: {elapsed:.2f}s")
    print_separator("结果")
    
    print(f"✅ 成功: {result['success']}")
    print(f"📋 消息: {result['message']}")
    
    if result.get('thought_process'):
        print("\n📝 思考过程:")
        for i, step in enumerate(result['thought_process'], 1):
            print(f"  {i}. {step}")
    
    if result.get('dag'):
        print(f"\n📊 生成的 DAG:")
        print(f"  - 节点数: {len(result['dag'].get('nodes', []))}")
        print(f"  - 边数: {len(result['dag'].get('edges', []))}")
        print("\n  节点列表:")
        for node in result['dag'].get('nodes', []):
            print(f"    - {node.get('id')}: {node.get('type')}")
    
    return result


def test_think_mode(prompt: str, current_graph: dict = None):
    """Test AnalyzeStrategyNode (Think Mode / ReAct)."""
    print_separator("Think Mode (AnalyzeStrategy - ReAct) 测试")
    
    node = AnalyzeStrategyNode()
    def print_status(msg: str):
        print(f"  [Status] {msg}")

    ctx = Context(
        run_id=str(uuid.uuid4()),
        workflow_id="test_workflow",
        node_id="test_analyze_strategy",
        inputs={
            "current_graph": current_graph or {"nodes": [], "edges": []},
            "prompt": prompt
        },
        on_status_update=print_status
    )
    
    print(f"📝 输入 Prompt: {prompt}")
    print(f"📊 当前图: {len((current_graph or {}).get('nodes', []))} 个节点")
    print(f"🔄 最大分析尝试: {getattr(node, 'MAX_RETRIES', 30)}")
    print("\n⏳ 正在执行结构化分析...")
    
    start = datetime.now()
    result = node.run(ctx)
    elapsed = (datetime.now() - start).total_seconds()
    
    print(f"\n⏱️ 耗时: {elapsed:.2f}s")
    print_separator("结果")
    
    print(f"✅ 成功: {result['success']}")
    print(f"📋 消息: {result['message']}")
    
    if result.get('thought_process'):
        print("\n📝 完整思考过程:")
        for i, step in enumerate(result['thought_process'], 1):
            print(f"  [{i:02d}] {step}")
    
    if result.get('dag'):
        print(f"\n📊 最终 DAG:")
        print(f"  - 节点数: {len(result['dag'].get('nodes', []))}")
        print(f"  - 边数: {len(result['dag'].get('edges', []))}")
    
    return result


def run_test_cases():
    """Run predefined test cases."""
    test_cases = [
        {
            "name": "Simple MA Strategy",
            "mode": "fast",
            "prompt": "创建一个简单的双均线金叉策略：5日均线上穿20日均线时买入",
            "graph": None
        },
        {
            "name": "RSI Oversold Strategy",
            "mode": "fast",
            "prompt": "创建一个 RSI 超卖反弹策略：当 RSI(14) < 30 时买入",
            "graph": None
        },
        {
            "name": "Analyze RSI Strategy",
            "mode": "think",
            "prompt": "分析这个 RSI 策略的表现，找出可能的问题并优化",
            "graph": {
                "nodes": [
                    {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "timeframe": "1h"}},
                    {"id": "n2", "type": "indicator.rsi", "data": {"period": 14}},
                    {"id": "n3", "type": "logic.condition", "data": {"condition_expr": "rsi < 30"}},
                    {"id": "n4", "type": "signal.buy", "data": {}}
                ],
                "edges": [
                    {"source": "n1", "target": "n2", "target_port": "source"},
                    {"source": "n2", "target": "n3", "target_port": "condition_input"},
                    {"source": "n3", "target": "n4", "source_port": "true"}
                ]
            }
        },
        {
            "name": "Add Stop Loss",
            "mode": "think",
            "prompt": "在这个双均线策略上添加止损条件：当亏损超过 5% 时平仓",
            "graph": {
                "nodes": [
                    {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "timeframe": "1h"}},
                    {"id": "n2", "type": "indicator.ma", "data": {"period": 5}},
                    {"id": "n3", "type": "indicator.ma", "data": {"period": 20}},
                    {"id": "n4", "type": "indicator.crossover", "data": {}},
                    {"id": "n5", "type": "signal.buy", "data": {}}
                ],
                "edges": [
                    {"source": "n1", "target": "n2", "target_port": "source"},
                    {"source": "n1", "target": "n3", "target_port": "source"},
                    {"source": "n2", "target": "n4", "target_port": "fast"},
                    {"source": "n3", "target": "n4", "target_port": "slow"},
                    {"source": "n4", "target": "n5", "target_port": "condition"}
                ]
            }
        }
    ]
    
    print_separator("预定义测试用例")
    print("可用测试用例:")
    for i, tc in enumerate(test_cases, 1):
        print(f"  {i}. [{tc['mode'].upper()}] {tc['name']}")
    
    choice = input("\n选择测试用例 (1-4) 或输入 'a' 运行全部, 'q' 退出: ").strip()
    
    if choice == 'q':
        return
    elif choice == 'a':
        for tc in test_cases:
            run_single_test(tc)
    elif choice.isdigit() and 1 <= int(choice) <= len(test_cases):
        run_single_test(test_cases[int(choice) - 1])
    else:
        print("无效选择")


def run_single_test(tc: dict):
    """Run a single test case."""
    print_separator(f"运行测试: {tc['name']}")
    
    if tc['mode'] == 'fast':
        test_fast_mode(tc['prompt'], tc['graph'])
    else:
        test_think_mode(tc['prompt'], tc['graph'])
    
    input("\n按 Enter 继续...")


def interactive_mode():
    """Interactive mode for custom prompts."""
    print_separator("交互模式")
    
    current_graph = {"nodes": [], "edges": []}
    
    while True:
        print("\n当前图状态:")
        print(f"  - 节点数: {len(current_graph.get('nodes', []))}")
        print(f"  - 边数: {len(current_graph.get('edges', []))}")
        
        print("\n选项:")
        print("  1. Fast Mode (一次性生成)")
        print("  2. Think Mode (ReAct 分析)")
        print("  3. 查看当前图 JSON")
        print("  4. 重置图")
        print("  5. 加载测试图")
        print("  q. 退出")
        
        choice = input("\n选择: ").strip()
        
        if choice == 'q':
            break
        elif choice == '1':
            prompt = input("输入 Prompt: ").strip()
            if prompt:
                result = test_fast_mode(prompt, current_graph)
                if result.get('success') and result.get('dag'):
                    update = input("更新当前图为生成结果? (y/n): ").strip().lower()
                    if update == 'y':
                        current_graph = result['dag']
        elif choice == '2':
            prompt = input("输入 Prompt: ").strip()
            if prompt:
                result = test_think_mode(prompt, current_graph)
                if result.get('dag'):
                    update = input("更新当前图? (y/n): ").strip().lower()
                    if update == 'y':
                        current_graph = result['dag']
        elif choice == '3':
            print(json.dumps(current_graph, indent=2, ensure_ascii=False))
        elif choice == '4':
            current_graph = {"nodes": [], "edges": []}
            print("图已重置")
        elif choice == '5':
            current_graph = {
                "nodes": [
                    {"id": "data_1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT", "interval": "1h"}},
                    {"id": "ma_5", "type": "logic.ma", "data": {"period": 5}},
                    {"id": "ma_20", "type": "logic.ma", "data": {"period": 20}}
                ],
                "edges": [
                    {"source": "data_1", "target": "ma_5"},
                    {"source": "data_1", "target": "ma_20"}
                ]
            }
            print("已加载测试图 (BTC 双均线)")


def main():
    """Main entry point."""
    print_separator("Strategy ToolChain 测试客户端")
    print("这是用于测试 Fast Mode 和 Think Mode 的交互式客户端。")
    print()
    print("模式:")
    print("  1. 运行预定义测试用例")
    print("  2. 交互模式 (自定义 Prompt)")
    print("  3. 查看注入节点文档")
    print("  q. 退出")
    
    while True:
        choice = input("\n选择模式: ").strip()
        
        if choice == 'q':
            print("再见!")
            break
        elif choice == '1':
            run_test_cases()
        elif choice == '2':
            interactive_mode()
        elif choice == '3':
            show_injected_nodes()
            input("\n按 Enter 继续...")
        else:
            print("无效选择，请输入 1, 2, 3 或 q")


if __name__ == "__main__":
    main()
