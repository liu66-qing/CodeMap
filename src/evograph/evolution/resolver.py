"""Entity resolution: deduplication and linking."""

from __future__ import annotations

import structlog

from evograph.models.domain import ExtractedEntity, ExtractionResult
from evograph.graph.neo4j_client import neo4j_client
from evograph.llm.client import llm_client

logger = structlog.get_logger()


class EntityResolver:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    async def resolve(
        self, extraction_results: list[ExtractionResult]
    ) -> dict[str, str]:
        """
        Returns a mapping of extracted entity names to canonical entity IDs.
        Deduplicates across chunks and links to existing graph entities.
        """
        all_entities: list[ExtractedEntity] = []
        for result in extraction_results:
            all_entities.extend(result.entities)

        name_to_canonical = self._deduplicate_by_name(all_entities)
        name_to_graph_id = await self._link_to_existing(list(name_to_canonical.keys()))

        final_mapping: dict[str, str] = {}
        for entity in all_entities:
            canonical = name_to_canonical.get(entity.name, entity.name)
            graph_id = name_to_graph_id.get(canonical)
            final_mapping[entity.name] = graph_id or canonical

        logger.info(
            "entity_resolution_complete",
            total_entities=len(all_entities),
            unique_entities=len(name_to_canonical),
            linked_to_existing=sum(1 for v in name_to_graph_id.values() if v),
        )
        return final_mapping

    def _deduplicate_by_name(
        self, entities: list[ExtractedEntity]
    ) -> dict[str, str]:
        """Group entities by normalized name and aliases."""
        canonical_map: dict[str, str] = {}
        seen: dict[str, str] = {}

        for entity in entities:
            normalized = entity.name.lower().strip()
            if normalized in seen:
                canonical_map[entity.name] = seen[normalized]
                continue

            matched = False
            for alias in entity.aliases:
                alias_norm = alias.lower().strip()
                if alias_norm in seen:
                    canonical_map[entity.name] = seen[alias_norm]
                    seen[normalized] = seen[alias_norm]
                    matched = True
                    break

            if not matched:
                seen[normalized] = entity.name
                canonical_map[entity.name] = entity.name
                for alias in entity.aliases:
                    seen[alias.lower().strip()] = entity.name

        return canonical_map

    async def _link_to_existing(self, entity_names: list[str]) -> dict[str, str | None]:
        """Try to link extracted entities to existing graph nodes."""
        mapping: dict[str, str | None] = {}

        for name in entity_names:
            results = await neo4j_client.execute_query(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) = toLower($name)
                   OR any(alias IN e.aliases WHERE toLower(alias) = toLower($name))
                RETURN e.id AS id, e.name AS name
                LIMIT 1
                """,
                {"name": name},
            )
            mapping[name] = results[0]["id"] if results else None

        return mapping
