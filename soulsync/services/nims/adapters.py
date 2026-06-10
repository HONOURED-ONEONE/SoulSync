"""
Candidate model adapters for NIMS.

This file will normalize calls to Gemini, fallback models, or future
voice-enabled LLM APIs. It must return raw semantic responses only.
"""


def generate_candidate_response(
    provider: str,
    model_id: str,
    user_text: str,
    context: str | None = None,
    voice_mode: str | None = None,
) -> str:
    raise NotImplementedError("NIMS candidate model adapters are not implemented yet.")
