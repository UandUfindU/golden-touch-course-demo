from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import copy

from app.nodes.base import BaseNode, Context
from app.nodes.registry import register_node, NodeRegistry
from app.core.enums import NodeCategory, NodeScope, NodeRole
from app.nodes.impl.structure.composite_node import CompositeNode

class RetryInput(BaseModel):
    graph: Dict[str, Any] = Field(description="The subgraph to execute in a loop")
    max_retries: int = Field(default=3, description="Maximum number of attempts")
    break_condition: str = Field(default="success", description="Output field to check for True to break loop")
    feedback_key: Optional[str] = Field(default=None, description="Optional: Output field containing error/feedback to feed into next run")
    history_input_key: Optional[str] = Field(default=None, description="Optional: Input field (List) to append feedback to")
    
    model_config = {"extra": "allow"} # Allow dynamic inputs for the subgraph

class RetryOutput(BaseModel):
    final_output: Dict[str, Any] = Field(description="Output of the last execution")
    success: bool = Field(description="Whether the break condition was met")
    attempts: int = Field(description="Number of attempts used")
    history: List[Any] = Field(default_factory=list, description="Execution history/trace")
    
    model_config = {"extra": "allow"}

@register_node(
    category=NodeCategory.FLOW,
    name="flow.retry",
    scopes=[NodeScope.TOOL, NodeScope.WORKFLOW, NodeScope.STRATEGY],
    role=NodeRole.MIDDLE
)
class RetryNode(BaseNode):
    """
    Retry Loop Node (Flow Control).
    
    Executes a subgraph repeatedly until break_condition is met or max_retries reached.
    accepts dynamic inputs which are passed to the subgraph.
    """
    description = "执行子图直到满足条件或达到最大重试次数"
    InputSchema = RetryInput
    OutputSchema = RetryOutput
    
    def run(self, ctx: Context) -> Dict[str, Any]:
        # Allow extra fields for subgraph inputs
        params = self.validate_inputs(ctx.inputs)
        
        # Extract inputs for the subgraph: everything in ctx.inputs that is NOT a control param
        # Or better: everything in params (since extra='allow') that is not a control param
        control_params = {"graph", "max_retries", "break_condition", "feedback_key", "history_input_key"}
        subgraph_inputs = {
            k: v for k, v in params.model_dump().items() 
            if k not in control_params
        }
        
        # Instantiate the composite node once (validates the graph)
        try:
            subgraph_node = CompositeNode(graph_definition=params.graph)
        except Exception as e:
            raise ValueError(f"Invalid Retry Subgraph: {str(e)}")
            
        current_inputs = copy.deepcopy(subgraph_inputs)
        last_output = {}
        history = []
        success = False
        
        ctx.emit_status(f"🔄 Starting Retry Loop (Max: {params.max_retries})")
        
        for attempt in range(1, params.max_retries + 1):
            ctx.emit_status(f"🔄 Attempt {attempt}/{params.max_retries} executing...")
            
            # Run Subgraph
            sub_ctx = Context(
                run_id=ctx.run_id,
                workflow_id=ctx.workflow_id,
                node_id=f"{ctx.node_id}_try_{attempt}",
                inputs=current_inputs,
                on_status_update=ctx.on_status_update
            )
            
            try:
                # Execute
                output = subgraph_node.run(sub_ctx)
                last_output = output
                history.append({
                    "attempt": attempt, 
                    "status": "success", 
                    "output": str(output)[:200]
                })
                
                # Check Break Condition
                # Default: check if output['success'] is True
                condition_val = output.get(params.break_condition)
                if condition_val:
                    ctx.emit_status(f"✅ Success on attempt {attempt}")
                    success = True
                    break
                
                # If Failed and not last attempt, handle Feedback
                if attempt < params.max_retries:
                    ctx.emit_status(f"⚠️ Attempt {attempt} failed condition '{params.break_condition}'. Retrying...")
                    
                    if params.feedback_key and params.history_input_key:
                        feedback_val = output.get(params.feedback_key)
                        history_list = current_inputs.get(params.history_input_key)
                        
                        if feedback_val is not None:
                            # Enhanced logging for CLI visibility
                            # Note: In production this should be a proper log, but for CLI debugging print is visible
                            print(f"\n[Retry Feedback/Error]: {str(feedback_val)[:500]}\n")
                            ctx.emit_status(f"  > Feedback: {str(feedback_val)[:100]}...")

                        if feedback_val is not None and isinstance(history_list, list):
                            if isinstance(feedback_val, list):
                                history_list.extend(feedback_val)
                            else:
                                history_list.append(feedback_val)
                            current_inputs[params.history_input_key] = history_list
                        else:
                            # Log warning if types mismatch
                            pass
                            
            except Exception as e:
                history.append({"attempt": attempt, "status": "error", "error": str(e)})
                ctx.emit_status(f"❌ Error in attempt {attempt}: {str(e)}")
                # If exception, do we retry? 
                # Usually exception means system crash, but maybe transient.
                # Let's count it as a failure.
                if attempt == params.max_retries:
                    raise e
        
        # Merge last_output to top level so mapping works
        return {
            **last_output,
            "final_output": last_output,
            "success": success,
            "attempts": attempt,
            "history": history
        }
