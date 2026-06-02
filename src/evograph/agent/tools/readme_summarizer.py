"""README summarizer — rule-based extraction of structured info from README.

No LLM needed. Extracts: title, tagline, features, badges, install/usage hints.
"""

from __future__ import annotations

import re
from typing import Any


async def summarize_readme(content: str) -> dict[str, Any]:
    """Parse README to extract structured signals.

    Returns: {
        "title": str,
        "tagline": str,
        "features": [...],
        "has_quickstart": bool,
        "has_examples": bool,
        "tech_keywords": [...],
        "sections": [...]
    }
    """
    if not content:
        return {
            "title": "",
            "tagline": "",
            "features": [],
            "has_quickstart": False,
            "has_examples": False,
            "tech_keywords": [],
            "sections": [],
        }

    title = _extract_title(content)
    tagline = _extract_tagline(content)
    features = _extract_features(content)
    sections = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)

    has_quickstart = bool(
        re.search(r"#{1,3}\s+(quick.?start|getting.?started|installation|setup)", content, re.IGNORECASE)
    )
    has_examples = bool(re.search(r"#{1,3}\s+(example|usage|how.?to)", content, re.IGNORECASE))

    tech_keywords = _extract_tech_keywords(content)

    return {
        "title": title,
        "tagline": tagline,
        "features": features[:10],
        "has_quickstart": has_quickstart,
        "has_examples": has_examples,
        "tech_keywords": tech_keywords,
        "sections": sections[:20],
    }


def _extract_title(content: str) -> str:
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        # Strip badges
        return re.sub(r"\[!\[.+?\]\(.+?\)\]\(.+?\)", "", m.group(1)).strip()
    return ""


def _extract_tagline(content: str) -> str:
    """First non-empty line after the title that's not a badge."""
    lines = content.split("\n")
    found_title = False
    for line in lines:
        line = line.strip()
        if not found_title:
            if line.startswith("#"):
                found_title = True
            continue
        if not line:
            continue
        if line.startswith("[![") or line.startswith("<!--"):
            continue
        if line.startswith("#"):
            break
        # Strip markdown
        clean = re.sub(r"\*+", "", line)
        clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)
        if len(clean) > 20:
            return clean[:300]
    return ""


def _extract_features(content: str) -> list[str]:
    features = []
    in_features = False
    for line in content.split("\n"):
        if re.match(r"^#{1,3}\s+(features?|why|highlights?|capabilit)", line, re.IGNORECASE):
            in_features = True
            continue
        if in_features and line.startswith("#"):
            break
        if in_features:
            m = re.match(r"^\s*[-*+]\s+(.+)$", line)
            if m:
                feat = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(1))
                feat = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", feat)
                features.append(feat.strip())
    return features


_TECH_PATTERNS = [
    "react", "vue", "angular", "svelte", "next.js", "nextjs",
    "node.js", "nodejs", "express", "fastapi", "flask", "django",
    "spring", "rails", "laravel",
    "postgres", "mysql", "mongodb", "redis", "neo4j", "elasticsearch",
    "kafka", "rabbitmq", "grpc", "graphql", "rest",
    "docker", "kubernetes", "k8s", "terraform",
    "tensorflow", "pytorch", "huggingface",
    "openai", "claude", "llm", "rag", "langchain", "vector",
    "typescript", "python", "rust", "go", "java",
]


def _extract_tech_keywords(content: str) -> list[str]:
    text = content.lower()
    found = []
    for kw in _TECH_PATTERNS:
        if kw in text:
            found.append(kw)
    return found[:15]
