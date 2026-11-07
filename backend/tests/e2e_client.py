
import os
import sys
import uuid
import json
import asyncio
from dotenv import load_dotenv

# Add backend to sys.path
# Since this file is in backend/tests, we need to go up two levels to find 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir)) # backend/
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from app.nodes.base import Context
from app.core.session_manager import session_manager
from app.nodes.impl.agent.main_router import MainRouterNode

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

async def main():
    # Load .env from backend root
    load_dotenv(os.path.join(backend_dir, ".env"))
    
    print(f"{CYAN}================================================={RESET}")
    print(f"{CYAN}       Golden Touch - E2E Interactive Client     {RESET}")
    print(f"{CYAN}================================================={RESET}")
    print("Simulates the Frontend <-> Main Agent interaction.")
    print("Commands:")
    print(f"  {YELLOW}/offline{RESET} : Switch to Strategy Layer")
    print(f"  {YELLOW}/online{RESET}  : Switch to Workflow Layer")
    print(f"  {YELLOW}/ctx{RESET}     : View current Client Context")
    print(f"  {YELLOW}/quit{RESET}    : Exit")
    print("-------------------------------------------------")

    session_id = f"cli_{uuid.uuid4().hex[:6]}"
    await session_manager.save_session(session_id)
    
    # Client State
    current_layer = "offline"
    current_mode = "auto"
    client_ctx = {
        "node_count": 0,
        "available_strategies": []
    }
    
    router = MainRouterNode()
    
    print(f"Session ID: {session_id}")
    print(f"Current Layer: {GREEN}{current_layer.upper()}{RESET}")
    print(f"Current Mode : {YELLOW}{current_mode.upper()}{RESET}")
    
    while True:
        try:
            # Show prompt with state
            mode_display = f"[{current_mode[0].upper()}]" 
            user_input = input(f"\n{mode_display}[{current_layer}] You > ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["/quit", "/exit", "q"]:
                break
            
            # --- Slash Commands ---
            if user_input.lower().startswith("/mode"):
                parts = user_input.split()
                if len(parts) > 1:
                    new_mode = parts[1].lower()
                    if new_mode in ["auto", "fast", "think"]:
                        current_mode = new_mode
                        print(f"Switched Mode to: {YELLOW}{current_mode.upper()}{RESET}")
                    else:
                        print(f"{RED}Invalid mode. Options: auto, fast, think{RESET}")
                else:
                     print(f"Current Mode: {current_mode}")
                continue

            if user_input.lower() == "/offline":
                current_layer = "offline"
                print(f"Switched to: {GREEN}OFFLINE (Strategy Lab){RESET}")
                continue
            
            if user_input.lower() == "/online":
                current_layer = "online"
                print(f"Switched to: {GREEN}ONLINE (Workflow Editor){RESET}")
                continue
                
            if user_input.lower() == "/ctx":
                print(f"{YELLOW}Client Context:{RESET}")
                print(json.dumps(client_ctx, indent=2, ensure_ascii=False))
                continue
            
            # --- Mock Logic: Simulating "Hot Save" ---
            # If user previously built a strategy, logic (in a real app) would update client_ctx.
            # Here we hack it: if input contains "saved", we inject a mock strategy.
            if "mock_save" in user_input:
                print(f"{YELLOW}[System] Simulating Strategy Save...{RESET}")
                client_ctx["available_strategies"].append({
                    "id": f"strat_{len(client_ctx['available_strategies'])+1}",
                    "name": "My New Strategy"
                })
                print(f"{GREEN}Strategy added to Registry!{RESET}")
                continue

            # --- Fetch Chat History (Async) ---
            # Retrieve recent history from DB to provide memory
            raw_history = await session_manager.get_chat_history(session_id, limit=20)
            # Format for LLM: [{"role": "user", "content": "..."}, ...]
            formatted_history = []
            for msg in raw_history:
                # Map 'assistant'/'user' roles. Ignore 'system' from DB if any?
                # Actually, our DB ChatMessage has 'role' field.
                formatted_history.append({"role": msg.role, "content": msg.content})
            
            # --- Send to Router ---
            inputs = {
                "message": user_input,
                "session_id": session_id,
                "layer": current_layer,
                "mode": current_mode, # Dynamic
                "client_context": client_ctx,
                "history": formatted_history # Injection!
            }
            
            print(f"{CYAN}[MainAgent] Thinking...{RESET}", end="\r")
            
            # API Layer typically persists USER message first.
            await session_manager.add_chat_message(session_id, "user", user_input)
            
            result = router.run(Context(
                run_id="cli_run", workflow_id="cli_wf", node_id="router",
                inputs=inputs
            ))
            
            # output
            response = result.get("response", "")
            source = result.get("source", "unknown")
            
            # Persist ASSISTANT message
            await session_manager.add_chat_message(session_id, "assistant", response, source=source)
            
            color = GREEN if source == "main_agent" else YELLOW
            print(f"{color}[{source}]{RESET} {response}")
            
            # --- Tool Execution Logic ---
            if source.startswith("tool:"):
                tool_name = source.split(":")[1]
                
                # Fetch optimized instruction from Main Router
                tool_args = result.get("tool_args", {})
                instruction = "Generate default strategy" # fallback
                
                if tool_args and "instruction" in tool_args:
                    instruction = tool_args["instruction"]
                    print(f"{CYAN}>>> [MainAgent] 🧬 Optimized Prompt: \"{instruction}\"{RESET}")
                else:
                    print(f"{YELLOW}>>> [Warning] Using raw input (no optimization).{RESET}")
                    instruction = user_input
                
                # --- CRITICAL: Context Injection ---
                # The User (Client) confirmed that the Main Agent only gives the PROMPT.
                # The SYSTEM (this loop) must inject the current graph.
                
                if tool_name.startswith("build_"):
                    # --- Build Tools ---
                    print(f"{CYAN}>>> [System] 💉 Injecting Context: Fetching '{tool_name}' graph snapshot...{RESET}")
                    
                    # Mode Logic (Fast vs Think)
                    actual_graph_tool = tool_name
                    if current_mode == "think" and tool_name == "build_strategy":
                        actual_graph_tool = "analyze_strategy"
                        print(f"{MAGENTA}>>> [System] 🧠 THINK MODE ACTIVATE: Switching to '{actual_graph_tool}' chain.{RESET}")
                    
                    print(f"{CYAN}>>> [System] 🚀 Executing Tool: {actual_graph_tool}{RESET}")
                    
                    from app.nodes.impl.tool.llm.agent_executor_node import AgentExecutorNode
                    executor = AgentExecutorNode()
                    tool_inputs = {
                        "query": instruction,
                        "session_id": session_id,
                        "scope": "strategy" if tool_name == "build_strategy" else "workflow",
                        "max_retries": 3,
                        "mode": current_mode
                    }
                    
                    tool_ctx = Context(run_id=f"tool_{uuid.uuid4().hex[:6]}", workflow_id=f"wf_{tool_name}", node_id="executor", inputs=tool_inputs)
                    
                    try:
                        tool_res = executor.run(tool_ctx)
                        if tool_res.get("success"):
                            dag = tool_res.get("dag", {})
                            node_count = len(dag.get("nodes", []))
                            print(f"{GREEN}>>> ✅ Graph Generated! ({node_count} nodes){RESET}")
                            print(f"{YELLOW}>>> [AI] {tool_res.get('final_answer')}{RESET}")
                            
                            client_ctx["node_count"] = node_count
                            # Capture Last Graph State for Save Tool
                            client_ctx["last_graph_dag"] = dag 
                            
                            # Extract Code
                            final_ans = tool_res.get('final_answer', '')
                            import re
                            code_match = re.search(r"```python\s*(.*?)\s*```", final_ans, re.DOTALL)
                            if code_match:
                                client_ctx["current_graph_code"] = code_match.group(1).strip()
                            else:
                                client_ctx["current_graph_code"] = "# Code not parsed"
                                
                            print(f"{CYAN}>>> [Frontend] Canvas Updated.{RESET}")
                        else:
                            print(f"{RED}>>> ❌ Tool Execution Failed: {tool_res.get('final_answer')}{RESET}")
                    except Exception as e:
                         print(f"{RED}>>> Tool Error: {e}{RESET}")

                elif tool_name == "save_strategy":
                    # --- Save Tool ---
                    from app.nodes.impl.tool.storage.save_strategy_node import SaveStrategyNode
                    
                    print(f"{CYAN}>>> [System] 💾 Invoking Save Strategy...{RESET}")
                    
                    # Prepare Data
                    strat_name = tool_args.get("name", "Untitled Strategy")
                    graph_data = client_ctx.get("last_graph_dag", {})
                    code = client_ctx.get("current_graph_code", "")
                    
                    if not graph_data:
                        print(f"{RED}>>> [Error] No strategy to save! Build one first.{RESET}")
                    else:
                        print(f"    - Name: {strat_name}")
                        print(f"    - Nodes: {len(graph_data.get('nodes',[]))}")
                        
                        saver = SaveStrategyNode()
                        save_ctx = Context(
                            run_id=f"save_{uuid.uuid4().hex[:6]}", workflow_id="save_op", node_id="saver",
                            inputs={
                                "name": strat_name,
                                "graph_data": graph_data,
                                "code": code
                            }
                        )
                        save_res = saver.run(save_ctx)
                        if save_res.get("success"):
                            print(f"{GREEN}>>> ✅ Strategy Saved! ID: {save_res.get('strategy_id')}{RESET}")
                            print(f"    - Path: storage/strategies/{save_res.get('strategy_id')}.json")
                            # Add to registry mock
                            client_ctx["available_strategies"].append({"id": save_res.get("strategy_id"), "name": strat_name})
                        else:
                            print(f"{RED}>>> Save Failed: {save_res.get('message')}{RESET}")

                elif tool_name == "run_backtest":
                    # --- Backtest Tool ---
                    print(f"{CYAN}>>> [System] 📈 Invoking Backtest Runner...{RESET}")
                    
                    # 1. Prepare Data (Mocking Market Data for now)
                    # In real app, this comes from DataFeeder
                    mock_data = [
                        {"timestamp": i, "open": 100+i, "high": 105+i, "low": 95+i, "close": 102+i, "volume": 1000} 
                        for i in range(100)
                    ]
                    
                    graph_data = client_ctx.get("last_graph_dag", {})
                    if not graph_data:
                         print(f"{RED}>>> [Error] No graph loaded in context.{RESET}")
                    else:
                        print(f"{CYAN}>>> [System] 🔍 Validating Strategy Graph...{RESET}")
                        
                        # 2. VALIDATION STEP
                        # We use the backend's validator if possible, or simulate it.
                        # Trying to import the real validator
                        try:
                            from app.nodes.impl.engine.graph_validator import validate_graph
                            validation = validate_graph(graph_data)
                            
                            if not validation.valid:
                                print(f"{RED}>>> ❌ Validation Failed: {validation.summary}{RESET}")
                            else:
                                print(f"{GREEN}>>> ✅ Graph Validated. Structure OK.{RESET}")
                                
                                # 3. EXECUTION STEP
                                print(f"{CYAN}>>> [System] 🚀 Running BacktestRunnerNode...{RESET}")
                                
                                # Instantiate Runner
                                from app.nodes.impl.backtest.runner import BacktestRunnerNode
                                runner = BacktestRunnerNode()
                                
                                runner_ctx = Context(
                                    run_id=f"bt_{uuid.uuid4().hex[:6]}", workflow_id="bt_op", node_id="runner",
                                    inputs={
                                        "data": mock_data,
                                        "strategy_dag": graph_data,
                                        "config": {"initial_capital": 10000.0}
                                    }
                                )
                                
                                # Run (This will actually execute the logic inside Runner!)
                                # Note: Since we are mocking data, signals might be empty or dummy, 
                                # but it proves the parsing works.
                                try:
                                    bt_res = runner.run(runner_ctx)
                                    metrics = bt_res.get("metrics", {})
                                    equity = bt_res.get("equity_curve", [])
                                    
                                    final_eq = equity[-1]['equity'] if equity else 0
                                    
                                    print(f"{GREEN}>>> ✅ Backtest Completed!{RESET}")
                                    print(f"    - Final Equity: ${final_eq:.2f}")
                                    print(f"    - Total Trades: {metrics.get('total_trades', 0)}")
                                    print(f"    - Sharpe Ratio: {metrics.get('sharpe_ratio', 0.0):.2f}")
                                    
                                except Exception as e:
                                     print(f"{RED}>>> Runner Execution Failed: {e}{RESET}")
                                     import traceback
                                     traceback.print_exc()

                        except ImportError:
                            print(f"{YELLOW}>>> [System] Validator/Runner not fully importable in this CLI env. Simulating success.{RESET}")
                            print(f"{GREEN}>>> ✅ Backtest Completed! (Simulated){RESET}")

                if current_layer == "online" and source == "tool:build_workflow":
                    print(f"{CYAN}>>> Checking for Backtest Conflicts... ✅ Passed (Simulation){RESET}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
