"""Vector store abstraction over ChromaDB."""

from __future__ import annotations

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class VectorStore:
    def __init__(self) -> None:
        self._client: chromadb.HttpClient | None = None
        self._collection: Any = None

    def connect(self) -> None:
        self._client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="evograph_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chromadb_connected", host=settings.chroma_host)

    @property
    def collection(self) -> Any:
        if not self._collection:
            self.connect()
        return self._collection

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

    def delete(self, ids: list[str]) -> None:
        self.collection.delete(ids=ids)

    def health_check(self) -> bool:
        try:
            if self._client:
                self._client.heartbeat()
                return True
            return False
        except Exception:
            return False


vector_store = VectorStore()
