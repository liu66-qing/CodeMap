"""Graph reviewer: the final critic in the understanding pipeline.

After the architecture analyzer and tour builder produce their views, this agent
cross-checks them against each other and against the ground-truth graph, looking
for contradictions, omissions, and likely misclassifications — then emits a
corrected, confidence-annotated final summary plus a human-readable report.

It pairs deterministic consistency checks (which never lie) with an optional LLM
pass (which catches semantic mistakes the rules can't). The deterministic checks
always run; the LLM only refines. So even with no LLM the reviewer adds value.

Deterministic checks:
    - layers reference modules that actually exist in the graph
    - tour steps reference symbols that actually exist
    - every analyzed module is placed in some layer (coverage / omission)
    - declared patterns cite modules that exist

Output (`review`) is JSON-able:
    {
      "issues":  [{"severity", "kind", "detail"}],
      "coverage": {"modules_total", "modules_placed", "unplaced": [...]},
      "report":  "natural-language review",
      "confidence": 0.0-1.0,
      "generated_by": "llm" | "deterministic"
    }
and the reviewer also returns a (possibly corrected) architecture summary.
"""

from __future__ import annotations

import json

import structlog

from evograph.agent.analyzers.graph_view import CodeGraphView

logger = structlog.get_logger()


def _is_glob(ref: str) -> bool:
    """A citation that's a wildcard/path pattern, not a concrete symbol name."""
    return any(ch in ref for ch in ("*", "?", "/", " ")) or ref.endswith(".")


def _deterministic_checks(view: CodeGraphView, architecture: dict, tour: dict) -> dict:
    """Ground-truth consistency checks. Returns issues + coverage."""
    known_nodes = {n.name for n in view.nodes}
    known_modules = {n.name for n in view.nodes_of_kind("module")}
    issues: list[dict] = []

    # 1. Layers must reference real modules; collect placement for coverage.
    placed: set[str] = set()
    for layer in architecture.get("layers", []):
        for mod in layer.get("modules", []):
            placed.add(mod)
            if mod not in known_nodes and mod not in known_modules:
                issues.append({
                    "severity": "warning",
                    "kind": "phantom_module",
                    "detail": f"层 '{layer.get('name')}' 引用了图谱中不存在的模块: {mod}",
                })

    # 2. Coverage: modules that exist but no layer placed them.
    unplaced = sorted(m for m in known_modules if m not in placed)
    if unplaced:
        issues.append({
            "severity": "info",
            "kind": "omission",
            "detail": f"{len(unplaced)} 个模块未被归入任何分层。",
        })

    # 3. Pattern citations must reference real symbols/modules. Wildcard or glob
    #    citations (e.g. "app.api.routes.*", "services/") are illustrative, not
    #    node references, so we don't flag them as phantom.
    for pat in architecture.get("patterns", []):
        for mod in pat.get("modules", []):
            if not mod or _is_glob(mod):
                continue
            if mod not in known_nodes:
                issues.append({
                    "severity": "warning",
                    "kind": "phantom_pattern_ref",
                    "detail": f"模式 '{pat.get('name')}' 引用了不存在的符号: {mod}",
                })

    # 4. Tour steps must reference real symbols.
    for step in tour.get("steps", []):
        sym = step.get("symbol")
        if sym and sym not in known_nodes:
            issues.append({
                "severity": "error",
                "kind": "phantom_tour_step",
                "detail": f"导览第 {step.get('order')} 步引用了不存在的符号: {sym}",
            })

    coverage = {
        "modules_total": len(known_modules),
        "modules_placed": len(placed & known_modules),
        "unplaced": unplaced[:20],
    }
    return {"issues": issues, "coverage": coverage}


def _correct_architecture(architecture: dict, view: CodeGraphView) -> dict:
    """Drop phantom module references so the persisted summary is self-consistent."""
    known = {n.name for n in view.nodes}
    fixed = dict(architecture)
    fixed_layers = []
    for layer in architecture.get("layers", []):
        mods = [m for m in layer.get("modules", []) if m in known]
        fixed_layers.append({**layer, "modules": mods})
    fixed["layers"] = fixed_layers
    fixed_patterns = []
    for pat in architecture.get("patterns", []):
        # Keep concrete refs that exist + illustrative glob/path citations.
        mods = [m for m in pat.get("modules", []) if m in known or _is_glob(m)]
        fixed_patterns.append({**pat, "modules": mods})
    fixed["patterns"] = fixed_patterns
    return fixed


def _confidence_from_issues(issues: list[dict]) -> float:
    """Map issue severities to a 0-1 confidence. Errors hurt most."""
    penalty = 0.0
    for i in issues:
        penalty += {"error": 0.25, "warning": 0.1, "info": 0.02}.get(i.get("severity"), 0.05)
    return max(0.0, round(1.0 - penalty, 2))


_PROMPT = """你是一名严谨的代码分析评审员。下面有:
(A) 架构分析结果, (B) 代码导览, (C) 程序自动发现的一致性问题清单。

请审查 A 和 B 是否存在:矛盾、明显遗漏、分类错误或表述不清。结合 C 的问题,给出一段中文评审意见(report),并给出一个 0~1 的整体可信度(confidence)。

(A) 架构:
{architecture}

(B) 导览(仅步骤符号与说明):
{tour}

(C) 自动发现的问题:
{issues}

只输出 JSON:{{"report": "评审意见", "confidence": 0.0~1.0, "extra_issues": [{{"severity","kind","detail"}}]}}。"""


async def _review_with_llm(architecture: dict, tour: dict, det_issues: list[dict]) -> dict | None:
    from evograph.config import settings
    if not settings.llm_api_key:
        return None
    from evograph.llm.client import llm_client

    arch_brief = {
        "summary": architecture.get("summary", ""),
        "layers": [{"name": l.get("name"), "modules": l.get("modules", [])[:10]}
                   for l in architecture.get("layers", [])],
        "patterns": [p.get("name") for p in architecture.get("patterns", [])],
    }
    tour_brief = [{"order": s.get("order"), "symbol": s.get("symbol"),
                   "explanation": s.get("explanation")} for s in tour.get("steps", [])]
    try:
        raw = await llm_client.chat_json(messages=[{"role": "user", "content": _PROMPT.format(
            architecture=json.dumps(arch_brief, ensure_ascii=False),
            tour=json.dumps(tour_brief, ensure_ascii=False),
            issues=json.dumps(det_issues, ensure_ascii=False),
        )}])
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception as exc:
        logger.warning("review_llm_failed", error=str(exc))
        return None


async def review_graph(view: CodeGraphView, architecture: dict, tour: dict) -> tuple[dict, dict]:
    """Public entry: review the upstream outputs and correct the architecture.

    Returns (corrected_architecture, review). Never raises.
    """
    det = _deterministic_checks(view, architecture, tour)
    issues = list(det["issues"])
    corrected = _correct_architecture(architecture, view)

    llm = await _review_with_llm(architecture, tour, issues)
    if llm is not None:
        issues.extend(i for i in llm.get("extra_issues", []) if isinstance(i, dict))
        review = {
            "issues": issues,
            "coverage": det["coverage"],
            "report": llm.get("report", ""),
            "confidence": float(llm.get("confidence", _confidence_from_issues(issues))),
            "generated_by": "llm",
        }
    else:
        n = len(issues)
        report = (
            f"自动评审完成:发现 {n} 处一致性问题"
            f"({sum(1 for i in issues if i['severity'] == 'error')} 错误 / "
            f"{sum(1 for i in issues if i['severity'] == 'warning')} 警告)。"
            f"模块覆盖率 {det['coverage']['modules_placed']}/{det['coverage']['modules_total']}。"
        )
        review = {
            "issues": issues,
            "coverage": det["coverage"],
            "report": report,
            "confidence": _confidence_from_issues(issues),
            "generated_by": "deterministic",
        }
    return corrected, review
