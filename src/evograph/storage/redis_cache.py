"""Redis cache client with per-event-loop connections.

Like the Neo4j client, redis.asyncio connections bind to the loop that created
them, so a background worker thread needs its own connection. The single global
`redis_client` hands each running loop its own connection pool.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class RedisClient:
    def __init__(self) -> None:
        self._clients: dict[asyncio.AbstractEventLoop, aioredis.Redis] = {}

    async def _get_client(self) -> aioredis.Redis:
        loop = asyncio.get_running_loop()
        client = self._clients.get(loop)
        if client is None:
            client = aioredis.from_url(
                settings.redis_url, decode_responses=True, max_connections=20
            )
            self._clients[loop] = client
        return client

    async def connect(self) -> None:
        client = await self._get_client()
        await client.ping()
        logger.info("redis_connected", url=settings.redis_url)

    async def close(self) -> None:
        loop = asyncio.get_running_loop()
        client = self._clients.pop(loop, None)
        if client:
            await client.close()
            logger.info("redis_disconnected")

    @property
    def client(self) -> aioredis.Redis:
        loop = asyncio.get_event_loop()
        client = self._clients.get(loop)
        if client is None:
            raise RuntimeError("Redis client not connected for this loop")
        return client

    async def get(self, key: str) -> Any | None:
        client = await self._get_client()
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        client = await self._get_client()
        await client.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        client = await self._get_client()
        await client.publish(channel, json.dumps(message, default=str))

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False


redis_client = RedisClient()
