"""
Deterministic pragmatic arbitration rules for NIMS.
"""

from __future__ import annotations

import re


FORBIDDEN_IDIOMS = {
    "falling apart": "very difficult",
    "piece of cake": "easy",
    "hit the books": "study",
    "under the weather": "not feeling well",
    "pull yourself together": "take one small step",
    "snap out of it": "pause and choose one small action",
}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _limit_sentences(text: str, max_sentences: int) -> str:
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return text.strip()
    return " ".join(sentences[:max_sentences]).strip()


def _replace_idioms(text: str) -> tuple[str, list[str]]:
    changed = []
    result = text

    for idiom, replacement in FORBIDDEN_IDIOMS.items():
        pattern = re.compile(re.escape(idiom), re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(replacement, result)
            changed.append(idiom)

    return result, changed


def arbitrate_response(
    raw_response: str,
    control_vector: dict,
    context: str | None = None,
) -> dict:
    """
    Applies deterministic constraints to raw model response.

    Returns:
        {
            "final_text": str,
            "changed": bool,
            "rejections": list[str],
            "rules_applied": list[str]
        }
    """

    final_text = (raw_response or "").strip()
    rejections = []
    rules_applied = []

    if not final_text:
        final_text = "Let's keep this simple. What is one thing you want help with?"
        rejections.append("empty_response")
        rules_applied.append("fallback_empty_response")

    if control_vector.get("literalness") == "high":
        final_text, idioms_changed = _replace_idioms(final_text)
        if idioms_changed:
            rejections.append("figurative_language_detected")
            rules_applied.append("literalize_response")

    response_length = control_vector.get("response_length", "short")
    if response_length == "short":
        before = final_text
        final_text = _limit_sentences(final_text, 3)
        if final_text != before:
            rejections.append("response_too_long")
            rules_applied.append("shorten_to_three_sentences")

    if control_vector.get("cognitive_load") == "low":
        if len(final_text.split()) > 70:
            words = final_text.split()[:70]
            final_text = " ".join(words).rstrip(",;:") + "."
            rejections.append("high_cognitive_load")
            rules_applied.append("word_limit_70")

    return {
        "final_text": final_text,
        "changed": bool(rejections),
        "rejections": rejections,
        "rules_applied": rules_applied,
    }
