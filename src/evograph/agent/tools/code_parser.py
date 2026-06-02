"""Code parser tool — AST-based extraction of functions, classes, imports, and call relations.

Uses tree-sitter when available, falls back to regex-based heuristic parsing.
Returns structured data about code entities and their relationships.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


async def parse_code_structure(
    repo_url: str, files: list[str], file_contents: dict[str, str] | None = None
) -> dict[str, Any]:
    """Parse code structure from a list of files.

    Args:
        repo_url: repo URL or local path (used for local file reading if file_contents not provided)
        files: list of file paths to parse
        file_contents: optional pre-fetched file contents {path: content}

    Returns: {
        "modules": [...],
        "functions": [...],
        "classes": [...],
        "imports": [...],
        "call_relations": [...],
        "entry_points": [...]
    }
    """
    modules: list[dict] = []
    functions: list[dict] = []
    classes: list[dict] = []
    imports: list[dict] = []
    call_relations: list[dict] = []
    entry_points: list[str] = []

    for fpath in files:
        content = ""
        if file_contents and fpath in file_contents:
            content = file_contents[fpath]
        else:
            local = Path(repo_url) / fpath
            if local.is_file():
                try:
                    content = local.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

        if not content:
            continue

        lang = _detect_lang(fpath)
        parsed = _parse_file(fpath, content, lang)
        modules.append({"path": fpath, "language": lang, "lines": content.count("\n") + 1})
        functions.extend(parsed["functions"])
        classes.extend(parsed["classes"])
        imports.extend(parsed["imports"])
        call_relations.extend(parsed["calls"])

        if _is_entry_point(fpath, content, lang):
            entry_points.append(fpath)

    return {
        "modules": modules,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "call_relations": call_relations,
        "entry_points": entry_points,
    }


def _detect_lang(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }.get(ext, "unknown")


def _parse_file(path: str, content: str, lang: str) -> dict[str, list]:
    if lang == "python":
        return _parse_python(path, content)
    if lang in ("javascript", "typescript"):
        return _parse_js_ts(path, content)
    if lang == "go":
        return _parse_go(path, content)
    if lang == "java":
        return _parse_java(path, content)
    return {"functions": [], "classes": [], "imports": [], "calls": []}


def _parse_python(path: str, content: str) -> dict[str, list]:
    functions = []
    classes = []
    imports = []
    calls = []

    for m in re.finditer(r"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", content, re.MULTILINE):
        functions.append({
            "name": m.group(1),
            "file": path,
            "params": m.group(2).strip(),
            "line": content[: m.start()].count("\n") + 1,
        })

    for m in re.finditer(r"^class\s+(\w+)(?:\(([^)]*)\))?:", content, re.MULTILINE):
        classes.append({
            "name": m.group(1),
            "file": path,
            "bases": m.group(2) or "",
            "line": content[: m.start()].count("\n") + 1,
        })

    for m in re.finditer(r"^(?:from\s+([\w.]+)\s+)?import\s+(.+)$", content, re.MULTILINE):
        imports.append({
            "file": path,
            "from_module": m.group(1) or "",
            "names": m.group(2).strip(),
        })

    # Simple call detection: function_name(
    func_names = {f["name"] for f in functions}
    for m in re.finditer(r"(\w+)\s*\(", content):
        callee = m.group(1)
        if callee in func_names or callee[0].isupper():
            line = content[: m.start()].count("\n") + 1
            # Find enclosing function
            caller = _find_enclosing_function(content, m.start(), functions)
            if caller and caller != callee:
                calls.append({"caller": caller, "callee": callee, "file": path, "line": line})

    return {"functions": functions, "classes": classes, "imports": imports, "calls": calls}


def _parse_js_ts(path: str, content: str) -> dict[str, list]:
    functions = []
    classes = []
    imports = []
    calls = []

    # function declarations and arrow functions assigned to const/let/var
    for m in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", content):
        functions.append({"name": m.group(1), "file": path, "params": "", "line": content[: m.start()].count("\n") + 1})
    for m in re.finditer(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(", content):
        functions.append({"name": m.group(1), "file": path, "params": "", "line": content[: m.start()].count("\n") + 1})

    for m in re.finditer(r"class\s+(\w+)", content):
        classes.append({"name": m.group(1), "file": path, "bases": "", "line": content[: m.start()].count("\n") + 1})

    for m in re.finditer(r"import\s+.+?\s+from\s+['\"]([^'\"]+)['\"]", content):
        imports.append({"file": path, "from_module": m.group(1), "names": ""})

    return {"functions": functions, "classes": classes, "imports": imports, "calls": calls}


def _parse_go(path: str, content: str) -> dict[str, list]:
    functions = []
    for m in re.finditer(r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", content, re.MULTILINE):
        functions.append({"name": m.group(1), "file": path, "params": "", "line": content[: m.start()].count("\n") + 1})
    imports = []
    for m in re.finditer(r'"([^"]+)"', content[:2000]):
        if "/" in m.group(1):
            imports.append({"file": path, "from_module": m.group(1), "names": ""})
    return {"functions": functions, "classes": [], "imports": imports, "calls": []}


def _parse_java(path: str, content: str) -> dict[str, list]:
    functions = []
    classes = []
    for m in re.finditer(r"(?:public|private|protected)?\s*class\s+(\w+)", content):
        classes.append({"name": m.group(1), "file": path, "bases": "", "line": content[: m.start()].count("\n") + 1})
    for m in re.finditer(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", content):
        functions.append({"name": m.group(1), "file": path, "params": "", "line": content[: m.start()].count("\n") + 1})
    return {"functions": functions, "classes": classes, "imports": [], "calls": []}


def _find_enclosing_function(content: str, pos: int, functions: list[dict]) -> str | None:
    """Find which function encloses a given position."""
    best = None
    best_line = 0
    target_line = content[:pos].count("\n") + 1
    for f in functions:
        if f["line"] <= target_line and f["line"] > best_line:
            best = f["name"]
            best_line = f["line"]
    return best


def _is_entry_point(path: str, content: str, lang: str) -> bool:
    name = Path(path).stem.lower()
    if name in ("main", "app", "server", "index", "cli", "run", "manage"):
        return True
    if lang == "python" and 'if __name__' in content:
        return True
    if lang == "go" and "func main()" in content:
        return True
    return False
