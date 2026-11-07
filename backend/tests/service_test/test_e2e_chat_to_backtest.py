"""
端到端测试：对话生成图 -> 提取图结构 -> 运行回测
E2E Test: Chat generates graph -> Extract graph -> Run backtest
"""

import requests
import json
import sys
import time
import os
import glob
from typing import Optional, Dict, Any, List
from datetime import datetime

CHAT_URL = "http://localhost:8000/api/v1/chat/send"
BACKTEST_URL = "http://localhost:8000/api/v1/backtest/run"
OPTIMIZE_URL = "http://localhost:8000/api/v1/backtest/optimize"

# Directory to save intermediate data
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


class ArtifactCache:
    """Simple artifact cache for saving and loading test intermediate data."""
    
    def __init__(self, directory: str = ARTIFACTS_DIR):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
    
    def save(self, name: str, data: Any, iteration: int = 0) -> str:
        """Save data to a timestamped JSON file."""
        filename = f"{name}_iter{iteration}_{int(time.time())}.json"
        filepath = os.path.join(self.directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"  [Cache] Saved {name} -> {filename}")
        return filepath
    
    def load_latest(self, name_pattern: str) -> Optional[Dict]:
        """Load the most recent file matching the pattern."""
        pattern = os.path.join(self.directory, f"{name_pattern}*.json")
        files = glob.glob(pattern)
        if not files:
            return None
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r', encoding='utf-8') as f:
            print(f"  [Cache] Loaded {os.path.basename(latest)}")
            return json.load(f)
    
    def save_latest_run(self, graph: Dict, metrics: Dict):
        """Convenience method: save graph and metrics from the latest run."""
        self.save("latest_graph", graph)
        self.save("latest_metrics", metrics)
    
    def load_latest_run(self) -> tuple:
        """Convenience method: load graph and metrics from the latest run."""
        graph = self.load_latest("latest_graph")
        metrics = self.load_latest("latest_metrics")
        return graph, metrics


# Global cache instance
cache = ArtifactCache()


def chat_generate_graph(prompt: str, session_id: str = None, client_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    调用Chat API，让LLM生成策略图
    
    Args:
        prompt: 用户请求
        session_id: 会话ID
        client_context: 客户端上下文 (可包含 last_graph_dag, backtest_results)
        
    Returns: 包含所有事件的字典 {messages, graph_updates, errors}
    """
    if session_id is None:
        session_id = f"e2e-test-{int(time.time())}"
    
    payload = {
        "session_id": session_id,
        "message": prompt,
        "layer": "offline",
        "mode": "auto",
        # model: uses API default from .env (LLM_DEFAULT_MODEL)
        "client_context": client_context or {}
    }
    
    result = {
        "session_id": session_id,
        "messages": [],
        "graph_updates": [],
        "errors": [],
        "raw_events": []
    }
    
    print(f"[Chat] 发送请求 (Full Prompt): {prompt}")
    
    try:
        with requests.post(CHAT_URL, json=payload, stream=True, timeout=120) as r:
            if r.status_code != 200:
                result["errors"].append(f"HTTP Error: {r.status_code}")
                return result
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        result["raw_events"].append(event)
                        
                        event_type = event.get("type")
                        
                        if event_type == "message":
                            result["messages"].append(event.get("content", ""))
                            
                        elif event_type == "graph_update":
                            # 这是图更新事件，包含nodes和edges
                            result["graph_updates"].append(event)
                            print(f"[Chat] 收到图更新事件")
                            
                        elif event_type == "error":
                            result["errors"].append(event.get("content", ""))
                            
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def extract_graph_from_response(chat_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    从Chat响应中提取图结构
    Returns: {"nodes": [...], "edges": [...]} 或 None
    """
    # 方式1: 从 graph_generated 事件提取 (chat_service返回的标准格式)
    for event in chat_result.get("raw_events", []):
        if event.get("type") == "graph_generated":
            dag = event.get("dag", {})
            nodes = dag.get("nodes", [])
            edges = dag.get("edges", [])
            if nodes:
                print(f"[Extract] 从graph_generated事件提取: {len(nodes)} nodes, {len(edges)} edges")
                print("[Extract] === 完整DAG结构 ===")
                for n in nodes:
                    print(f"  Node: {n.get('id')} | Type: {n.get('type')} | Data: {n.get('data')}")
                print("[Extract] ===================")
                # DEBUG: check for expressions
                if "expressions" in dag:
                    print(f"[Extract] Found {len(dag['expressions'])} expressions in DAG")
                return dag
    
    # 方式2: 从graph_update事件提取 (兼容旧格式)
    if chat_result.get("graph_updates"):
        latest = chat_result["graph_updates"][-1]
        nodes = latest.get("nodes", latest.get("content", {}).get("nodes", []))
        edges = latest.get("edges", latest.get("content", {}).get("edges", []))
        
        if nodes:
            print(f"[Extract] 从graph_update提取: {len(nodes)} nodes, {len(edges)} edges")
            return latest.get("content", {}) if latest.get("content") else latest
    
    # 方式3: 从消息内容中解析JSON (如果LLM返回了JSON格式的图)
    for msg in chat_result.get("messages", []):
        # 尝试查找JSON代码块
        if "```json" in msg:
            try:
                start = msg.find("```json") + 7
                end = msg.find("```", start)
                json_str = msg[start:end].strip()
                data = json.loads(json_str)
                if "nodes" in data:
                    print(f"[Extract] 从JSON代码块提取: {len(data['nodes'])} nodes")
                    return data
            except:
                pass
    
    # 方式4: 检查raw_events中是否有包含dag的事件
    for event in chat_result.get("raw_events", []):
        # 检查dag字段
        dag = event.get("dag", {})
        if dag and dag.get("nodes"):
            print(f"[Extract] 从raw event的dag字段提取: {len(dag['nodes'])} nodes")
            # DEBUG: check for expressions
            if "expressions" in dag:
                print(f"[Extract] Found {len(dag['expressions'])} expressions in DAG")
            return dag
        
        # 检查content是否包含nodes
        content = event.get("content", {})
        if isinstance(content, dict) and "nodes" in content:
            nodes = content.get("nodes", [])
            if nodes:
                print(f"[Extract] 从raw event的content提取: {len(nodes)} nodes")
                # Return the FULL content object which should be the DAG
                return content
    
    print("[Extract] 未能提取到图结构")
    # 打印所有事件类型以便调试
    print("[Debug] 收到的事件类型:")
    for event in chat_result.get("raw_events", []):
        etype = event.get("type")
        print(f"  - {etype}")
    return None


def run_backtest_with_graph(graph: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
    """
    使用提取的图运行回测
    Returns: 回测结果
    """
    if session_id is None:
        session_id = f"bt-{int(time.time())}"
    
    payload = {
        "session_id": session_id,
        "graph_json": graph,
        "config": {"initial_capital": 100000.0}
    }
    
    result = {
        "logs": [],
        "metrics": None,
        "errors": [],
        "success": False
    }
    
    print(f"[Backtest] 启动回测 (节点数: {len(graph.get('nodes', []))})")
    
    try:
        with requests.post(BACKTEST_URL, json=payload, stream=True, timeout=180) as r:
            if r.status_code != 200:
                result["errors"].append(f"HTTP Error: {r.status_code}")
                return result
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        event_type = event.get("type")
                        
                        if event_type == "log":
                            log_msg = event.get("content", "")
                            result["logs"].append(log_msg)
                            print(f"  [Log] {log_msg[:80]}")
                            
                        elif event_type == "result":
                            result["metrics"] = event.get("metrics", {})
                            result["success"] = True
                            print(f"  [Result] 回测完成!")
                            
                        elif event_type == "error":
                            result["errors"].append(event.get("content", ""))
                            print(f"  [Error] {event.get('content', '')[:80]}")
                            
    except Exception as e:
        result["errors"].append(str(e))
    
    return result


def test_e2e_ma_crossover():
    """
    端到端测试: 生成均线交叉策略并回测
    """
    print("=" * 60)
    print("E2E Test: 均线交叉策略")
    print("=" * 60)
    
    # Step 1: 让LLM生成图
    prompt = "帮我创建一个简单的美股均线交叉策略，使用10日和20日均线，当短期均线上穿长期均线时买入"
    chat_result = chat_generate_graph(prompt)
    
    if chat_result["errors"]:
        print(f"[FAIL] Chat错误: {chat_result['errors']}")
        return False
    
    # Step 2: 提取图
    graph = extract_graph_from_response(chat_result)
    
    if not graph:
        print("[WARN] 未能提取图，尝试打印原始消息:")
        for msg in chat_result["messages"]:
            print(f"  Message: {msg[:200]}...")
        for event in chat_result["raw_events"]:
            print(f"  Event type: {event.get('type')}")
        return False
    
    print(f"[OK] 成功提取图: {len(graph['nodes'])} 节点, {len(graph['edges'])} 边")
    
    # 打印节点信息
    for node in graph["nodes"]:
        print(f"  Node: {node.get('id')} - {node.get('type')}")
    
    # Step 3: 运行回测
    bt_result = run_backtest_with_graph(graph)
    
    if bt_result["errors"]:
        print(f"[FAIL] Backtest错误: {bt_result['errors']}")
        return False
    
    if bt_result["success"]:
        metrics = bt_result["metrics"]
        print("\n[PASS] 回测成功!")
        print("\n  === 核心指标 ===")
        print(f"  总收益率: {metrics.get('total_return', 0):.2f}%")
        print(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  索提诺比率: {metrics.get('sortino_ratio', 0):.2f}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2f}%")
        
        print("\n  === 交易统计 ===")
        print(f"  总交易次数: {metrics.get('total_trades', 0)}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2f}%")
        print(f"  盈利因子: {metrics.get('profit_factor', 0):.2f}")
        print(f"  盈利交易: {metrics.get('winning_trades', 0)}")
        print(f"  亏损交易: {metrics.get('losing_trades', 0)}")
        
        print("\n  === 盈亏分析 ===")
        print(f"  平均盈利: ${metrics.get('avg_win', 0):.2f}")
        print(f"  平均亏损: ${metrics.get('avg_loss', 0):.2f}")
        print(f"  最大单笔盈利: ${metrics.get('largest_win', 0):.2f}")
        print(f"  最大单笔亏损: ${metrics.get('largest_loss', 0):.2f}")
        print(f"  风险回报比: {metrics.get('risk_reward_ratio', 0):.2f}")
        
        print("\n  === 信号统计 ===")
        print(f"  买入信号次数: {metrics.get('buy_signals_count', 0)}")
        print(f"  卖出信号次数: {metrics.get('sell_signals_count', 0)}")
        print(f"  最大连续盈利: {metrics.get('max_consecutive_wins', 0)}")
        print(f"  最大连续亏损: {metrics.get('max_consecutive_losses', 0)}")
        return True
    
    print("[FAIL] 回测未返回结果")
    return False


def test_e2e_rsi_strategy():
    """
    端到端测试: 生成RSI策略并回测
    """
    print("\n" + "=" * 60)
    print("E2E Test: RSI超买超卖策略")
    print("=" * 60)
    
    prompt = "请你设计一个 1 天间隔的双均线策略，使用美股 USAU 进行交易"
    # prompt = '''
    # 请为我生成一个名为“TV-MRA 五维共振趋势系统”的复杂量化策略。该策略需要综合利用当前系统所有可用的高级节点，逻辑如下：

    #     1. **数据源**：
    #     - 获取 BTC/USDT 的 1小时数据。

    #     2. **多重技术指标计算 (调用 indicator 节点)**：
    #     - **趋势层**：计算三条均线，EMA(20)作为短期趋势，EMA(50)作为中期趋势，SMA(200)作为牛熊分界线。
    #     - **动能层**：计算 MACD(12, 26, 9)，我们需要获取 diff_line 和 signal_line。
    #     - **过滤器**：计算 RSI(14) 用于防止高位追涨。
    #     - **量能层**：计算成交量均线 Volume_MA(20)。
    #     - **风控层**：计算 ATR(14) 用于动态止损。

    #     3. **复杂的入场逻辑 (调用 logic 节点)**：
    #     - 这里需要一个多条件的“与”逻辑 (AND condition)：
    #         - **条件A (趋势排列)**：收盘价必须大于 SMA(200)，且 EMA(20) 大于 EMA(50)（多头排列）。
    #         - **条件B (动能确认)**：MACD 的 diff_line 大于 signal_line (处于金叉状态)。
    #         - **条件C (量能确认)**：当前 Volume 大于 Volume_MA(20) (以此确认趋势有效性)。
    #         - **条件D (安全过滤)**：RSI 必须小于 70 (避免在超买区接盘)。

    #     4. **信号生成 (调用 signal 节点)**：
    #     - 当 A、B、C、D 四个条件同时满足时，生成 Buy 信号。
    #     - 理由备注填写：“趋势+动能+量能+RSI安全 四重共振”。

    #     请输出完整的策略代码结构，并确保所有指标和逻辑节点都被正确连接。
    # '''

    # prompt = "创建一个ETH的RSI策略，当RSI低于30时买入，高于70时卖出"
    # prompt = "帮我生成一个简单的双均线策略，用5日和20日移动平均线，金叉买入死叉卖出"
    # prompt = "帮我绘制：均值回归“接飞刀”策略 (Mean Reversion / Dip Buyer) 风格： 逆向思维、抄底 核心逻辑： 利用布林带下轨和 RSI 超卖区的双重确认，捕捉恐慌抛售后的反弹。最好有高点卖出的逻辑。"

    chat_result = chat_generate_graph(prompt)
    
    if chat_result["errors"]:
        print(f"[FAIL] Chat错误: {chat_result['errors']}")
        return False
    
    graph = extract_graph_from_response(chat_result)
    
    if not graph:
        print("[WARN] 未能提取图")
        return False
    
    bt_result = run_backtest_with_graph(graph)
    
    if bt_result["success"]:
        metrics = bt_result["metrics"]
        print("\n[PASS] RSI策略回测成功!")
        print("\n  === 核心指标 ===")
        print(f"  总收益率: {metrics.get('total_return', 0):.2f}%")
        print(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2f}%")
        
        print("\n  === 交易统计 ===")
        print(f"  总交易次数: {metrics.get('total_trades', 0)}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2f}%")
        print(f"  买入信号: {metrics.get('buy_signals_count', 0)} | 卖出信号: {metrics.get('sell_signals_count', 0)}")
        
        # Save to cache for optimization tests
        cache.save_latest_run(graph, metrics)
        
        return True
    
    return False

def test_optimization_loop(iterations: int = 2):
    """
    测试策略优化循环：
    1. 生成初始策略
    2. 运行回测获取指标
    3. 将指标反馈给LLM生成改进策略
    4. 重复步骤2-3
    """
    print("\n" + "=" * 60)
    print("策略优化循环测试 (Optimization Loop)")
    print("=" * 60)
    
    # Step 1: Initial strategy
    initial_prompt = """帮我绘制：均值回归"接飞刀"策略
    风格：逆向思维、抄底
    核心逻辑：利用布林带下轨和RSI超卖区双重确认"""
    
    session_id = f"opt-test-{int(time.time())}"
    
    current_dag = None
    metrics_history = []
    
    for i in range(iterations):
        print(f"\n--- 优化迭代 {i + 1}/{iterations} ---")
        
        if i == 0:
            # First iteration: generate from scratch
            chat_result = chat_generate_graph(initial_prompt, session_id=session_id)
        else:
            # Subsequent iterations: optimize with backtest results
            optimization_prompt = "请根据回测结果优化这个策略，提高夏普比率并降低回撤"
            chat_result = chat_generate_graph(
                optimization_prompt,
                session_id=session_id,
                client_context={
                    "last_graph_dag": current_dag,
                    "backtest_results": metrics_history[-1] if metrics_history else {}
                }
            )
        
        # Extract graph
        dag = extract_graph_from_response(chat_result)
        if not dag:
            print(f"[FAIL] 迭代 {i + 1}: 无法提取图")
            return False
        
        current_dag = dag
        print(f"[OK] 生成策略图: {len(dag.get('nodes', []))} 节点")
        
        # Run backtest
        bt_result = run_backtest(dag)
        if not bt_result or not bt_result.get("success"):
            print(f"[FAIL] 迭代 {i + 1}: 回测失败")
            return False
        
        metrics = bt_result.get("metrics", {})
        metrics_history.append(metrics)
        
        print(f"[OK] 回测完成:")
        print(f"     夏普: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"     回撤: {metrics.get('max_drawdown', 0):.1f}%")
        print(f"     胜率: {metrics.get('win_rate', 0):.1f}%")
    
    # Summary
    print("\n--- 优化结果汇总 ---")
    for i, m in enumerate(metrics_history):
        print(f"  迭代 {i + 1}: Sharpe={m.get('sharpe_ratio', 0):.2f}, DD={m.get('max_drawdown', 0):.1f}%")
    
    return True


def save_artifact(name: str, data: Any, iteration: int = 0):
    """保存中间数据到 artifacts 目录"""
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    filename = f"{name}_iter{iteration}_{int(time.time())}.json"
    filepath = os.path.join(ARTIFACTS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  [Artifact] 保存 {name} -> {filename}")
    return filepath


def call_optimize_api(session_id: str, graph_json: Dict, backtest_results: Dict, 
                      prompt: str = "请根据回测结果优化这个策略") -> Optional[Dict]:
    """
    调用 /backtest/optimize API
    Returns: 优化后的图 或 None
    """
    payload = {
        "session_id": session_id,
        "graph_json": graph_json,
        "backtest_results": backtest_results,
        "optimization_prompt": prompt
    }
    
    print(f"[Optimize API] 调用优化接口...")
    
    result = {"graph": None, "messages": [], "errors": []}
    
    try:
        with requests.post(OPTIMIZE_URL, json=payload, stream=True, timeout=180) as r:
            if r.status_code != 200:
                result["errors"].append(f"HTTP Error: {r.status_code}")
                return None
            
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        event_type = event.get("type")
                        
                        if event_type == "graph_generated":
                            result["graph"] = event.get("dag", {})
                            print(f"[Optimize API] 收到优化后的策略图")
                        elif event_type == "message":
                            result["messages"].append(event.get("content", ""))
                        elif event_type == "error":
                            result["errors"].append(event.get("content", ""))
                            
    except Exception as e:
        result["errors"].append(str(e))
    
    if result["errors"]:
        print(f"[Optimize API] 错误: {result['errors']}")
        
    return result.get("graph")


def test_optimization_api(use_cache: bool = True):
    """
    测试优化 API (/backtest/optimize)
    
    工作流 (简化版):
    1. 从缓存加载最新的图 (last_graph) 和回测结果 (metrics)
    2. 直接调用 /backtest/optimize 接口进行优化
    3. 验证是否返回了优化后的图
    """
    print("\n" + "=" * 60)
    print("优化 API 测试 (Simplified Flow)")
    print("=" * 60)
    
    # 1. Load from cache
    graph, metrics = cache.load_latest_run()
    if not graph or not metrics:
        print("[FAIL] 缓存为空，请先运行 RSI 策略测试生成基准数据")
        return False
        
    print(f"[OK] 已加载基准数据:")
    print(f"     Metrics: Sharpe={metrics.get('sharpe_ratio', 0):.2f}, DD={metrics.get('max_drawdown', 0):.1f}%")
    
    # 2. Call Optimize API
    session_id = f"opt-test-{int(time.time())}"
    print(f"\n--- 调用优化接口 ---")
    
    optimized_dag = call_optimize_api(
        session_id=session_id,
        graph_json=graph,
        backtest_results=metrics,
        prompt="请根据回测结果优化策略"
    )
    
    if not optimized_dag or not optimized_dag.get("nodes"):
        print("[FAIL] 优化接口未返回有效策略 (节点数为 0)")
        return False
        
    # 3. Save Result
    save_artifact("optimized_graph", optimized_dag, 1)
    
    print(f"[OK] 优化成功! 新策略包含 {len(optimized_dag.get('nodes', []))} 个节点")
    print(f"[Artifact] 结果已保存到 contexts/artifacts")
    
    # 4. Verify with Backtest
    print(f"\n--- 验证优化效果 (Running Backtest) ---")
    bt_result = run_backtest_with_graph(optimized_dag, session_id=session_id)
    
    if bt_result and bt_result.get("success"):
        new_metrics = bt_result.get("metrics", {})
        print(f"[PASS] 优化后回测成功!")
        print(f"     Metrics: Sharpe={new_metrics.get('sharpe_ratio', 0):.2f}, "
              f"DD={new_metrics.get('max_drawdown', 0):.1f}%, "
              f"WinRate={new_metrics.get('win_rate', 0):.1f}%")
              
        # Compare
        old_sharpe = metrics.get('sharpe_ratio', 0)
        new_sharpe = new_metrics.get('sharpe_ratio', 0)
        diff = new_sharpe - old_sharpe
        print(f"     Δ Sharpe: {diff:+.2f} {'(Improved)' if diff > 0 else ''}")
    else:
        print(f"[FAIL] 优化后的策略回测失败")
        return False
    
    return True


def run_all_tests():
    """运行所有E2E测试"""
    print("=" * 60)
    print("端到端测试套件: Chat -> Graph -> Backtest")
    print("=" * 60)
    
    results = []
    
    # 基础测试：生成策略并回测（同时保存结果到缓存）
    results.append(("RSI超买超卖策略", test_e2e_rsi_strategy()))
    
    # # 优化测试：使用缓存的结果进行优化循环 (不计入最终报告)
    # print("\n[Running] 策略优化循环 (use_cache=True) - Result Ignored in Summary")
    # test_optimization_api(use_cache=True)
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "通过" if result else "失败"
        print(f"  [{status}] {name}")
    
    print(f"\n共计: {passed} 通过, {failed} 失败")
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
