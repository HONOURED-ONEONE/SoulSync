# soulsync/services/mood_suggester.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from .missions import compute_time_context  # reuse existing function


def _norm_int(val: Any, default: int) -> int:
    try:
        v = int(val)
        if v < 0:
            return default
        return v
    except Exception:
        return default


def _normalize_signals(signals: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize journal signals with sane defaults."""
    signals = signals or {}
    return {
        "mood": (signals.get("mood") or "neutral").lower(),
        "energy": _norm_int(signals.get("energy", 3), 3),
        "focus": _norm_int(signals.get("focus", 3), 3),
        "stress": _norm_int(signals.get("stress", 2), 2),
        "wins": signals.get("wins", []) or [],
        "needs": signals.get("needs", []) or [],
        "intent": signals.get("intent", "") or "",
    }


def suggest_mood_actions(
    user_id: int,
    db: Session,
    *,
    signals: Optional[Dict[str, Any]] = None,
    voice_intent: Optional[Dict[str, Any]] = None,
    time_context: Optional[Dict[str, Any]] = None,
    max_suggestions: int = 4,
) -> List[Dict[str, Any]]:
    """
    Produce 2–4 gentle mood suggestions (≤5 min micro or small actions).
    Each item:
      {
        "title": str,
        "emoji": str,
        "minutes": int,
        "type": "reflection|sleep|fitness|nutrition|social|chores|study",
        "reason": str,
        "kind": "micro|tip"
      }
    """
    tc = time_context or compute_time_context(user_id, db)
    after_bedtime = tc.get("effective_mins_to_bedtime", 0) == 0

    s = _normalize_signals(signals)
    vm_priority = ((voice_intent or {}).get("priority") or "other").lower()
    intent_summary = (voice_intent or {}).get("intent_summary", "")

    # Base pool—each is a safe ≤5 min micro or tiny action
    pool: List[Dict[str, Any]] = [
        {"title": "Two‑minute breathe/reset", "type": "reflection", "minutes": 2, "emoji": "🫧",
         "reason": "Small reset to settle the mind.", "kind": "micro"},
        {"title": "Micro journal line", "type": "reflection", "minutes": 3, "emoji": "📝",
         "reason": "Capture one thought to declutter.", "kind": "micro"},
        {"title": "Prepare sleep spot", "type": "sleep", "minutes": 5, "emoji": "🛏️",
         "reason": "Set up a calming wind‑down.", "kind": "micro"},
        {"title": "Refill water", "type": "nutrition", "minutes": 2, "emoji": "💧",
         "reason": "Hydration helps focus and energy.", "kind": "micro"},
        {"title": "Quick stretch", "type": "fitness", "minutes": 3, "emoji": "🤸",
         "reason": "Ease tension; better posture.", "kind": "micro"},
        {"title": "Text a friend hello", "type": "social", "minutes": 3, "emoji": "👋",
         "reason": "Light social check‑in; uplifting.", "kind": "micro"},
        {"title": "Desk tidy micro", "type": "chores", "minutes": 3, "emoji": "🧹",
         "reason": "Tiny declutter boosts focus.", "kind": "micro"},
    ]

    # Wind-down restriction after bedtime: only reflection/sleep
    if after_bedtime:
        pool = [m for m in pool if m["type"] in ("reflection", "sleep")]

    # Light tailoring based on signals and voice intent
    suggestions: List[Dict[str, Any]] = []
    energy = s["energy"]
    stress = s["stress"]
    focus = s["focus"]
    mood = s["mood"]

    for m in pool:
        # Stress ↑ → prefer reflection/sleep
        if stress >= 4 and m["type"] not in ("reflection", "sleep"):
            continue
        # Energy low → deprioritize fitness unless short (we have 3 min)
        if energy <= 2 and m["type"] == "fitness" and m["minutes"] > 3:
            continue
        # Focus low → prefer water/reflection/chores tidy
        if focus <= 2 and m["type"] not in ("nutrition", "reflection", "chores"):
            continue
        # Mood low → gentle types (reflection/sleep/nutrition)
        if mood in ("sad", "low") and m["type"] not in ("reflection", "sleep", "nutrition"):
            continue
        # Voice intent hints (study buddy / planning)
        if vm_priority == "study" and m["type"] not in ("reflection", "nutrition", "fitness", "chores", "sleep"):
            # allow only small reset actions that help focus
            continue

        suggestions.append(m)

    # Deduplicate and cap
    seen = set()
    final: List[Dict[str, Any]] = []
    for m in suggestions:
        key = (m["title"], m["type"])
        if key not in seen:
            seen.add(key)
            final.append(m)
        if len(final) >= max_suggestions:
            break

    # Provide minimal fallback if everything filtered out
    if not final:
        final = [
            {"title": "Two‑minute breathe/reset", "type": "reflection", "minutes": 2, "emoji": "🫧",
             "reason": "Small reset to settle the mind.", "kind": "micro"}
        ]

    # Attach a tiny context hint derived from voice intent
    if intent_summary:
        for m in final:
            m["reason"] = (m.get("reason") or "") + " " + "(aligned with your chat intent.)"

    return final
