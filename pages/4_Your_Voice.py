import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.services.voice import get_ai_response
from soulsync.services.moderation import check_safety
from soulsync.models import VoiceMessage, JournalEntry
from soulsync.ui.theme import load_css

try:
    from soulsync.config import NIMS_ENABLED, NIMS_DEBUG_PANEL
except Exception:
    NIMS_ENABLED = False
    NIMS_DEBUG_PANEL = False

try:
    from soulsync.services.nims.runtime_guard import run_nims_guarded_turn
    from soulsync.services.nims.errors import NoApprovedModelError, RuntimeGuardRejected
except Exception:
    run_nims_guarded_turn = None

    class NoApprovedModelError(Exception):
        pass

    class RuntimeGuardRejected(Exception):
        pass

try:
    from soulsync.services.voice_intent import extract_voice_intent_summary
except Exception:
    extract_voice_intent_summary = None

from soulsync.services.missions import compute_time_context

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Your Voice 💭")
st.caption("Optimistic, but honest. A thinking tool — not a diary. Planning happens only when you click a tool button.")

st.session_state.setdefault("voice_mode", "Cheer me on")
st.session_state.setdefault("latest_voice_intent", None)
st.session_state.setdefault("open_swaps_on_missions", False)

user_id = st.session_state.user["id"]
user_tz = st.session_state.user.get("timezone")

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("Chat")
with col2:
    st.session_state.voice_mode = st.selectbox(
        "Mode",
        ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"],
        index=["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"].index(st.session_state.voice_mode) if st.session_state.voice_mode in ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"] else 0,
        key="voice_mode_select",
    )

if NIMS_DEBUG_PANEL:
    if st.button("Reset NIMS topic ledger"):
        st.session_state.pop("nims_topic_ledger", None)
        st.success("NIMS topic ledger reset.")

db = SessionLocal()
try:
    history = db.query(VoiceMessage).filter(VoiceMessage.user_id == user_id).order_by(VoiceMessage.created_at).all()

    st.markdown("### Tools")
    st.button("Open Dashboard", key="btn_voice_dashboard", on_click=lambda: None)
    if st.button("Open Dashboard"):
        try:
            st.switch_page("pages/1_Dashboard.py")
        except Exception:
            st.info("Go to the Dashboard to view your agenda.")

    if st.session_state.get("latest_voice_intent"):
        vi = st.session_state["latest_voice_intent"]
        st.caption(f"🧭 Intent summary saved: **{vi.get('intent_summary','')}**")

    st.divider()
    st.subheader("Suggested Micro Actions (≤5 min)")
    time_ctx = compute_time_context(user_id, db)
    after_bedtime = time_ctx.get("effective_mins_to_bedtime", 0) == 0
    if after_bedtime:
        st.info("🌙 After bedtime: gentle wind‑down. Reflection/sleep micros only.")

    vm = st.session_state.voice_mode
    vi = st.session_state.get("latest_voice_intent") or {"priority": "other", "intent_summary": ""}
    priority = (vi.get("priority") or "other").lower()

    micro_pool = [
        {"title": "Two‑minute breathe/reset", "type": "reflection", "minutes": 2, "emoji": "🫧"},
        {"title": "Micro journal line", "type": "reflection", "minutes": 3, "emoji": "📝"},
        {"title": "Prepare sleep spot", "type": "sleep", "minutes": 5, "emoji": "🛏️"},
        {"title": "Quick stretch", "type": "fitness", "minutes": 3, "emoji": "🤸"},
        {"title": "Refill water", "type": "nutrition", "minutes": 2, "emoji": "💧"},
        {"title": "Text a friend hello", "type": "social", "minutes": 3, "emoji": "👋"},
        {"title": "Desk tidy micro", "type": "chores", "minutes": 3, "emoji": "🧹"},
    ]
    if after_bedtime:
        micro_pool = [m for m in micro_pool if m["type"] in ("reflection", "sleep")]

    tailored = []
    for m in micro_pool:
        if vm == "Reflect with me" and m["type"] == "reflection":
            tailored.append(m); continue
        if vm == "Study buddy" or priority == "study":
            if m["type"] in ("reflection", "nutrition", "fitness"):
                tailored.append(m); continue
        if vm == "Cheer me on":
            if m["type"] in ("reflection", "social", "nutrition"):
                tailored.append(m); continue
        tailored.append(m)

    seen = set(); suggestions = []
    for m in tailored:
        key = (m["title"], m["type"])
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(m)
    suggestions = suggestions[:4]

    if suggestions:
        for idx, m in enumerate(suggestions, start=1):
            cols = st.columns([6, 2])
            with cols[0]:
                st.markdown(f"**{m['emoji']} {m['title']}**")
                st.caption(f"Micro • {m['type']} • {m['minutes']} min")
            with cols[1]:
                if st.button("Use this now →", key=f"btn_voice_micro_{idx}"):
                    st.session_state["latest_voice_intent"] = {"intent_summary": "Micro action selected from voice chat.", "priority": "other", "constraints": []}
                    st.session_state["micro_hint"] = {"title": m["title"], "type": m["type"], "minutes": m["minutes"]}
                    try:
                        st.switch_page("pages/1_Dashboard.py")
                    except Exception:
                        st.info("Go to the Dashboard to apply actions.")
    else:
        st.caption("No micro suggestions right now. You can review your agenda on the Dashboard.")

    st.divider()
    for msg in history:
        cls = "ss-bubble-user" if msg.role == "user" else "ss-bubble-assistant"
        st.markdown(f'<div class="{cls}">{msg.text}</div><div style="clear: both;"></div>', unsafe_allow_html=True)

    st.write("")

    has_private = False
    recent_entries = db.query(JournalEntry).filter(JournalEntry.user_id == user_id).order_by(JournalEntry.created_at.desc()).limit(3).all()
    for entry in recent_entries:
        tags = []
        try:
            tags = entry.tags.split(",") if entry.tags else []
            tags = [t.strip().lower() for t in tags]
        except Exception:
            tags = []
        if "private" in tags or "sensitive" in tags:
            has_private = True
            break

    if has_private and "private_memory_approved" not in st.session_state:
        st.info("I found something you wrote that might help. Use it?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, use it", key="btn_private_yes"):
                st.session_state.private_memory_approved = True
                st.rerun()
        with c2:
            if st.button("No, keep it private", key="btn_private_no"):
                st.session_state.private_memory_approved = False
                st.rerun()

    user_input = st.chat_input("What's on your mind?")
    if user_input:
        safe, warning = check_safety(user_input)
        if not safe:
            st.error(warning)
        else:
            umsg = VoiceMessage(user_id=user_id, role="user", text=user_input, created_at=datetime.utcnow())
            db.add(umsg)
            db.commit()
            context = f"User mode: {st.session_state.voice_mode}. User is a student."
            if NIMS_ENABLED and run_nims_guarded_turn is not None:
                try:
                    nims_topic_ledger = st.session_state.get("nims_topic_ledger")
                    nims_result = run_nims_guarded_turn(db=db, user_id=user_id, user_text=user_input, voice_mode=st.session_state.voice_mode, context=context, topic_ledger=nims_topic_ledger)
                    response = nims_result["final_text"]
                    st.session_state["nims_topic_ledger"] = nims_result.get("topic_ledger", {})
                except NoApprovedModelError:
                    response = "Your Voice is currently in safe fallback mode because no approved conversation model is active."
                except RuntimeGuardRejected:
                    response = "I want to keep this safe and clear. Could you rephrase that in one sentence?"
                except Exception:
                    response = "I had trouble generating a governed response. Let's keep it simple: what is one thing you want help with?"
            else:
                response, has_private_used = get_ai_response(user_id=user_id, user_text=user_input, context=context, db=db, mode=st.session_state.voice_mode)
            if response:
                last_assistant = db.query(VoiceMessage).filter(VoiceMessage.user_id == user_id, VoiceMessage.role == "assistant").order_by(VoiceMessage.created_at.desc()).first()
                if not last_assistant or (last_assistant.text or "").strip() != (response or "").strip():
                    amsg = VoiceMessage(user_id=user_id, role="assistant", text=response, created_at=datetime.utcnow())
                    db.add(amsg)
                    db.commit()
            st.rerun()
finally:
    db.close()
