"""Redis cache client."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class RedisClient:
    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            settings.redis_url, decode_responses=True, max_connections=20
        )
        await self._client.ping()
        logger.info("redis_connected", url=settings.redis_url)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            logger.info("redis_disconnected")

    @property
    def client(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("Redis client not connected")
        return self._client

    async def get(self, key: str) -> Any | None:
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        await self.client.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        await self.client.publish(channel, json.dumps(message, default=str))

    async def health_check(self) -> bool:
        try:
            await self.client.ping()
            return True
        except Exception:
            return False


redis_client = RedisClient()
