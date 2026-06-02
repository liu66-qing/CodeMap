"""Code repository analysis endpoints.

Accepts a local git repository path, walks its history, builds the code graph,
and detects breaking changes. This is the code-assistant entry point, parallel
to the document ingestion endpoints.
"""

from __future__ import annotations

import json
import os
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from evograph.graph.neo4j_client import neo4j_client

logger = structlog.get_logger()
router = APIRouter()


class AnalyzeRepoRequest(BaseModel):
    # Provide EITHER a local path OR a clonable git URL (repo_url).
    repo_path: str | None = None
    repo_url: str | None = None
    repo_id: str | None = None
    subdir: str | None = None          # analyze only this subtree (monorepo sub-app)
    max_commits: int | None = None
    entry_point: str | None = None


class AnalyzeRepoResponse(BaseModel):
    repo_id: str
    status: str
    repo_path: str
    mode: str = "async"               # "async" (celery) | "inline" (no worker)


@router.post("", response_model=AnalyzeRepoResponse)
async def analyze_repository(req: AnalyzeRepoRequest) -> AnalyzeRepoResponse:
    """Analyze a git repository — by local path OR by clonable URL (GitHub etc.).

    A `repo_url` is cloned (and cached) first; `subdir` scopes analysis to one
    sub-app inside a monorepo. Dispatches to a Celery worker when available,
    otherwise runs in a background daemon thread so a brand-new clone + the
    CPU-heavy parse never block the request event loop (which would stall the
    HTTP response). Inputs are validated synchronously so obvious mistakes still
    return a 400 immediately.
    """
    from evograph.ingestion.git_loader import is_remote_url, _slug_for_url

    repo_path = req.repo_path
    derived_id = req.repo_id
    remote_url: str | None = None

    # Resolve URL vs local path. For a URL we DON'T clone here (could be slow) —
    # we defer the clone to the background worker, but validate the format now.
    if req.repo_url and not repo_path:
        if not is_remote_url(req.repo_url):
            raise HTTPException(status_code=400, detail=f"Not a valid git URL: {req.repo_url}")
        remote_url = req.repo_url
        if not derived_id:
            derived_id = _slug_for_url(req.repo_url)
    elif repo_path:
        if not os.path.isdir(repo_path):
            raise HTTPException(status_code=400, detail=f"Path not found: {repo_path}")
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise HTTPException(status_code=400, detail="Path is not a git repository (.git not found)")
    else:
        raise HTTPException(status_code=400, detail="Provide either repo_path or repo_url")

    # Normalize subdir pathspec to end with "/". For a local path we can verify it
    # now; for a remote URL we verify after cloning (in the worker).
    path_prefix = ""
    if req.subdir:
        path_prefix = req.subdir.strip().strip("/").replace("\\", "/") + "/"
        if repo_path and not os.path.isdir(os.path.join(repo_path, path_prefix.rstrip("/"))):
            raise HTTPException(status_code=400, detail=f"subdir not found in repo: {req.subdir}")

    repo_id = derived_id or f"repo_{uuid.uuid4().hex[:8]}"
    if path_prefix:
        repo_id = f"{repo_id}:{path_prefix.rstrip('/').rsplit('/', 1)[-1]}"

    # Prefer the Celery worker (only usable for already-local paths); otherwise
    # run in a background thread so cloning + parsing never block this loop.
    mode = "background"
    if repo_path and not remote_url:
        try:
            from evograph.tasks.code_tasks import analyze_repository_task
            analyze_repository_task.delay(repo_id, repo_path, req.max_commits, req.entry_point)
            mode = "async"
        except Exception as exc:
            logger.warning("celery_dispatch_unavailable_running_background", error=str(exc))

    if mode != "async":
        _run_analysis_in_background(
            repo_id=repo_id, repo_path=repo_path, remote_url=remote_url,
            path_prefix=path_prefix, max_commits=req.max_commits, entry_point=req.entry_point,
        )

    logger.info("repo_analysis_started", repo_id=repo_id, repo_path=repo_path,
                remote_url=remote_url, subdir=path_prefix, mode=mode)
    return AnalyzeRepoResponse(
        repo_id=repo_id, status="processing", repo_path=repo_path or remote_url or "", mode=mode
    )


def _run_analysis_in_background(
    *, repo_id: str, repo_path: str | None, remote_url: str | None,
    path_prefix: str, max_commits: int | None, entry_point: str | None,
) -> None:
    """Clone (if needed) and run the full pipeline on a daemon thread with its own
    event loop. Keeps all blocking work off the request loop."""
    import threading

    def _worker() -> None:
        import asyncio as _asyncio
        from evograph.ingestion.git_loader import clone_repo, GitHistoryError
        from evograph.evolution.code_repo_pipeline import code_repo_pipeline
        from evograph.graph.neo4j_client import neo4j_client
        from evograph.storage.redis_cache import redis_client

        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        try:
            local_path = repo_path
            if remote_url:
                try:
                    local_path = clone_repo(remote_url)
                except GitHistoryError as exc:
                    logger.error("background_clone_failed", repo_id=repo_id, error=str(exc))
                    return
            if path_prefix and local_path and not os.path.isdir(
                os.path.join(local_path, path_prefix.rstrip("/"))
            ):
                logger.error("background_subdir_missing", repo_id=repo_id, subdir=path_prefix)
                return

            async def _run() -> None:
                # The worker thread has no shared driver connections — open its own.
                try:
                    await neo4j_client.connect()
                except Exception as exc:
                    logger.warning("background_neo4j_connect_failed", error=str(exc))
                try:
                    await redis_client.connect()
                except Exception:
                    pass
                try:
                    await code_repo_pipeline.process_repository(
                        repo_id, local_path, max_commits=max_commits,
                        entry_point=entry_point, path_prefix=path_prefix,
                    )
                finally:
                    try:
                        await neo4j_client.close()
                    except Exception:
                        pass
                    try:
                        await redis_client.close()
                    except Exception:
                        pass

            loop.run_until_complete(_run())
            logger.info("background_analysis_complete", repo_id=repo_id)
        except Exception as exc:
            logger.error("background_analysis_failed", repo_id=repo_id, error=str(exc))
        finally:
            loop.close()

    threading.Thread(target=_worker, name=f"analyze-{repo_id}", daemon=True).start()


@router.get("")
async def list_repositories() -> dict:
    """List repositories that have been analyzed (have code entities or commits)."""
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (e:Entity)
            WHERE e.repo_id IS NOT NULL
            WITH e.repo_id AS repo_id, count(e) AS nodes
            OPTIONAL MATCH (cm:Commit {repo_id: repo_id})
            WITH repo_id, nodes, count(cm) AS commits
            RETURN repo_id, nodes, commits
            ORDER BY nodes DESC
            LIMIT 100
            """
        )
        return {"repositories": rows, "total": len(rows)}
    except Exception as exc:  # Neo4j down — degrade gracefully, never 500.
        logger.warning("list_repositories_failed", error=str(exc))
        return {"repositories": [], "total": 0}


@router.get("/{repo_id}/graph")
async def get_repo_graph(repo_id: str, limit: int = 300) -> dict:
    """Return the code graph (nodes + edges) for a repo, shaped for the frontend
    force-directed view. Nodes are code symbols; edges are CALLS/IMPORTS/etc."""
    try:
        nodes = await neo4j_client.execute_query(
            """
            MATCH (e:Entity {repo_id: $repo_id})
            RETURN e.id AS id, e.name AS name, e.code_kind AS kind,
                   e.signature AS signature, e.file_path AS file_path
            LIMIT $limit
            """,
            {"repo_id": repo_id, "limit": limit},
        )
        edges = await neo4j_client.execute_query(
            """
            MATCH (s:Entity {repo_id: $repo_id})-[r:RELATION]->(t:Entity {repo_id: $repo_id})
            RETURN s.name AS source, t.name AS target, r.type AS type
            LIMIT $limit
            """,
            {"repo_id": repo_id, "limit": limit},
        )
        return {"repo_id": repo_id, "nodes": nodes, "edges": edges}
    except Exception as exc:
        logger.warning("get_repo_graph_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "nodes": [], "edges": []}


@router.get("/{repo_id}/commits")
async def get_repo_commits(repo_id: str) -> dict:
    """Return the commit history (oldest-first) with per-commit counts and a flag
    for whether the commit introduced any breaking change — drives the Timeline."""
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (cm:Commit {repo_id: $repo_id})
            OPTIONAL MATCH (cf:Conflict {kind: 'breaking_change'})-[:INTRODUCED_IN]->(cm)
            WITH cm, count(cf) AS breaking
            RETURN cm.sha AS sha, cm.short_sha AS short_sha, cm.subject AS subject,
                   cm.author AS author, cm.timestamp AS timestamp,
                   cm.callable_count AS callables, cm.file_count AS files,
                   breaking AS breaking_changes
            ORDER BY cm.timestamp ASC
            LIMIT 500
            """,
            {"repo_id": repo_id},
        )
        return {"repo_id": repo_id, "commits": rows, "total": len(rows)}
    except Exception as exc:
        logger.warning("get_repo_commits_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "commits": [], "total": 0}


@router.get("/{repo_id}/breaking-changes")
async def get_breaking_changes(repo_id: str) -> dict:
    """List detected breaking changes for a repo, newest commit first."""
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (cf:Conflict {kind: 'breaking_change', repo_id: $repo_id})-[:INTRODUCED_IN]->(cm:Commit)
            RETURN cf.qualified_name AS symbol, cf.type AS type, cf.description AS description,
                   cf.old_signature AS old_signature, cf.new_signature AS new_signature,
                   cf.callers AS affected_callers, cm.short_sha AS commit, cm.subject AS commit_subject
            ORDER BY cm.short_sha
            LIMIT 200
            """,
            {"repo_id": repo_id},
        )
        return {"repo_id": repo_id, "breaking_changes": rows, "total": len(rows)}
    except Exception as exc:
        logger.warning("get_breaking_changes_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "breaking_changes": [], "total": 0}


@router.get("/{repo_id}/stats")
async def get_repo_stats(repo_id: str) -> dict:
    """Node/relation/commit/breaking-change counts for a repo's code graph."""
    empty = {"repo_id": repo_id, "nodes": 0, "relations": 0, "commits": 0, "breaking_changes": 0}
    try:
        rows = await neo4j_client.execute_query(
            """
            OPTIONAL MATCH (e:Entity {repo_id: $repo_id})
            WITH count(e) AS nodes
            OPTIONAL MATCH (:Entity {repo_id: $repo_id})-[r:RELATION]->(:Entity {repo_id: $repo_id})
            WITH nodes, count(r) AS relations
            OPTIONAL MATCH (cm:Commit {repo_id: $repo_id})
            WITH nodes, relations, count(cm) AS commits
            OPTIONAL MATCH (cf:Conflict {kind: 'breaking_change', repo_id: $repo_id})
            RETURN nodes, relations, commits, count(cf) AS breaking_changes
            """,
            {"repo_id": repo_id},
        )
        if not rows:
            return empty
        out = dict(rows[0])
        out["repo_id"] = repo_id
        return out
    except Exception as exc:
        logger.warning("get_repo_stats_failed", repo_id=repo_id, error=str(exc))
        return empty


# === Code-understanding endpoints (architecture / tour / review) ===
#
# These serve what the pipeline's understanding stage persisted. If nothing was
# persisted yet (e.g. Celery never ran, or the repo predates the feature), they
# fall back to computing on-demand straight from the graph in Neo4j — so the
# views are never blank when a graph exists.


async def _load_understanding(repo_id: str) -> dict | None:
    """Read the persisted analysis: Redis first (fast), then the :RepoAnalysis
    node in Neo4j. Returns {architecture, tour, review} or None."""
    try:
        from evograph.storage.redis_cache import redis_client
        cached = await redis_client.get(f"repo_analysis:{repo_id}")
        if cached:
            return cached
    except Exception:
        pass
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (a:RepoAnalysis {repo_id: $repo_id})
            RETURN a.architecture AS architecture, a.tour AS tour, a.review AS review,
                   a.learning_path AS learning_path
            """,
            {"repo_id": repo_id},
        )
        if rows and rows[0].get("architecture"):
            return {
                "architecture": json.loads(rows[0]["architecture"]),
                "tour": json.loads(rows[0]["tour"]) if rows[0].get("tour") else {},
                "review": json.loads(rows[0]["review"]) if rows[0].get("review") else {},
                "learning_path": json.loads(rows[0]["learning_path"]) if rows[0].get("learning_path") else {},
            }
    except Exception as exc:
        logger.warning("load_understanding_failed", repo_id=repo_id, error=str(exc))
    return None


async def _compute_understanding(repo_id: str, entry_point: str | None = None) -> dict | None:
    """On-demand fallback: build a graph view from Neo4j and run the agents now.
    Caches the result so subsequent reads are served from storage."""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.architecture_analyzer import analyze_architecture
        from evograph.agent.analyzers.tour_builder import build_tour
        from evograph.agent.analyzers.graph_reviewer import review_graph
        from evograph.agent.analyzers.learning_path import build_learning_path_annotated

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return None
        architecture = await analyze_architecture(view)
        tour = await build_tour(view, entry_point=entry_point)
        learning = await build_learning_path_annotated(view, architecture)
        architecture, review = await review_graph(view, architecture, tour)
        result = {"architecture": architecture, "tour": tour, "review": review,
                  "learning_path": learning}
        try:
            from evograph.storage.redis_cache import redis_client
            await redis_client.set(f"repo_analysis:{repo_id}", result, ttl=86400)
        except Exception:
            pass
        return result
    except Exception as exc:
        logger.warning("compute_understanding_failed", repo_id=repo_id, error=str(exc))
        return None


async def _get_understanding(repo_id: str, recompute: bool, entry_point: str | None = None) -> dict | None:
    if recompute:
        return await _compute_understanding(repo_id, entry_point)
    return await _load_understanding(repo_id) or await _compute_understanding(repo_id, entry_point)


@router.get("/{repo_id}/architecture")
async def get_repo_architecture(repo_id: str, recompute: bool = False) -> dict:
    """Architecture summary: layers / patterns / module boundaries."""
    data = await _get_understanding(repo_id, recompute)
    if not data:
        return {"repo_id": repo_id, "architecture": None,
                "message": "尚无分析结果(图谱为空或后端未连接)"}
    return {"repo_id": repo_id, "architecture": data.get("architecture")}


@router.get("/{repo_id}/tour")
async def get_repo_tour(repo_id: str, entry_point: str | None = None, recompute: bool = False) -> dict:
    """Narrated code tour: an ordered walk from an entry point down the call graph.
    Pass `entry_point` (simple or qualified name) to start the tour somewhere
    specific; this forces a recompute for that entry."""
    data = await _get_understanding(repo_id, recompute or bool(entry_point), entry_point)
    if not data:
        return {"repo_id": repo_id, "tour": None,
                "message": "尚无分析结果(图谱为空或后端未连接)"}
    return {"repo_id": repo_id, "tour": data.get("tour")}


@router.get("/{repo_id}/review")
async def get_repo_review(repo_id: str, recompute: bool = False) -> dict:
    """Review report: contradictions / omissions found, plus a confidence score."""
    data = await _get_understanding(repo_id, recompute)
    if not data:
        return {"repo_id": repo_id, "review": None,
                "message": "尚无分析结果(图谱为空或后端未连接)"}
    return {"repo_id": repo_id, "review": data.get("review")}


@router.get("/{repo_id}/learning-path")
async def get_repo_learning_path(repo_id: str, recompute: bool = False) -> dict:
    """Guided learning path: ordered, layer-grouped reading list for newcomers."""
    data = await _get_understanding(repo_id, recompute)
    if not data:
        return {"repo_id": repo_id, "learning_path": None,
                "message": "尚无分析结果(图谱为空或后端未连接)"}
    return {"repo_id": repo_id, "learning_path": data.get("learning_path")}


@router.get("/{repo_id}/modules")
async def get_repo_modules(repo_id: str, recompute: bool = False) -> dict:
    """Module-card map: symbols aggregated into module cards plus weighted
    inter-module dependency edges. Powers the card 'system map'. Cached in Redis."""
    cache_key = f"module_map:{repo_id}"
    if not recompute:
        try:
            from evograph.storage.redis_cache import redis_client
            cached = await redis_client.get(cache_key)
            if cached:
                return {"repo_id": repo_id, "module_map": cached}
        except Exception:
            pass
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.module_cards import build_module_map

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return {"repo_id": repo_id, "module_map": None, "message": "图谱为空"}
        understanding = await _load_understanding(repo_id)
        architecture = understanding.get("architecture") if understanding else None
        module_map = await build_module_map(view, architecture)
        try:
            from evograph.storage.redis_cache import redis_client
            await redis_client.set(cache_key, module_map, ttl=86400)
        except Exception:
            pass
        return {"repo_id": repo_id, "module_map": module_map}
    except Exception as exc:
        logger.warning("get_repo_modules_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "module_map": None, "message": str(exc)}


@router.get("/{repo_id}/modules/{module_id}/mechanism")
async def get_module_mechanism(repo_id: str, module_id: str) -> dict:
    """Mechanism analysis: reads the real code bodies of a module's core symbols
    and synthesizes a design narrative (division of labor, connections, data flow,
    state/memory management). This is what lets users understand HOW a module
    works, not just what symbols it has."""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.mechanism_analyzer import analyze_mechanism

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return {"repo_id": repo_id, "module": module_id, "mechanism": None,
                    "message": "图谱为空"}
        mechanism = await analyze_mechanism(repo_id, view, module_id)
        return {"repo_id": repo_id, "module": module_id, "mechanism": mechanism}
    except Exception as exc:
        logger.warning("get_module_mechanism_failed", repo_id=repo_id, module=module_id, error=str(exc))
        return {"repo_id": repo_id, "module": module_id, "mechanism": None, "message": str(exc)}


@router.get("/{repo_id}/symbols/{symbol}/source")
async def get_symbol_source(repo_id: str, symbol: str, context: int = 3) -> dict:
    """Read the real source code body of a symbol from the on-disk clone.
    Returns the code snippet with file path, line range, and language hint.
    `context` adds N lines of padding around the symbol's range."""
    from evograph.ingestion.source_reader import get_symbol_source as _get_source
    try:
        snip = await _get_source(repo_id, symbol, context=context)
        if not snip:
            return {"repo_id": repo_id, "symbol": symbol, "source": None,
                    "message": "源码不可用(仓库未在本地或符号无行号)"}
        return {
            "repo_id": repo_id, "symbol": symbol,
            "source": {
                "file_path": snip.file_path,
                "line_start": snip.line_start,
                "line_end": snip.line_end,
                "code": snip.code,
                "language": snip.language,
                "truncated": snip.truncated,
            },
        }
    except Exception as exc:
        logger.warning("get_symbol_source_failed", repo_id=repo_id, symbol=symbol, error=str(exc))
        return {"repo_id": repo_id, "symbol": symbol, "source": None, "message": str(exc)}


@router.get("/{repo_id}/source")
async def get_source_snippet(repo_id: str, path: str, start: int = 1, end: int = 50) -> dict:
    """Generic source snippet reader: fetch lines [start, end] of any file in the
    repo's on-disk clone. Used by the frontend source viewer for arbitrary files."""
    from evograph.ingestion.source_reader import get_repo_location, read_snippet_from_disk
    try:
        loc = await get_repo_location(repo_id)
        if not loc:
            return {"repo_id": repo_id, "source": None, "message": "仓库本地路径未知"}
        snip = read_snippet_from_disk(loc.local_path, path, start, end)
        if not snip:
            return {"repo_id": repo_id, "source": None, "message": "文件不存在或路径非法"}
        return {
            "repo_id": repo_id,
            "source": {
                "file_path": snip.file_path,
                "line_start": snip.line_start,
                "line_end": snip.line_end,
                "code": snip.code,
                "language": snip.language,
                "truncated": snip.truncated,
            },
        }
    except Exception as exc:
        logger.warning("get_source_snippet_failed", repo_id=repo_id, path=path, error=str(exc))
        return {"repo_id": repo_id, "source": None, "message": str(exc)}


class AskCodebaseRequest(BaseModel):
    question: str


@router.get("/{repo_id}/quickstart")
async def get_repo_quickstart(repo_id: str) -> dict:
    """Quickstart info: how to install, run, and find the entry point of this repo.
    Deterministically parsed from package.json/pyproject/Makefile/Dockerfile/README."""
    from evograph.agent.analyzers.quickstart import extract_quickstart
    try:
        qs = await extract_quickstart(repo_id)
        return {"repo_id": repo_id, "quickstart": qs}
    except Exception as exc:
        logger.warning("get_quickstart_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "quickstart": {"available": False, "message": str(exc)}}


@router.get("/{repo_id}/panorama")
async def get_repo_panorama(repo_id: str) -> dict:
    """Panorama: conceptual overview of how the system works — capabilities,
    data-flow journey, collaboration patterns, and key abstractions."""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.panorama_analyzer import analyze_panorama
        from evograph.agent.analyzers.module_cards import build_cards
        from evograph.agent.analyzers.mechanism_analyzer import analyze_mechanism

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return {"repo_id": repo_id, "panorama": None, "message": "图谱为空"}
        understanding = await _load_understanding(repo_id)
        architecture = understanding.get("architecture") if understanding else None
        cards, edges = build_cards(view, architecture)
        # Get mechanism for top modules (by size).
        top_modules = sorted(cards, key=lambda c: c["symbol_count"], reverse=True)[:5]
        mechanisms = []
        for card in top_modules:
            m = await analyze_mechanism(repo_id, view, card["id"])
            mechanisms.append(m)
        panorama = await analyze_panorama(view, architecture, mechanisms, edges)
        return {"repo_id": repo_id, "panorama": panorama}
    except Exception as exc:
        logger.warning("get_panorama_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "panorama": None, "message": str(exc)}


@router.get("/{repo_id}/highlights")
async def get_repo_highlights(repo_id: str) -> dict:
    """Design highlights: non-trivial design decisions with problem→solution→tradeoff."""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.highlights_analyzer import analyze_highlights
        from evograph.agent.analyzers.module_cards import build_cards
        from evograph.agent.analyzers.mechanism_analyzer import analyze_mechanism

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return {"repo_id": repo_id, "highlights": None, "message": "图谱为空"}
        understanding = await _load_understanding(repo_id)
        architecture = understanding.get("architecture") if understanding else None
        cards, _ = build_cards(view, architecture)
        top_modules = sorted(cards, key=lambda c: c["symbol_count"], reverse=True)[:5]
        mechanisms = []
        for card in top_modules:
            m = await analyze_mechanism(repo_id, view, card["id"])
            mechanisms.append(m)
        highlights = await analyze_highlights(view, architecture, mechanisms)
        return {"repo_id": repo_id, "highlights": highlights}
    except Exception as exc:
        logger.warning("get_highlights_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "highlights": None, "message": str(exc)}


@router.get("/{repo_id}/patterns")
async def get_repo_patterns(repo_id: str) -> dict:
    """Transferable patterns: reusable design patterns extracted from this codebase,
    with minimal examples and applicability notes."""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.highlights_analyzer import analyze_highlights
        from evograph.agent.analyzers.patterns_extractor import extract_patterns
        from evograph.agent.analyzers.module_cards import build_cards
        from evograph.agent.analyzers.mechanism_analyzer import analyze_mechanism

        view = await CodeGraphView.from_neo4j(repo_id)
        if view.is_empty:
            return {"repo_id": repo_id, "patterns": None, "message": "图谱为空"}
        understanding = await _load_understanding(repo_id)
        architecture = understanding.get("architecture") if understanding else None
        cards, _ = build_cards(view, architecture)
        top_modules = sorted(cards, key=lambda c: c["symbol_count"], reverse=True)[:5]
        mechanisms = []
        for card in top_modules:
            m = await analyze_mechanism(repo_id, view, card["id"])
            mechanisms.append(m)
        highlights = await analyze_highlights(view, architecture, mechanisms)
        patterns = await extract_patterns(highlights, mechanisms)
        return {"repo_id": repo_id, "patterns": patterns}
    except Exception as exc:
        logger.warning("get_patterns_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "patterns": None, "message": str(exc)}


@router.post("/{repo_id}/ask")
async def ask_codebase_endpoint(repo_id: str, req: AskCodebaseRequest) -> dict:
    """Ask a natural-language question about a codebase. Retrieves relevant symbols,
    reads their real source code, and synthesizes an answer with traceable citations.
    Example: 'How is context managed between agents?' or '记忆存在哪里?'"""
    try:
        from evograph.agent.analyzers.graph_view import CodeGraphView
        from evograph.agent.analyzers.ask_codebase import ask_codebase

        view = await CodeGraphView.from_neo4j(repo_id)
        result = await ask_codebase(repo_id, view, req.question)
        return {"repo_id": repo_id, "question": req.question, **result}
    except Exception as exc:
        logger.warning("ask_codebase_failed", repo_id=repo_id, error=str(exc))
        return {"repo_id": repo_id, "question": req.question,
                "answer": f"查询失败: {exc}", "sources": [], "generated_by": "error"}


@router.get("/{repo_id}/symbols/{symbol}")
async def get_symbol_detail(repo_id: str, symbol: str) -> dict:
    """Full detail for one code symbol: its node, callers, callees, enclosing
    module, and any breaking-change history. Powers the GraphExplorer detail panel
    and the 'changing this affects where?' question."""
    empty = {"repo_id": repo_id, "symbol": symbol, "node": None,
             "callers": [], "callees": [], "module": None, "history": []}
    try:
        node_rows = await neo4j_client.execute_query(
            """
            MATCH (e:Entity {repo_id: $repo_id})
            WHERE e.name = $symbol OR e.name ENDS WITH '.' + $symbol
            RETURN e.name AS name, e.code_kind AS kind, e.signature AS signature,
                   e.file_path AS file_path, e.description AS description
            LIMIT 1
            """,
            {"repo_id": repo_id, "symbol": symbol},
        )
        if not node_rows:
            return empty
        node = node_rows[0]
        full_name = node["name"]

        callers = await neo4j_client.execute_query(
            """
            MATCH (c:Entity {repo_id: $repo_id})-[r:RELATION {type: 'CALLS'}]->(t:Entity {name: $name})
            WHERE r.is_active = true
            RETURN c.name AS caller, c.file_path AS file_path
            LIMIT 100
            """,
            {"repo_id": repo_id, "name": full_name},
        )
        callees = await neo4j_client.execute_query(
            """
            MATCH (s:Entity {name: $name})-[r:RELATION {type: 'CALLS'}]->(d:Entity {repo_id: $repo_id})
            WHERE r.is_active = true
            RETURN d.name AS callee, d.file_path AS file_path
            LIMIT 100
            """,
            {"repo_id": repo_id, "name": full_name},
        )
        history = await neo4j_client.execute_query(
            """
            MATCH (cf:Conflict {kind: 'breaking_change', repo_id: $repo_id})-[:INTRODUCED_IN]->(cm:Commit)
            WHERE cf.qualified_name = $name
            RETURN cm.short_sha AS commit, cm.subject AS subject, cf.description AS change,
                   cf.old_signature AS old_signature, cf.new_signature AS new_signature
            ORDER BY cm.short_sha
            LIMIT 50
            """,
            {"repo_id": repo_id, "name": full_name},
        )
        # Enclosing module = longest module-name prefix of this symbol.
        module = full_name.rsplit(".", 1)[0] if "." in full_name else None
        # Related tests: test functions that test this symbol (by naming or CALLS).
        related_tests: list[dict] = []
        try:
            from evograph.agent.analyzers.graph_view import CodeGraphView
            from evograph.agent.analyzers.test_association import get_tests_for_symbol
            view = await CodeGraphView.from_neo4j(repo_id)
            related_tests = get_tests_for_symbol(view, full_name)
        except Exception:
            pass
        return {
            "repo_id": repo_id, "symbol": full_name, "node": node,
            "callers": callers, "callees": callees, "module": module,
            "history": history, "related_tests": related_tests,
        }
    except Exception as exc:
        logger.warning("get_symbol_detail_failed", repo_id=repo_id, symbol=symbol, error=str(exc))
        return empty


@router.get("/{repo_id}/symbols/{symbol}/explain")
async def explain_symbol_endpoint(repo_id: str, symbol: str, persona: str = "junior") -> dict:
    """Plain-language, persona-tuned ('junior'|'pm'|'senior') summary of a symbol.

    Cached per (symbol, persona) in Redis. Uses the persisted architecture for
    layer context. Returns {explanation: null} if the symbol is unknown."""
    cache_key = f"explain:{repo_id}:{persona}:{symbol}"
    try:
        from evograph.storage.redis_cache import redis_client
        cached = await redis_client.get(cache_key)
        if cached:
            return {"repo_id": repo_id, "explanation": cached}
    except Exception:
        pass

    try:
        from evograph.agent.analyzers.symbol_explainer import explain_symbol
        understanding = await _load_understanding(repo_id)
        architecture = understanding.get("architecture") if understanding else None
        explanation = await explain_symbol(repo_id, symbol, persona=persona, architecture=architecture)
        if explanation is None:
            return {"repo_id": repo_id, "explanation": None, "message": "符号未找到"}
        try:
            from evograph.storage.redis_cache import redis_client
            await redis_client.set(cache_key, explanation, ttl=86400)
        except Exception:
            pass
        return {"repo_id": repo_id, "explanation": explanation}
    except Exception as exc:
        logger.warning("explain_symbol_failed", repo_id=repo_id, symbol=symbol, error=str(exc))
        return {"repo_id": repo_id, "explanation": None, "message": str(exc)}
