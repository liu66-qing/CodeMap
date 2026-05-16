"""Agent tools: executable actions the agent can invoke during reasoning."""

from __future__ import annotations

from typing import Any

import structlog

from evograph.retrieval.hybrid import hybrid_retriever
from evograph.retrieval.graph_retriever import graph_retriever
from evograph.retrieval.vector_retriever import vector_retriever
from evograph.graph.neo4j_client import neo4j_client
from evograph.graph import traversal

logger = structlog.get_logger()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {
            "graph_query": self._graph_query,
            "vector_search": self._vector_search,
            "temporal_query": self._temporal_query,
            "conflict_check": self._conflict_check,
            "causal_reason": self._causal_reason,
            "hybrid_search": self._hybrid_search,
        }

    def get_tool(self, name: str):
        return self._tools.get(name)

    async def execute(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool_fn = self._tools.get(tool_name)
        if not tool_fn:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = await tool_fn(**params)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error("tool_execution_failed", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def _graph_query(
        self, query: str = "", entities: list[str] | None = None, **kwargs
    ) -> list[dict]:
        return await graph_retriever.retrieve(query, entities=entities)

    async def _vector_search(
        self, query: str = "", n_results: int = 10, **kwargs
    ) -> list[dict]:
        return await vector_retriever.retrieve(query, n_results=n_results)

    async def _temporal_query(
        self, entity_id: str = "", timestamp: str | None = None, **kwargs
    ) -> list[dict]:
        if not entity_id:
            return []
        return await traversal.get_temporal_relations(entity_id, timestamp)

    async def _conflict_check(
        self, entity_name: str = "", **kwargs
    ) -> list[dict]:
        results = await neo4j_client.execute_query(
            """
            MATCH (e:Entity)-[r]->(target:Entity)
            WHERE toLower(e.name) CONTAINS toLower($name)
              AND r.is_active = true
            WITH e, collect({rel: r, target: target}) AS rels
            WHERE size(rels) > 1
            MATCH (c:Conflict)
            WHERE c.status = 'open'
            RETURN c
            LIMIT 10
            """,
            {"name": entity_name},
        )
        return results

    async def _causal_reason(
        self, event_id: str = "", entity_name: str = "", depth: int = 3, **kwargs
    ) -> list[dict]:
        if event_id:
            return await traversal.get_causal_chain(event_id, depth)
        if entity_name:
            events = await neo4j_client.execute_query(
                """
                MATCH (e:Entity)-[:INVOLVED_IN|CAUSED|RESULTED_IN]-(ev:Event)
                WHERE toLower(e.name) CONTAINS toLower($name)
                RETURN ev
                ORDER BY ev.occurred_at DESC
                LIMIT 5
                """,
                {"name": entity_name},
            )
            return events
        return []

    async def _hybrid_search(
        self, query: str = "", entities: list[str] | None = None, **kwargs
    ) -> dict:
        return await hybrid_retriever.retrieve(query, entities=entities)


tool_registry = ToolRegistry()
