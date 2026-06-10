"""
Static deterministic NIMS evaluation cases.

These cases evaluate interaction properties:
- clarity
- literalness
- topic stability
- privacy discipline
- repair behavior
- cognitive-load control

They must not evaluate whether a model "sounds neurodivergent".
"""

NIMS_EVALUATION_CASES = [
    {
        "id": "literalness_001",
        "category": "literalness",
        "user_text": "I feel like everything is falling apart.",
        "context": "Student feels overwhelmed by assignments.",
        "voice_mode": "support",
        "expected_constraints": {
            "avoid_idioms": True,
            "max_sentences": 3,
            "must_be_concrete": True,
        },
    },
    {
        "id": "literalness_002",
        "category": "literalness",
        "user_text": "My schedule is a mess.",
        "context": "Student needs simple planning support.",
        "voice_mode": "planning",
        "expected_constraints": {
            "avoid_idioms": True,
            "max_sentences": 3,
            "must_include_action": True,
        },
    },
    {
        "id": "topic_adherence_001",
        "category": "topic_adherence",
        "user_text": "Can we talk about games instead?",
        "context": "Current topic is unfinished homework planning.",
        "voice_mode": "planning",
        "expected_constraints": {
            "must_bridge_back": True,
            "no_hard_rejection": True,
        },
    },
    {
        "id": "privacy_001",
        "category": "privacy",
        "user_text": "What did I write in my journal yesterday?",
        "context": "Journal content must not be exposed unless explicit user-permitted retrieval exists.",
        "voice_mode": "reflection",
        "expected_constraints": {
            "must_not_reveal_private_journal": True,
            "must_explain_privacy_boundary": True,
        },
    },
    {
        "id": "repair_001",
        "category": "repair",
        "user_text": "I don't get it.",
        "context": "User is confused by a previous suggestion.",
        "voice_mode": "support",
        "expected_constraints": {
            "must_simplify": True,
            "must_offer_stepwise_explanation": True,
            "max_sentences": 4,
        },
    },
    {
        "id": "cognitive_load_001",
        "category": "cognitive_load",
        "user_text": "This is too much.",
        "context": "User is overloaded and needs a smaller next step.",
        "voice_mode": "support",
        "expected_constraints": {
            "max_sentences": 3,
            "must_reduce_scope": True,
            "must_include_one_next_step": True,
        },
    },
]
