# SoulSync MVP

This is a Streamlit-based Student Life RPG.

## Setup

1.  **Dependencies**: Installed via `packager_tool` (Streamlit, SQLAlchemy, Requests).
2.  **Run**: `streamlit run app.py --server.port 3000 --server.address 0.0.0.0`
    *   (In Replit, the `.replit` file should handle this, or run manually in Shell).

## Configuration

*   **Database**: Defaults to `sqlite:///soulsync.db`. Set `DATABASE_URL` for Postgres.
*   **AI**: Set `GOOGLE_API_KEY` for Gemini integration. Defaults to fallback mode if missing.

## Features

*   **Dashboard**: View RPG stats.
*   **Missions**: Daily tasks based on journal inputs.
*   **Journal**: Daily check-in.
*   **Your Voice**: Supportive chat (Gemini or Fallback).


## NIMS: Neurodivergent Interaction Modelling System

SoulSync includes an optional internal extension called **NIMS**
(Neurodivergent Interaction Modelling System).

NIMS is used to evaluate and govern candidate conversational models before
they are allowed to power the `Your Voice` experience.

NIMS does **not** diagnose users, simulate neurodivergent identity, or attempt
to imitate any individual speech style. Instead, it evaluates and enforces
interaction properties such as:

- clarity
- predictability
- topic stability
- repair behavior
- cognitive-load control
- privacy discipline
- safe response boundaries

Candidate models must pass deterministic NIMS evaluation before activation.
At runtime, NIMS can apply additional guardrails such as pragmatic arbitration,
topic ledger checks, response-length control, and audit logging.

### NIMS Environment Variables

```env
NIMS_ENABLED=true
NIMS_REQUIRE_APPROVED_MODEL=true
NIMS_DEBUG_PANEL=false
NIMS_DEFAULT_PROVIDER=gemini
NIMS_DEFAULT_MODEL_ID=gemini-default
NIMS_MIN_APPROVAL_SCORE=0.82
NIMS_MAX_SAFETY_FAILURES=0
NIMS_MAX_TOPIC_FAILURES=1
NIMS_MAX_LITERALNESS_FAILURES=1
```

For local development, set `NIMS_REQUIRE_APPROVED_MODEL=false` if you want
`Your Voice` to fall back safely when no approved model exists.

