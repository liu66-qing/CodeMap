"""LLM-based entity and relation extraction from text chunks."""

from __future__ import annotations

import json

import structlog

from evograph.llm.client import llm_client
from evograph.models.domain import ExtractedEntity, ExtractedRelation, ExtractionResult, EntityType

logger = structlog.get_logger()

EXTRACTION_PROMPT = """You are a knowledge graph extraction engine. Extract entities and relationships from the given text.

Rules:
1. Extract named entities (people, organizations, products, events, locations, technologies, concepts)
2. Extract relationships between entities with temporal information when available
3. For each relationship, estimate a confidence score (0.0-1.0)
4. If temporal information is present (dates, "since", "until", "from X to Y"), include it
5. Use normalized relationship types: WORKS_AT, CEO_OF, FOUNDED, ACQUIRED, LOCATED_IN, PARTNER_OF, COMPETES_WITH, PRODUCES, INVESTED_IN, CAUSED, SUCCEEDED_BY

Output JSON format:
{
  "entities": [
    {"name": "...", "type": "person|organization|product|event|location|technology|concept", "aliases": [], "description": "..."}
  ],
  "relations": [
    {"source_entity": "...", "target_entity": "...", "relation_type": "...", "temporal_start": "YYYY-MM-DD or null", "temporal_end": "YYYY-MM-DD or null", "confidence": 0.9}
  ]
}

Text to extract from:
---
{text}
---

Extract all entities and relationships. Be thorough but precise."""


async def extract_from_chunk(
    chunk_text: str, document_id: str, chunk_id: str
) -> ExtractionResult:
    prompt = EXTRACTION_PROMPT.format(text=chunk_text)

    try:
        response = await llm_client.chat_json(
            messages=[{"role": "user", "content": prompt}]
        )
        data = json.loads(response)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("extraction_failed", chunk_id=chunk_id, error=str(e))
        return ExtractionResult(entities=[], relations=[], document_id=document_id, chunk_id=chunk_id)

    entities = []
    for ent in data.get("entities", []):
        try:
            entity_type = EntityType(ent.get("type", "concept").lower())
        except ValueError:
            entity_type = EntityType.CONCEPT
        entities.append(ExtractedEntity(
            name=ent["name"],
            type=entity_type,
            aliases=ent.get("aliases", []),
            description=ent.get("description", ""),
        ))

    relations = []
    for rel in data.get("relations", []):
        relations.append(ExtractedRelation(
            source_entity=rel["source_entity"],
            target_entity=rel["target_entity"],
            relation_type=rel["relation_type"].upper(),
            temporal_start=rel.get("temporal_start"),
            temporal_end=rel.get("temporal_end"),
            confidence=float(rel.get("confidence", 0.8)),
        ))

    logger.info(
        "extraction_complete",
        chunk_id=chunk_id,
        entities=len(entities),
        relations=len(relations),
    )

    return ExtractionResult(
        entities=entities,
        relations=relations,
        document_id=document_id,
        chunk_id=chunk_id,
    )


async def extract_from_document(
    chunks: list[dict], document_id: str
) -> list[ExtractionResult]:
    results = []
    for chunk in chunks:
        result = await extract_from_chunk(
            chunk_text=chunk["text"],
            document_id=document_id,
            chunk_id=chunk["id"],
        )
        results.append(result)
    return results
