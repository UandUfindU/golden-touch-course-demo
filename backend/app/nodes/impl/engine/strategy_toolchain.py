"""
Strategy ToolChain - Official tools for Strategy Layer (Offline).

This module provides TWO official tools for the Strategy Layer:
1. Standard.BuildStrategy (Fast Mode) - One-shot DAG generation
2. Standard.AnalyzeStrategy (Think Mode) - ReAct loop for analysis/modification

Both tools accept:
- current_graph: JSON DAG (can be empty) - the current canvas state
- prompt: User's request to build/modify the graph

The tools inject:
- Strategy nodes (indicators, logic, signals)
- Custom user-defined nodes (from session)
- Data source nodes
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node, registry
from app.core.enums import NodeCategory, NodeScope


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

STRATEGY_FAST_SYSTEM_PROMPT = '''你是一个专业的量化策略构建助手。你的任务是根据用户需求生成或修改策略图 (DAG)。

## 当前画布状态
```python
{current_graph_as_python}
```

## 可用节点库
以下是你可以使用的所有节点。**严格使用这些节点，不要虚构不存在的节点。**

{nodes_documentation}

## 输出格式
请输出完整的 Python 伪代码来表示策略图。规则：
1. **实例化节点**: `variable = node_type(param1=value1, param2=value2)`
2. **连接节点**: 将上游变量作为下游参数传入
3. **条件分支**: 使用 Python if/else 语法
4. **信号输出**: 策略必须以 signal 节点结尾

## 示例
用户请求: "创建一个双均线金叉策略"

{example_code}

## 重要提示
- 如果当前画布已有节点，在其基础上修改，不要重新创建已存在的节点
- 确保所有节点连接正确，不要有孤立节点
- **严格使用上方节点库中列出的节点名称，不要使用其他名称**
- 参数名称必须与节点定义一致

现在请根据用户请求生成策略代码。'''


STRATEGY_THINK_SYSTEM_PROMPT = '''你是一个专业的量化策略分析师和调试员。你的任务是分析、诊断和优化用户的策略。

## 当前策略图
```python
{current_graph_as_python}
```

## 可用工具
你可以使用以下工具来分析和修改策略：

### 分析工具
- `backtest(params)`: 运行回测，获取策略表现报告
- `validate()`: 检查当前图的合法性
- `explain(node_id)`: 解释某个节点的作用

### 修改工具  
- `add_node(type, params)`: 添加新节点
- `remove_node(node_id)`: 删除节点
- `connect(from_node, to_node, port)`: 连接两个节点
- `modify_param(node_id, param, value)`: 修改节点参数

### 策略节点库
{nodes_documentation}

## 工作流程 (ReAct)
1. **思考 (Thought)**: 分析用户请求，确定需要做什么
2. **行动 (Action)**: 选择一个工具执行
3. **观察 (Observation)**: 查看工具返回的结果
4. 重复以上步骤直到任务完成
5. **最终答案 (Final Answer)**: 总结改动并输出最终的策略代码

## 示例
用户: "分析下我的策略为什么总是亏钱"

Thought: 用户想知道策略亏钱的原因。我需要先运行回测看看具体表现。
Action: backtest
Action Input: {{"start_date": "2024-01-01", "end_date": "2024-12-01"}}
Observation: 回测结果显示胜率 32%，平均盈亏比 0.8:1，最大回撤 45%...

Thought: 胜率和盈亏比都很低，需要检查入场条件是否合理。策略使用了 RSI < 30 作为入场条件，这在趋势市可能不适用。
Action: explain
Action Input: {{"node_id": "rsi_node"}}
...

现在请根据用户请求进行分析。'''


# NOTE: Node role definitions and documentation formatting have been moved to
# ToolRetrieverNode (app/nodes/impl/tool/llm/tool_retriever_node.py)
# for centralized management and single responsibility.


# =============================================================================
# STRATEGY TOOLCHAIN NODES
# =============================================================================

class StrategyToolInput(BaseModel):
    """Input schema for Strategy tools."""
    current_graph: Dict[str, Any] = Field(
        default_factory=lambda: {"nodes": [], "edges": []},
        description="当前画布的 DAG JSON (可为空)"
    )
    prompt: str = Field(
        description="用户的构图/改图请求"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for context/memory"
    )
    max_retries: int = Field(
        default=5,
        description="最大重试次数 (默认 5)"
    )
    # NEW: Backtest results for optimization mode
    backtest_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="回测结果用于策略优化 (包含 sharpe_ratio, max_drawdown, win_rate 等)"
    )


class StrategyToolOutput(BaseModel):
    """Output schema for Strategy tools."""
    dag: Optional[Dict[str, Any]] = Field(description="生成/修改后的 DAG JSON")
    success: bool = Field(description="是否成功")
    message: str = Field(description="执行摘要或错误信息")
    thought_process: List[str] = Field(default_factory=list, description="推理过程 (Think Mode)")


@register_node(
    category=NodeCategory.AI,
    name="standard.build_strategy",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class BuildStrategyNode(BaseNode):
    """
    Standard.BuildStrategy - Fast Mode 策略生成工具。
    
    一次性生成完整的策略 DAG。适用于：
    - 从零开始构建策略
    - 根据描述快速生成初稿
    
    调用方式示例 (给调用此工具的 LLM 的指导):
    ```
    要创建策略时，调用 build_strategy 工具:
    - prompt: 详细描述策略逻辑，包括使用的指标、入场/出场条件
    - current_graph: 如果要在现有图基础上修改，传入当前图 JSON；否则传空
    
    好的 prompt 示例:
    - "创建一个 RSI 超卖反弹策略：当 RSI(14) < 30 且价格站上 MA(20) 时买入"
    - "在当前策略基础上，添加止损条件：当亏损超过 5% 时平仓"
    ```
    """
    description = "Fast Mode: 一次性生成完整策略图"
    InputSchema = StrategyToolInput
    OutputSchema = StrategyToolOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Import dependencies
        from app.nodes.impl.engine.dag_to_python import DAGtoPythonNode
        from app.nodes.impl.tool.llm.llm_chat_node import LLMChatNode
        from app.nodes.impl.tool.llm.response_parser_node import ResponseParserNode
        from app.nodes.impl.tool.llm.code_to_dag_node import CodeToDAGNode
        from app.nodes.impl.engine.graph_validator import validate_graph
        
        thought_process = []
        
        # 1. Convert current graph to Python for context
        current_python = "# 空画布 - 从零开始构建"
        if params.current_graph.get("nodes"):
            dag_to_py = DAGtoPythonNode()
            py_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_d2p",
                inputs={"dag": params.current_graph}
            )
            py_res = dag_to_py.run(py_ctx)
            current_python = py_res.get("python_code", current_python)
        
        thought_process.append(f"当前画布: {len(params.current_graph.get('nodes', []))} 个节点")
        
        thought_process.append(f"当前画布: {len(params.current_graph.get('nodes', []))} 个节点")
        
        # 2. Retrieve node documentation via ToolRetrieverNode (single source of truth)
        ctx.emit_status("📚 正在检索可用节点文档...")
        from app.nodes.impl.tool.llm.tool_retriever_node import ToolRetrieverNode
        
        retriever = ToolRetrieverNode()
        retriever_ctx = Context(
            run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_retriever",
            inputs={
                "scope": "strategy",
                "scenario": "strategy_building",
                "output_format": "documentation",
                "include_roles": True
            }
        )
        retriever_res = retriever.run(retriever_ctx)
        nodes_doc = retriever_res.get("documentation", "")
        example_code = retriever_res.get("example_code", "")  # Now from ToolRetrieverNode
        thought_process.append(f"已加载 {retriever_res.get('count', 0)} 个节点文档")
        
        # 3. Build prompt
        # Inject strict reminders about common errors (Input Data)
        system_prompt = STRATEGY_FAST_SYSTEM_PROMPT.format(
            current_graph_as_python=current_python,
            nodes_documentation=nodes_doc,
            example_code=example_code
        )
        # Add explicit reminder about data inputs for indicators
        system_prompt += """

CRITICAL RULES:
1. Most indicators (e.g., ma, rsi, bollinger_bands) REQUIRE a 'source' input (e.g., source=data). DO NOT Forget it.
2. MULTI-OUTPUT INDICATORS - Use tuple unpacking:
   - Bollinger Bands: `upper, middle, lower = indicator.bollinger_bands(source=data, period=20)`
   - MACD: `line, signal, histogram = indicator.macd(source=data)`
3. CONDITIONS are BOOLEAN values:
   - CORRECT: if entry_condition: signal.buy()
   - WRONG: if entry_condition.result: signal.buy()  # .result does NOT exist!
4. PREFER `condition` PARAMETER over nested if/elif (more DAG-friendly):
   - PREFERRED: signal.buy(condition=close < lower)
   - PREFERRED: signal.sell(condition=close > upper)
   - AVOID: if cond1: ... elif cond2: ... elif cond3: ...
5. Use data columns directly: close, open, high, low, volume
"""
        
        # === OPTIMIZATION MODE: Inject backtest results if provided ===
        if params.backtest_results:
            bt = params.backtest_results
            optimization_prompt = f"""

## 📊 上一次回测结果分析
当前策略的回测表现如下，请据此优化策略：

| 指标 | 值 | 评价 |
|------|-----|------|
| 夏普比率 | {bt.get('sharpe_ratio', 0):.2f} | {'⚠️ 较低' if bt.get('sharpe_ratio', 0) < 1.0 else '✅ 良好'} |
| 最大回撤 | {bt.get('max_drawdown', 0):.1f}% | {'⚠️ 过高' if bt.get('max_drawdown', 0) > 20 else '✅ 可控'} |
| 胜率 | {bt.get('win_rate', 0):.1f}% | {'⚠️ 偏低' if bt.get('win_rate', 0) < 50 else '✅ 良好'} |
| 总收益率 | {bt.get('total_return', 0):.1f}% | - |
| 总交易次数 | {bt.get('total_trades', 0)} | {'⚠️ 过少' if bt.get('total_trades', 0) < 5 else '✅ 正常'} |
| 买入信号数 | {bt.get('buy_signals_count', 0)} | - |
| 卖出信号数 | {bt.get('sell_signals_count', 0)} | {'⚠️ 无卖出' if bt.get('sell_signals_count', 0) == 0 else '-'} |

## 🔧 优化建议
基于以上结果，请生成改进后的策略代码：
"""
            # Add specific suggestions based on metrics
            suggestions = []
            if bt.get('sharpe_ratio', 0) < 1.0:
                suggestions.append("- 夏普比率低：考虑调整入场条件阈值，使信号更精准")
            if bt.get('max_drawdown', 0) > 20:
                suggestions.append("- 回撤过大：添加止损条件或降低仓位")
            if bt.get('win_rate', 0) < 50:
                suggestions.append("- 胜率偏低：优化入场条件，可能需要更严格的过滤")
            if bt.get('total_trades', 0) < 5:
                suggestions.append("- 交易次数太少：放宽入场条件阈值")
            if bt.get('sell_signals_count', 0) == 0:
                suggestions.append("- 无卖出信号：添加 signal.sell() 定义退出条件")
            
            if suggestions:
                optimization_prompt += "\n".join(suggestions)
            else:
                optimization_prompt += "- 策略表现良好，可尝试微调参数进一步优化"
            
            system_prompt += optimization_prompt
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": params.prompt}
        ]
        
        llm = LLMChatNode()
        parser = ResponseParserNode()
        converter = CodeToDAGNode()
        
        max_retries = params.max_retries  # User-configurable, default 10
        generated_dag = None
        
        ctx.emit_status(f"🤖 开始生成策略代码 (最大重试 {max_retries} 次)...")
        
        for attempt in range(max_retries):
            retry_msg = f"🔄 尝试 {attempt + 1}/{max_retries}: 调用 LLM..."
            thought_process.append(retry_msg)
            ctx.emit_status(retry_msg)
            
            # 4. Call LLM
            llm_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_llm_{attempt}",
                inputs={
                    "messages": messages,
                    "model": "glm-4-flash",
                    "provider": "glm",
                    "temperature": 0.1 + attempt * 0.1,  # Increase creativity on retries
                    "max_tokens": 8192
                }
            )
            llm_res = llm.run(llm_ctx)
            response = llm_res.get("response", "")
            thought_process.append(f"LLM 响应长度: {len(response)}")
            
            # 5. Parse code from response
            ctx.emit_status(f"🧩 解析代码 (尝试 {attempt + 1})...")
            parse_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_parse_{attempt}",
                inputs={"llm_output": response, "parse_mode": "code"}
            )
            parse_res = parser.run(parse_ctx)
            code_blocks = parse_res.get("parsed", {}).get("code_blocks", [])
            
            if not code_blocks:
                error_msg = "未生成有效的 Python 代码块。请确保输出包含 ```python ... ``` 代码块。"
                thought_process.append(f"解析失败: {error_msg}")
                ctx.emit_status("⚠️ 解析失败:未找到代码块，正在重试...")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"错误: {error_msg}\n请重新生成代码。"})
                continue
            
            # 6. Convert code to DAG
            ctx.emit_status(f"⚙️ 转换代码为 DAG (尝试 {attempt + 1})...")
            dag_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_dag_{attempt}",
                inputs={"code": code_blocks[0]}
            )
            dag_res = converter.run(dag_ctx)
            
            if not dag_res.get("success"):
                error_msg = f"代码转换失败: {dag_res.get('error', 'Unknown')}"
                thought_process.append(f"转换失败: {error_msg}")
                ctx.emit_status(f"⚠️ 转换显示: {error_msg}")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"错误: {error_msg}\n请修正代码语法并重新生成。"})
                continue
            
            # 7. Validate the generated DAG
            generated_dag = dag_res.get("dag", {})
            validation = validate_graph(generated_dag)
            
            if not validation.valid:
                error_msg = f"图验证失败: {validation.summary}"
                # REMOVED TRUNCATION here
                thought_process.append(f"验证失败: {validation.summary}") 
                ctx.emit_status(f"❌ 验证失败: {validation.summary}") # Keep status short for display
                
                # DEBUG: Print the code that failed
                print("\n" + "="*40)
                print("DEBUG: [FAILED LLM CODE]")
                print(dag_res.get("code", "No code returned")) # params.code passed through or need to fetch?
                # CodeToDAG output contains 'dag', inputs contained 'code'. 
                # params are inputs. 'code' was input.
                # Actually dag_res is the OUTPUT of CodeToDAGNode.run().
                # CodeToDAGNode output schema: dag, nodes, edges... NO CODE.
                # But 'params.code' was available in the node execution scope.
                # Wait, this is 'BuildStrategyNode'. It calls 'code_to_dag' via `tool.llm.code_to_dag_node`.
                # If I want to see the code, I rely on the fact that `response` (LLM text) usually contains it.
                print(response) # The full LLM response
                print("="*40 + "\n")

                messages.append({"role": "assistant", "content": response})
                
                # DYNAMIC ERROR-BASED EXAMPLE INJECTION
                # Analyze specific errors and inject relevant examples
                feedback_examples = []
                error_summary = validation.summary.lower()
                
                # Check for multi-output / tuple unpacking issues
                if "bollinger" in error_summary or "undefined variable" in error_summary:
                    if "upper" in error_summary or "lower" in error_summary or "middle" in error_summary:
                        feedback_examples.append("""
[FIX: Bollinger Bands requires tuple unpacking!]
WRONG: bollinger_bands = indicator.bollinger_bands(source=data, period=20)
       signal.buy(condition=bollinger_bands['lower'] < close)  # FAILS!

CORRECT:
upper, middle, lower = indicator.bollinger_bands(source=data, period=20)
signal.buy(condition=close < lower)
""")
                
                if "macd" in error_summary:
                    if "line" in error_summary or "signal" in error_summary or "histogram" in error_summary:
                        feedback_examples.append("""
[FIX: MACD requires tuple unpacking!]
WRONG: macd = indicator.macd(source=data)
       signal.buy(condition=macd['line'] > macd['signal'])  # FAILS!

CORRECT:
line, signal_macd, histogram = indicator.macd(source=data)
signal.buy(condition=line > signal_macd)
""")
                
                # Check for dictionary/subscript access pattern
                if "['close']" in response or "['lower']" in response or "['upper']" in response or "['values']" in response:
                    feedback_examples.append("""
[FIX: NO dictionary/subscript access allowed!]
WRONG: data['close'], bollinger_bands['lower'], rsi['values']
CORRECT: close, lower, rsi (use variables directly after assignment/tuple-unpack)
""")
                
                # Check for missing source parameter
                if "missing" in error_summary and "source" in error_summary:
                    feedback_examples.append("""
[FIX: Indicator missing 'source' parameter!]
WRONG: rsi = indicator.rsi(period=14)
CORRECT: rsi = indicator.rsi(source=data, period=14)
""")
                
                # Check for signal connection issues
                if "logic dead end" in error_summary or "unreachable signal" in error_summary:
                    feedback_examples.append("""
[FIX: Signal Connection Issue!]
If using 'if' block, ensure signal is INSIDE:
  if condition:
      signal.buy()
OR pass condition directly:
  signal.buy(condition=close < lower and rsi < 30)
""")
                
                # Default tip if no specific patterns matched
                if not feedback_examples:
                    feedback_examples.append("""
General tips:
1. All indicators need source=data
2. Multi-output indicators (bollinger_bands, macd) MUST use tuple unpacking
3. Use variables directly: close, lower, rsi (NOT data['close'], bb['lower'])
4. signal.buy/sell need condition parameter
""")
                
                feedback = f"错误: {error_msg}\n\n{''.join(feedback_examples)}\n\nPlease regenerate the COMPLETE corrected code."
                messages.append({"role": "user", "content": feedback})
                continue
            
            # SUCCESS!
            thought_process.append("策略图生成并验证成功")
            ctx.emit_status("✅ 策略生成成功！")
            return {
                "dag": generated_dag,
                "success": True,
                "message": f"成功生成策略图，包含 {len(generated_dag.get('nodes', []))} 个节点 (尝试 {attempt + 1} 次)",
                "thought_process": thought_process
            }
        
        # All retries exhausted
        return {
            "dag": generated_dag,  # Return last attempt for debugging
            "success": False,
            "message": f"经过 {max_retries} 次尝试仍无法生成有效策略图",
            "thought_process": thought_process
        }


# =============================================================================
# THINK MODE (Structured Analysis) IMPLEMENTATION
# =============================================================================

THINK_ANALYSIS_PROMPT = '''You are a Senior Quantitative Strategy Analyst.
Your task is to conduct a deep analysis of the provided Quantitative Strategy DAG and suggest concrete improvements based on the user's intent.

## Current Strategy Graph (Python Representation)
```python
{current_graph_as_python}
```

## User Intent
{user_prompt}

## Available Node Library (Documentation)
{nodes_documentation}

## Analysis Task
Analyze the strategy from the following dimensions:

1. **Rationality**: Is the logic self-consistent? Are the node connections valid?
2. **Intent Match**: Does the current graph genuinely reflect what the user wants? What is missing?
3. **Improvements**: Specific, actionable suggestions to optimize the strategy.

## Output Format
Please output a structured report in Markdown format. Do NOT include any code implementations here.

### 1. Rationality Analysis
...

### 2. Intent Alignment
...

### 3. Improvement Suggestions
- Suggestion 1...
- Suggestion 2...

### 4. Summary
...
'''


@register_node(
    category=NodeCategory.AI,
    name="standard.analyze_strategy",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class AnalyzeStrategyNode(BaseNode):
    """
    Standard.AnalyzeStrategy - Think Mode 策略分析工具。
    
    结构化分析流程:
    1. 无图时: 调用 Fast Mode 生成初稿
    2. 有图时: 深度分析 + 改进建议
    3. 验证: 确保输出图合法
    4. 输出: 图 + 分析报告
    
    适用于:
    - 策略诊断和优化
    - 策略设计审查
    - 用户意图与实现的对比分析
    """
    description = "Think Mode: 结构化分析和优化策略，输出图 + 分析报告"
    InputSchema = StrategyToolInput
    OutputSchema = StrategyToolOutput
    
    MAX_RETRIES = 30  # For validation failures (delegated to Fast Mode) (delegated to Fast Mode)
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        from app.nodes.impl.tool.llm.llm_chat_node import LLMChatNode
        from app.nodes.impl.tool.llm.tool_retriever_node import ToolRetrieverNode
        # BuildStrategyNode is in the same file, but we use local import to avoid top-level circular issues if moved
        from app.nodes.impl.engine.strategy_toolchain import BuildStrategyNode
        
        thought_process = []
        current_graph = dict(params.current_graph) if params.current_graph else {"nodes": [], "edges": []}
        is_empty_graph = not current_graph.get("nodes")
        
        # ========== STEP 0: 无图时调用 Fast Mode 生成初稿 ==========
        if not current_graph.get("nodes"):
            thought_process.append("无现有图，调用 Fast Mode 生成初稿...")
            ctx.emit_status("📡 正在调用 Fast Mode 生成初始草稿...")
            
            fast_node = BuildStrategyNode()
            fast_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id,
                node_id=f"{ctx.node_id}_fast",
                inputs={
                    "current_graph": current_graph,
                    "prompt": params.prompt,
                    "max_retries": 5  # Quick draft
                },
                on_status_update=ctx.on_status_update # Propagate callback
            )
            fast_result = fast_node.run(fast_ctx)
            
            if fast_result.get("success"):
                current_graph = fast_result.get("dag", {})
                thought_process.append(f"Fast Mode 生成初稿: {len(current_graph.get('nodes', []))} 个节点")
            else:
                return {
                    "dag": current_graph,
                    "success": False,
                    "message": f"无法生成初稿: {fast_result.get('message', '未知错误')}",
                    "thought_process": thought_process
                }
        else:
            thought_process.append(f"分析现有图: {len(current_graph.get('nodes', []))} 个节点")
        
        # ========== PREP: 获取上下文 ==========
        ctx.emit_status("📖 正在读取节点文档...")
        retriever = ToolRetrieverNode()
        retriever_ctx = Context(
            run_id=ctx.run_id, workflow_id=ctx.workflow_id,
            node_id=f"{ctx.node_id}_retriever",
            inputs={"scope": "strategy", "output_format": "documentation", "include_roles": True}
        )
        nodes_doc = retriever.run(retriever_ctx).get("documentation", "")
        current_python = self._graph_to_python(current_graph, ctx)
        
        llm = LLMChatNode()
        
        # ========== STEP 1: Analysis / Design (Report Generation) ==========
        thought_process.append("Step 1: Strategic Analysis & Planning...")
        ctx.emit_status("🧠 Step 1: 正在进行深度策略分析 (Generating Report)...")
        
        analysis_content = ""
        analysis_prompt = ""
        
        if is_empty_graph:
            # Design Mode: Create a plan from scratch
            analysis_prompt = f"""You are a Senior Quantitative Strategy Architect.
User Request: "{params.prompt}"

Please design a comprehensive strategy structure based on this request.
Do not write code yet, but outline the key components, logic flow, and necessary risk management modules.
Output a structured Markdown design document.
"""
        else:
            # Analysis Mode: Critique and improve existing graph
            # Note: We use the English prompt defined globally
            analysis_prompt = THINK_ANALYSIS_PROMPT.replace(
                "{current_graph_as_python}", current_python
            ).replace(
                "{user_prompt}", params.prompt
            ).replace(
                "{nodes_documentation}", nodes_doc
            )
        
        try:
            analysis_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id,
                node_id=f"{ctx.node_id}_analyze",
                inputs={
                    "messages": [{"role": "user", "content": analysis_prompt}],
                    "model": "glm-4-flash",
                    "temperature": 0.4
                }
            )
            analysis_res = llm.run(analysis_ctx)
            analysis_content = analysis_res.get("response", "")
            thought_process.append("Analysis/Design complete.")
            ctx.emit_status("✅ 分析报告生成完成，准备执行...")
        except Exception as e:
             thought_process.append(f"Analysis failed: {str(e)}")
             analysis_content = f"Analysis failed. Original request: {params.prompt}"
             ctx.emit_status(f"❌ 分析步骤出错: {str(e)}")

        # ========== STEP 2: Execution (Delegate to Fast Mode) ==========
        thought_process.append("Step 2: Delegating to Builder (Fast Mode)...")
        ctx.emit_status("🛠️ Step 2: 正在调用构建器 (BuildStrategyNode) 执行修改...")
        
        # Construct a rich prompt that acts as the "spec" for Fast Mode
        enhanced_prompt = f"""
[User Request]
{params.prompt}

[Expert Analysis & Implementation Plan]
{analysis_content}

## CRITICAL IMPLEMENTATION INSTRUCTION
1. The Analysis Report above may contain **PSEUDO-CODE** or hypothetical node types (e.g., `custom.max`, `indicator.drawdown`).
2. **DO NOT** use any node type unless it is explicitly listed in your system's "Available Node Library".
3. You MUST translate the *logic* described in the report into valid nodes.
   - Example: If report says `max_drawdown(price)`, implement it using `calculate` or `accumulator` nodes if a direct node doesn't exist.
   - Example: If report says `stop_loss(...)`, implement it using `logic.condition` + `signal.sell`.
4. Ensure the graph is strictly valid and atomic.
"""
        
        # Call BuildStrategyNode (Fast Mode)
        fast_node = BuildStrategyNode()
        fast_ctx = Context(
            run_id=ctx.run_id, workflow_id=ctx.workflow_id,
            node_id=f"{ctx.node_id}_fast_execution",
            inputs={
                "current_graph": current_graph,
                "prompt": enhanced_prompt, # Pass the enhanced prompt
                "max_retries": self.MAX_RETRIES # Use Think Mode's higher retry budget
            },
            on_status_update=ctx.on_status_update # Propagate callback
        )
        
        fast_result = fast_node.run(fast_ctx)
        
        # Merge thought processes for visibility
        if fast_result.get("thought_process"):
             thought_process.extend([f"[Builder] {t}" for t in fast_result.get("thought_process", [])])
        
        return {
            "dag": fast_result.get("dag", current_graph),
            "success": fast_result.get("success", False),
            "message": analysis_content, # Important: Return the Analysis Report as the message
            "thought_process": thought_process
        }
    
    def _graph_to_python(self, graph: Dict, ctx: Context) -> str:
        """Convert graph to Python pseudo-code."""
        if not graph.get("nodes"):
            return "# Empty Canvas"
        
        from app.nodes.impl.engine.dag_to_python import DAGtoPythonNode
        dag_to_py = DAGtoPythonNode()
        py_ctx = Context(
            run_id=ctx.run_id, workflow_id=ctx.workflow_id, 
            node_id=f"{ctx.node_id}_d2p",
            inputs={"dag": graph}
        )
        return dag_to_py.run(py_ctx).get("python_code", "# Conversion Failed")


# =============================================================================
# CREATE NODE (LLM Fallback)
# =============================================================================

CREATE_NODE_SYSTEM_PROMPT = '''你是一个专业的量化节点开发助手。你的任务是根据用户描述创建一个新的计算节点。

## 输出格式
你需要输出一个完整的节点定义，包含以下部分：

1. **节点名称**: 简洁的 snake_case 名称，如 `custom.my_indicator`
2. **节点描述**: 一句话描述节点功能
3. **输入参数**: 参数名、类型、是否必填、默认值、描述
4. **输出字段**: 字段名、类型、描述
5. **计算逻辑**: Python 代码，使用 pandas/numpy 进行计算

## 示例
用户请求: "创建一个布林带指标，输出上轨、中轨、下轨"

```json
{
  "name": "custom.bollinger_bands",
  "description": "布林带指标，计算上轨、中轨、下轨",
  "inputs": {
    "source": {"type": "DataFrame", "required": true, "description": "OHLCV 数据"},
    "period": {"type": "int", "required": false, "default": 20, "description": "计算周期"},
    "std_dev": {"type": "float", "required": false, "default": 2.0, "description": "标准差倍数"}
  },
  "outputs": {
    "upper": {"type": "Series", "description": "上轨"},
    "middle": {"type": "Series", "description": "中轨 (SMA)"},
    "lower": {"type": "Series", "description": "下轨"}
  },
  "code": "import pandas as pd\\nmiddle = source['close'].rolling(period).mean()\\nstd = source['close'].rolling(period).std()\\nupper = middle + std_dev * std\\nlower = middle - std_dev * std"
}
```

请确保代码使用标准的 pandas/numpy 操作，不要使用外部库。'''


class CreateNodeInput(BaseModel):
    """Input for CreateNode."""
    description: str = Field(
        description="描述你需要的节点功能"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID (节点将绑定到此 Session)"
    )


class CreateNodeOutput(BaseModel):
    """Output for CreateNode."""
    node_definition: Optional[Dict[str, Any]] = Field(description="生成的节点定义 JSON")
    node_name: Optional[str] = Field(description="节点名称")
    success: bool = Field(description="是否成功")
    message: str = Field(description="结果消息")
    thought_process: List[str] = Field(default_factory=list, description="生成过程")


@register_node(
    category=NodeCategory.AI,
    name="standard.create_node",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class CreateNodeNode(BaseNode):
    """
    Standard.CreateNode - LLM 驱动的自定义节点创建。
    
    当现有节点无法满足需求时，LLM 可以调用此工具创建临时节点。
    生成的节点是 Session 级别的，Session 结束后销毁。
    
    用途:
    - 创建自定义技术指标
    - 创建特殊的数据处理逻辑
    - 扩展系统能力
    
    限制:
    - 节点代码在沙箱中执行
    - 只能使用 pandas, numpy 等安全库
    - 每个 Session 最多创建 10 个自定义节点
    """
    description = "LLM 创建自定义节点 (Session 级别)"
    InputSchema = CreateNodeInput
    OutputSchema = CreateNodeOutput
    
    MAX_CUSTOM_NODES_PER_SESSION = 10
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        from app.nodes.impl.tool.llm.llm_chat_node import LLMChatNode
        
        thought_process = []
        thought_process.append(f"用户需求: {params.description[:100]}...")
        
        # Build prompt
        messages = [
            {"role": "system", "content": CREATE_NODE_SYSTEM_PROMPT},
            {"role": "user", "content": f"请创建以下节点:\n\n{params.description}"}
        ]
        
        # Call LLM
        llm = LLMChatNode()
        llm_ctx = Context(
            run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_llm",
            inputs={
                "messages": messages,
                "model": "glm-4-flash",
                "provider": "glm",
                "temperature": 0.2,
                "max_tokens": 8192
            }
        )
        llm_res = llm.run(llm_ctx)
        response = llm_res.get("response", "")
        thought_process.append(f"LLM 响应长度: {len(response)} 字符")
        
        # Parse JSON from response
        import re
        import json
        
        json_match = re.search(r'\{[\s\S]+\}', response)
        if not json_match:
            return {
                "node_definition": None,
                "node_name": None,
                "success": False,
                "message": "LLM 未生成有效的 JSON 节点定义",
                "thought_process": thought_process
            }
        
        try:
            node_def = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            return {
                "node_definition": None,
                "node_name": None,
                "success": False,
                "message": f"JSON 解析失败: {e}",
                "thought_process": thought_process
            }
        
        # Validate node definition structure
        required_fields = ["name", "description", "inputs", "outputs"]
        for field in required_fields:
            if field not in node_def:
                return {
                    "node_definition": node_def,
                    "node_name": node_def.get("name"),
                    "success": False,
                    "message": f"节点定义缺少必填字段: {field}",
                    "thought_process": thought_process
                }
        
        node_name = node_def.get("name", "custom.unnamed")
        thought_process.append(f"成功解析节点: {node_name}")
        
        # TODO: Register to session-scoped registry
        # For now, just return the definition
        thought_process.append("节点定义生成成功 (Session 注册待实现)")
        
        return {
            "node_definition": node_def,
            "node_name": node_name,
            "success": True,
            "message": f"成功生成节点: {node_name}",
            "thought_process": thought_process
        }
