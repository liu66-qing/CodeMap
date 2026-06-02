from fastapi import APIRouter

from codegraph.api.v1 import (
    documents,
    query,
    graph,
    conflicts,
    timeline,
    admin,
    repositories,
    analysis,
    learning,
    agent_stats,
)

api_router = APIRouter()

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
v1_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
v1_router.include_router(query.router, prefix="/query", tags=["query"])
v1_router.include_router(graph.router, prefix="/graph", tags=["graph"])
v1_router.include_router(conflicts.router, prefix="/conflicts", tags=["conflicts"])
v1_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
v1_router.include_router(admin.router, prefix="/admin", tags=["admin"])
v1_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
v1_router.include_router(learning.router, prefix="/learning", tags=["learning"])
v1_router.include_router(agent_stats.router)

api_router.include_router(v1_router)
