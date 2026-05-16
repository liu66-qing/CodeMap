from fastapi import APIRouter

from evograph.api.v1 import documents, query, graph, conflicts, timeline, admin

api_router = APIRouter()

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
v1_router.include_router(query.router, prefix="/query", tags=["query"])
v1_router.include_router(graph.router, prefix="/graph", tags=["graph"])
v1_router.include_router(conflicts.router, prefix="/conflicts", tags=["conflicts"])
v1_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
v1_router.include_router(admin.router, prefix="/admin", tags=["admin"])

api_router.include_router(v1_router)
