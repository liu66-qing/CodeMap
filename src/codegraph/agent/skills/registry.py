"""Skill system — reusable, composable agent capabilities.

Inspired by: Claude Code skills, LLM-wiki patterns.

A Skill is a named, self-contained capability that:
1. Has a trigger condition (regex, keyword, or classifier)
2. Has a structured prompt template
3. Can compose other skills
4. Tracks usage and success metrics

This enables:
- Modular agent behavior (add/remove skills without touching core)
- Skill discovery (LLM can list available skills)
- Skill chaining (complex behaviors from simple primitives)
- A/B testing (swap skill implementations transparently)
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum


class SkillTrigger(str, Enum):
    KEYWORD = "keyword"      # Match specific keywords
    REGEX = "regex"          # Match regex pattern
    INTENT = "intent"        # LLM-classified intent
    EXPLICIT = "explicit"    # Only when explicitly invoked (e.g., /skill_name)


@dataclass
class Skill:
    name: str
    description: str
    trigger_type: SkillTrigger
    trigger_pattern: str  # Keyword, regex, or intent label
    prompt_template: str  # Template with {variable} placeholders
    category: str = "general"
    version: str = "1.0"
    depends_on: list[str] = field(default_factory=list)  # Other skills this requires
    examples: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Runtime stats
    invocation_count: int = 0
    avg_latency_ms: float = 0
    success_rate: float = 1.0


@dataclass
class SkillResult:
    skill_name: str
    output: str
    success: bool
    latency_ms: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SkillRegistry:
    """Central registry for agent skills with trigger-based activation."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._executors: dict[str, Callable[..., Awaitable[str]]] = {}
        self._invocation_log: list[SkillResult] = []

    def register(self, skill: Skill, executor: Callable[..., Awaitable[str]]) -> None:
        """Register a skill with its executor function."""
        self._skills[skill.name] = skill
        self._executors[skill.name] = executor

    def match(self, query: str) -> list[Skill]:
        """Find skills that match the query based on their triggers."""
        matches = []
        for skill in self._skills.values():
            if self._triggers(skill, query):
                matches.append(skill)
        return sorted(matches, key=lambda s: s.invocation_count, reverse=True)

    async def execute(self, skill_name: str, context: dict[str, Any]) -> SkillResult:
        """Execute a skill with given context."""
        if skill_name not in self._skills:
            return SkillResult(skill_name=skill_name, output=f"Skill '{skill_name}' not found", success=False)

        skill = self._skills[skill_name]
        executor = self._executors[skill_name]
        start = time.time()

        try:
            # Resolve dependencies first
            dep_results = {}
            for dep_name in skill.depends_on:
                if dep_name in self._skills:
                    dep_result = await self.execute(dep_name, context)
                    dep_results[dep_name] = dep_result.output

            context["dependency_results"] = dep_results
            output = await executor(**context)
            latency = (time.time() - start) * 1000

            # Update stats
            skill.invocation_count += 1
            skill.avg_latency_ms = (skill.avg_latency_ms * (skill.invocation_count - 1) + latency) / skill.invocation_count

            result = SkillResult(skill_name=skill_name, output=output, success=True, latency_ms=latency)
            self._invocation_log.append(result)
            return result

        except Exception as e:
            latency = (time.time() - start) * 1000
            skill.invocation_count += 1
            skill.success_rate = (skill.success_rate * (skill.invocation_count - 1)) / skill.invocation_count

            result = SkillResult(skill_name=skill_name, output=str(e), success=False, latency_ms=latency)
            self._invocation_log.append(result)
            return result

    def list_skills(self, category: str | None = None) -> list[dict[str, Any]]:
        """List available skills (for LLM tool description generation)."""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return [
            {
                "name": s.name,
                "description": s.description,
                "trigger": s.trigger_pattern,
                "category": s.category,
                "examples": s.examples,
            }
            for s in skills
        ]

    def _triggers(self, skill: Skill, query: str) -> bool:
        """Check if query matches skill trigger."""
        if skill.trigger_type == SkillTrigger.KEYWORD:
            keywords = skill.trigger_pattern.lower().split("|")
            return any(kw in query.lower() for kw in keywords)
        elif skill.trigger_type == SkillTrigger.REGEX:
            return bool(re.search(skill.trigger_pattern, query, re.IGNORECASE))
        elif skill.trigger_type == SkillTrigger.EXPLICIT:
            return query.strip().startswith(f"/{skill.name}")
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_skills": len(self._skills),
            "categories": list(set(s.category for s in self._skills.values())),
            "total_invocations": len(self._invocation_log),
            "top_skills": sorted(
                [(s.name, s.invocation_count) for s in self._skills.values()],
                key=lambda x: x[1], reverse=True,
            )[:5],
        }
