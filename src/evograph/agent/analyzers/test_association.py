"""Test association: links test functions to the production symbols they test.

This is a query-time computation (not a pipeline stage) that works on any
already-ingested repo. It uses three signals to associate tests:

1. **Naming convention**: `test_foo` or `TestFoo` → look for `foo` / `Foo` in the graph.
2. **CALLS edges**: if a test function calls a production function, that's a direct test.
3. **File-level imports**: test file imports from module X → tests symbols in X.

The result is a list of {test_symbol, tested_symbol, confidence, reason} pairs.
This powers the "相关测试" section in the symbol detail panel — showing users
"here's how this function is used" via its tests (the best usage documentation).
"""

from __future__ import annotations

import re
from collections import defaultdict

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView, GraphNode

logger = structlog.get_logger()


def _is_test_file(file_path: str) -> bool:
    """Heuristic: is this file path a test file?"""
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/tests/" in file_path
        or "/test/" in file_path
        or file_path.startswith("tests/")
        or file_path.startswith("test/")
    )


def _is_test_symbol(name: str, file_path: str) -> bool:
    """Is this symbol a test function/class?"""
    simple = name.rsplit(".", 1)[-1]
    return (
        simple.startswith("test_")
        or simple.startswith("Test")
        or _is_test_file(file_path)
    )


def _extract_tested_name(test_name: str) -> str | None:
    """From 'test_foo_bar' extract 'foo_bar'; from 'TestFooBar' extract 'FooBar'."""
    simple = test_name.rsplit(".", 1)[-1]
    if simple.startswith("test_"):
        candidate = simple[5:]  # strip "test_"
        return candidate if candidate else None
    if simple.startswith("Test"):
        candidate = simple[4:]  # strip "Test"
        return candidate if candidate else None
    return None


def find_test_associations(view: CodeGraphView) -> list[dict]:
    """Find test→production associations in the graph. Returns a list of
    {test_symbol, tested_symbol, confidence, reason} dicts."""

    # Partition symbols into test vs production.
    test_symbols: list[GraphNode] = []
    prod_by_simple: dict[str, list[GraphNode]] = defaultdict(list)
    prod_by_name: dict[str, GraphNode] = {}

    for n in view.nodes:
        if n.kind == "module":
            continue
        if _is_test_symbol(n.name, n.file_path):
            test_symbols.append(n)
        else:
            simple = n.name.rsplit(".", 1)[-1].lower()
            prod_by_simple[simple].append(n)
            prod_by_name[n.name] = n

    associations: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for t in test_symbols:
        # Signal 1: naming convention.
        candidate_name = _extract_tested_name(t.name)
        if candidate_name:
            matches = prod_by_simple.get(candidate_name.lower(), [])
            for m in matches:
                key = (t.name, m.name)
                if key not in seen:
                    seen.add(key)
                    associations.append({
                        "test_symbol": t.name,
                        "tested_symbol": m.name,
                        "confidence": 0.9,
                        "reason": "naming_convention",
                    })

        # Signal 2: CALLS edges from this test to production symbols.
        for callee_name in view.callees(t.name):
            callee = prod_by_name.get(callee_name)
            if callee and not _is_test_symbol(callee.name, callee.file_path):
                key = (t.name, callee.name)
                if key not in seen:
                    seen.add(key)
                    associations.append({
                        "test_symbol": t.name,
                        "tested_symbol": callee.name,
                        "confidence": 0.8,
                        "reason": "calls_edge",
                    })

    # Sort by tested_symbol for easy lookup.
    associations.sort(key=lambda a: (a["tested_symbol"], -a["confidence"]))
    return associations


def get_tests_for_symbol(view: CodeGraphView, symbol: str) -> list[dict]:
    """Get all tests that test a specific symbol. Returns [{test_symbol, confidence, reason}]."""
    all_assoc = find_test_associations(view)
    return [
        {"test_symbol": a["test_symbol"], "confidence": a["confidence"], "reason": a["reason"]}
        for a in all_assoc
        if a["tested_symbol"] == symbol or a["tested_symbol"].endswith("." + symbol)
    ]
