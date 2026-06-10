"""
Deterministic embedding-similarity topic ledger for NIMS.

This module uses local deterministic hashed embeddings, not a remote model.
The goal is not semantic creativity; the goal is stable, auditable topic
governance with hard threshold enforcement.

Boundary:
- No LLM decides whether a topic switch is allowed.
- Topic switching is governed by cosine similarity and fixed thresholds.
"""

from __future__ import annotations

import hashlib
import math
import re

from soulsync.services.nims.config import (
    NIMS_TOPIC_EMBEDDING_DIM,
    NIMS_TOPIC_HIGH_ADHERENCE_THRESHOLD,
    NIMS_TOPIC_MEDIUM_ADHERENCE_THRESHOLD,
    NIMS_TOPIC_LOW_ADHERENCE_THRESHOLD,
    NIMS_TOPIC_MAX_LEDGER_TERMS,
)


STOPWORDS = {
    "the", "a", "an", "is", "are", "am", "to", "of", "and", "or", "in",
    "on", "for", "with", "it", "this", "that", "i", "you", "we", "can",
    "could", "should", "would", "my", "your", "me", "our", "their",
    "be", "been", "being", "was", "were", "do", "does", "did",
}


def _tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return [
        token
        for token in raw_tokens
        if token not in STOPWORDS and len(token) > 2
    ]


def _stable_hash_index(term: str, dim: int) -> int:
    digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % dim


def _stable_hash_sign(term: str) -> float:
    digest = hashlib.sha256(("sign:" + term).encode("utf-8")).hexdigest()
    return 1.0 if int(digest[-2:], 16) % 2 == 0 else -1.0


def _ngrams(tokens: list[str]) -> list[str]:
    """
    Builds deterministic unigram + bigram features.

    Bigrams help the ledger distinguish:
    - "homework planning"
    - "game planning"
    - "exam stress"
    """

    features: list[str] = []

    for token in tokens:
        features.append(token)

    for idx in range(len(tokens) - 1):
        features.append(tokens[idx] + "_" + tokens[idx + 1])

    return features


def build_topic_embedding(text: str, dim: int | None = None) -> list[float]:
    """
    Builds a deterministic local hashed embedding.

    This is not a neural embedding. It is a stable vector representation
    suitable for hard-threshold governance and reproducible evaluation.
    """

    dim = dim or NIMS_TOPIC_EMBEDDING_DIM
    vector = [0.0 for _ in range(dim)]

    tokens = _tokens(text)
    features = _ngrams(tokens)

    if not features:
        return vector

    for feature in features:
        idx = _stable_hash_index(feature, dim)
        sign = _stable_hash_sign(feature)
        vector[idx] += sign

    norm = math.sqrt(sum(value * value for value in vector))

    if norm == 0:
        return vector

    return [value / norm for value in vector]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Computes deterministic cosine similarity.
    """

    if not vec_a or not vec_b:
        return 0.0

    length = min(len(vec_a), len(vec_b))

    dot = sum(vec_a[idx] * vec_b[idx] for idx in range(length))
    norm_a = math.sqrt(sum(vec_a[idx] * vec_a[idx] for idx in range(length)))
    norm_b = math.sqrt(sum(vec_b[idx] * vec_b[idx] for idx in range(length)))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def _extract_terms(text: str) -> list[str]:
    terms = _tokens(text)
    deduped = []

    for term in terms:
        if term not in deduped:
            deduped.append(term)

    return deduped[:NIMS_TOPIC_MAX_LEDGER_TERMS]


def _threshold_for_adherence(control_vector: dict) -> float:
    adherence = control_vector.get("topic_adherence", "medium")

    if adherence == "high":
        return NIMS_TOPIC_HIGH_ADHERENCE_THRESHOLD

    if adherence == "low":
        return NIMS_TOPIC_LOW_ADHERENCE_THRESHOLD

    return NIMS_TOPIC_MEDIUM_ADHERENCE_THRESHOLD


def initialize_topic_ledger(user_text: str, context: str | None = None) -> dict:
    """
    Creates the initial topic ledger.

    The ledger stores a deterministic embedding vector in session state.
    This is acceptable for MVP because vectors are numeric and serializable.
    """

    source_text = context or user_text or "general support"

    terms = _extract_terms(source_text)
    embedding = build_topic_embedding(source_text)

    return {
        "current_topic": " ".join(terms[:8]) if terms else "general_support",
        "terms": terms,
        "topic_embedding": embedding,
        "topic_strength": 1.0,
        "last_similarity": 1.0,
        "switch_threshold": NIMS_TOPIC_MEDIUM_ADHERENCE_THRESHOLD,
        "last_switch_allowed": True,
        "governance": "deterministic_hashed_embedding_cosine",
    }


def should_allow_topic_switch(
    ledger: dict,
    user_text: str,
    control_vector: dict,
) -> bool:
    """
    Determines whether a topic switch is allowed.

    Hard governance rule:
    - Similarity must meet or exceed the threshold for the current adherence level.
    - LLM output cannot override this decision.
    """

    existing_embedding = ledger.get("topic_embedding") or []
    new_embedding = build_topic_embedding(user_text)

    similarity = cosine_similarity(existing_embedding, new_embedding)
    threshold = _threshold_for_adherence(control_vector)

    ledger["last_similarity"] = similarity
    ledger["switch_threshold"] = threshold

    return similarity >= threshold


def update_topic_ledger(
    ledger: dict,
    user_text: str,
    control_vector: dict,
) -> dict:
    """
    Updates the topic ledger using deterministic embedding similarity.
    """

    allow_switch = should_allow_topic_switch(
        ledger=ledger,
        user_text=user_text,
        control_vector=control_vector,
    )

    ledger["last_switch_allowed"] = allow_switch

    if allow_switch:
        previous_terms = ledger.get("terms", [])
        new_terms = _extract_terms(user_text)

        merged_terms = []

        for term in previous_terms + new_terms:
            if term not in merged_terms:
                merged_terms.append(term)

        merged_terms = merged_terms[:NIMS_TOPIC_MAX_LEDGER_TERMS]

        combined_text = " ".join(merged_terms)

        ledger["terms"] = merged_terms
        ledger["current_topic"] = " ".join(merged_terms[:8]) if merged_terms else "general_support"
        ledger["topic_embedding"] = build_topic_embedding(combined_text)
        ledger["topic_strength"] = min(
            1.0,
            float(ledger.get("topic_strength", 0.8)) + 0.05,
        )
    else:
        ledger["topic_strength"] = max(
            0.0,
            float(ledger.get("topic_strength", 0.8)) - 0.1,
        )

    return ledger


def build_topic_bridge_response(ledger: dict) -> str:
    """
    Builds deterministic bridge response when topic switch is blocked.
    """

    topic = ledger.get("current_topic") or "the current topic"

    return (
        f"Before we switch, let's finish this topic: {topic}. "
        "What is one small step you want to take for this first?"
    )
