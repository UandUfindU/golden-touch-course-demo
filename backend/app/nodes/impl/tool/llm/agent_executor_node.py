"""
Agent Executor Node - Orchestrates ReAct agent loop.

Composite node that combines Tool Retrieval, Prompt Building,
LLM Calling, and Response Parsing in a loop.
Uses LangGraph StateGraph for orchestration.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node
from app.core.enums import NodeCategory, NodeScope


class AgentExecutorInput(BaseModel):
    """AgentExecutor node input"""
    query: str = Field(
        description="User query to process"
    )
    session_id: str = Field(
        description="Session ID for memory management"
    )
    scope: str = Field(
        default="strategy",
        description="Scope for tool retrieval"
    )
    max_iterations: int = Field(
        default=5,
        description="Maximum ReAct iterations"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries upon execution failure"
    )
    model: str = Field(
        default="glm-4-flash",
        description="LLM model to use"
    )
    provider: str = Field(
        default="glm",
        description="LLM provider"
    )


class AgentExecutorOutput(BaseModel):
    final_answer: str = Field(description="Final response from agent")
    dag: Optional[Dict[str, Any]] = Field(default=None, description="Generated DAG if any")
    iterations: int = Field(description="Number of iterations taken")
    thought_process: List[str] = Field(description="Agent's thought process")
    success: bool = Field(description="Whether execution succeeded")


@register_node(
    category=NodeCategory.AI,
    name="llm.agent_executor",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW]
)
class AgentExecutorNode(BaseNode):
    """
    Agent Executor Node - Robust ReAct/DAG Generation Loop.
    
    Orchestrates the LLM -> Code -> Verify loop.
    1. Retrieves tools and builds initial prompt.
    2. Calls LLM.
    3. If Code Generated -> Parses and Converts to DAG.
    4. If DAG Parsing Fails -> Feeds error back to LLM (Feedback Loop).
    5. Retries until max_retries or success.
    
    Implements "Self-Correction" pattern.
    """
    description = "Run robust agent loop with error recovery"
    InputSchema = AgentExecutorInput
    OutputSchema = AgentExecutorOutput

    def run(self, ctx: Context) -> Dict[str, Any]:
        params = self.validate_inputs(ctx.inputs)
        
        # Import node classes explicitly inside run to avoid circular imports during registry loading
        from .tool_retriever_node import ToolRetrieverNode
        from .prompt_builder_node import PromptBuilderNode
        from .llm_chat_node import LLMChatNode
        from .response_parser_node import ResponseParserNode
        from .code_to_dag_node import CodeToDAGNode
        from .memory_manager_node import MemoryManagerNode
        
        # Initialize sub-nodes
        retriever = ToolRetrieverNode()
        prompt_builder = PromptBuilderNode()
        llm_chat = LLMChatNode()
        parser = ResponseParserNode()
        dag_converter = CodeToDAGNode()
        memory = MemoryManagerNode()
        
        thought_process = []
        iterations = 0
        current_messages = []
        
        try:
            # --- PRE-LOOP: Context Building ---
            
            # 1. Retrieve tools
            if ctx.on_status_update:
                ctx.on_status_update("🔍 Retrieving tools...")
                
            retriever_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_ret",
                inputs={"query": params.query, "scope": params.scope, "top_k": 10}
            )
            # Support 'scenario' if user context provides it, otherwise default
            if "scenario" in ctx.inputs:
                retriever_ctx.inputs["scenario"] = ctx.inputs["scenario"]
                
            tools_result = retriever.run(retriever_ctx)
            tools = tools_result.get("tools", [])
            tool_names = [t.get('name', 'unknown') for t in tools]
            thought_process.append(f"Retrieved {len(tools)} tools: {', '.join(tool_names)}")

            # 2. Get Memory
            memory_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_mem_get",
                inputs={"session_id": params.session_id, "action": "get"}
            )
            hist_result = memory.run(memory_ctx)
            history = hist_result.get("history", [])

            # 3. Build Initial Prompt
            if ctx.on_status_update:
                ctx.on_status_update("📝 Constructing prompt...")
                
            prompt_ctx = Context(
                run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_prompt",
                inputs={
                    "template_name": "dag_generator",
                    "tools": tools,
                    "query": params.query,
                    "history": history
                }
            )
            prompt_result = prompt_builder.run(prompt_ctx)
            current_messages = prompt_result.get("messages", [])

            # --- MAIN LOOP: Generate -> Verify -> Retry ---
            
            max_attempts = params.max_retries + 1  # 1 initial + retries
            for attempt in range(max_attempts):
                iterations += 1
                thought_process.append(f"--- Iteration {iterations} ---")
                
                if ctx.on_status_update:
                    status_msg = f"🧠 Thinking (Attempt {iterations}/{max_attempts})..."
                    if attempt > 0:
                        status_msg = f"🔧 Self-Correcting (Attempt {iterations}/{max_attempts})..."
                    ctx.on_status_update(status_msg)
                
                # 4. LLM Generation
                llm_ctx = Context(
                    run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_llm_{iterations}",
                    inputs={
                        "messages": current_messages,
                        "model": params.model,
                        "provider": params.provider,
                        "temperature": 0.1 if attempt > 0 else 0.1, # Keep low temp for code
                        "max_tokens": 8192
                    }
                )
                llm_res = llm_chat.run(llm_ctx)
                response_text = llm_res.get("response", "")
                thought_process.append(f"LLM Response: {response_text[:100]}...")
                
                # Append assistant response to history chain for next turn if needed
                current_messages.append({"role": "assistant", "content": response_text})

                # 5. Parse Response
                if ctx.on_status_update:
                    ctx.on_status_update("⚙️ Parsing code...")
                    
                parser_ctx = Context(
                    run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_parse_{iterations}",
                    inputs={"llm_output": response_text, "parse_mode": "code"}
                )
                parse_res = parser.run(parser_ctx)
                code_blocks = parse_res.get("parsed", {}).get("code_blocks", [])

                if not code_blocks:
                    # No code generated? Feedback loop.
                    error_msg = "Error: No Python code block found in response. Please generate valid Python code inside ```python ``` blocks."
                    thought_process.append(error_msg)
                    # Feed error back to loop inputs
                    current_messages.append({"role": "user", "content": error_msg})
                    continue # Retry
                
                # 6. Verify / Convert to DAG
                if ctx.on_status_update:
                    ctx.on_status_update("🏗️ Building graph structure...")
                    
                code = code_blocks[0]
                dag_ctx = Context(
                    run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_dag_{iterations}",
                    inputs={"code": code}
                )
                dag_res = dag_converter.run(dag_ctx)
                
                if dag_res["success"]:
                    # Check graph validity
                    if ctx.on_status_update:
                        ctx.on_status_update("🔍 Validating logic...")
                        
                    from app.nodes.impl.engine.graph_validator import validate_graph
                    validation = validate_graph(dag_res["dag"])
                    
                    if not validation.valid:
                        # Validation failed - feedback to LLM
                        err_summary = validation.summary
                        
                        # --- ENHANCED FEEDBACK INJECTION ---
                        if "Logic Dead End" in err_summary or "Unreachable Signal" in err_summary:
                            err_summary += """
\n[CRITICAL FIX GUIDE]
You defined logic/conditions but they are disconnected from the final triggers.
To fix "Logic Dead End":
1. Ensure every condition variable is used in a `signal.buy()` or `signal.sell()` call.
2. Use Python `if` blocks correctly for logic flow.

EXAMPLE FIX:
   # ❌ WRONG (Dead End):
   c1 = logic.condition(...) 
   # c1 is never used!

   # ✅ RIGHT:
   if c1:
       signal.buy()
   
   # OR:
   signal.buy(condition=c1)
"""
                        thought_process.append(f"DAG Validation Failed: {validation.summary}")
                        if attempt < max_attempts - 1:
                            feedback = f"Your generated graph is INVALID:\n{err_summary}\nPlease fix the issues and regenerate."
                            current_messages.append({"role": "user", "content": feedback})
                            if ctx.on_status_update:
                                ctx.on_status_update(f"❌ Validation failed: {validation.summary[:50]}... Retrying.")
                            continue  # Retry
                        else:
                            return {
                                "final_answer": f"Failed to generate valid graph: {validation.summary}",
                                "dag": None,
                                "iterations": iterations,
                                "thought_process": thought_process,
                                "success": False
                            }
                    
                    # SUCCESS - Both parsing and validation passed!
                    thought_process.append("DAG Parsing and Validation Successful.")
                    if ctx.on_status_update:
                        ctx.on_status_update("✅ Graph generated successfully!")
                    
                    # Store interaction in Long-term Memory
                    mem_add_ctx = Context(
                        run_id=ctx.run_id, workflow_id=ctx.workflow_id, node_id=f"{ctx.node_id}_mem_add",
                        inputs={
                            "session_id": params.session_id,
                            "action": "add",
                            "message": {"role": "user", "content": params.query}
                        }
                    )
                    memory.run(mem_add_ctx)
                    mem_add_ctx.inputs["message"] = {"role": "assistant", "content": response_text}
                    memory.run(mem_add_ctx)

                    return {
                        "final_answer": response_text,
                        "dag": dag_res["dag"],
                        "nodes": dag_res.get("nodes"),
                        "edges": dag_res.get("edges"),
                        "iterations": iterations,
                        "thought_process": thought_process,
                        "success": True
                    }
                else:
                    # FAILURE: Feedback Loop
                    error_detail = dag_res.get("error", "Unknown DAG parsing error")
                    feedback_msg = f"System Error: Failed to convert to DAG. Error: {error_detail}. Please fix code."
                    thought_process.append(f"DAG Fail: {error_detail}")
                    
                    if attempt < max_attempts - 1:
                        # Construct feedback prompt
                        feedback = f"Your previous code generation failed with the following error:\n{error_detail}\n\nPlease regenerate the complete code fixing this error."
                        current_messages.append({"role": "user", "content": feedback})
                        thought_process.append("Triggering Retry with Error Feedback...")
                        if ctx.on_status_update:
                            ctx.on_status_update(f"❌ Build failed: {error_detail[:50]}... Retrying.")
                    else:
                        thought_process.append("Max retries reached. Giving up.")

            # End of Loop (Failure)
            return {
                "final_answer": "Failed to generate valid DAG after multiple attempts.",
                "dag": None,
                "iterations": iterations,
                "thought_process": thought_process,
                "success": False
            }

        except Exception as e:
            return {
                "final_answer": f"System Error: {str(e)}",
                "dag": None,
                "iterations": iterations,
                "thought_process": thought_process + [f"Critical Error: {str(e)}"],
                "success": False
            }
