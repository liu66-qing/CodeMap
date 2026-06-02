"""Pattern matcher — detects common design patterns in code structure."""

from __future__ import annotations

import re
from typing import Any


_DESIGN_PATTERNS = {
    "factory": {
        "indicators": [r"class\s+\w*Factory", r"def\s+create_\w+", r"def\s+make_\w+"],
        "description": "Factory pattern: centralized object creation",
    },
    "observer": {
        "indicators": [r"def\s+(subscribe|notify|emit|on_)", r"class\s+\w*(Observer|Subscriber|Listener)"],
        "description": "Observer pattern: event subscription/notification",
    },
    "strategy": {
        "indicators": [r"class\s+\w*Strategy", r"class\s+\w*Policy"],
        "description": "Strategy pattern: pluggable algorithms",
    },
    "singleton": {
        "indicators": [r"_instance\s*=\s*None", r"@singleton", r"def\s+get_instance"],
        "description": "Singleton pattern: single instance enforcement",
    },
    "decorator": {
        "indicators": [r"@\w+\s*\n\s*def", r"def\s+\w+_decorator", r"functools\.wraps"],
        "description": "Decorator pattern: behavior wrapping",
    },
    "middleware": {
        "indicators": [r"middleware", r"class\s+\w*Middleware", r"def\s+\w*middleware"],
        "description": "Middleware pattern: request/response interceptor chain",
    },
    "registry": {
        "indicators": [r"class\s+\w*Registry", r"def\s+register", r"_registry\s*[:=]"],
        "description": "Registry pattern: name-based component lookup",
    },
    "adapter": {
        "indicators": [r"class\s+\w*Adapter", r"class\s+\w*Wrapper"],
        "description": "Adapter pattern: interface translation",
    },
    "repository": {
        "indicators": [r"class\s+\w*Repository", r"def\s+(find_by|save|delete|find_all)"],
        "description": "Repository pattern: data access abstraction",
    },
    "pipeline": {
        "indicators": [r"class\s+\w*Pipeline", r"def\s+\w*pipeline", r"\.pipe\("],
        "description": "Pipeline pattern: staged data transformation",
    },
}


async def match_patterns(file_contents: dict[str, str]) -> dict[str, Any]:
    """Match design patterns across file contents.

    Args:
        file_contents: {file_path: content}

    Returns: {
        "patterns": [{
            "name": str,
            "description": str,
            "matches": [{"file": str, "line": int, "snippet": str}],
            "confidence": float
        }]
    }
    """
    pattern_hits: dict[str, list[dict]] = {p: [] for p in _DESIGN_PATTERNS}

    for path, content in file_contents.items():
        for pattern_name, spec in _DESIGN_PATTERNS.items():
            for ind in spec["indicators"]:
                for m in re.finditer(ind, content, re.IGNORECASE):
                    line = content[: m.start()].count("\n") + 1
                    snippet = content[m.start() : m.start() + 120].split("\n")[0]
                    pattern_hits[pattern_name].append({
                        "file": path,
                        "line": line,
                        "snippet": snippet.strip(),
                    })

    patterns = []
    for name, hits in pattern_hits.items():
        if not hits:
            continue
        unique_files = len({h["file"] for h in hits})
        confidence = min(1.0, unique_files / 3)
        patterns.append({
            "name": name,
            "description": _DESIGN_PATTERNS[name]["description"],
            "matches": hits[:5],
            "match_count": len(hits),
            "files_involved": unique_files,
            "confidence": round(confidence, 2),
        })

    patterns.sort(key=lambda p: p["confidence"], reverse=True)
    return {"patterns": patterns}
