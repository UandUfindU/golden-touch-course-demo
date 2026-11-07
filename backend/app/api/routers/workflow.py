from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.workflow import Workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])

@router.post("/", response_model=Workflow)
async def create_workflow(workflow: Workflow, session: AsyncSession = Depends(get_session)):
    """Create a new workflow"""
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return workflow

@router.get("/", response_model=List[Workflow])
async def list_workflows(session: AsyncSession = Depends(get_session)):
    """List all workflows"""
    result = await session.exec(select(Workflow))
    return result.all()

@router.get("/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get a specific workflow"""
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.put("/{workflow_id}", response_model=Workflow)
async def update_workflow(workflow_id: UUID, workflow_update: Workflow, session: AsyncSession = Depends(get_session)):
    """Update a workflow"""
    db_workflow = await session.get(Workflow, workflow_id)
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow_data = workflow_update.model_dump(exclude_unset=True)
    for key, value in workflow_data.items():
        setattr(db_workflow, key, value)
        
    session.add(db_workflow)
    await session.commit()
    await session.refresh(db_workflow)
    return db_workflow

@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: UUID, session: AsyncSession = Depends(get_session)):
    """Delete a workflow"""
    workflow = await session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    await session.delete(workflow)
    await session.commit()
    return {"ok": True}
