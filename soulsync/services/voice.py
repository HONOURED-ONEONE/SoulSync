import requests
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID
from ..models import VoiceMessage, JournalEntry
from sqlalchemy.orm import Session

VOICE_MODE_PROMPTS = {
    "Cheer me on": "Act as an enthusiastic, supportive coach cheering on the user.",
    "Help me plan": "Help the user organize their tasks and create an action plan.",
    "Reflect with me": "Guide the user through reflection and deeper thinking.",
    "Study buddy": "Be a helpful study partner; explain concepts, ask questions, encourage learning."
}

def get_ai_response(user_id: int, user_text: str, context: str, db: Session, mode: str = "Cheer me on"):
    """
    Get AI response with mode support and permission gate for private memory.
    
    Args:
        user_id: User ID
        user_text: User's input text
        context: Base context
        db: Database session
        mode: Voice mode (Cheer me on, Help me plan, Reflect with me, Study buddy)
    """
    # Save user message
    db.add(VoiceMessage(user_id=user_id, role="user", text=user_text))
    db.commit()

    # Build mode-specific prompt
    mode_prompt = VOICE_MODE_PROMPTS.get(mode, VOICE_MODE_PROMPTS["Cheer me on"])
    
    # Check for private memory and implement permission gate
    recent_entries = db.query(JournalEntry).filter(
        JournalEntry.user_id == user_id
    ).order_by(JournalEntry.created_at.desc()).limit(3).all()
    
    private_entries = []
    for entry in recent_entries:
        tags = entry.tags.split(",") if entry.tags else []
        if "private" in tags or "sensitive" in tags:
            private_entries.append(entry)
    
    # If private memory exists, check session state for permission
    enhanced_context = context
    if private_entries:
        if "pending_permission" not in db:
            # Store pending permission request
            db.pending_permission = {
                "user_id": user_id,
                "entries": private_entries
            }
        # Don't include private entries yet without explicit consent
    else:
        # Include recent journal summary
        if recent_entries:
            entry_summaries = "; ".join([f"'{e.text[:30]}...'" for e in recent_entries])
            enhanced_context += f"\nRecent reflections: {entry_summaries}"
    
    if not GOOGLE_API_KEY:
        response_text = get_fallback_response(mode)
    else:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            full_prompt = f"{mode_prompt}\n\nContext: {enhanced_context}\n\nUser: {user_text}\n\nRespond as a supportive student life coach."
            payload = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }]
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                response_text = resp.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                response_text = get_fallback_response(mode)
        except Exception as e:
            response_text = get_fallback_response(mode)

    # Save AI message
    db.add(VoiceMessage(user_id=user_id, role="assistant", text=response_text))
    db.commit()
    return response_text, bool(private_entries)

def get_fallback_response(mode: str):
    """Return deterministic fallback response based on mode when AI is unavailable."""
    fallback_map = {
        "Cheer me on": "You've got this! Keep pushing forward. (AI features are in fallback mode, but I'm rooting for you!)",
        "Help me plan": "Let's break this down: what's your biggest priority today? (AI features are in fallback mode, but I'm here to help organize your thoughts.)",
        "Reflect with me": "That sounds important. What does this mean to you? (AI features are in fallback mode, but I'm listening.)",
        "Study buddy": "Great question! Let me help you think through this. (AI features are in fallback mode, but we can work through it together.)"
    }
    return fallback_map.get(mode, fallback_map["Cheer me on"])

def check_private_memory_permission(user_id: int, db: Session):
    """Check if user has pending private memory permission request."""
    return getattr(db, "pending_permission", {}).get("user_id") == user_id


def generate_raw_voice_response(
    user_text: str,
    context: str | None = None,
    mode: str | None = None,
    provider: str = "gemini",
    model_id: str | None = None,
) -> str:
    """
    Low-level raw semantic response function for NIMS.

    NIMS expects this function to return ungoverned model text.
    Do not apply NIMS arbitration, topic control, or approval logic here.
    """
    mode_map = {
        "support": "Cheer me on",
        "planning": "Help me plan",
        "reflection": "Reflect with me",
        "planner": "Help me plan",
        "mission": "Help me plan",
    }
    mapped_mode = mode_map.get(mode) or mode or "Cheer me on"
    mode_prompt = VOICE_MODE_PROMPTS.get(mapped_mode, VOICE_MODE_PROMPTS["Cheer me on"])
    
    if GOOGLE_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id or GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            enhanced_context = context or ""
            full_prompt = f"{mode_prompt}\n\nContext: {enhanced_context}\n\nUser: {user_text}\n\nRespond as a supportive student life coach."
            payload = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }]
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            pass

    # Safe local fallback response if provider/API is unavailable or failed
    if not user_text.strip():
        return "Please share one thing you want help with."

    return (
        "I understand. Let's keep this clear and simple. "
        "Please tell me the main thing you want to focus on first."
    )

