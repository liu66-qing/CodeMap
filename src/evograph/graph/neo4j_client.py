"""Neo4j async client wrapper with per-event-loop connection pooling.

The driver is created lazily and cached PER EVENT LOOP. neo4j's async driver
binds its internal connection pool to the loop that created it, so a driver made
on the request loop cannot be used (or closed) from a background worker thread's
loop. Keying drivers by their running loop lets the single global `neo4j_client`
serve every loop safely — the API loop and any analysis worker each transparently
get (and only ever close) their own driver.
"""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class Neo4jClient:
    def __init__(self) -> None:
        # One driver per event loop, plus a flag for whether indexes were ensured.
        self._drivers: dict[asyncio.AbstractEventLoop, AsyncDriver] = {}
        self._indexed: set[asyncio.AbstractEventLoop] = set()

    async def _get_driver(self) -> AsyncDriver:
        """Return (creating if needed) the driver bound to the current loop."""
        loop = asyncio.get_running_loop()
        driver = self._drivers.get(loop)
        if driver is None:
            driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                max_connection_pool_size=50,
            )
            self._drivers[loop] = driver
        return driver

    async def connect(self) -> None:
        """Eagerly establish the current loop's driver and ensure indexes once."""
        driver = await self._get_driver()
        await driver.verify_connectivity()
        loop = asyncio.get_running_loop()
        if loop not in self._indexed:
            self._indexed.add(loop)
            await self._ensure_indexes()
        logger.info("neo4j_connected", uri=settings.neo4j_uri)

    async def close(self) -> None:
        """Close only the current loop's driver (leaves other loops untouched)."""
        loop = asyncio.get_running_loop()
        driver = self._drivers.pop(loop, None)
        self._indexed.discard(loop)
        if driver:
            await driver.close()
            logger.info("neo4j_disconnected")

    def session(self) -> AsyncSession:
        # Synchronous accessor kept for callers that already hold a driver; prefer
        # execute_query/execute_write which lazily provision the per-loop driver.
        loop = asyncio.get_event_loop()
        driver = self._drivers.get(loop)
        if driver is None:
            raise RuntimeError("Neo4j driver not initialized for this loop")
        return driver.session(database=settings.neo4j_database)

    async def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        driver = await self._get_driver()
        async with driver.session(database=settings.neo4j_database) as session:
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
            "CREATE INDEX repo_analysis_id IF NOT EXISTS FOR (a:RepoAnalysis) ON (a.repo_id)",
            "CREATE INDEX repo_id_idx IF NOT EXISTS FOR (r:Repo) ON (r.repo_id)",
        ]
        for idx in indexes:
            try:
                await self.execute_write(idx)
            except Exception as e:
                logger.warning("index_creation_skipped", query=idx, error=str(e))


neo4j_client = Neo4jClient()
