"""BM25 keyword retriever."""

from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi
import structlog

from evograph.storage.vector_store import vector_store

logger = structlog.get_logger()


class KeywordRetriever:
    async def retrieve(
        self, query: str, n_results: int = 10
    ) -> list[dict[str, Any]]:
        all_docs = vector_store.collection.get(
            limit=1000,
            include=["documents", "metadatas"],
        )

        if not all_docs or not all_docs.get("documents"):
            return []

        documents = all_docs["documents"]
        metadatas = all_docs["metadatas"]
        ids = all_docs["ids"]

        tokenized_docs = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized_docs)

        query_tokens = query.lower().split()
        scores = bm25.get_scores(query_tokens)

        scored_docs = list(zip(scores, documents, metadatas, ids))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:n_results]

        results = []
        for score, doc, meta, chunk_id in top_docs:
            if score > 0:
                results.append({
                    "chunk_id": chunk_id,
                    "text": doc,
                    "document_id": meta.get("document_id", ""),
                    "score": float(score),
                })

        logger.info("keyword_retriever", query=query, results=len(results))
        return results


keyword_retriever = KeywordRetriever()
