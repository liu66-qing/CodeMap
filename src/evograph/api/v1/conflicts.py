"""Conflict management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import structlog

from evograph.models.api_schemas import ConflictListResponse, ConflictResolveRequest
from evograph.models.domain import ConflictStatus
from evograph.graph.neo4j_client import neo4j_client

logger = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=ConflictListResponse)
async def list_conflicts(
    status: ConflictStatus | None = None,
    skip: int = 0,
    limit: int = 20,
) -> ConflictListResponse:
    where_clause = ""
    params: dict = {"skip": skip, "limit": limit}
    if status:
        where_clause = "WHERE c.status = $status"
        params["status"] = status.value

    results = await neo4j_client.execute_query(
        f"""
        MATCH (c:Conflict)
        {where_clause}
        RETURN c
        ORDER BY c.detected_at DESC
        SKIP $skip LIMIT $limit
        """,
        params,
    )

    count_result = await neo4j_client.execute_query(
        "MATCH (c:Conflict {status: 'open'}) RETURN count(c) AS cnt"
    )
    open_count = count_result[0]["cnt"] if count_result else 0

    return ConflictListResponse(
        conflicts=[],
        total=len(results),
        open_count=open_count,
    )


@router.get("/{conflict_id}")
async def get_conflict(conflict_id: str) -> dict:
    results = await neo4j_client.execute_query(
        "MATCH (c:Conflict {id: $id}) RETURN c",
        {"id": conflict_id},
    )
    if not results:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return results[0]


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str, request: ConflictResolveRequest
) -> dict[str, str]:
    await neo4j_client.execute_write(
        """
        MATCH (c:Conflict {id: $id})
        SET c.status = 'resolved',
            c.resolved_at = datetime(),
            c.resolution_note = $note
        """,
        {"id": conflict_id, "note": request.note or request.resolution},
    )
    logger.info("conflict_resolved", conflict_id=conflict_id, resolution=request.resolution)
    return {"status": "resolved", "id": conflict_id}
