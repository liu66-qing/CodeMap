"""Learning path planner: recommends stage order + estimated time.

Three path levels:
  - quick (30min): overview only, skim mainflow
  - standard (1.5h): all 4 stages at normal depth
  - deep (5h): all 4 stages + revisit highlights + copy patterns

Path is adjusted based on current progress — completed stages are skipped
and replaced with "revisit" suggestions for spaced repetition.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PathStep:
    stage: str
    title: str
    action: str  # "learn" | "revisit" | "skim"
    estimated_minutes: int
    description: str
    status: str = "pending"  # pending | done | skipped


STAGE_META = {
    "overview": {
        "title": "先看门道",
        "learn_minutes": 15,
        "skim_minutes": 5,
        "revisit_minutes": 5,
        "learn_desc": "了解仓库定位、核心问题和心智模型",
        "skim_desc": "快速浏览定位和阅读顺序",
        "revisit_desc": "回顾心智模型，强化记忆",
    },
    "mainflow": {
        "title": "跑通主线",
        "learn_minutes": 25,
        "skim_minutes": 10,
        "revisit_minutes": 8,
        "learn_desc": "跟踪主请求流程，理解调用链",
        "skim_desc": "浏览流程节点，了解大致路径",
        "revisit_desc": "复习流程节点的关键步骤",
    },
    "showcase": {
        "title": "拆它绝活",
        "learn_minutes": 30,
        "skim_minutes": 12,
        "revisit_minutes": 10,
        "learn_desc": "深入 3 个设计亮点，理解 tradeoff",
        "skim_desc": "快速了解亮点标题和方案",
        "revisit_desc": "重读 tradeoff 分析，对比自己经验",
    },
    "takeaway": {
        "title": "抄走一招",
        "learn_minutes": 20,
        "skim_minutes": 8,
        "revisit_minutes": 10,
        "learn_desc": "提炼可复用模式，动手抄代码",
        "skim_desc": "浏览模式名称和适用场景",
        "revisit_desc": "复习模式代码，尝试变形应用",
    },
}

STAGE_ORDER = ["overview", "mainflow", "showcase", "takeaway"]


class LearningPathPlanner:
    def plan(
        self,
        level: str = "standard",
        progress: dict | None = None,
    ) -> dict[str, Any]:
        """Generate a learning path.

        Args:
            level: "quick" | "standard" | "deep"
            progress: output of ProgressTracker.get_progress() (optional)

        Returns: {
            "level": str,
            "total_minutes": int,
            "steps": [PathStep as dict],
            "next_action": str,
            "mentor_hint": str,
        }
        """
        stages_done = set()
        if progress:
            for stage, stats in progress.get("stages", {}).items():
                if stats.get("complete"):
                    stages_done.add(stage)

        steps: list[PathStep] = []

        for stage in STAGE_ORDER:
            meta = STAGE_META[stage]
            if stage in stages_done:
                if level == "deep":
                    steps.append(
                        PathStep(
                            stage=stage,
                            title=meta["title"],
                            action="revisit",
                            estimated_minutes=meta["revisit_minutes"],
                            description=meta["revisit_desc"],
                            status="done",
                        )
                    )
                # quick/standard: skip completed
                continue

            if level == "quick" and stage not in ("overview", "mainflow"):
                steps.append(
                    PathStep(
                        stage=stage,
                        title=meta["title"],
                        action="skim",
                        estimated_minutes=meta["skim_minutes"],
                        description=meta["skim_desc"],
                    )
                )
            else:
                steps.append(
                    PathStep(
                        stage=stage,
                        title=meta["title"],
                        action="learn",
                        estimated_minutes=meta["learn_minutes"],
                        description=meta["learn_desc"],
                    )
                )

        total_minutes = sum(s.estimated_minutes for s in steps)
        next_step = next((s for s in steps if s.status == "pending"), None)
        next_action = f"前往「{next_step.title}」" if next_step else "全部完成！"
        mentor_hint = self._generate_hint(level, progress, next_step)

        return {
            "level": level,
            "total_minutes": total_minutes,
            "steps": [asdict(s) for s in steps],
            "next_action": next_action,
            "mentor_hint": mentor_hint,
        }

    def _generate_hint(
        self, level: str, progress: dict | None, next_step: PathStep | None
    ) -> str:
        if not progress:
            return "开始你的代码探索之旅！先从「先看门道」了解仓库全貌。"

        pct = progress.get("overall_percent", 0)
        if pct >= 100:
            return "恭喜通关！试试分析一个新仓库，或切换到深度路径复习。"
        if pct >= 70:
            return "快到终点了！最后一个阶段会让你带走可复用的模式。"
        if pct >= 40:
            return "进度不错。接下来深入设计亮点，看看这个项目最精彩的决策。"
        if next_step:
            return f"下一站：{next_step.title} — {next_step.description}"
        return "继续探索吧！"


path_planner = LearningPathPlanner()
