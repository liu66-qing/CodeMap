"""Quickstart extractor: tells the user how to run the project.

Scans the repo's on-disk clone for well-known config files (package.json,
pyproject.toml, Makefile, Dockerfile, requirements.txt, README) and extracts:
- install commands (pip install, npm install, etc.)
- run/start commands (npm start, python main.py, uvicorn, etc.)
- detected entry points (main.py, app.py, manage.py, index.ts, etc.)
- tech stack (frameworks, languages)
- a short README excerpt (first meaningful paragraph)

All deterministic parsing — no LLM needed. This powers the "快速上手" panel that
tells a newcomer "here's how to get this running" (step 1 of reading a codebase).
"""

from __future__ import annotations

import json
import os
import re

import structlog

from evograph.ingestion.source_reader import get_repo_location

logger = structlog.get_logger()

# Well-known entry point filenames (checked in order of priority).
_ENTRY_FILES = [
    "main.py", "app.py", "manage.py", "server.py", "run.py", "cli.py",
    "index.ts", "index.js", "main.ts", "main.js", "app.ts", "app.js",
    "main.go", "cmd/main.go", "Main.java", "Program.cs",
]


def _read_file(root: str, rel: str, max_bytes: int = 50000) -> str | None:
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except OSError:
        return None


def _extract_package_json(root: str) -> dict:
    """Extract from package.json: scripts, dependencies (framework detection)."""
    raw = _read_file(root, "package.json")
    if not raw:
        return {}
    try:
        pkg = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    scripts = pkg.get("scripts", {})
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    install = "npm install" if os.path.isfile(os.path.join(root, "package-lock.json")) else (
        "pnpm install" if os.path.isfile(os.path.join(root, "pnpm-lock.yaml")) else
        "yarn install" if os.path.isfile(os.path.join(root, "yarn.lock")) else "npm install"
    )
    run = scripts.get("start") or scripts.get("dev") or scripts.get("serve") or ""
    run_cmd = f"npm run {next((k for k in ('start','dev','serve') if k in scripts), 'start')}" if run else ""
    frameworks = []
    for fw in ("react", "vue", "angular", "next", "nuxt", "svelte", "express", "fastify", "nest"):
        if fw in deps or f"@{fw}" in " ".join(deps.keys()):
            frameworks.append(fw)
    return {"install": install, "run": run_cmd, "frameworks": frameworks, "scripts": scripts}


def _extract_pyproject(root: str) -> dict:
    """Extract from pyproject.toml: project scripts, dependencies."""
    raw = _read_file(root, "pyproject.toml")
    if not raw:
        return {}
    install = "pip install -e ." if "[project]" in raw else "pip install -r requirements.txt"
    # Look for [project.scripts] or [tool.poetry.scripts]
    run = ""
    m = re.search(r'\[project\.scripts\]\s*\n([^\[]+)', raw)
    if m:
        first_script = m.group(1).strip().split("\n")[0]
        name = first_script.split("=")[0].strip().strip('"')
        if name:
            run = name
    frameworks = []
    for fw in ("fastapi", "flask", "django", "streamlit", "gradio", "celery", "langchain"):
        if fw in raw.lower():
            frameworks.append(fw)
    return {"install": install, "run": run, "frameworks": frameworks}


def _extract_requirements(root: str) -> dict:
    raw = _read_file(root, "requirements.txt")
    if not raw:
        return {}
    frameworks = []
    for fw in ("fastapi", "flask", "django", "streamlit", "gradio", "celery", "langchain", "torch", "tensorflow"):
        if fw in raw.lower():
            frameworks.append(fw)
    return {"install": "pip install -r requirements.txt", "frameworks": frameworks}


def _extract_dockerfile(root: str) -> dict:
    raw = _read_file(root, "Dockerfile")
    if not raw:
        return {}
    # Look for CMD/ENTRYPOINT
    run = ""
    for line in raw.splitlines():
        if line.strip().startswith(("CMD", "ENTRYPOINT")):
            run = line.strip()
            break
    return {"docker_run": run, "has_docker": True}


def _extract_makefile(root: str) -> dict:
    raw = _read_file(root, "Makefile")
    if not raw:
        return {}
    targets = re.findall(r'^(\w[\w-]*):', raw, re.MULTILINE)
    run_targets = [t for t in targets if t in ("run", "start", "serve", "dev", "up")]
    return {"make_targets": targets[:10], "run_target": run_targets[0] if run_targets else ""}


def _extract_readme_excerpt(root: str) -> str:
    for name in ("README.md", "README.rst", "README.txt", "README"):
        raw = _read_file(root, name, max_bytes=8000)
        if raw:
            # Skip title lines (# ...) and badges, find first real paragraph.
            lines = raw.split("\n")
            para = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", "![", "[![", "---", "===")):
                    if para:
                        break
                    continue
                para.append(stripped)
            return " ".join(para)[:500] if para else ""
    return ""


def _find_entry_points(root: str) -> list[str]:
    found = []
    for ep in _ENTRY_FILES:
        if os.path.isfile(os.path.join(root, ep)):
            found.append(ep)
    return found


async def extract_quickstart(repo_id: str) -> dict:
    """Public entry: extract quickstart info for a repo. Returns a dict with
    install, run, entrypoints, stack, readme_excerpt. Never raises."""
    loc = await get_repo_location(repo_id)
    if not loc:
        return {"available": False, "message": "仓库本地路径未知"}

    # If there's a path_prefix (monorepo sub-app), look inside that subtree.
    root = loc.local_path
    subroot = os.path.join(root, loc.path_prefix.rstrip("/")) if loc.path_prefix else root
    # Prefer the subroot for config files; fall back to repo root.
    effective = subroot if os.path.isdir(subroot) else root

    pkg = _extract_package_json(effective)
    pyp = _extract_pyproject(effective)
    req = _extract_requirements(effective)
    docker = _extract_dockerfile(effective)
    make = _extract_makefile(effective)
    readme = _extract_readme_excerpt(effective) or _extract_readme_excerpt(root)
    entries = _find_entry_points(effective)

    # Merge: pick the best install/run from available sources.
    install = pkg.get("install") or pyp.get("install") or req.get("install") or ""
    run = pkg.get("run") or pyp.get("run") or (f"make {make['run_target']}" if make.get("run_target") else "") or ""
    if not run and entries:
        # Guess a run command from the entry point.
        ep = entries[0]
        if ep.endswith(".py"):
            run = f"python {ep}"
        elif ep.endswith((".ts", ".js")):
            run = f"npx ts-node {ep}" if ep.endswith(".ts") else f"node {ep}"

    frameworks = list(dict.fromkeys(
        pkg.get("frameworks", []) + pyp.get("frameworks", []) + req.get("frameworks", [])
    ))

    return {
        "available": True,
        "install": install,
        "run": run,
        "entrypoints": entries,
        "stack": frameworks,
        "has_docker": docker.get("has_docker", False),
        "docker_cmd": docker.get("docker_run", ""),
        "make_targets": make.get("make_targets", []),
        "readme_excerpt": readme,
        "scripts": pkg.get("scripts", {}),
    }
