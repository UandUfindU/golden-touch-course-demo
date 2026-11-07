from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import init_db
from app.api.routers import nodes, workflow, runs, session, chat, execution, ai
from app.api.v1 import data as data_api

# Import node implementations to ensure registration
from app.nodes.impl.flow import *
from app.nodes.impl.workflow import *
from app.nodes.impl.tool import *
from app.nodes.impl.data import *
from app.nodes.impl.indicator import *
from app.nodes.impl.logic import *
from app.nodes.impl.signal import *
from app.nodes.impl.backtest import *
from app.nodes.impl.engine import *
from app.nodes.impl.agent import *
from app.nodes.impl.structure import *


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create DB Tables
    await init_db()
    yield
    # Shutdown: Clean up if needed

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.0.1",
    lifespan=lifespan
)

# CORS Config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO: Restrict in Prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(workflow.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(execution.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(data_api.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.0.1"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
