"""Graph-based retriever: generates Cypher queries and extracts relevant subgraphs."""

from __future__ import annotations

import json
from typing import Any

import structlog

from evograph.graph.neo4j_client import neo4j_client
from evograph.llm.client import llm_client

logger = structlog.get_logger()

CYPHER_GENERATION_PROMPT = """You are a Neo4j Cypher query generator. Given a natural language question and the graph schema, generate a Cypher query to retrieve relevant information.

Graph Schema:
- Nodes: Entity (id, name, type, aliases, description, first_seen, last_updated)
- Nodes: Document (id, title, source_url, ingested_at)
- Nodes: Event (id, name, description, occurred_at, event_type)
- Nodes: Chunk (id, text, position)
- Relationships: RELATION (id, type, valid_from, valid_to, observed_at, confidence, source_ids, is_active)
- Relationships: CAUSED_BY, RESULTED_IN (between Events)
- Relationships: EXTRACTED_FROM (Entity -> Chunk), BELONGS_TO (Chunk -> Document)

Entity types: person, organization, product, event, location, technology, concept
Relation types: WORKS_AT, CEO_OF, FOUNDED, ACQUIRED, LOCATED_IN, PARTNER_OF, COMPETES_WITH, PRODUCES, INVESTED_IN, CAUSED, SUCCEEDED_BY

Rules:
1. Always filter by is_active = true for relationships unless asking about historical data
2. Use toLower() for case-insensitive name matching
3. Limit results to 20 unless the question implies needing more
4. Return both nodes and relationships when relevant

Question: {question}

Output only the Cypher query, no explanation."""


class GraphRetriever:
    async def retrieve(
        self, question: str, entities: list[str] | None = None
    ) -> list[dict[str, Any]]:
        if entities:
            return await self._retrieve_by_entities(entities)
        return await self._retrieve_by_cypher(question)

    async def _retrieve_by_cypher(self, question: str) -> list[dict[str, Any]]:
        prompt = CYPHER_GENERATION_PROMPT.format(question=question)
        cypher = await llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        cypher = cypher.strip().strip("`").strip()
        if cypher.startswith("cypher"):
            cypher = cypher[6:].strip()

        logger.info("graph_retriever_cypher", query=cypher)

        try:
            results = await neo4j_client.execute_query(cypher)
            return results
        except Exception as e:
            logger.warning("cypher_execution_failed", error=str(e), query=cypher)
            return []

    async def _retrieve_by_entities(self, entities: list[str]) -> list[dict[str, Any]]:
        all_results = []
        for entity_name in entities:
            results = await neo4j_client.execute_query(
                """
                MATCH (e:Entity)-[r]->(target:Entity)
                WHERE (toLower(e.name) CONTAINS toLower($name)
                   OR any(alias IN e.aliases WHERE toLower(alias) CONTAINS toLower($name)))
                  AND r.is_active = true
                RETURN e.name AS source, type(r) AS relation, r.type AS rel_type,
                       target.name AS target, r.confidence AS confidence,
                       r.valid_from AS valid_from, r.valid_to AS valid_to
                LIMIT 10
                """,
                {"name": entity_name},
            )
            all_results.extend(results)
        return all_results


graph_retriever = GraphRetriever()
