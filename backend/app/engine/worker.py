import asyncio
from uuid import UUID
from celery import Task
from sqlmodel import Session, select
from redis.asyncio import Redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import engine as db_engine
from app.models.workflow import Workflow
from app.models.run import WorkflowRun
from app.engine.runner import GraphRunner
from app.core.enums import RunStatus

class AsyncTask(Task):
    """Celery Task that runs in an asyncio loop"""
    def __call__(self, *args, **kwargs):
        return asyncio.run(self.run_async(*args, **kwargs))
        
    async def run_async(self, *args, **kwargs):
        raise NotImplementedError

@celery_app.task(bind=True, base=AsyncTask, name="execute_workflow")
async def execute_workflow(self, run_id: str):
    """
    Celery task to execute a workflow run.
    1. Load Run & Workflow from DB
    2. Initialize GraphRunner
    3. Execute
    """
    print(f"Worker: Starting execution for run_id={run_id}")
    
    # We need to construct a new Redis client for the worker process
    # Redis client from main app (if any) shouldn't be shared across processes usually, 
    # but ContextManager takes a redis instance.
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    try:
        # Load Data
        async with Session(db_engine) as session:
            # Note: db_engine is async engine, but Session can be sync? 
            # No, we need AsyncSession for async engine.
            # But standard Session is sync.
            # Let's use AsyncSession.
            from sqlalchemy.ext.asyncio import AsyncSession
            async with AsyncSession(db_engine) as async_session:
                stmt = select(WorkflowRun).where(WorkflowRun.id == UUID(run_id))
                result = await async_session.exec(stmt)
                run = result.first()
                
                if not run:
                    print(f"Run {run_id} not found")
                    return
                
                stmt_wf = select(Workflow).where(Workflow.id == run.workflow_id)
                result_wf = await async_session.exec(stmt_wf)
                workflow = result_wf.first()
                
                if not workflow:
                     print(f"Workflow {run.workflow_id} not found")
                     return
            
                # Update status to RUNNING if not already
                if run.status == RunStatus.PENDING:
                    run.status = RunStatus.RUNNING
                    async_session.add(run)
                    await async_session.commit()

                # Run
                runner = GraphRunner(workflow, run.id, redis_client)
                try:
                    await runner.execute()
                    # On success, update DB? ContextManager updates Redis. 
                    # We might want final sync to DB here.
                    run.status = RunStatus.COMPLETED
                    async_session.add(run)
                    await async_session.commit()
                    
                except Exception as e:
                    print(f"Execution Error: {e}")
                    run.status = RunStatus.FAILED
                    run.error_message = str(e)
                    async_session.add(run)
                    await async_session.commit()
                    # Re-raise to mark celery task as failed
                    raise e
                    
    finally:
        await redis_client.close()
