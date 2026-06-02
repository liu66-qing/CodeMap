"""Architecture detector — heuristic detection of architectural patterns.

Identifies layering, common patterns (MVC, microservices, plugin, etc.),
and module boundaries from file structure and code relationships.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# Common directory patterns that indicate architecture layers
_LAYER_PATTERNS = {
    "api": ["api", "routes", "handlers", "controllers", "endpoints", "views"],
    "service": ["services", "service", "usecases", "use_cases", "domain"],
    "data": ["models", "entities", "schemas", "db", "database", "repositories", "repo"],
    "infra": ["infra", "infrastructure", "config", "middleware", "utils", "helpers", "lib"],
    "ui": ["components", "pages", "views", "templates", "ui", "frontend"],
    "test": ["tests", "test", "__tests__", "spec", "specs"],
}

_ARCH_PATTERNS = {
    "mvc": {"indicators": ["controllers", "models", "views"], "min_match": 3},
    "layered": {"indicators": ["api", "service", "repository"], "min_match": 2},
    "hexagonal": {"indicators": ["ports", "adapters", "domain"], "min_match": 2},
    "microservice": {"indicators": ["docker-compose", "proto", "grpc"], "min_match": 2},
    "plugin": {"indicators": ["plugins", "extensions", "hooks"], "min_match": 1},
    "event_driven": {"indicators": ["events", "handlers", "subscribers", "listeners"], "min_match": 2},
    "monorepo": {"indicators": ["packages", "apps", "libs"], "min_match": 2},
}


async def detect_architecture(
    files: list[str],
    directories: list[str] | None = None,
    imports: list[dict] | None = None,
) -> dict[str, Any]:
    """Detect architectural patterns from file structure.

    Returns: {
        "layers": [{"name": str, "directories": [...], "file_count": int}],
        "patterns": [{"name": str, "confidence": float, "evidence": [...]}],
        "boundaries": [{"from": str, "to": str, "coupling": str}],
        "style": str,
        "summary": str
    }
    """
    dirs = directories or _extract_dirs(files)
    dir_lower = [d.lower() for d in dirs]
    file_lower = [f.lower() for f in files]

    # Detect layers
    layers = _detect_layers(dirs, files)

    # Detect patterns
    patterns = _detect_patterns(dir_lower, file_lower)

    # Detect boundaries (module coupling)
    boundaries = _detect_boundaries(imports or [])

    # Determine overall style
    style = "unknown"
    if patterns:
        style = patterns[0]["name"]

    summary = _generate_summary(layers, patterns, len(files))

    return {
        "layers": layers,
        "patterns": patterns,
        "boundaries": boundaries,
        "style": style,
        "summary": summary,
    }


def _extract_dirs(files: list[str]) -> list[str]:
    dirs = set()
    for f in files:
        parts = Path(f).parts
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return sorted(dirs)


def _detect_layers(dirs: list[str], files: list[str]) -> list[dict]:
    layers = []
    for layer_name, keywords in _LAYER_PATTERNS.items():
        matched_dirs = []
        file_count = 0
        for d in dirs:
            d_lower = d.lower().split("/")[-1]
            if d_lower in keywords:
                matched_dirs.append(d)
                file_count += sum(1 for f in files if f.startswith(d + "/") or f.startswith(d + "\\"))
        if matched_dirs:
            layers.append({
                "name": layer_name,
                "directories": matched_dirs,
                "file_count": file_count,
            })
    return layers


def _detect_patterns(dir_lower: list[str], file_lower: list[str]) -> list[dict]:
    patterns = []
    all_names = set()
    for d in dir_lower:
        all_names.update(d.split("/"))
    for f in file_lower:
        all_names.add(Path(f).stem)

    for pattern_name, spec in _ARCH_PATTERNS.items():
        evidence = [ind for ind in spec["indicators"] if ind in all_names]
        if len(evidence) >= spec["min_match"]:
            confidence = min(1.0, len(evidence) / len(spec["indicators"]))
            patterns.append({
                "name": pattern_name,
                "confidence": round(confidence, 2),
                "evidence": evidence,
            })

    patterns.sort(key=lambda p: p["confidence"], reverse=True)
    return patterns


def _detect_boundaries(imports: list[dict]) -> list[dict]:
    """Detect module coupling from import relations."""
    coupling: dict[tuple[str, str], int] = Counter()
    for imp in imports:
        src_module = _top_module(imp.get("file", ""))
        target = imp.get("from_module", "")
        if target.startswith("."):
            continue
        tgt_module = target.split(".")[0] if "." in target else target
        if src_module and tgt_module and src_module != tgt_module:
            coupling[(src_module, tgt_module)] += 1

    boundaries = []
    for (src, tgt), count in coupling.most_common(10):
        boundaries.append({
            "from": src,
            "to": tgt,
            "coupling": "high" if count > 5 else "medium" if count > 2 else "low",
        })
    return boundaries


def _top_module(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2:
        return parts[0] if parts[0] != "src" else parts[1] if len(parts) > 2 else parts[0]
    return ""


def _generate_summary(layers: list[dict], patterns: list[dict], total_files: int) -> str:
    parts = []
    if patterns:
        parts.append(f"Architecture style: {patterns[0]['name']}")
    if layers:
        layer_names = [l["name"] for l in layers]
        parts.append(f"Layers: {', '.join(layer_names)}")
    parts.append(f"Total files: {total_files}")
    return ". ".join(parts)
