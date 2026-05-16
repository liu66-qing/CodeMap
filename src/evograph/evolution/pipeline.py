"""Evolution pipeline orchestrator: document → extract → resolve → merge → notify."""

from __future__ import annotations

import structlog

from evograph.ingestion.loader import load_document, chunk_text, embed_chunks
from evograph.evolution.extractor import extract_from_document
from evograph.evolution.resolver import EntityResolver
from evograph.evolution.merger import graph_merger
from evograph.storage.vector_store import vector_store
from evograph.storage.redis_cache import redis_client

logger = structlog.get_logger()


class EvolutionPipeline:
    def __init__(self) -> None:
        self.resolver = EntityResolver()

    async def process_document(
        self, document_id: str, file_path: str, content: bytes | None = None
    ) -> dict:
        logger.info("pipeline_start", document_id=document_id, file_path=file_path)

        # Stage 1: Load and chunk
        doc = await load_document(file_path, content)
        chunks = chunk_text(doc["text"])
        logger.info("pipeline_chunked", document_id=document_id, chunks=len(chunks))

        # Stage 2: Embed chunks and store in vector DB
        chunks_with_embeddings = await embed_chunks(chunks)
        vector_store.add_documents(
            ids=[c["id"] for c in chunks_with_embeddings],
            documents=[c["text"] for c in chunks_with_embeddings],
            embeddings=[c["embedding"] for c in chunks_with_embeddings],
            metadatas=[{"document_id": document_id, "position": c["position"]} for c in chunks_with_embeddings],
        )
        logger.info("pipeline_embedded", document_id=document_id)

        # Stage 3: Extract entities and relations
        extractions = await extract_from_document(chunks, document_id)
        total_entities = sum(len(e.entities) for e in extractions)
        total_relations = sum(len(e.relations) for e in extractions)
        logger.info(
            "pipeline_extracted",
            document_id=document_id,
            entities=total_entities,
            relations=total_relations,
        )

        # Stage 4: Resolve entities (dedup + link)
        entity_mapping = await self.resolver.resolve(extractions)

        # Stage 5: Merge into graph (with conflict detection)
        total_stats = {
            "entities_created": 0,
            "entities_updated": 0,
            "relations_created": 0,
            "conflicts_detected": 0,
        }
        for extraction in extractions:
            stats = await graph_merger.merge_extraction(extraction, entity_mapping)
            for key in total_stats:
                total_stats[key] += stats[key]

        logger.info("pipeline_merged", document_id=document_id, stats=total_stats)

        # Stage 6: Notify via Redis pub/sub
        await redis_client.publish(
            "graph_updates",
            {
                "event": "document_processed",
                "document_id": document_id,
                "stats": total_stats,
            },
        )

        return {
            "document_id": document_id,
            "chunks_processed": len(chunks),
            **total_stats,
        }


evolution_pipeline = EvolutionPipeline()
