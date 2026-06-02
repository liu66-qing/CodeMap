"""Code repository pipeline: git repo -> code graph + breaking changes in Neo4j.

This is the orchestrator that ties the deterministic parser, the git-history
loader, and the breaking-change detector into the existing graph store. It is
the code-side analogue of `evolution/pipeline.py` (which handles documents).

Flow:
    1. Walk git history (oldest -> newest) via git_loader.
    2. For the LATEST snapshot, build the current code graph and merge it into
       Neo4j as :Entity nodes + :RELATION edges (reusing GraphMerger).
    3. Across ALL consecutive snapshots, detect breaking changes and persist
       them as :Conflict nodes (reusing the conflict store shape), each linked
       to the commit that introduced it.
    4. Run the code-UNDERSTANDING agents over the current graph (distilled from
       the Understand-Anything multi-agent design):
         4a. architecture_analyzer -> layers / patterns / module boundaries
         4b. tour_builder          -> an ordered, narrated walk from an entry point
         4c. graph_reviewer        -> cross-checks 4a/4b, corrects, scores confidence
    5. Persist the architecture summary + tour + review onto a :RepoAnalysis node
       in Neo4j and (best-effort) cache them in Redis, so the frontend can read
       comprehension results without re-running the agents.

The current-state graph powers "what calls this / what does this depend on",
the breaking-change history powers "which commit broke this contract", and the
understanding layer powers "what is this system and how does a request flow".
"""

from __future__ import annotations

import json

import structlog

from evograph.ingestion.git_loader import iter_history, CommitSnapshot
from evograph.ingestion.code_graph_adapter import build_extraction_from_parses
from evograph.evolution.breaking_change_detector import scan_history, BreakingChange
from evograph.evolution.merger import graph_merger
from evograph.graph.neo4j_client import neo4j_client
from evograph.agent.analyzers.graph_view import CodeGraphView
from evograph.agent.analyzers.architecture_analyzer import analyze_architecture
from evograph.agent.analyzers.tour_builder import build_tour
from evograph.agent.analyzers.graph_reviewer import review_graph
from evograph.agent.analyzers.learning_path import build_learning_path_annotated

logger = structlog.get_logger()


class CodeRepoPipeline:
    async def process_repository(
        self,
        repo_id: str,
        repo_path: str,
        max_commits: int | None = None,
        src_prefixes: tuple[str, ...] = ("src/", "lib/"),
        entry_point: str | None = None,
        run_understanding: bool = True,
        path_prefix: str = "",
    ) -> dict:
        logger.info("code_pipeline_start", repo_id=repo_id, repo_path=repo_path,
                    path_prefix=path_prefix)

        # Stage 1: walk full history once, materialize snapshots.
        snapshots: list[CommitSnapshot] = list(
            iter_history(repo_path, max_commits=max_commits, src_prefixes=src_prefixes,
                         path_prefix=path_prefix)
        )
        if not snapshots:
            return {"repo_id": repo_id, "error": "no commits found", "commits": 0}

        latest = snapshots[-1]
        logger.info(
            "code_pipeline_history_loaded",
            repo_id=repo_id,
            commits=len(snapshots),
            latest=latest.commit.short_sha,
        )

        # Stage 2: merge the current code graph into Neo4j.
        extraction, adapter_stats = build_extraction_from_parses(
            latest.parses, document_id=repo_id
        )
        # Entities are pre-canonicalized (qualified names are unique), so the
        # resolver step is unnecessary — pass an identity mapping.
        identity_map = {e.name: e.name for e in extraction.entities}
        merge_stats = await graph_merger.merge_extraction(extraction, identity_map)

        # Stage 3: detect breaking changes across the whole history.
        breaking = scan_history(snapshots)
        await self._store_breaking_changes(repo_id, breaking)

        # Stage 4: persist the full commit chain (every commit, not just the
        # ones with breaking changes) so the Timeline can replay evolution.
        await self._store_commit_history(repo_id, snapshots)

        # Persist where this repo lives on disk + which subtree, so the source
        # reader can fetch real code bodies later (mechanism analysis, viewer).
        await self._store_repo_location(repo_id, repo_path, path_prefix, latest.commit.sha)

        # Stages 4a-6: code-understanding agents over the current graph.
        # Built straight from the in-memory extraction — no Neo4j round-trip —
        # so understanding still works even if the merge above degraded.
        understanding: dict = {}
        if run_understanding:
            understanding = await self._run_understanding(repo_id, extraction, entry_point)

        result = {
            "repo_id": repo_id,
            "commits": len(snapshots),
            "latest_commit": latest.commit.short_sha,
            "nodes": adapter_stats["nodes"],
            "relations_merged": merge_stats.get("relations_created", 0),
            "breaking_changes": len(breaking),
            "adapter_stats": adapter_stats,
            "understanding": understanding,
        }
        logger.info("code_pipeline_complete", **{
            k: v for k, v in result.items() if k not in ("adapter_stats", "understanding")
        })
        return result

    async def _run_understanding(
        self, repo_id: str, extraction, entry_point: str | None
    ) -> dict:
        """Run architecture -> tour -> review, then persist (Stage 7).

        Best-effort: any failure is logged and the rest of the pipeline result is
        still returned. Comprehension is additive, never a hard dependency.
        """
        try:
            view = CodeGraphView.from_extraction(extraction, repo_id=repo_id)
            architecture = await analyze_architecture(view)               # 4a
            tour = await build_tour(view, entry_point=entry_point)         # 4b
            learning = await build_learning_path_annotated(view, architecture)  # 4c
            architecture, review = await review_graph(view, architecture, tour)  # 6 (corrects 4a)
            await self._store_understanding(repo_id, architecture, tour, review, learning)  # 7
            logger.info(
                "understanding_complete",
                repo_id=repo_id,
                layers=len(architecture.get("layers", [])),
                tour_steps=len(tour.get("steps", [])),
                learning_steps=len(learning.get("steps", [])),
                review_confidence=review.get("confidence"),
            )
            return {
                "architecture_generated_by": architecture.get("generated_by"),
                "layers": len(architecture.get("layers", [])),
                "patterns": len(architecture.get("patterns", [])),
                "tour_steps": len(tour.get("steps", [])),
                "learning_steps": len(learning.get("steps", [])),
                "review_confidence": review.get("confidence"),
                "review_issues": len(review.get("issues", [])),
            }
        except Exception as exc:
            logger.warning("understanding_failed", repo_id=repo_id, error=str(exc))
            return {"error": str(exc)}

    async def _store_breaking_changes(
        self, repo_id: str, changes: list[BreakingChange]
    ) -> None:
        """Persist each breaking change as a :Conflict node, linked to the
        :Commit that introduced it and the affected :Entity symbol.

        Reuses the :Conflict label so breaking changes surface in the same
        conflicts API/dashboard the document pipeline already feeds.
        """
        for bc in changes:
            await neo4j_client.execute_write(
                """
                MERGE (cm:Commit {sha: $sha})
                  ON CREATE SET cm.short_sha = $short, cm.subject = $subject, cm.repo_id = $repo_id
                MERGE (cf:Conflict {id: $conflict_id})
                  ON CREATE SET cf.type = $type,
                                cf.status = 'open',
                                cf.kind = 'breaking_change',
                                cf.description = $description,
                                cf.qualified_name = $qname,
                                cf.old_signature = $old_sig,
                                cf.new_signature = $new_sig,
                                cf.callers = $callers,
                                cf.repo_id = $repo_id,
                                cf.detected_at = datetime()
                MERGE (cf)-[:INTRODUCED_IN]->(cm)
                """,
                {
                    "sha": bc.commit_sha,
                    "short": bc.commit_short,
                    "subject": bc.commit_subject,
                    "repo_id": repo_id,
                    "conflict_id": f"{repo_id}:{bc.commit_sha}:{bc.qualified_name}:{bc.kind}",
                    "type": "logical_contradiction",  # maps onto existing ConflictType
                    "description": f"[{bc.kind}] {bc.qualified_name}: {bc.detail}",
                    "qname": bc.qualified_name,
                    "old_sig": bc.old_signature,
                    "new_sig": bc.new_signature,
                    "callers": bc.callers,
                },
            )
            # Link the conflict to the affected symbol entity if present.
            await neo4j_client.execute_write(
                """
                MATCH (cf:Conflict {id: $conflict_id})
                MATCH (e:Entity {name: $qname})
                MERGE (cf)-[:AFFECTS]->(e)
                """,
                {
                    "conflict_id": f"{repo_id}:{bc.commit_sha}:{bc.qualified_name}:{bc.kind}",
                    "qname": bc.qualified_name,
                },
            )

        if changes:
            logger.info("breaking_changes_stored", repo_id=repo_id, count=len(changes))

    async def _store_commit_history(
        self, repo_id: str, snapshots: list[CommitSnapshot]
    ) -> None:
        """Persist every commit as a :Commit node with PARENT edges and per-commit
        counts, so the Timeline can step through the repo's evolution.

        Counts are cheap snapshot-local tallies: how many callables and how many
        .py files existed at that commit. The PARENT edge mirrors git's first-parent
        chain, which is also what the breaking-change detector diffs against.
        """
        for snap in snapshots:
            c = snap.commit
            callables = sum(
                1
                for p in snap.parses
                if not p.parse_error
                for n in p.nodes
                if n.kind in ("function", "method")
            )
            files = sum(1 for p in snap.parses if not p.parse_error)
            await neo4j_client.execute_write(
                """
                MERGE (cm:Commit {sha: $sha})
                  SET cm.short_sha = $short,
                      cm.subject = $subject,
                      cm.author = $author,
                      cm.timestamp = $ts,
                      cm.repo_id = $repo_id,
                      cm.callable_count = $callables,
                      cm.file_count = $files
                """,
                {
                    "sha": c.sha,
                    "short": c.short_sha,
                    "subject": c.subject,
                    "author": c.author,
                    "ts": c.timestamp.isoformat() if c.timestamp else None,
                    "repo_id": repo_id,
                    "callables": callables,
                    "files": files,
                },
            )
            if c.parent_sha:
                await neo4j_client.execute_write(
                    """
                    MATCH (cm:Commit {sha: $sha})
                    MERGE (parent:Commit {sha: $parent})
                      ON CREATE SET parent.repo_id = $repo_id
                    MERGE (cm)-[:PARENT]->(parent)
                    """,
                    {"sha": c.sha, "parent": c.parent_sha, "repo_id": repo_id},
                )
        logger.info("commit_history_stored", repo_id=repo_id, commits=len(snapshots))

    async def _store_repo_location(
        self, repo_id: str, repo_path: str, path_prefix: str, head_sha: str
    ) -> None:
        """Persist the repo's on-disk clone path + analyzed subtree + HEAD sha on a
        :Repo node, so the source reader can fetch real code bodies for any symbol.

        Best-effort: a failure here only disables source-code features, not the
        rest of the pipeline.
        """
        try:
            import os
            await neo4j_client.execute_write(
                """
                MERGE (r:Repo {repo_id: $repo_id})
                  SET r.local_path = $local_path,
                      r.path_prefix = $path_prefix,
                      r.head_sha = $head_sha,
                      r.updated_at = datetime()
                """,
                {
                    "repo_id": repo_id,
                    "local_path": os.path.abspath(repo_path),
                    "path_prefix": path_prefix or "",
                    "head_sha": head_sha,
                },
            )
        except Exception as exc:
            logger.warning("store_repo_location_failed", repo_id=repo_id, error=str(exc))

    async def _store_understanding(
        self, repo_id: str, architecture: dict, tour: dict, review: dict,
        learning: dict | None = None,
    ) -> None:
        """Stage 7: persist comprehension results so the frontend can read them
        without re-running the agents.

        Stored two ways, both best-effort:
          - Neo4j  : one :RepoAnalysis node keyed by repo_id, payloads JSON-encoded
                     (Neo4j can't store nested maps as properties, so we serialize).
          - Redis  : a cache entry for fast reads, TTL 24h.
        The two are independent — if Neo4j is down, Redis still serves the API,
        and vice-versa.
        """
        learning = learning or {"steps": []}
        arch_json = json.dumps(architecture, ensure_ascii=False, default=str)
        tour_json = json.dumps(tour, ensure_ascii=False, default=str)
        review_json = json.dumps(review, ensure_ascii=False, default=str)
        learning_json = json.dumps(learning, ensure_ascii=False, default=str)

        try:
            await neo4j_client.execute_write(
                """
                MERGE (a:RepoAnalysis {repo_id: $repo_id})
                  SET a.architecture = $architecture,
                      a.tour = $tour,
                      a.review = $review,
                      a.learning_path = $learning,
                      a.review_confidence = $confidence,
                      a.architecture_generated_by = $arch_by,
                      a.updated_at = datetime()
                """,
                {
                    "repo_id": repo_id,
                    "architecture": arch_json,
                    "tour": tour_json,
                    "review": review_json,
                    "learning": learning_json,
                    "confidence": review.get("confidence"),
                    "arch_by": architecture.get("generated_by"),
                },
            )
        except Exception as exc:
            logger.warning("store_understanding_neo4j_failed", repo_id=repo_id, error=str(exc))

        try:
            from evograph.storage.redis_cache import redis_client
            payload = {"architecture": architecture, "tour": tour, "review": review,
                       "learning_path": learning}
            await redis_client.set(f"repo_analysis:{repo_id}", payload, ttl=86400)
        except Exception as exc:
            logger.warning("store_understanding_redis_failed", repo_id=repo_id, error=str(exc))


code_repo_pipeline = CodeRepoPipeline()

