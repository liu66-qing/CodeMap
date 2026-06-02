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
            # === Code-assistant tools ===
            "find_callers": self._find_callers,
            "find_dependencies": self._find_dependencies,
            "get_symbol_history": self._get_symbol_history,
            "find_breaking_changes": self._find_breaking_changes,
            # === Code-understanding tools (architecture / impact / evolution) ===
            "explain_architecture": self._explain_architecture,
            "analyze_impact": self._analyze_impact,
            "feature_evolution": self._feature_evolution,
            "explain_symbol": self._explain_symbol,
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

    # === Code-assistant tools ===

    async def _find_callers(self, symbol: str = "", **kwargs) -> list[dict]:
        """Who calls this function/method? Reverse CALLS edges."""
        if not symbol:
            return []
        return await neo4j_client.execute_query(
            """
            MATCH (caller:Entity)-[r:RELATION {type: 'CALLS'}]->(target:Entity)
            WHERE r.is_active = true
              AND (target.name = $symbol OR target.name ENDS WITH '.' + $symbol)
            RETURN caller.name AS caller, target.name AS target
            LIMIT 50
            """,
            {"symbol": symbol},
        )

    async def _find_dependencies(self, symbol: str = "", **kwargs) -> list[dict]:
        """What does this function/method call (its outgoing dependencies)?"""
        if not symbol:
            return []
        return await neo4j_client.execute_query(
            """
            MATCH (src:Entity)-[r:RELATION {type: 'CALLS'}]->(dep:Entity)
            WHERE r.is_active = true
              AND (src.name = $symbol OR src.name ENDS WITH '.' + $symbol)
            RETURN src.name AS source, dep.name AS dependency
            LIMIT 50
            """,
            {"symbol": symbol},
        )

    async def _get_symbol_history(self, symbol: str = "", **kwargs) -> list[dict]:
        """Commits that introduced breaking changes to this symbol over time."""
        if not symbol:
            return []
        return await neo4j_client.execute_query(
            """
            MATCH (cf:Conflict {kind: 'breaking_change'})-[:INTRODUCED_IN]->(cm:Commit)
            WHERE cf.qualified_name = $symbol OR cf.qualified_name ENDS WITH '.' + $symbol
            RETURN cm.short_sha AS commit, cm.subject AS subject,
                   cf.description AS change, cf.old_signature AS old_sig,
                   cf.new_signature AS new_sig, cf.callers AS affected_callers
            ORDER BY cm.short_sha
            LIMIT 50
            """,
            {"symbol": symbol},
        )

    async def _find_breaking_changes(self, repo_id: str = "", **kwargs) -> list[dict]:
        """All detected breaking changes, optionally scoped to one repo."""
        if repo_id:
            query = """
            MATCH (cf:Conflict {kind: 'breaking_change', repo_id: $repo_id})-[:INTRODUCED_IN]->(cm:Commit)
            RETURN cf.qualified_name AS symbol, cf.description AS change,
                   cm.short_sha AS commit, cm.subject AS subject, cf.callers AS affected_callers
            ORDER BY cm.short_sha
            LIMIT 100
            """
            params = {"repo_id": repo_id}
        else:
            query = """
            MATCH (cf:Conflict {kind: 'breaking_change'})-[:INTRODUCED_IN]->(cm:Commit)
            RETURN cf.qualified_name AS symbol, cf.description AS change,
                   cm.short_sha AS commit, cm.subject AS subject, cf.callers AS affected_callers
            ORDER BY cm.short_sha
            LIMIT 100
            """
            params = {}
        return await neo4j_client.execute_query(query, params)

    # === Code-understanding tools ===

    async def _explain_architecture(self, repo_id: str = "", **kwargs) -> dict:
        """'What does this system look like?' — layers, patterns, boundaries.

        Reads the persisted RepoAnalysis if present, else computes on-demand from
        the graph. Answers 'what is this module/system' questions with grounding.
        """
        if not repo_id:
            return {"error": "repo_id required"}
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.architecture_analyzer import analyze_architecture
        # Prefer the persisted summary.
        rows = await neo4j_client.execute_query(
            "MATCH (a:RepoAnalysis {repo_id: $repo_id}) RETURN a.architecture AS architecture",
            {"repo_id": repo_id},
        )
        if rows and rows[0].get("architecture"):
            import json
            return json.loads(rows[0]["architecture"])
        view = await CodeGraphView.from_neo4j(repo_id)
        return await analyze_architecture(view)

    async def _analyze_impact(self, symbol: str = "", repo_id: str = "", **kwargs) -> dict:
        """'If I change this function, what breaks?' — transitive caller closure.

        Walks reverse CALLS edges outward from `symbol` to find every symbol that
        (transitively) depends on it, plus any breaking-change history. This is the
        core 'change impact' question for a code-understanding agent.
        """
        if not symbol:
            return {"error": "symbol required"}
        scope = "AND n.repo_id = $repo_id" if repo_id else ""
        rows = await neo4j_client.execute_query(
            f"""
            MATCH (target:Entity)
            WHERE target.name = $symbol OR target.name ENDS WITH '.' + $symbol
            CALL {{
                WITH target
                MATCH (n:Entity)-[r:RELATION*1..6]->(target)
                WHERE all(rel IN r WHERE rel.type = 'CALLS' AND rel.is_active = true)
                  {scope}
                RETURN DISTINCT n.name AS dependent, length(r) AS distance
            }}
            RETURN dependent, min(distance) AS distance
            ORDER BY distance ASC
            LIMIT 200
            """,
            {"symbol": symbol, "repo_id": repo_id} if repo_id else {"symbol": symbol},
        )
        history = await self._get_symbol_history(symbol=symbol)
        return {
            "symbol": symbol,
            "impacted": rows,
            "impacted_count": len(rows),
            "breaking_change_history": history,
        }

    async def _feature_evolution(self, symbol: str = "", repo_id: str = "", **kwargs) -> dict:
        """'When did this start / how did it evolve?' — the commit where a symbol
        first appears and the breaking changes it accumulated since.

        Combines first-appearance (earliest commit touching its file or the
        earliest breaking-change record) with the ordered change history.
        """
        if not symbol:
            return {"error": "symbol required"}
        history = await self._get_symbol_history(symbol=symbol)
        # Earliest commit that references this symbol's qualified name as a conflict
        # anchor, else fall back to the repo's first commit overall.
        first = await neo4j_client.execute_query(
            """
            MATCH (cm:Commit)
            WHERE ($repo_id = '' OR cm.repo_id = $repo_id)
            RETURN cm.short_sha AS commit, cm.subject AS subject, cm.timestamp AS timestamp
            ORDER BY cm.timestamp ASC
            LIMIT 1
            """,
            {"repo_id": repo_id},
        )
        return {
            "symbol": symbol,
            "first_commit": first[0] if first else None,
            "evolution": history,
            "change_count": len(history),
        }

    async def _explain_symbol(
        self, symbol: str = "", repo_id: str = "", persona: str = "junior", **kwargs
    ) -> dict:
        """'What does this symbol do?' — a plain-language, persona-tuned summary."""
        if not symbol or not repo_id:
            return {"error": "symbol and repo_id required"}
        from evograph.agent.analyzers.symbol_explainer import explain_symbol
        # Pull architecture for layer context if persisted.
        architecture = None
        rows = await neo4j_client.execute_query(
            "MATCH (a:RepoAnalysis {repo_id: $r}) RETURN a.architecture AS arch",
            {"r": repo_id},
        )
        if rows and rows[0].get("arch"):
            import json
            architecture = json.loads(rows[0]["arch"])
        result = await explain_symbol(repo_id, symbol, persona=persona, architecture=architecture)
        return result or {"error": "symbol not found"}


tool_registry = ToolRegistry()
