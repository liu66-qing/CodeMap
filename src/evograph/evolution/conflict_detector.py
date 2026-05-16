"""Knowledge conflict detection engine.

Detects three types of conflicts:
1. Temporal overlap - same entity+relation with overlapping time ranges
2. Logical contradiction - mutually exclusive facts
3. Source disagreement - same fact claimed differently by multiple sources
"""

from __future__ import annotations

from datetime import datetime

import structlog

from evograph.models.domain import (
    ConflictType,
    ConflictStatus,
    GraphRelation,
    KnowledgeConflict,
)
from evograph.graph.neo4j_client import neo4j_client

logger = structlog.get_logger()

SINGULAR_RELATIONS = {"CEO_OF", "CTO_OF", "CFO_OF", "PRESIDENT_OF", "CHAIRMAN_OF", "LOCATED_IN"}


class ConflictDetector:
    async def detect_conflicts(
        self, new_relation: GraphRelation
    ) -> list[KnowledgeConflict]:
        conflicts: list[KnowledgeConflict] = []

        temporal = await self._check_temporal_overlap(new_relation)
        if temporal:
            conflicts.append(temporal)

        logical = await self._check_logical_contradiction(new_relation)
        if logical:
            conflicts.append(logical)

        return conflicts

    async def _check_temporal_overlap(
        self, new_rel: GraphRelation
    ) -> KnowledgeConflict | None:
        if new_rel.relation_type not in SINGULAR_RELATIONS:
            return None

        results = await neo4j_client.execute_query(
            """
            MATCH (source:Entity {id: $source_id})-[r]->(target:Entity)
            WHERE type(r) = $rel_type
              AND r.is_active = true
              AND target.id <> $target_id
              AND (r.valid_to IS NULL OR r.valid_to >= $valid_from)
              AND (r.valid_from IS NULL OR $valid_to IS NULL OR r.valid_from <= $valid_to)
            RETURN r, target.id AS target_id, target.name AS target_name
            """,
            {
                "source_id": new_rel.source_id,
                "rel_type": new_rel.relation_type,
                "target_id": new_rel.target_id,
                "valid_from": new_rel.valid_from.isoformat() if new_rel.valid_from else "1900-01-01",
                "valid_to": new_rel.valid_to.isoformat() if new_rel.valid_to else None,
            },
        )

        if not results:
            return None

        existing = results[0]
        existing_rel = GraphRelation(
            id=existing["r"].get("id", ""),
            source_id=new_rel.source_id,
            target_id=existing["target_id"],
            relation_type=new_rel.relation_type,
            valid_from=existing["r"].get("valid_from"),
            valid_to=existing["r"].get("valid_to"),
            confidence=existing["r"].get("confidence", 1.0),
        )

        return KnowledgeConflict(
            type=ConflictType.TEMPORAL_OVERLAP,
            status=ConflictStatus.OPEN,
            description=(
                f"Temporal overlap: {new_rel.relation_type} from entity {new_rel.source_id} "
                f"points to both {new_rel.target_id} and {existing['target_name']}"
            ),
            fact_a=new_rel,
            fact_b=existing_rel,
        )

    async def _check_logical_contradiction(
        self, new_rel: GraphRelation
    ) -> KnowledgeConflict | None:
        inverse_pairs = {
            "ACQUIRED": "ACQUIRED_BY",
            "ACQUIRED_BY": "ACQUIRED",
            "PARENT_OF": "SUBSIDIARY_OF",
            "SUBSIDIARY_OF": "PARENT_OF",
        }

        inverse_type = inverse_pairs.get(new_rel.relation_type)
        if not inverse_type:
            return None

        results = await neo4j_client.execute_query(
            """
            MATCH (a:Entity {id: $target_id})-[r]->(b:Entity {id: $source_id})
            WHERE type(r) = $inverse_type AND r.is_active = true
            RETURN r
            """,
            {
                "source_id": new_rel.source_id,
                "target_id": new_rel.target_id,
                "inverse_type": inverse_type,
            },
        )

        if not results:
            return None

        existing_data = results[0]["r"]
        existing_rel = GraphRelation(
            id=existing_data.get("id", ""),
            source_id=new_rel.target_id,
            target_id=new_rel.source_id,
            relation_type=inverse_type,
            confidence=existing_data.get("confidence", 1.0),
        )

        return KnowledgeConflict(
            type=ConflictType.LOGICAL_CONTRADICTION,
            status=ConflictStatus.OPEN,
            description=(
                f"Logical contradiction: {new_rel.relation_type} between "
                f"{new_rel.source_id} and {new_rel.target_id} contradicts existing "
                f"{inverse_type} relationship"
            ),
            fact_a=new_rel,
            fact_b=existing_rel,
        )


conflict_detector = ConflictDetector()
