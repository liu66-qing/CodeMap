"""Source reader: fetch real code bodies from a repo's on-disk clone.

This is the foundation for "read the actual code", not just its structure:
- the mechanism analyzer feeds these bodies to the LLM to explain *how* a module
  works (not just what symbols it has),
- the source viewer shows the exact lines behind a symbol,
- the ask-codebase tool grounds answers in real code + citations.

A repo's location is persisted on a :Repo node (local_path + path_prefix +
head_sha) by the pipeline. We resolve a symbol's file_path against that local
clone and slice out its line range. Everything is defensive: a missing file,
moved clone, or out-of-range line just yields None/empty, never an exception.

Security: file_path is always resolved INSIDE the repo's local_path; any path
that escapes it (via .. or absolute paths) is rejected.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

from evograph.graph.neo4j_client import neo4j_client

logger = structlog.get_logger()

# Extension -> highlight.js / Prism language hint for the frontend.
_LANG_BY_EXT = {
    "py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript",
    "tsx": "typescript", "go": "go", "java": "java", "rb": "ruby", "rs": "rust",
    "c": "c", "h": "c", "cpp": "cpp", "cc": "cpp", "cs": "csharp", "php": "php",
    "kt": "kotlin", "swift": "swift", "scala": "scala", "sh": "bash",
    "yaml": "yaml", "yml": "yaml", "json": "json", "toml": "toml", "md": "markdown",
}

# Bound how much code we ever read/return, so a giant file can't blow up memory
# or the LLM context.
MAX_SNIPPET_LINES = 400


@dataclass
class RepoLocation:
    repo_id: str
    local_path: str
    path_prefix: str
    head_sha: str


@dataclass
class SourceSnippet:
    file_path: str          # repo-relative path
    line_start: int
    line_end: int
    code: str
    language: str
    truncated: bool = False


async def get_repo_location(repo_id: str) -> RepoLocation | None:
    """Read the :Repo node's on-disk location for a repo, or None."""
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (r:Repo {repo_id: $repo_id})
            RETURN r.local_path AS local_path, r.path_prefix AS path_prefix,
                   r.head_sha AS head_sha
            """,
            {"repo_id": repo_id},
        )
    except Exception as exc:
        logger.warning("get_repo_location_failed", repo_id=repo_id, error=str(exc))
        return None
    if not rows or not rows[0].get("local_path"):
        return None
    r = rows[0]
    return RepoLocation(
        repo_id=repo_id,
        local_path=r["local_path"],
        path_prefix=r.get("path_prefix") or "",
        head_sha=r.get("head_sha") or "",
    )


def _language_for(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return _LANG_BY_EXT.get(ext, "text")


def _safe_join(root: str, rel_path: str) -> str | None:
    """Join rel_path under root, rejecting any escape (.. / absolute paths)."""
    root_abs = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(root_abs, rel_path))
    if candidate != root_abs and not candidate.startswith(root_abs + os.sep):
        return None
    return candidate


def read_snippet_from_disk(
    local_path: str, file_path: str, line_start: int | None, line_end: int | None,
    context: int = 0,
) -> SourceSnippet | None:
    """Read a code slice from disk. `file_path` is repo-relative. If line numbers
    are missing, returns the whole file (capped). `context` adds N lines of
    padding around the range. Returns None if unreadable or path escapes root."""
    full = _safe_join(local_path, file_path)
    if not full or not os.path.isfile(full):
        return None
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as exc:
        logger.warning("read_snippet_failed", file=file_path, error=str(exc))
        return None

    total = len(lines)
    if line_start and line_start > 0:
        s = max(1, line_start - context)
        e = min(total, (line_end or line_start) + context)
    else:
        s, e = 1, total

    truncated = False
    if e - s + 1 > MAX_SNIPPET_LINES:
        e = s + MAX_SNIPPET_LINES - 1
        truncated = True

    code = "".join(lines[s - 1 : e])
    return SourceSnippet(
        file_path=file_path, line_start=s, line_end=e,
        code=code, language=_language_for(file_path), truncated=truncated,
    )


async def get_symbol_source(repo_id: str, symbol: str, context: int = 0) -> SourceSnippet | None:
    """Fetch the real code body for a symbol (resolved by its persisted
    file_path + line_start/line_end), or None if unavailable."""
    loc = await get_repo_location(repo_id)
    if not loc:
        return None
    try:
        rows = await neo4j_client.execute_query(
            """
            MATCH (e:Entity {repo_id: $repo_id})
            WHERE e.name = $symbol OR e.name ENDS WITH '.' + $symbol
            RETURN e.file_path AS file_path, e.line_start AS line_start,
                   e.line_end AS line_end
            LIMIT 1
            """,
            {"repo_id": repo_id, "symbol": symbol},
        )
    except Exception:
        return None
    if not rows or not rows[0].get("file_path"):
        return None
    r = rows[0]
    return read_snippet_from_disk(
        loc.local_path, r["file_path"], r.get("line_start"), r.get("line_end"),
        context=context,
    )
