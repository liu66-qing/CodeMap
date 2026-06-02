"""CodeGraphView: a database-agnostic, in-memory snapshot of a repo's code graph.

The understanding agents reason over *structure* (who calls whom, what lives in
which module/file), not over a live database. So we give them one small, pure
data object they can traverse synchronously — no `await` mid-algorithm, no
Neo4j coupling — and build it from whichever source is available:

    from_extraction(...)  : during the pipeline, straight off the parsed graph.
    from_neo4j(repo_id)    : standalone / API, reading what the merger persisted.

Both produce the SAME shape, so an agent (and its tests) never knows or cares
where the graph came from.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class GraphNode:
    """A code symbol: module / class / function / method."""
    name: str                       # canonical qualified name
    kind: str                       # module | class | function | method
    signature: str = ""
    file_path: str = ""
    docstring: str = ""
    line_start: int = 0
    line_end: int = 0


@dataclass
class GraphEdge:
    source: str                     # qualified name
    target: str                     # qualified name
    type: str                       # CALLS | IMPORTS | INHERITS | DEFINES


@dataclass
class CodeGraphView:
    """An immutable-ish view with pre-built adjacency indexes for cheap traversal."""
    repo_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    # Indexes (built in __post_init__).
    _by_name: dict[str, GraphNode] = field(default_factory=dict, repr=False)
    _calls_out: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _calls_in: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _edges_by_type: dict[str, list[GraphEdge]] = field(default_factory=lambda: defaultdict(list), repr=False)

    def __post_init__(self) -> None:
        self._by_name = {n.name: n for n in self.nodes}
        self._calls_out = defaultdict(list)
        self._calls_in = defaultdict(list)
        self._edges_by_type = defaultdict(list)
        for e in self.edges:
            self._edges_by_type[e.type].append(e)
            if e.type == "CALLS":
                self._calls_out[e.source].append(e.target)
                self._calls_in[e.target].append(e.source)

    # === Lookups ===

    def get(self, name: str) -> GraphNode | None:
        return self._by_name.get(name)

    def nodes_of_kind(self, *kinds: str) -> list[GraphNode]:
        return [n for n in self.nodes if n.kind in kinds]

    def callees(self, name: str) -> list[str]:
        """Symbols this one calls (outgoing CALLS)."""
        return list(self._calls_out.get(name, []))

    def callers(self, name: str) -> list[str]:
        """Symbols that call this one (incoming CALLS)."""
        return list(self._calls_in.get(name, []))

    def edges_of_type(self, edge_type: str) -> list[GraphEdge]:
        return list(self._edges_by_type.get(edge_type, []))

    def file_of(self, name: str) -> str:
        n = self._by_name.get(name)
        return n.file_path if n else ""

    @property
    def is_empty(self) -> bool:
        return not self.nodes

    # === Constructors ===

    @classmethod
    def from_extraction(cls, extraction, repo_id: str) -> CodeGraphView:
        """Build a view from an in-memory ExtractionResult (pipeline path).

        Entities carry code metadata in `entity.metadata` (code_kind / signature
        / file_path); relations carry the edge type in `relation_type`.
        """
        nodes: list[GraphNode] = []
        for e in extraction.entities:
            meta = getattr(e, "metadata", None) or {}
            nodes.append(GraphNode(
                name=e.name,
                kind=meta.get("code_kind") or _entity_type_to_kind(getattr(e, "type", None)),
                signature=meta.get("signature") or "",
                file_path=meta.get("file_path") or "",
                docstring=(getattr(e, "description", "") or "")[:300],
                line_start=meta.get("line_start") or 0,
                line_end=meta.get("line_end") or 0,
            ))
        edges = [
            GraphEdge(source=r.source_entity, target=r.target_entity, type=r.relation_type)
            for r in extraction.relations
        ]
        return cls(repo_id=repo_id, nodes=nodes, edges=edges)

    @classmethod
    async def from_neo4j(cls, repo_id: str, limit: int = 5000) -> CodeGraphView:
        """Build a view by reading the persisted code graph for a repo.

        Mirrors the shape the merger writes: :Entity nodes tagged with repo_id +
        code_kind/signature/file_path, and :RELATION edges carrying a `type`.
        """
        from evograph.graph.neo4j_client import neo4j_client

        node_rows = await neo4j_client.execute_query(
            """
            MATCH (e:Entity {repo_id: $repo_id})
            RETURN e.name AS name, e.code_kind AS kind, e.signature AS signature,
                   e.file_path AS file_path, e.description AS description,
                   e.line_start AS line_start, e.line_end AS line_end
            LIMIT $limit
            """,
            {"repo_id": repo_id, "limit": limit},
        )
        edge_rows = await neo4j_client.execute_query(
            """
            MATCH (s:Entity {repo_id: $repo_id})-[r:RELATION]->(t:Entity {repo_id: $repo_id})
            WHERE r.is_active = true
            RETURN s.name AS source, t.name AS target, r.type AS type
            LIMIT $limit
            """,
            {"repo_id": repo_id, "limit": limit},
        )
        nodes = [
            GraphNode(
                name=r["name"],
                kind=r.get("kind") or "function",
                signature=r.get("signature") or "",
                file_path=r.get("file_path") or "",
                docstring=(r.get("description") or "")[:300],
                line_start=r.get("line_start") or 0,
                line_end=r.get("line_end") or 0,
            )
            for r in node_rows
            if r.get("name")
        ]
        edges = [
            GraphEdge(source=r["source"], target=r["target"], type=r.get("type") or "CALLS")
            for r in edge_rows
            if r.get("source") and r.get("target")
        ]
        return cls(repo_id=repo_id, nodes=nodes, edges=edges)


def _entity_type_to_kind(entity_type) -> str:
    """Fallback when code_kind metadata is missing — derive from EntityType."""
    val = getattr(entity_type, "value", entity_type)
    return {"module": "module", "class": "class", "function": "function", "method": "method"}.get(
        str(val).lower(), "function"
    )
