"""GitHub repository fetcher tools.

Fetches repo file tree, file content, and README via GitHub API or local clone.
Supports both public GitHub repos (via API) and local git repos.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30.0


def _parse_github_url(repo_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url)
    if m:
        return m.group(1), m.group(2)
    return None


def _github_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def fetch_repo_tree(repo_url: str) -> dict[str, Any]:
    """Fetch repository file tree.

    Returns: {"files": [...], "directories": [...], "total_files": int, "languages": [...]}
    """
    parsed = _parse_github_url(repo_url)
    if parsed:
        return await _fetch_tree_github(*parsed)
    # Treat as local path
    return _fetch_tree_local(repo_url)


async def _fetch_tree_github(owner: str, repo: str) -> dict[str, Any]:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_github_headers())
        resp.raise_for_status()
        data = resp.json()

    files: list[str] = []
    dirs: set[str] = set()
    for item in data.get("tree", []):
        if item["type"] == "blob":
            files.append(item["path"])
        elif item["type"] == "tree":
            dirs.add(item["path"])

    languages = _detect_languages(files)
    return {
        "files": files,
        "directories": sorted(dirs),
        "total_files": len(files),
        "languages": languages,
    }


def _fetch_tree_local(path: str) -> dict[str, Any]:
    root = Path(path)
    if not root.is_dir():
        return {"files": [], "directories": [], "total_files": 0, "languages": []}
    files: list[str] = []
    dirs: set[str] = set()
    for p in root.rglob("*"):
        if ".git" in p.parts:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if p.is_file():
            files.append(rel)
        elif p.is_dir():
            dirs.add(rel)
    languages = _detect_languages(files)
    return {
        "files": files[:2000],
        "directories": sorted(dirs)[:500],
        "total_files": len(files),
        "languages": languages,
    }


async def fetch_file_content(repo_url: str, file_path: str) -> dict[str, Any]:
    """Fetch a single file's content.

    Returns: {"path": str, "content": str, "lines": int, "language": str}
    """
    parsed = _parse_github_url(repo_url)
    if parsed:
        return await _fetch_file_github(*parsed, file_path)
    return _fetch_file_local(repo_url, file_path)


async def _fetch_file_github(owner: str, repo: str, file_path: str) -> dict[str, Any]:
    import base64

    url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_github_headers())
        resp.raise_for_status()
        data = resp.json()

    content = ""
    if data.get("encoding") == "base64":
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    else:
        content = data.get("content", "")

    return {
        "path": file_path,
        "content": content,
        "lines": content.count("\n") + 1,
        "language": _ext_to_lang(file_path),
    }


def _fetch_file_local(repo_path: str, file_path: str) -> dict[str, Any]:
    full = Path(repo_path) / file_path
    if not full.is_file():
        return {"path": file_path, "content": "", "lines": 0, "language": ""}
    content = full.read_text(encoding="utf-8", errors="replace")
    return {
        "path": file_path,
        "content": content,
        "lines": content.count("\n") + 1,
        "language": _ext_to_lang(file_path),
    }


async def fetch_readme(repo_url: str) -> dict[str, Any]:
    """Fetch README content.

    Returns: {"content": str, "has_badges": bool, "sections": [...]}
    """
    parsed = _parse_github_url(repo_url)
    if parsed:
        return await _fetch_readme_github(*parsed)
    return _fetch_readme_local(repo_url)


async def _fetch_readme_github(owner: str, repo: str) -> dict[str, Any]:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/readme"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            url, headers={**_github_headers(), "Accept": "application/vnd.github.raw"}
        )
        if resp.status_code == 404:
            return {"content": "", "has_badges": False, "sections": []}
        resp.raise_for_status()
        content = resp.text
    return _parse_readme(content)


def _fetch_readme_local(repo_path: str) -> dict[str, Any]:
    root = Path(repo_path)
    for name in ("README.md", "readme.md", "README.rst", "README"):
        p = root / name
        if p.is_file():
            content = p.read_text(encoding="utf-8", errors="replace")
            return _parse_readme(content)
    return {"content": "", "has_badges": False, "sections": []}


def _parse_readme(content: str) -> dict[str, Any]:
    has_badges = bool(re.search(r"\[!\[", content))
    sections = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
    return {"content": content, "has_badges": has_badges, "sections": sections}


# --- Helpers ---

_EXT_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".php": "php",
    ".vue": "vue",
    ".svelte": "svelte",
}


def _ext_to_lang(path: str) -> str:
    ext = Path(path).suffix.lower()
    return _EXT_MAP.get(ext, ext.lstrip("."))


def _detect_languages(files: list[str]) -> list[str]:
    from collections import Counter

    exts = Counter(Path(f).suffix.lower() for f in files if Path(f).suffix)
    langs = []
    for ext, _ in exts.most_common(8):
        lang = _EXT_MAP.get(ext)
        if lang and lang not in langs:
            langs.append(lang)
    return langs
