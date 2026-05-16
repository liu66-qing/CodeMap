"""Neo4j async client wrapper with connection pooling."""

from __future__ import annotations

from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=50,
        )
        await self._driver.verify_connectivity()
        logger.info("neo4j_connected", uri=settings.neo4j_uri)
        await self._ensure_indexes()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            logger.info("neo4j_disconnected")

    @property
    def driver(self) -> AsyncDriver:
        if not self._driver:
            raise RuntimeError("Neo4j client not connected")
        return self._driver

    def session(self) -> AsyncSession:
        return self.driver.session()

    async def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            await result.consume()
            return records

    async def health_check(self) -> bool:
        try:
            await self.execute_query("RETURN 1 AS ok")
            return True
        except Exception:
            return False

    async def _ensure_indexes(self) -> None:
        indexes = [
            "CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX document_id IF NOT EXISTS FOR (d:Document) ON (d.id)",
            "CREATE INDEX chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.id)",
            "CREATE INDEX event_id IF NOT EXISTS FOR (ev:Event) ON (ev.id)",
            "CREATE INDEX conflict_id IF NOT EXISTS FOR (cf:Conflict) ON (cf.id)",
        ]
        for idx in indexes:
            try:
                await self.execute_write(idx)
            except Exception as e:
                logger.warning("index_creation_skipped", query=idx, error=str(e))


neo4j_client = Neo4jClient()
