"""
Voice intent summary extraction module.

Extracts a concise intent summary from recent voice chat messages using Gemini,
with deterministic fallback when API unavailable.

Returns intent dict:
{
  "intent_summary": "1-2 lines max",
  "priority": "focus|sleep|stress|confidence|health|relationships|other",
  "constraints": [string]
}
"""

import requests
import json
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID


def extract_voice_intent_summary(
    recent_user_messages: list[str],
    user_timezone: str | None = None
) -> dict:
    """
    Extract concise intent summary from recent voice messages.
    
    Args:
        recent_user_messages: List of recent user messages from voice chat
        user_timezone: Optional user timezone for context
    
    Returns:
        Dict with intent_summary (1-2 lines), priority category, and constraints.
        Falls back to fallback_intent() if Gemini unavailable or messages empty.
    """
    if not recent_user_messages or not GOOGLE_API_KEY:
        return fallback_intent()
    
    try:
        # Join messages for analysis
        messages_str = "\n".join(recent_user_messages[-5:])  # Use last 5 messages max
        
        prompt = f"""Analyze these recent voice chat messages and extract intent. Return ONLY valid JSON, no markdown, no explanation.

User's recent messages:
{messages_str}

Timezone hint: {user_timezone or 'UTC'}

Return this exact JSON structure:
{{
  "intent_summary": "1-2 sentence summary of what user wants to achieve/discuss",
  "priority": "focus|sleep|stress|confidence|health|relationships|other",
  "constraints": ["any specific constraints or blockers mentioned"]
}}"""
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 120
            }
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return fallback_intent()
        
        response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        # Extract JSON from response (strip code fences if present)
        json_str = response_text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        intent = json.loads(json_str)
        
        # Validate required keys
        required_keys = {"intent_summary", "priority", "constraints"}
        if not all(key in intent for key in required_keys):
            return fallback_intent()
        
        # Ensure types and limits
        intent["intent_summary"] = str(intent.get("intent_summary", "")).strip()[:200]
        intent["priority"] = intent.get("priority", "other")
        if intent["priority"] not in ["focus", "sleep", "stress", "confidence", "health", "relationships", "other"]:
            intent["priority"] = "other"
        intent["constraints"] = intent.get("constraints", []) if isinstance(intent.get("constraints"), list) else []
        
        return intent
    
    except Exception as e:
        # Any error (network, JSON parse, etc.) -> fallback
        return fallback_intent()


def fallback_intent() -> dict:
    """
    Return deterministic fallback intent when Gemini unavailable or no messages provided.
    
    Returns:
        Dict matching the intent schema with safe defaults.
    """
    return {
        "intent_summary": "No specific intent yet.",
        "priority": "other",
        "constraints": []
    }


def get_voice_intent_features(user_text: str) -> dict:
    """
    Returns simple, non-private, deterministic features for NIMS.

    This helper does not approve models.
    This helper does not generate responses.
    This helper does not expose journal content.
    """

    text = (user_text or "").lower()

    confusion_markers = [
        "i don't get it",
        "i dont get it",
        "confused",
        "confusing",
        "what?",
        "i'm lost",
        "im lost",
        "too much",
    ]

    planning_markers = [
        "plan",
        "schedule",
        "task",
        "homework",
        "assignment",
        "deadline",
        "study",
    ]

    emotional_intensity_markers = [
        "overwhelmed",
        "angry",
        "sad",
        "stressed",
        "anxious",
        "panic",
        "tired",
    ]

    return {
        "has_confusion": any(marker in text for marker in confusion_markers),
        "has_planning_intent": any(marker in text for marker in planning_markers),
        "has_emotional_intensity": any(marker in text for marker in emotional_intensity_markers),
        "token_count": len(text.split()),
    }

