"""Achievement engine: pure-function badge computation from event history.

Badges:
  - novice (初探者): first visit to any stage
  - explorer (探索者): analyzed 3+ distinct repos
  - analyst (分析师): read 10+ highlights across all analyses
  - craftsman (手艺人): copied 5+ patterns from takeaway
  - speedrunner (速通者): completed all 4 stages in one analysis within 10 min
  - scholar (学者): spent 30+ total minutes studying
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Badge:
    id: str
    title: str
    description: str
    icon: str  # matches frontend asset key or emoji
    unlocked: bool = False
    unlocked_at: float | None = None


BADGE_DEFINITIONS: list[dict[str, str]] = [
    {
        "id": "novice",
        "title": "初探者",
        "description": "首次访问任意学习阶段",
        "icon": "badgeMap",
    },
    {
        "id": "explorer",
        "title": "探索者",
        "description": "分析过 3 个不同仓库",
        "icon": "routeArrowBlue",
    },
    {
        "id": "analyst",
        "title": "分析师",
        "description": "阅读 10 个以上设计亮点",
        "icon": "crystalAgentBlue",
    },
    {
        "id": "craftsman",
        "title": "手艺人",
        "description": "从 Takeaway 复制 5 个以上模式",
        "icon": "campfireCrates",
    },
    {
        "id": "speedrunner",
        "title": "速通者",
        "description": "10 分钟内完成一次四阶段全分析",
        "icon": "mentorRunner",
    },
    {
        "id": "scholar",
        "title": "学者",
        "description": "累计学习时长超过 30 分钟",
        "icon": "badgeClipboard",
    },
]


class AchievementEngine:
    def compute(self, events: list[dict], progress: dict) -> list[Badge]:
        """Evaluate all badge rules against user's event history."""
        badges: list[Badge] = []
        for defn in BADGE_DEFINITIONS:
            unlocked, ts = self._check(defn["id"], events, progress)
            badges.append(
                Badge(
                    id=defn["id"],
                    title=defn["title"],
                    description=defn["description"],
                    icon=defn["icon"],
                    unlocked=unlocked,
                    unlocked_at=ts,
                )
            )
        return badges

    def _check(
        self, badge_id: str, events: list[dict], progress: dict
    ) -> tuple[bool, float | None]:
        if badge_id == "novice":
            visit = next((e for e in events if e["type"] == "visit"), None)
            return (True, visit["ts"]) if visit else (False, None)

        if badge_id == "explorer":
            repos = {e.get("repo_url") for e in events if e.get("repo_url")}
            if len(repos) >= 3:
                # Timestamp = when 3rd repo was first visited
                repo_first: dict[str, float] = {}
                for e in events:
                    r = e.get("repo_url")
                    if r and r not in repo_first:
                        repo_first[r] = e["ts"]
                ts_sorted = sorted(repo_first.values())
                return True, ts_sorted[2] if len(ts_sorted) >= 3 else None
            return False, None

        if badge_id == "analyst":
            reads = [e for e in events if e["type"] == "highlight_read"]
            if len(reads) >= 10:
                return True, reads[9]["ts"]
            return False, None

        if badge_id == "craftsman":
            copies = [e for e in events if e["type"] == "pattern_copied"]
            if len(copies) >= 5:
                return True, copies[4]["ts"]
            return False, None

        if badge_id == "speedrunner":
            # Group by task_id, check if all 4 stages completed within 10 min
            from collections import defaultdict

            tasks: dict[str, list[dict]] = defaultdict(list)
            for e in events:
                if e["type"] == "visit":
                    tasks[e.get("task_id", "")].append(e)
            for tid, task_events in tasks.items():
                stages_visited = {e["stage"] for e in task_events}
                if stages_visited >= {"overview", "mainflow", "showcase", "takeaway"}:
                    times = [e["ts"] for e in task_events]
                    if max(times) - min(times) <= 600:
                        return True, max(times)
            return False, None

        if badge_id == "scholar":
            total_seconds = progress.get("total_time_seconds", 0)
            if total_seconds >= 1800:
                # Approximate unlock time: when cumulative passed threshold
                cumulative = 0.0
                for e in events:
                    if e["type"] == "time_spent":
                        cumulative += e.get("value", 0)
                        if cumulative >= 1800:
                            return True, e["ts"]
            return False, None

        return False, None


achievement_engine = AchievementEngine()
