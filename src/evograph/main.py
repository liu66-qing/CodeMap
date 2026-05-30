from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from evograph.config import settings
from evograph.api.router import api_router
from evograph.api.websocket import router as ws_router
from evograph.graph.neo4j_client import neo4j_client
from evograph.storage.redis_cache import redis_client
from evograph.observability.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    # Connect services with graceful degradation
    try:
        await neo4j_client.connect()
    except Exception as e:
        logger.warning("neo4j_connect_failed", error=str(e))
    try:
        await redis_client.connect()
    except Exception as e:
        logger.warning("redis_connect_failed", error=str(e))
    yield
    try:
        await neo4j_client.close()
    except Exception:
        pass
    try:
        await redis_client.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="GitGraph - 基于 Agentic RAG 的代码演化分析引擎（git 历史驱动的破坏性变更检测）",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Allow all origins in production for demo purposes
    origins = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    # Allow any Vercel deployment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()
