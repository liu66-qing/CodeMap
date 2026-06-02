"""Knowledge graph exploration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
import structlog

from evograph.models.api_schemas import EntityResponse, SubgraphResponse
from evograph.models.domain import EntityType
from evograph.graph import traversal

logger = structlog.get_logger()
router = APIRouter()


@router.get("/entities")
async def search_entities(
    q: str = Query("", description="Search query"),
    entity_type: EntityType | None = None,
    repo_id: str | None = Query(None, description="Scope search to one repo's code symbols"),
    skip: int = 0,
    limit: int = 20,
) -> list[dict]:
    if repo_id:
        # Code-symbol search within a repo: match qualified name OR simple name.
        from evograph.graph.neo4j_client import neo4j_client
        try:
            return await neo4j_client.execute_query(
                """
                MATCH (e:Entity {repo_id: $repo_id})
                WHERE $q = '' OR toLower(e.name) CONTAINS toLower($q)
                RETURN e.id AS id, e.name AS name, e.code_kind AS kind,
                       e.signature AS signature, e.file_path AS file_path
                ORDER BY size(e.name) ASC
                SKIP $skip LIMIT $limit
                """,
                {"repo_id": repo_id, "q": q, "skip": skip, "limit": limit},
            )
        except Exception:
            return []
    if q:
        results = await traversal.get_entity_by_name(q)
        return results
    return []


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str) -> dict:
    entity = await traversal.get_entity_by_id(entity_id)
    if not entity:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/neighborhood")
async def get_entity_neighborhood(
    entity_id: str,
    hops: int = Query(2, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
) -> SubgraphResponse:
    result = await traversal.get_neighborhood(entity_id, hops=hops, limit=limit)
    return SubgraphResponse(
        entities=result["entities"],
        relations=result["relations"],
        total_entities=len(result["entities"]),
        total_relations=len(result["relations"]),
    )


@router.get("/entities/{entity_id}/timeline")
async def get_entity_timeline(entity_id: str) -> dict:
    relations = await traversal.get_temporal_relations(entity_id)
    return {"entity_id": entity_id, "temporal_relations": relations}


@router.get("/stats")
async def get_graph_stats() -> dict:
    return await traversal.get_graph_stats()


@router.get("/path")
async def find_path(
    source_id: str = Query(...),
    target_id: str = Query(...),
    max_hops: int = Query(5, ge=1, le=10),
) -> dict:
    paths = await traversal.find_path(source_id, target_id, max_hops)
    return {"paths": paths}
