"""
Candidate model adapters for NIMS.

This module normalizes all model-provider calls into one function:
generate_candidate_response(...)

Important boundary:
- This layer returns raw semantic model output only.
- It must not enforce style, safety, topic adherence, or neurodivergent interaction rules.
- Deterministic governance belongs to NIMS arbitration/runtime files.
"""

from __future__ import annotations


def _fallback_response(user_text: str, context: str | None = None) -> str:
    """
    Safe local fallback used when the configured provider is unavailable.

    This is intentionally simple. It gives NIMS something deterministic
    to evaluate without depending on a remote model.
    """
    if not user_text.strip():
        return "Please share one thing you want help with."

    return (
        "I understand. Let's keep this clear and simple. "
        "Please tell me the main thing you want to focus on first."
    )


def _call_soulsync_voice_layer(
    provider: str,
    model_id: str,
    user_text: str,
    context: str | None = None,
    voice_mode: str | None = None,
) -> str:
    """
    Attempts to call the existing SoulSync voice service.

    This function is intentionally defensive because the exact function name
    in voice.py may differ across SoulSync snapshots.
    """

    try:
        from soulsync.services import voice
    except Exception:
        return _fallback_response(user_text, context)

    # Preferred future low-level function.
    if hasattr(voice, "generate_raw_voice_response"):
        return voice.generate_raw_voice_response(
            user_text=user_text,
            context=context,
            mode=voice_mode,
            provider=provider,
            model_id=model_id,
        )

    # Compatibility path if existing project uses get_ai_response.
    # This may need adjustment depending on your current voice.py signature.
    if hasattr(voice, "get_ai_response"):
        try:
            return voice.get_ai_response(
                user_text=user_text,
                context=context,
                mode=voice_mode,
            )
        except TypeError:
            try:
                return voice.get_ai_response(user_text)
            except Exception:
                return _fallback_response(user_text, context)

    return _fallback_response(user_text, context)


def generate_candidate_response(
    provider: str,
    model_id: str,
    user_text: str,
    context: str | None = None,
    voice_mode: str | None = None,
) -> str:
    """
    Generates raw candidate model response text.

    Parameters:
        provider: Model provider name, e.g. "gemini", "fallback".
        model_id: Provider-specific model identifier.
        user_text: User input.
        context: Optional scenario/context string.
        voice_mode: Optional SoulSync voice mode.

    Returns:
        Raw semantic response text.

    Boundary rule:
        Do not apply deterministic NIMS rules here.
    """

    provider = (provider or "fallback").strip().lower()

    if provider == "fallback":
        return _fallback_response(user_text, context)

    if provider in {"gemini", "google", "default"}:
        return _call_soulsync_voice_layer(
            provider=provider,
            model_id=model_id,
            user_text=user_text,
            context=context,
            voice_mode=voice_mode,
        )

    # Unknown providers are not fatal during early evaluation.
    # They degrade into fallback behavior.
    return _fallback_response(user_text, context)
