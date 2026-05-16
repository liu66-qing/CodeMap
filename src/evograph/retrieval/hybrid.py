"""Hybrid retrieval orchestrator with graph-aware reciprocal rank fusion."""

from __future__ import annotations

from typing import Any

import structlog

from evograph.retrieval.graph_retriever import graph_retriever
from evograph.retrieval.vector_retriever import vector_retriever
from evograph.retrieval.keyword_retriever import keyword_retriever

logger = structlog.get_logger()


class HybridRetriever:
    def __init__(self, graph_weight: float = 0.4, vector_weight: float = 0.4, keyword_weight: float = 0.2):
        self.graph_weight = graph_weight
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    async def retrieve(
        self,
        query: str,
        entities: list[str] | None = None,
        n_results: int = 10,
    ) -> dict[str, Any]:
        # Run all three retrievers in parallel conceptually (sequential for simplicity)
        graph_results = await graph_retriever.retrieve(query, entities=entities)
        vector_results = await vector_retriever.retrieve(query, n_results=n_results)
        keyword_results = await keyword_retriever.retrieve(query, n_results=n_results)

        # Fuse results using graph-aware RRF
        fused_chunks = self._reciprocal_rank_fusion(
            vector_results, keyword_results, graph_results
        )

        logger.info(
            "hybrid_retrieval",
            graph_results=len(graph_results),
            vector_results=len(vector_results),
            keyword_results=len(keyword_results),
            fused_results=len(fused_chunks),
        )

        return {
            "chunks": fused_chunks[:n_results],
            "graph_context": graph_results,
            "sources": {
                "graph": len(graph_results),
                "vector": len(vector_results),
                "keyword": len(keyword_results),
            },
        }

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        keyword_results: list[dict],
        graph_results: list[dict],
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Graph-aware RRF: chunks that are structurally connected to graph-retrieved
        entities get a boost, creating a "snowball" effect for multi-hop reasoning.
        """
        scores: dict[str, float] = {}
        chunk_data: dict[str, dict] = {}

        # Collect entity names from graph results for boosting
        graph_entity_names = set()
        for gr in graph_results:
            if "source" in gr:
                graph_entity_names.add(gr["source"].lower())
            if "target" in gr:
                graph_entity_names.add(gr["target"].lower())

        # Score vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.get("chunk_id", f"vec_{rank}")
            rrf_score = self.vector_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            chunk_data[chunk_id] = result

        # Score keyword results
        for rank, result in enumerate(keyword_results):
            chunk_id = result.get("chunk_id", f"kw_{rank}")
            rrf_score = self.keyword_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = result

        # Graph-aware boost: if a chunk mentions entities found in graph results
        for chunk_id, data in chunk_data.items():
            text_lower = data.get("text", "").lower()
            boost = sum(
                0.1 for entity in graph_entity_names if entity in text_lower
            )
            if boost > 0:
                scores[chunk_id] = scores.get(chunk_id, 0) + min(boost, 0.3)

        # Sort by fused score
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for chunk_id, score in sorted_chunks:
            data = chunk_data.get(chunk_id, {})
            data["fusion_score"] = score
            results.append(data)

        return results


hybrid_retriever = HybridRetriever()
