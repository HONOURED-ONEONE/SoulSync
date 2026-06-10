"""
Journal signals extraction module.

Extracts structured signals from journal text using Gemini JSON-only extraction,
with deterministic fallback when API unavailable.

Returns signals schema:
{
  "mood": "happy|neutral|sad|stressed|angry|tired|excited|anxious|other",
  "energy": 1-5,
  "focus": 1-5,
  "stress": 1-5,
  "wins": [string],
  "blockers": [string],
  "needs": [string],
  "intent": string,
  "privacy_tags": [string],
  "safety_flag": boolean,
  "safety_reason": string
}
"""

import requests
import json
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID


def extract_journal_signals(
    journal_text: str,
    mood_label: str | None = None,
    tags: list[str] | None = None,
    user_timezone: str | None = None
) -> dict:
    """
    Extract structured signals from journal text using Gemini.
    
    Args:
        journal_text: The journal entry text
        mood_label: Optional mood pre-selected by user (happy, sad, etc.)
        tags: Optional tags from journal entry (e.g., ["private", "urgent"])
        user_timezone: Optional user timezone for context
    
    Returns:
        Dict matching the signals schema (with all required keys).
        Falls back to fallback_signals() if Gemini unavailable.
    """
    if not GOOGLE_API_KEY:
        return fallback_signals(mood_label)
    
    try:
        # Build extraction prompt (JSON only, no advice)
        tags_str = ", ".join(tags) if tags else ""
        mood_str = f"Pre-selected mood: {mood_label}. " if mood_label else ""
        
        prompt = f"""Extract signals from this journal entry. Return ONLY valid JSON, no markdown, no explanation.

{mood_str}Tags: {tags_str}
Timezone hint: {user_timezone or 'UTC'}

Journal entry:
{journal_text}

Return this exact JSON structure (no extra text):
{{
  "mood": "happy|neutral|sad|stressed|angry|tired|excited|anxious|other",
  "energy": 1-5,
  "focus": 1-5,
  "stress": 1-5,
  "wins": ["list of positive things mentioned"],
  "blockers": ["list of obstacles or challenges"],
  "needs": ["list of what user needs or wants"],
  "intent": "one short sentence summarizing the core intent",
  "privacy_tags": ["tags indicating sensitivity level"],
  "safety_flag": true if content mentions harm/risk, false otherwise,
  "safety_reason": "empty string if safe, brief reason if unsafe"
}}"""
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300
            }
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return fallback_signals(mood_label)
        
        response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        # Extract JSON from response (strip code fences if present)
        json_str = response_text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        signals = json.loads(json_str)
        
        # Validate all required keys are present
        required_keys = {
            "mood", "energy", "focus", "stress",
            "wins", "blockers", "needs", "intent",
            "privacy_tags", "safety_flag", "safety_reason"
        }
        
        if not all(key in signals for key in required_keys):
            return fallback_signals(mood_label)
        
        # Ensure types are correct
        signals["energy"] = int(min(5, max(1, signals.get("energy", 3))))
        signals["focus"] = int(min(5, max(1, signals.get("focus", 3))))
        signals["stress"] = int(min(5, max(1, signals.get("stress", 3))))
        signals["wins"] = signals.get("wins", []) if isinstance(signals.get("wins"), list) else []
        signals["blockers"] = signals.get("blockers", []) if isinstance(signals.get("blockers"), list) else []
        signals["needs"] = signals.get("needs", []) if isinstance(signals.get("needs"), list) else []
        signals["intent"] = str(signals.get("intent", "")).strip()
        signals["privacy_tags"] = signals.get("privacy_tags", []) if isinstance(signals.get("privacy_tags"), list) else []
        signals["safety_flag"] = bool(signals.get("safety_flag", False))
        signals["safety_reason"] = str(signals.get("safety_reason", "")).strip()
        
        return signals
    
    except Exception as e:
        # Any error (network, JSON parse, etc.) -> fallback
        return fallback_signals(mood_label)


def fallback_signals(mood_label: str | None = None) -> dict:
    """
    Return deterministic fallback signals when Gemini is unavailable.
    
    Args:
        mood_label: Optional pre-selected mood to use
    
    Returns:
        Dict matching the signals schema with safe defaults.
    """
    mood_map = {
        "happy": {"mood": "happy", "energy": 5, "focus": 4, "stress": 1},
        "sad": {"mood": "sad", "energy": 2, "focus": 2, "stress": 4},
        "stressed": {"mood": "stressed", "energy": 2, "focus": 2, "stress": 5},
        "angry": {"mood": "angry", "energy": 4, "focus": 3, "stress": 4},
        "tired": {"mood": "tired", "energy": 1, "focus": 2, "stress": 2},
        "excited": {"mood": "excited", "energy": 5, "focus": 4, "stress": 1},
        "anxious": {"mood": "anxious", "energy": 3, "focus": 2, "stress": 4},
    }
    
    base_mood = mood_map.get(mood_label, {
        "mood": "neutral",
        "energy": 3,
        "focus": 3,
        "stress": 2
    })
    
    return {
        "mood": base_mood.get("mood", "neutral"),
        "energy": base_mood.get("energy", 3),
        "focus": base_mood.get("focus", 3),
        "stress": base_mood.get("stress", 2),
        "wins": [],
        "blockers": [],
        "needs": [],
        "intent": "No entry analyzed (AI offline)",
        "privacy_tags": [],
        "safety_flag": False,
        "safety_reason": ""
    }


def get_nims_safe_journal_signals(user_id: int, db) -> dict:
    """
    Returns only aggregate journal-derived signals for NIMS.

    Privacy boundary:
    - Do not return raw journal text.
    - Do not return exact journal entries.
    - Do not return quotes.
    - Do not return private names or sensitive details.
    """

    # MVP default. Later this can call existing journal signal extraction logic.
    signals = {
        "energy": "unknown",
        "stress": "unknown",
        "focus_need": "unknown",
        "source": "safe_aggregate_only",
    }

    try:
        # If the project already has a signal extractor, integrate it here.
        if "extract_journal_signals" in globals():
            extracted = extract_journal_signals(user_id=user_id, db=db)

            if isinstance(extracted, dict):
                signals["energy"] = extracted.get("energy", "unknown")
                signals["stress"] = extracted.get("stress", "unknown")
                signals["focus_need"] = extracted.get("focus_need", "unknown")

        elif "get_latest_journal_signals" in globals():
            extracted = get_latest_journal_signals(user_id=user_id, db=db)

            if isinstance(extracted, dict):
                signals["energy"] = extracted.get("energy", "unknown")
                signals["stress"] = extracted.get("stress", "unknown")
                signals["focus_need"] = extracted.get("focus_need", "unknown")

    except Exception:
        # Never fail Your Voice just because journal signals are unavailable.
        pass

    return signals

