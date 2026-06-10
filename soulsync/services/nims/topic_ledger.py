"""
Deterministic topic ledger for NIMS.

MVP uses keyword overlap instead of embeddings for repeatability and simplicity.
"""

from __future__ import annotations

import re


STOPWORDS = {
    "the", "a", "an", "is", "are", "am", "to", "of", "and", "or", "in",
    "on", "for", "with", "it", "this", "that", "i", "you", "we", "can",
    "could", "should", "would", "my", "your", "me",
}


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return {token for token in tokens if token not in STOPWORDS and len(token) > 2}


def _overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0

    return len(a.intersection(b)) / max(len(a.union(b)), 1)


def initialize_topic_ledger(user_text: str, context: str | None = None) -> dict:
    source = context or user_text
    keywords = sorted(_keywords(source))

    return {
        "current_topic": " ".join(keywords[:6]) if keywords else "general_support",
        "keywords": keywords,
        "topic_strength": 1.0,
        "switch_threshold": 0.35,
        "last_similarity": 1.0,
        "last_switch_allowed": True,
    }


def should_allow_topic_switch(
    ledger: dict,
    user_text: str,
    control_vector: dict,
) -> bool:
    existing_keywords = set(ledger.get("keywords", []))
    new_keywords = _keywords(user_text)

    similarity = _overlap_score(existing_keywords, new_keywords)

    adherence = control_vector.get("topic_adherence", "medium")

    if adherence == "high":
        threshold = 0.25
    elif adherence == "low":
        threshold = 0.05
    else:
        threshold = 0.15

    ledger["last_similarity"] = similarity
    ledger["switch_threshold"] = threshold

    return similarity >= threshold


def update_topic_ledger(
    ledger: dict,
    user_text: str,
    control_vector: dict,
) -> dict:
    allow_switch = should_allow_topic_switch(ledger, user_text, control_vector)
    ledger["last_switch_allowed"] = allow_switch

    if allow_switch:
        merged = set(ledger.get("keywords", []))
        merged.update(_keywords(user_text))
        ledger["keywords"] = sorted(merged)[:12]
        ledger["current_topic"] = " ".join(ledger["keywords"][:6])
        ledger["topic_strength"] = min(1.0, float(ledger.get("topic_strength", 0.8)) + 0.05)
    else:
        ledger["topic_strength"] = max(0.0, float(ledger.get("topic_strength", 0.8)) - 0.1)

    return ledger


def build_topic_bridge_response(ledger: dict) -> str:
    topic = ledger.get("current_topic") or "the current topic"

    return (
        f"Before we switch, let's finish the current topic: {topic}. "
        "What is one small step you want to take for this first?"
    )
