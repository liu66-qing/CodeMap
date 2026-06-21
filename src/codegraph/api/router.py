from fastapi import APIRouter, Depends

from codegraph.api.v1 import (
    analysis,
    query,
    graph,
    timeline,
    admin,
    agent_stats,
    learning,
    repositories,
)
from codegraph.api.security import require_admin_api_key

api_router = APIRouter()

v1_router = APIRouter(prefix="/v1")

# === Core Product: Multi-Agent Analysis ===
v1_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
v1_router.include_router(query.router, prefix="/query", tags=["query"])

# === Code Intelligence (repo ingestion + graph) ===
v1_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
v1_router.include_router(graph.router, prefix="/graph", tags=["graph"])
v1_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])

# === Engagement ===
v1_router.include_router(learning.router, prefix="/learning", tags=["learning"])

# === Internal / Ops ===
v1_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)
v1_router.include_router(agent_stats.router)

api_router.include_router(v1_router)
