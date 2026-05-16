"""Vector-based retriever using ChromaDB."""

from __future__ import annotations

from typing import Any

import structlog

from evograph.llm.client import llm_client
from evograph.storage.vector_store import vector_store

logger = structlog.get_logger()


class VectorRetriever:
    async def retrieve(
        self,
        query: str,
        n_results: int = 10,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query_embedding = await llm_client.embed_single(query)

        where_filter = None
        if document_ids:
            where_filter = {"document_id": {"$in": document_ids}}

        results = vector_store.query(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where_filter,
        )

        retrieved = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

            for doc, meta, dist, chunk_id in zip(docs, metadatas, distances, ids):
                retrieved.append({
                    "chunk_id": chunk_id,
                    "text": doc,
                    "document_id": meta.get("document_id", ""),
                    "position": meta.get("position", 0),
                    "score": 1.0 - dist,  # cosine distance to similarity
                })

        logger.info("vector_retriever", query_len=len(query), results=len(retrieved))
        return retrieved


vector_retriever = VectorRetriever()
