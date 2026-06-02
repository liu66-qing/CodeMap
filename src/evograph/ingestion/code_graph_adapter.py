"""Adapter: turn parsed code (CodeNode/CodeEdge) into the existing
ExtractionResult shape so the code graph flows through the SAME merger,
resolver, and Neo4j model the document pipeline already uses.

The hard part here is *symbol resolution*: a CALLS edge target is a raw dotted
name like "self.bark", "helper", or "os.path.join". We resolve those to
internal qualified names where we can, and drop edges that point outside the
repo (external library calls) to keep the graph clean and meaningful.

Resolution is deliberately conservative — better to miss an edge than to invent
a wrong one, because wrong edges poison downstream reasoning.
"""

from __future__ import annotations

from collections import defaultdict

from evograph.ingestion.code_parser import CodeNode, CodeEdge, ParseResult
from evograph.models.domain import (
    EntityType,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)

_KIND_TO_ENTITY_TYPE = {
    "module": EntityType.MODULE,
    "class": EntityType.CLASS,
    "function": EntityType.FUNCTION,
    "method": EntityType.METHOD,
}


class SymbolResolver:
    """Resolves raw call/inherit targets to internal qualified names."""

    def __init__(self, nodes: list[CodeNode]) -> None:
        self.by_qname: dict[str, CodeNode] = {n.qualified_name: n for n in nodes}
        self.module_qnames: set[str] = {
            n.qualified_name for n in nodes if n.kind == "module"
        }
        # simple_name -> [qualified_name, ...]
        self.callable_by_simple: dict[str, list[str]] = defaultdict(list)
        for n in nodes:
            if n.kind in ("function", "method"):
                self.callable_by_simple[n.simple_name].append(n.qualified_name)
        self.class_by_simple: dict[str, list[str]] = defaultdict(list)
        for n in nodes:
            if n.kind == "class":
                self.class_by_simple[n.simple_name].append(n.qualified_name)

    def _enclosing_module(self, qname: str) -> str | None:
        """Longest module qname that prefixes `qname`."""
        best = None
        for m in self.module_qnames:
            if qname == m or qname.startswith(m + "."):
                if best is None or len(m) > len(best):
                    best = m
        return best

    def _parent_qname(self, qname: str) -> str | None:
        if "." not in qname:
            return None
        return qname.rsplit(".", 1)[0]

    def resolve_call(self, source_qname: str, target: str) -> str | None:
        """Resolve a CALLS target to an internal qualified name, or None."""
        # 1. self./cls. -> method on the enclosing class
        if target.startswith(("self.", "cls.")):
            method = target.split(".", 1)[1]
            parent = self._parent_qname(source_qname)
            if parent and self.by_qname.get(parent, None) and self.by_qname[parent].kind == "class":
                cand = f"{parent}.{method}"
                if cand in self.by_qname:
                    return cand
            return None

        # 2. exact qualified-name match (already fully qualified)
        if target in self.by_qname:
            return target

        # 3. bare name -> module-level callable in the same module
        if "." not in target:
            module = self._enclosing_module(source_qname)
            if module:
                cand = f"{module}.{target}"
                if cand in self.by_qname:
                    return cand
            # 3b. unique global callable / class with that simple name
            cands = self.callable_by_simple.get(target, []) or self.class_by_simple.get(target, [])
            if len(cands) == 1:
                return cands[0]
            return None

        # 4. dotted name "a.b.method" -> try last segment as a unique callable
        last = target.rsplit(".", 1)[-1]
        cands = self.callable_by_simple.get(last, [])
        if len(cands) == 1:
            return cands[0]
        return None

    def resolve_inherit(self, source_qname: str, target: str) -> str | None:
        """Resolve an INHERITS base to an internal class qualified name, or None."""
        if target in self.by_qname:
            return target
        module = self._enclosing_module(source_qname)
        if module:
            cand = f"{module}.{target.rsplit('.', 1)[-1]}"
            if cand in self.by_qname:
                return cand
        cands = self.class_by_simple.get(target.rsplit(".", 1)[-1], [])
        if len(cands) == 1:
            return cands[0]
        return None


def build_extraction_from_parses(
    parses: list[ParseResult],
    document_id: str,
    repo_internal_imports_only: bool = True,
) -> tuple[ExtractionResult, dict]:
    """Aggregate per-file ParseResults into ONE ExtractionResult for the whole
    repo, with cross-file call/inherit edges resolved globally.

    Returns (extraction_result, stats). Entities use the qualified name as their
    canonical `name`, so the merger's name-based upsert keeps them unique.
    """
    all_nodes: list[CodeNode] = []
    raw_edges: list[CodeEdge] = []
    for p in parses:
        if p.parse_error:
            continue
        all_nodes.extend(p.nodes)
        raw_edges.extend(p.edges)

    resolver = SymbolResolver(all_nodes)
    known_qnames = {n.qualified_name for n in all_nodes}

    entities: list[ExtractedEntity] = [
        ExtractedEntity(
            name=n.qualified_name,
            type=_KIND_TO_ENTITY_TYPE[n.kind],
            aliases=[n.simple_name] if n.simple_name != n.qualified_name else [],
            description=(n.signature or n.docstring[:200] or n.kind),
            metadata={
                "repo_id": document_id,   # document_id carries the repo_id here
                "code_kind": n.kind,      # module|class|function|method
                "signature": n.signature,
                "file_path": n.file_path,
                "line_start": n.line_start,
                "line_end": n.line_end,
            },
        )
        for n in all_nodes
    ]

    relations: list[ExtractedRelation] = []
    stats = {
        "nodes": len(all_nodes),
        "edges_total": len(raw_edges),
        "calls_resolved": 0,
        "calls_dropped_external": 0,
        "inherits_resolved": 0,
        "inherits_dropped_external": 0,
        "defines": 0,
        "imports_internal": 0,
        "imports_dropped_external": 0,
    }

    for e in raw_edges:
        if e.kind == "DEFINES":
            relations.append(ExtractedRelation(
                source_entity=e.source, target_entity=e.target,
                relation_type="DEFINES", confidence=1.0,
            ))
            stats["defines"] += 1

        elif e.kind == "CALLS":
            resolved = resolver.resolve_call(e.source, e.target)
            if resolved:
                relations.append(ExtractedRelation(
                    source_entity=e.source, target_entity=resolved,
                    relation_type="CALLS", confidence=1.0,
                ))
                stats["calls_resolved"] += 1
            else:
                stats["calls_dropped_external"] += 1

        elif e.kind == "INHERITS":
            resolved = resolver.resolve_inherit(e.source, e.target)
            if resolved:
                relations.append(ExtractedRelation(
                    source_entity=e.source, target_entity=resolved,
                    relation_type="INHERITS", confidence=1.0,
                ))
                stats["inherits_resolved"] += 1
            else:
                stats["inherits_dropped_external"] += 1

        elif e.kind == "IMPORTS":
            # Only keep imports that resolve to a module inside the repo.
            tgt = e.target.lstrip(".")
            internal = None
            if tgt in known_qnames:
                internal = tgt
            else:
                # "pkg.mod.symbol" -> try dropping the trailing symbol to a module
                head = tgt.rsplit(".", 1)[0] if "." in tgt else tgt
                if head in known_qnames:
                    internal = head
            if internal and not repo_internal_imports_only:
                pass
            if internal:
                relations.append(ExtractedRelation(
                    source_entity=e.source, target_entity=internal,
                    relation_type="IMPORTS", confidence=1.0,
                ))
                stats["imports_internal"] += 1
            else:
                stats["imports_dropped_external"] += 1

    result = ExtractionResult(
        entities=entities,
        relations=relations,
        document_id=document_id,
        chunk_id=f"{document_id}:codegraph",
    )
    return result, stats
