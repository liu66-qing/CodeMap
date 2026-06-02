"""Unit tests for the code-understanding analyzers.

These exercise the DETERMINISTIC paths only — the LLM is forced off by clearing
the api_key, so tests are reproducible and offline. They verify the graph view,
the architecture heuristic, the tour walk (BFS ordering, cycle safety, entry
detection), and the reviewer's consistency checks.
"""

from __future__ import annotations

import pytest

from evograph.agent.analyzers.graph_view import CodeGraphView, GraphNode, GraphEdge
from evograph.agent.analyzers import architecture_analyzer as A
from evograph.agent.analyzers import tour_builder as T
from evograph.agent.analyzers import graph_reviewer as R
from evograph.agent.analyzers import learning_path as LP
from evograph.agent.analyzers import module_cards as MC
from evograph.agent.analyzers import test_association as TA


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Force the heuristic/structural fallback so tests never hit the network."""
    from evograph.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)


@pytest.fixture
def layered_view() -> CodeGraphView:
    """A tiny controller -> service -> repo system."""
    nodes = [
        GraphNode("app.api.controller", "module"),
        GraphNode("app.service.user_service", "module"),
        GraphNode("app.repo.user_repo", "module"),
        GraphNode("app.api.controller.get_user", "function", "get_user(uid)", "api.py", "Handle GET /user"),
        GraphNode("app.service.user_service.load", "function", "load(uid)", "svc.py", "Load a user"),
        GraphNode("app.repo.user_repo.fetch", "function", "fetch(uid)", "repo.py", "DB fetch"),
    ]
    edges = [
        GraphEdge("app.api.controller", "app.api.controller.get_user", "DEFINES"),
        GraphEdge("app.service.user_service", "app.service.user_service.load", "DEFINES"),
        GraphEdge("app.repo.user_repo", "app.repo.user_repo.fetch", "DEFINES"),
        GraphEdge("app.api.controller.get_user", "app.service.user_service.load", "CALLS"),
        GraphEdge("app.service.user_service.load", "app.repo.user_repo.fetch", "CALLS"),
    ]
    return CodeGraphView("demo", nodes, edges)


class TestCodeGraphView:
    def test_indexes(self, layered_view):
        v = layered_view
        assert v.get("app.api.controller.get_user").kind == "function"
        assert v.callees("app.api.controller.get_user") == ["app.service.user_service.load"]
        assert v.callers("app.service.user_service.load") == ["app.api.controller.get_user"]
        assert {n.name for n in v.nodes_of_kind("module")} == {
            "app.api.controller", "app.service.user_service", "app.repo.user_repo"
        }

    def test_empty(self):
        assert CodeGraphView("x", [], []).is_empty


class TestArchitecture:
    async def test_layers_detected_heuristically(self, layered_view):
        result = await A.analyze_architecture(layered_view)
        assert result["generated_by"] == "heuristic"
        # Naming hints should split the three modules into distinct layers.
        all_modules = [m for layer in result["layers"] for m in layer["modules"]]
        assert "app.api.controller" in all_modules
        assert "app.repo.user_repo" in all_modules
        assert result["module_count"] == 3

    async def test_empty_graph(self):
        result = await A.analyze_architecture(CodeGraphView("x", [], []))
        assert result["generated_by"] == "empty"
        assert result["layers"] == []

    def test_fan_in_out(self, layered_view):
        features = {f["module"]: f for f in A.compute_module_features(layered_view)}
        # service is called by controller (fan_in) and calls repo (fan_out).
        assert features["app.service.user_service"]["fan_in"] >= 1
        assert features["app.service.user_service"]["fan_out"] >= 1


class TestTour:
    async def test_walks_call_chain_in_order(self, layered_view):
        tour = await T.build_tour(layered_view)
        symbols = [s["symbol"] for s in tour["steps"]]
        assert symbols == [
            "app.api.controller.get_user",
            "app.service.user_service.load",
            "app.repo.user_repo.fetch",
        ]
        assert tour["generated_by"] == "structural"
        # Each step gets a non-empty explanation (from docstring fallback).
        assert all(s["explanation"] for s in tour["steps"])

    async def test_explicit_entry_by_simple_name(self, layered_view):
        tour = await T.build_tour(layered_view, entry_point="load")
        assert tour["entry_point"] == "app.service.user_service.load"
        assert tour["auto_detected"] is False

    def test_cycle_safety(self):
        # a -> b -> a : must terminate and visit each once.
        nodes = [GraphNode("m.a", "function"), GraphNode("m.b", "function")]
        edges = [GraphEdge("m.a", "m.b", "CALLS"), GraphEdge("m.b", "m.a", "CALLS")]
        v = CodeGraphView("c", nodes, edges)
        steps = T.build_call_path(v, "m.a")
        assert [s["symbol"] for s in steps] == ["m.a", "m.b"]

    async def test_entry_detection_prefers_main(self):
        nodes = [
            GraphNode("app.main", "function"),
            GraphNode("app.helper", "function"),
            GraphNode("app.leaf", "function"),
        ]
        edges = [GraphEdge("app.main", "app.helper", "CALLS"),
                 GraphEdge("app.helper", "app.leaf", "CALLS")]
        v = CodeGraphView("e", nodes, edges)
        entry, auto = T.detect_entry_point(v)
        assert entry == "app.main"
        assert auto is True


class TestReviewer:
    async def test_clean_graph_high_confidence(self, layered_view):
        arch = await A.analyze_architecture(layered_view)
        tour = await T.build_tour(layered_view)
        corrected, review = await R.review_graph(layered_view, arch, tour)
        assert review["generated_by"] == "deterministic"
        assert review["confidence"] >= 0.7
        # No phantom references in a self-consistent graph.
        assert not any(i["kind"] == "phantom_tour_step" for i in review["issues"])

    async def test_detects_phantom_module(self, layered_view):
        bad_arch = {
            "layers": [{"name": "Ghost", "description": "", "modules": ["does.not.exist"]}],
            "patterns": [], "boundaries": [], "summary": "", "generated_by": "heuristic",
        }
        empty_tour = {"steps": []}
        corrected, review = await R.review_graph(layered_view, bad_arch, empty_tour)
        assert any(i["kind"] == "phantom_module" for i in review["issues"])
        # Correction strips the phantom module.
        assert corrected["layers"][0]["modules"] == []

    async def test_glob_pattern_ref_not_flagged(self, layered_view):
        # Wildcard citations in patterns are illustrative, not phantom refs.
        arch = {
            "layers": [], "summary": "", "generated_by": "llm",
            "patterns": [{"name": "Layered", "evidence": "x", "modules": ["app.api.*"]}],
            "boundaries": [],
        }
        _, review = await R.review_graph(layered_view, arch, {"steps": []})
        assert not any(i["kind"] == "phantom_pattern_ref" for i in review["issues"])


class TestLearningPath:
    @pytest.fixture
    def arch(self):
        return {
            "layers": [
                {"name": "接口层", "modules": ["app.api.controller"]},
                {"name": "业务层", "modules": ["app.service.user_service"]},
                {"name": "数据层", "modules": ["app.repo.user_repo"]},
            ]
        }

    def test_orders_top_down_by_layer(self, layered_view, arch):
        steps = LP.build_learning_path(layered_view, arch, max_steps=6)
        layers = [s["layer"] for s in steps]
        # Interface must come before service, service before data.
        assert layers.index("interface") < layers.index("service")
        assert layers.index("service") < layers.index("data")

    def test_skips_bare_modules(self, layered_view, arch):
        steps = LP.build_learning_path(layered_view, arch, max_steps=10)
        assert all(s["kind"] in ("function", "method", "class") for s in steps)

    async def test_annotated_structural_fallback(self, layered_view, arch):
        result = await LP.build_learning_path_annotated(layered_view, arch)
        assert result["generated_by"] == "structural"
        assert all(s["reason"] for s in result["steps"])

    async def test_empty_graph(self):
        result = await LP.build_learning_path_annotated(CodeGraphView("x", [], []))
        assert result["generated_by"] == "empty"
        assert result["steps"] == []


class TestModuleCards:
    @pytest.fixture
    def arch(self):
        return {"layers": [
            {"name": "接口层", "modules": ["app.api.controller"]},
            {"name": "业务层", "modules": ["app.service.user_service"]},
            {"name": "数据层", "modules": ["app.repo.user_repo"]},
        ]}

    def test_groups_symbols_into_cards(self, layered_view, arch):
        cards, edges = MC.build_cards(layered_view, arch)
        ids = {c["id"] for c in cards}
        # depth-2 module keys become cards
        assert "app.api" in ids and "app.service" in ids and "app.repo" in ids
        for c in cards:
            assert c["complexity"] in ("simple", "moderate", "complex")
            assert "layer" in c and "entities" in c and "symbols" in c

    def test_aggregates_inter_module_edges(self, layered_view, arch):
        _, edges = MC.build_cards(layered_view, arch)
        # controller->service->repo collapses to module-level CALLS edges
        pairs = {(e["source"], e["target"]) for e in edges if e["type"] == "CALLS"}
        assert ("app.api", "app.service") in pairs
        assert all(e["weight"] >= 1 for e in edges)

    async def test_module_map_has_meta(self, layered_view, arch):
        m = await MC.build_module_map(layered_view, arch)
        assert m["generated_by"] == "structural"
        assert m["meta"]["nodes"] == len(layered_view.nodes)
        assert all(c["summary"] for c in m["cards"])

    async def test_empty(self):
        m = await MC.build_module_map(CodeGraphView("x", [], []))
        assert m["generated_by"] == "empty"
        assert m["cards"] == []


class TestTestAssociation:
    def test_naming_convention(self):
        """test_foo should associate with foo by naming."""
        nodes = [
            GraphNode("app.service.foo", "function", file_path="app/service.py"),
            GraphNode("tests.test_service.test_foo", "function", file_path="tests/test_service.py"),
        ]
        edges = []
        v = CodeGraphView("t", nodes, edges)
        assoc = TA.find_test_associations(v)
        assert len(assoc) == 1
        assert assoc[0]["tested_symbol"] == "app.service.foo"
        assert assoc[0]["test_symbol"] == "tests.test_service.test_foo"
        assert assoc[0]["reason"] == "naming_convention"

    def test_calls_edge(self):
        """A test that calls a production function should associate via calls."""
        nodes = [
            GraphNode("app.util.helper", "function", file_path="app/util.py"),
            GraphNode("tests.test_util.test_something", "function", file_path="tests/test_util.py"),
        ]
        edges = [GraphEdge("tests.test_util.test_something", "app.util.helper", "CALLS")]
        v = CodeGraphView("t", nodes, edges)
        assoc = TA.find_test_associations(v)
        assert any(a["tested_symbol"] == "app.util.helper" and a["reason"] == "calls_edge" for a in assoc)

    def test_get_tests_for_symbol(self):
        nodes = [
            GraphNode("app.core.process", "function", file_path="app/core.py"),
            GraphNode("tests.test_core.test_process", "function", file_path="tests/test_core.py"),
            GraphNode("tests.test_core.test_other", "function", file_path="tests/test_core.py"),
        ]
        edges = [GraphEdge("tests.test_core.test_other", "app.core.process", "CALLS")]
        v = CodeGraphView("t", nodes, edges)
        tests = TA.get_tests_for_symbol(v, "app.core.process")
        assert len(tests) == 2  # one by naming, one by calls

    def test_no_false_positives_between_tests(self):
        """Tests should not associate with other tests."""
        nodes = [
            GraphNode("tests.test_a.test_foo", "function", file_path="tests/test_a.py"),
            GraphNode("tests.test_b.test_bar", "function", file_path="tests/test_b.py"),
        ]
        edges = [GraphEdge("tests.test_a.test_foo", "tests.test_b.test_bar", "CALLS")]
        v = CodeGraphView("t", nodes, edges)
        assoc = TA.find_test_associations(v)
        assert len(assoc) == 0  # no test-to-test associations
