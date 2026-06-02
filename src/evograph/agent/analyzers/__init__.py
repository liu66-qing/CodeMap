"""Code-understanding agents (distilled from the Understand-Anything multi-agent
design) layered on top of the deterministic code-evolution graph.

Where `evolution/` answers *"what broke and in which commit"*, this package
answers *"what is this codebase, how is it shaped, and how does a request flow
through it"* — the comprehension half of a developer-facing code assistant.

Three agents, each pure-input / structured-output so they unit-test without a
database and degrade gracefully when the LLM is unavailable:

    architecture_analyzer  : graph -> layers / patterns / module boundaries
    tour_builder           : graph + entry point -> ordered walk-through
    graph_reviewer         : all prior outputs -> contradictions + corrections

They all consume a `CodeGraphView` (see `graph_view.py`), which can be built
either from an in-memory ExtractionResult (during the pipeline) or by reading
Neo4j for a repo_id (standalone / API).
"""

from evograph.agent.analyzers.graph_view import CodeGraphView, GraphNode, GraphEdge

__all__ = ["CodeGraphView", "GraphNode", "GraphEdge"]
