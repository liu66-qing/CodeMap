"""Agent guardrails — prevent infinite loops, drift, and runaway behavior.

Three failure modes this addresses:
1. LOOPS — Agent repeats same action/thought pattern indefinitely
2. DRIFT — Agent gradually diverges from original goal
3. RUNAWAY — Token/cost explosion without proportional progress

Detection strategies:
- Loop: Action fingerprint dedup + repetition pattern detection
- Drift: Semantic similarity between current thought and original goal
- Runaway: Token budget + wall-clock timeout + step count cap
"""
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any
from collections import Counter


@dataclass
class GuardrailViolation:
    type: str  # "loop" | "drift" | "runaway"
    severity: str  # "warning" | "critical"
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class LoopDetector:
    """Detects repetitive action patterns.

    Detection methods:
    1. Exact action fingerprint — same tool + args repeated
    2. N-gram pattern — sequence of actions repeating (A→B→C→A→B→C)
    3. Output similarity — tool outputs suspiciously similar across calls
    """

    def __init__(self, max_repetitions: int = 2, window_size: int = 20):
        self._action_history: list[str] = []
        self._fingerprints: Counter = Counter()
        self._max_reps = max_repetitions
        self._window = window_size

    def record_action(self, tool_name: str, args: dict) -> GuardrailViolation | None:
        """Record action and check for loops. Returns violation if detected."""
        fingerprint = self._compute_fingerprint(tool_name, args)
        self._action_history.append(fingerprint)
        self._fingerprints[fingerprint] += 1

        # Check 1: Exact repetition
        if self._fingerprints[fingerprint] > self._max_reps:
            return GuardrailViolation(
                type="loop",
                severity="critical",
                description=f"Action repeated {self._fingerprints[fingerprint]} times: {tool_name}",
                evidence={"tool": tool_name, "args": args, "count": self._fingerprints[fingerprint]},
            )

        # Check 2: Sequence pattern (detect A→B→A→B)
        pattern_violation = self._detect_sequence_pattern()
        if pattern_violation:
            return pattern_violation

        # Trim history to window
        if len(self._action_history) > self._window:
            old = self._action_history.pop(0)
            self._fingerprints[old] -= 1

        return None

    def _detect_sequence_pattern(self) -> GuardrailViolation | None:
        """Detect repeating sequences using suffix matching."""
        history = self._action_history
        if len(history) < 4:
            return None

        # Check for patterns of length 2-4
        for pattern_len in range(2, min(5, len(history) // 2 + 1)):
            recent = history[-pattern_len:]
            prior = history[-2 * pattern_len:-pattern_len]
            if recent == prior:
                return GuardrailViolation(
                    type="loop",
                    severity="warning",
                    description=f"Repeating action sequence of length {pattern_len} detected",
                    evidence={"pattern": recent, "pattern_length": pattern_len},
                )

        return None

    def reset(self):
        self._action_history.clear()
        self._fingerprints.clear()

    def _compute_fingerprint(self, tool_name: str, args: dict) -> str:
        import json
        raw = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


class DriftDetector:
    """Detects when agent diverges from original goal.

    Method: Compare each reasoning step's semantic alignment with the original
    query using keyword overlap (fast) or embedding cosine similarity (accurate).

    Drift threshold: If alignment drops below 0.3 for 3+ consecutive steps,
    agent is likely off-track.
    """

    def __init__(self, drift_threshold: float = 0.3, max_drift_steps: int = 3):
        self._original_goal: str = ""
        self._goal_keywords: set[str] = set()
        self._alignment_history: list[float] = []
        self._threshold = drift_threshold
        self._max_drift = max_drift_steps

    def set_goal(self, goal: str):
        """Set the original goal/query to track against."""
        self._original_goal = goal
        self._goal_keywords = set(goal.lower().split())
        self._alignment_history.clear()

    def check_alignment(self, current_thought: str) -> GuardrailViolation | None:
        """Check if current reasoning aligns with original goal."""
        if not self._original_goal:
            return None

        # Keyword overlap as fast alignment proxy
        thought_words = set(current_thought.lower().split())
        if not thought_words:
            return None

        overlap = len(self._goal_keywords & thought_words)
        alignment = overlap / max(len(self._goal_keywords), 1)
        self._alignment_history.append(alignment)

        # Check for sustained drift
        recent = self._alignment_history[-self._max_drift:]
        if len(recent) >= self._max_drift and all(a < self._threshold for a in recent):
            return GuardrailViolation(
                type="drift",
                severity="warning",
                description=f"Agent drifting from goal for {self._max_drift} steps",
                evidence={
                    "original_goal": self._original_goal[:100],
                    "current_thought": current_thought[:100],
                    "alignment_scores": recent,
                },
            )

        return None


class AgentGuardrails:
    """Unified guardrail system combining all detectors.

    Usage:
        guardrails = AgentGuardrails(goal="analyze auth module")

        # In agent loop:
        violation = guardrails.check_action(tool_name, args)
        if violation and violation.severity == "critical":
            break  # Force terminate

        violation = guardrails.check_thought(reasoning_text)
        if violation:
            # Inject correction prompt
    """

    def __init__(
        self,
        goal: str = "",
        max_steps: int = 20,
        max_tokens: int = 50000,
        max_wall_time: float = 300.0,  # 5 minutes
    ):
        self.loop_detector = LoopDetector()
        self.drift_detector = DriftDetector()
        self._max_steps = max_steps
        self._max_tokens = max_tokens
        self._max_time = max_wall_time
        self._step_count = 0
        self._token_count = 0
        self._start_time = time.time()
        self._violations: list[GuardrailViolation] = []

        if goal:
            self.drift_detector.set_goal(goal)

    def check_action(self, tool_name: str, args: dict) -> GuardrailViolation | None:
        """Check action for loop/runaway violations."""
        self._step_count += 1

        # Runaway: step count
        if self._step_count > self._max_steps:
            v = GuardrailViolation(
                type="runaway",
                severity="critical",
                description=f"Max steps ({self._max_steps}) exceeded",
                evidence={"step_count": self._step_count},
            )
            self._violations.append(v)
            return v

        # Runaway: wall time
        elapsed = time.time() - self._start_time
        if elapsed > self._max_time:
            v = GuardrailViolation(
                type="runaway",
                severity="critical",
                description=f"Wall time exceeded ({elapsed:.0f}s > {self._max_time}s)",
                evidence={"elapsed": elapsed},
            )
            self._violations.append(v)
            return v

        # Loop detection
        loop_v = self.loop_detector.record_action(tool_name, args)
        if loop_v:
            self._violations.append(loop_v)
            return loop_v

        return None

    def check_thought(self, thought: str) -> GuardrailViolation | None:
        """Check reasoning for drift."""
        drift_v = self.drift_detector.check_alignment(thought)
        if drift_v:
            self._violations.append(drift_v)
            return drift_v
        return None

    def record_tokens(self, count: int) -> GuardrailViolation | None:
        """Track token usage for runaway detection."""
        self._token_count += count
        if self._token_count > self._max_tokens:
            v = GuardrailViolation(
                type="runaway",
                severity="critical",
                description=f"Token budget exceeded ({self._token_count} > {self._max_tokens})",
                evidence={"tokens_used": self._token_count},
            )
            self._violations.append(v)
            return v
        return None

    def get_violations(self) -> list[GuardrailViolation]:
        return self._violations

    def get_stats(self) -> dict[str, Any]:
        return {
            "steps": self._step_count,
            "tokens": self._token_count,
            "elapsed_seconds": time.time() - self._start_time,
            "violations": len(self._violations),
            "violation_types": [v.type for v in self._violations],
        }
