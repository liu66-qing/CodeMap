"""Graph merger: merges extracted entities and relations into Neo4j with temporal versioning."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog

from evograph.models.domain import (
    ExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
    GraphRelation,
    EntityType,
)
from evograph.graph.neo4j_client import neo4j_client
from evograph.evolution.conflict_detector import conflict_detector

logger = structlog.get_logger()


class GraphMerger:
    async def merge_extraction(
        self,
        extraction: ExtractionResult,
        entity_mapping: dict[str, str],
    ) -> dict[str, int]:
        stats = {
            "entities_created": 0,
            "entities_updated": 0,
            "relations_created": 0,
            "conflicts_detected": 0,
        }

        entity_id_map: dict[str, str] = {}

        for entity in extraction.entities:
            canonical = entity_mapping.get(entity.name, entity.name)
            entity_id = await self._upsert_entity(entity, canonical, extraction.document_id)
            entity_id_map[entity.name] = entity_id
            if canonical == entity.name:
                stats["entities_created"] += 1
            else:
                stats["entities_updated"] += 1

        for relation in extraction.relations:
            source_id = entity_id_map.get(relation.source_entity)
            target_id = entity_id_map.get(relation.target_entity)
            if not source_id or not target_id:
                continue

            graph_rel = GraphRelation(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation.relation_type,
                valid_from=_parse_date(relation.temporal_start),
                valid_to=_parse_date(relation.temporal_end),
                confidence=relation.confidence,
                source_ids=[extraction.document_id],
            )

            conflicts = await conflict_detector.detect_conflicts(graph_rel)
            if conflicts:
                stats["conflicts_detected"] += len(conflicts)
                for conflict in conflicts:
                    await self._store_conflict(conflict)

            await self._create_relation(graph_rel)
            stats["relations_created"] += 1

        await self._link_provenance(extraction)

        logger.info("merge_complete", stats=stats, document_id=extraction.document_id)
        return stats

    async def _upsert_entity(
        self, entity: ExtractedEntity, canonical_name: str, document_id: str
    ) -> str:
        existing = await neo4j_client.execute_query(
            """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
            RETURN e.id AS id
            LIMIT 1
            """,
            {"name": canonical_name},
        )

        if existing:
            entity_id = existing[0]["id"]
            await neo4j_client.execute_write(
                """
                MATCH (e:Entity {id: $id})
                SET e.last_updated = datetime(),
                    e.aliases = CASE
                        WHEN $aliases IS NOT NULL
                        THEN [x IN (coalesce(e.aliases, []) + $aliases) | x]
                        ELSE e.aliases
                    END
                """,
                {"id": entity_id, "aliases": entity.aliases},
            )
            return entity_id

        entity_id = str(uuid.uuid4())
        await neo4j_client.execute_write(
            """
            CREATE (e:Entity {
                id: $id,
                name: $name,
                type: $type,
                aliases: $aliases,
                description: $description,
                first_seen: datetime(),
                last_updated: datetime()
            })
            """,
            {
                "id": entity_id,
                "name": canonical_name,
                "type": entity.type.value,
                "aliases": entity.aliases,
                "description": entity.description,
            },
        )
        return entity_id

    async def _create_relation(self, rel: GraphRelation) -> None:
        await neo4j_client.execute_write(
            """
            MATCH (source:Entity {id: $source_id})
            MATCH (target:Entity {id: $target_id})
            CREATE (source)-[r:RELATION {
                id: $rel_id,
                type: $rel_type,
                valid_from: $valid_from,
                valid_to: $valid_to,
                observed_at: datetime(),
                confidence: $confidence,
                source_ids: $source_ids,
                is_active: true
            }]->(target)
            """,
            {
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "rel_id": rel.id,
                "rel_type": rel.relation_type,
                "valid_from": rel.valid_from.isoformat() if rel.valid_from else None,
                "valid_to": rel.valid_to.isoformat() if rel.valid_to else None,
                "confidence": rel.confidence,
                "source_ids": rel.source_ids,
            },
        )

    async def _store_conflict(self, conflict) -> None:
        await neo4j_client.execute_write(
            """
            CREATE (c:Conflict {
                id: $id,
                type: $type,
                status: $status,
                description: $description,
                detected_at: datetime()
            })
            """,
            {
                "id": conflict.id,
                "type": conflict.type.value,
                "status": conflict.status.value,
                "description": conflict.description,
            },
        )

    async def _link_provenance(self, extraction: ExtractionResult) -> None:
        await neo4j_client.execute_write(
            """
            MERGE (d:Document {id: $doc_id})
            MERGE (c:Chunk {id: $chunk_id})
            MERGE (c)-[:BELONGS_TO]->(d)
            """,
            {"doc_id": extraction.document_id, "chunk_id": extraction.chunk_id},
        )


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


graph_merger = GraphMerger()
