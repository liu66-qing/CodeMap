from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evograph.config import settings
from evograph.api.router import api_router
from evograph.api.websocket import router as ws_router
from evograph.graph.neo4j_client import neo4j_client
from evograph.storage.redis_cache import redis_client
from evograph.observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    await neo4j_client.connect()
    await redis_client.connect()
    yield
    await neo4j_client.close()
    await redis_client.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Real-time Knowledge Graph Evolution Agent - Agentic RAG",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()
