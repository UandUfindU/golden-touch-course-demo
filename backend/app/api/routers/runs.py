from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.workflow import Workflow
from app.models.run import WorkflowRun
from app.engine.worker import execute_workflow

router = APIRouter(prefix="/runs", tags=["runs"])

@router.post("/workflow/{workflow_id}", response_model=WorkflowRun)
async def trigger_run(workflow_id: UUID, session: AsyncSession = Depends(get_session)):
    """
    Trigger a new run for a workflow.
    Creates a Run record and dispatches a Celery task.
    """
    # 1. Verify Workflow exists
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
        
    # 2. Create Run Record
    run = WorkflowRun(workflow_id=workflow_id)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    
    # 3. Dispatch Celery Task
    # Note: run.id is UUID, celery expects serializable args (str)
    task = execute_workflow.delay(str(run.id))
    
    return run

@router.get("/{run_id}", response_model=WorkflowRun)
async def get_run_status(run_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get the status of a specific run"""
    run = await session.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
