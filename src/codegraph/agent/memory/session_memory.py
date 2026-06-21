"""Legacy session memory — backward-compatible re-export.

This is the original SessionMemory that existed before the 3-tier memory
architecture was introduced. It remains the active session store for the
query pipeline and multi-turn conversations.

The new MemoryManager handles structured memory (episodic, semantic,
procedural) while SessionMemory handles raw conversation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionMemory:
    """Session-level memory for multi-turn conversations."""

    session_id: str
    conversation_history: list[dict] = field(default_factory=list)
    entity_focus: dict[str, int] = field(default_factory=dict)

    def add_turn(self, question: str, answer: str, entities: list[str]):
        self.conversation_history.append({
            "question": question,
            "answer_summary": answer[:200],
            "entities": entities,
        })
        for e in entities:
            self.entity_focus[e] = self.entity_focus.get(e, 0) + 1

    def resolve_coreference(self, question: str) -> str:
        """Replace pronouns with the most recently focused entities."""
        pronouns = {"他": "", "她": "", "它": "", "这件事": "", "此事": "", "该国": ""}
        if not any(p in question for p in pronouns):
            return question

        if not self.entity_focus:
            return question

        top_entity = max(self.entity_focus, key=self.entity_focus.get)

        for pronoun in pronouns:
            if pronoun in question:
                question = question.replace(pronoun, top_entity, 1)
                break

        return question

    def get_context_for_planning(self) -> str:
        if not self.conversation_history:
            return ""
        recent = self.conversation_history[-3:]
        lines = [f"- {t['question']}" for t in recent]
        return "用户之前问过：\n" + "\n".join(lines)

    @property
    def recent_entities(self) -> list[str]:
        if not self.conversation_history:
            return []
        last = self.conversation_history[-1]
        return last.get("entities", [])


_sessions: dict[str, SessionMemory] = {}


def get_session(session_id: str) -> SessionMemory:
    if session_id not in _sessions:
        _sessions[session_id] = SessionMemory(session_id=session_id)
    return _sessions[session_id]
