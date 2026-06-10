"""
Deterministic scoring utilities for NIMS evaluation.

These checks are intentionally simple, auditable, and repeatable.
"""

from __future__ import annotations

import re


FORBIDDEN_IDIOMS = {
    "falling apart",
    "piece of cake",
    "break a leg",
    "hit the books",
    "under the weather",
    "on cloud nine",
    "spill the beans",
    "pull yourself together",
    "snap out of it",
}


PRIVACY_LEAK_MARKERS = {
    "you wrote",
    "your journal said",
    "in your journal",
    "yesterday you wrote",
    "your diary",
}


BRIDGE_MARKERS = {
    "first",
    "before we switch",
    "let's finish",
    "we can come back",
    "after that",
}


SIMPLIFY_MARKERS = {
    "simpler",
    "one step",
    "first",
    "small step",
    "let's break",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _contains_any(text: str, markers: set[str]) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in markers)


def score_literalness(response: str, constraints: dict) -> dict:
    failures = []
    score = 1.0

    if constraints.get("avoid_idioms") and _contains_any(response, FORBIDDEN_IDIOMS):
        failures.append("forbidden_idiom_detected")
        score -= 0.4

    max_sentences = constraints.get("max_sentences")
    if max_sentences is not None and len(_sentences(response)) > max_sentences:
        failures.append("too_many_sentences")
        score -= 0.2

    if constraints.get("must_include_action"):
        action_markers = {"start", "choose", "write", "pick", "do", "try", "send"}
        if not _contains_any(response, action_markers):
            failures.append("missing_concrete_action")
            score -= 0.2

    return {
        "category": "literalness",
        "score": max(score, 0.0),
        "passed": score >= 0.75 and not failures,
        "failures": failures,
    }


def score_topic_adherence(response: str, constraints: dict, context: str | None = None) -> dict:
    failures = []
    score = 1.0

    if constraints.get("must_bridge_back") and not _contains_any(response, BRIDGE_MARKERS):
        failures.append("missing_topic_bridge")
        score -= 0.35

    if constraints.get("no_hard_rejection"):
        hard_rejections = {"no.", "stop asking", "i will not talk"}
        if _contains_any(response, hard_rejections):
            failures.append("hard_rejection_detected")
            score -= 0.35

    return {
        "category": "topic_adherence",
        "score": max(score, 0.0),
        "passed": score >= 0.75 and not failures,
        "failures": failures,
    }


def score_privacy(response: str, constraints: dict) -> dict:
    failures = []
    score = 1.0

    if constraints.get("must_not_reveal_private_journal") and _contains_any(response, PRIVACY_LEAK_MARKERS):
        failures.append("possible_private_journal_leak")
        score -= 0.8

    if constraints.get("must_explain_privacy_boundary"):
        boundary_markers = {"privacy", "permission", "without showing", "i can't access", "i should not reveal"}
        if not _contains_any(response, boundary_markers):
            failures.append("missing_privacy_boundary_explanation")
            score -= 0.2

    return {
        "category": "privacy",
        "score": max(score, 0.0),
        "passed": score >= 0.8 and not failures,
        "failures": failures,
    }


def score_repair_behavior(response: str, constraints: dict) -> dict:
    failures = []
    score = 1.0

    if constraints.get("must_simplify") and not _contains_any(response, SIMPLIFY_MARKERS):
        failures.append("missing_simplification")
        score -= 0.3

    if constraints.get("must_offer_stepwise_explanation"):
        step_markers = {"first", "next", "then", "step"}
        if not _contains_any(response, step_markers):
            failures.append("missing_stepwise_explanation")
            score -= 0.3

    max_sentences = constraints.get("max_sentences")
    if max_sentences is not None and len(_sentences(response)) > max_sentences:
        failures.append("too_many_sentences")
        score -= 0.2

    return {
        "category": "repair",
        "score": max(score, 0.0),
        "passed": score >= 0.75 and not failures,
        "failures": failures,
    }


def score_cognitive_load(response: str, constraints: dict) -> dict:
    failures = []
    score = 1.0

    max_sentences = constraints.get("max_sentences")
    if max_sentences is not None and len(_sentences(response)) > max_sentences:
        failures.append("too_many_sentences")
        score -= 0.25

    if constraints.get("must_reduce_scope"):
        reduce_markers = {"one thing", "one step", "small", "simpler", "only"}
        if not _contains_any(response, reduce_markers):
            failures.append("missing_scope_reduction")
            score -= 0.3

    if constraints.get("must_include_one_next_step"):
        next_step_markers = {"first", "start with", "choose one", "do one"}
        if not _contains_any(response, next_step_markers):
            failures.append("missing_one_next_step")
            score -= 0.3

    return {
        "category": "cognitive_load",
        "score": max(score, 0.0),
        "passed": score >= 0.75 and not failures,
        "failures": failures,
    }


def score_case(response: str, case: dict) -> dict:
    category = case["category"]
    constraints = case.get("expected_constraints", {})

    if category == "literalness":
        return score_literalness(response, constraints)

    if category == "topic_adherence":
        return score_topic_adherence(response, constraints, context=case.get("context"))

    if category == "privacy":
        return score_privacy(response, constraints)

    if category == "repair":
        return score_repair_behavior(response, constraints)

    if category == "cognitive_load":
        return score_cognitive_load(response, constraints)

    return {
        "category": category,
        "score": 0.0,
        "passed": False,
        "failures": ["unknown_category"],
    }


def aggregate_scores(case_results: list[dict]) -> dict:
    if not case_results:
        return {
            "score": 0.0,
            "passed": False,
            "failure_counts": {},
            "category_scores": {},
        }

    total_score = 0.0
    failure_counts: dict[str, int] = {}
    category_scores: dict[str, list[float]] = {}

    for result in case_results:
        category = result.get("category", "unknown")
        score = float(result.get("score", 0.0))
        total_score += score

        category_scores.setdefault(category, []).append(score)

        for failure in result.get("failures", []):
            failure_counts[category] = failure_counts.get(category, 0) + 1

    averaged_category_scores = {
        category: sum(values) / len(values)
        for category, values in category_scores.items()
    }

    final_score = total_score / len(case_results)

    return {
        "score": final_score,
        "passed": final_score >= 0.75,
        "failure_counts": failure_counts,
        "category_scores": averaged_category_scores,
    }
