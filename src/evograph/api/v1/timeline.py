"""Timeline and temporal query endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
import structlog

from evograph.graph.neo4j_client import neo4j_client
from evograph.graph import traversal

logger = structlog.get_logger()
router = APIRouter()


@router.get("/entity/{entity_id}")
async def get_entity_timeline(entity_id: str) -> dict:
    results = await neo4j_client.execute_query(
        """
        MATCH (e:Entity {id: $id})-[r]-(other:Entity)
        WHERE r.valid_from IS NOT NULL
        RETURN type(r) AS rel_type, r.valid_from AS start, r.valid_to AS end,
               other.name AS other_name, other.id AS other_id,
               r.confidence AS confidence
        ORDER BY r.valid_from ASC
        """,
        {"id": entity_id},
    )
    return {"entity_id": entity_id, "timeline": results}


@router.get("/snapshot")
async def get_graph_snapshot(
    timestamp: str = Query(..., description="ISO 8601 timestamp"),
    entity_types: list[str] | None = Query(None),
) -> dict:
    type_filter = ""
    params: dict = {"ts": timestamp}
    if entity_types:
        type_filter = "AND e.type IN $types"
        params["types"] = entity_types

    results = await neo4j_client.execute_query(
        f"""
        MATCH (e:Entity)-[r]->(target:Entity)
        WHERE (r.valid_from IS NULL OR r.valid_from <= datetime($ts))
          AND (r.valid_to IS NULL OR r.valid_to >= datetime($ts))
          AND r.is_active = true
          {type_filter}
        RETURN e, r, target
        LIMIT 200
        """,
        params,
    )
    return {"timestamp": timestamp, "snapshot": results}


@router.get("/diff")
async def get_timeline_diff(
    from_ts: str = Query(..., description="Start timestamp (ISO 8601)"),
    to_ts: str = Query(..., description="End timestamp (ISO 8601)"),
) -> dict:
    added = await neo4j_client.execute_query(
        """
        MATCH (e:Entity)-[r]->(target:Entity)
        WHERE r.valid_from >= datetime($from_ts)
          AND r.valid_from <= datetime($to_ts)
        RETURN e.name AS source, type(r) AS relation, target.name AS target,
               r.valid_from AS added_at
        ORDER BY r.valid_from ASC
        """,
        {"from_ts": from_ts, "to_ts": to_ts},
    )

    expired = await neo4j_client.execute_query(
        """
        MATCH (e:Entity)-[r]->(target:Entity)
        WHERE r.valid_to >= datetime($from_ts)
          AND r.valid_to <= datetime($to_ts)
        RETURN e.name AS source, type(r) AS relation, target.name AS target,
               r.valid_to AS expired_at
        ORDER BY r.valid_to ASC
        """,
        {"from_ts": from_ts, "to_ts": to_ts},
    )

    return {"from": from_ts, "to": to_ts, "added": added, "expired": expired}
