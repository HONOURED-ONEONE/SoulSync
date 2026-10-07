import requests
from ..config import GOOGLE_API_KEY, GEMINI_MODEL_ID
from ..models import JournalEntry
from sqlalchemy.orm import Session

VOICE_MODE_PROMPTS = {
    "Cheer me on": "Act as an enthusiastic, supportive coach cheering on the user.",
    "Help me plan": "Help the user organize tasks and create an action plan.",
    "Reflect with me": "Guide the user through reflection and deeper thinking.",
    "Study buddy": "Be a helpful study partner; explain concepts and encourage learning.",
}

def get_ai_response(user_id: int, user_text: str, context: str, db: Session,
                    mode: str = "Cheer me on", allow_private_memory: bool = False):
    """Generate response text only. The page owns VoiceMessage persistence."""
    mode_prompt = VOICE_MODE_PROMPTS.get(mode, VOICE_MODE_PROMPTS["Cheer me on"])
    recent_entries = (db.query(JournalEntry).filter(JournalEntry.user_id == user_id)
                      .order_by(JournalEntry.created_at.desc()).limit(3).all())
    private_entries = []
    public_entries = []
    for entry in recent_entries:
        tags = [t.strip() for t in (entry.tags or "").split(",") if t.strip()]
        (private_entries if {"private", "sensitive"}.intersection(tags) else public_entries).append(entry)
    permitted = list(public_entries) + (private_entries if allow_private_memory else [])
    enhanced_context = context or ""
    if permitted:
        summaries = "; ".join(f"'{e.text[:30]}...'" for e in permitted)
        enhanced_context += f"\nRecent reflections: {summaries}"
    if not GOOGLE_API_KEY:
        response_text = get_fallback_response(mode)
    else:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_ID}:generateContent?key={GOOGLE_API_KEY}"
            payload = {"contents": [{"parts": [{"text": f"{mode_prompt}\n\nContext: {enhanced_context}\n\nUser: {user_text}\n\nRespond as a supportive student life coach."}]}]}
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            response_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"] if resp.status_code == 200 else get_fallback_response(mode)
        except Exception:
            response_text = get_fallback_response(mode)
    return response_text, bool(private_entries and not allow_private_memory)

def get_fallback_response(mode: str):
    fallback_map = {
        "Cheer me on": "You've got this! Keep moving forward. (AI features are in fallback mode.)",
        "Help me plan": "Let's start with your biggest priority today. (AI features are in fallback mode.)",
        "Reflect with me": "What feels most important about this? (AI features are in fallback mode.)",
        "Study buddy": "Let's work through one part at a time. (AI features are in fallback mode.)",
    }
    return fallback_map.get(mode, fallback_map["Cheer me on"])

def check_private_memory_permission(user_id: int, db: Session):
    entries = db.query(JournalEntry).filter(JournalEntry.user_id == user_id).all()
    return any({"private", "sensitive"}.intersection({t.strip() for t in (e.tags or "").split(",")}) for e in entries)
