import streamlit as st
from soulsync.db import SessionLocal
from soulsync.models import VoiceMessage
from soulsync.services.voice import get_ai_response, check_private_memory_permission
from soulsync.services.moderation import check_safety
from soulsync.services.voice_intent import extract_voice_intent_summary
from soulsync.ui.theme import load_css

load_css()
if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Your Voice 💭")
st.caption("A supportive thinking tool. Planning runs only when you choose a planning action.")
user_id = st.session_state.user["id"]
user_tz = st.session_state.user.get("timezone")
st.session_state.setdefault("voice_mode", "Cheer me on")
st.session_state.setdefault("allow_private_memory", False)
mode_options = ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"]
st.session_state.voice_mode = st.selectbox("Mode", mode_options, index=mode_options.index(st.session_state.voice_mode))

db = SessionLocal()
try:
    history = (db.query(VoiceMessage).filter(VoiceMessage.user_id == user_id)
               .order_by(VoiceMessage.created_at).all())
    for message in history:
        with st.chat_message(message.role):
            st.write(message.text)

    if check_private_memory_permission(user_id, db):
        st.session_state.allow_private_memory = st.checkbox(
            "Allow this chat turn to use private recent Journal context",
            value=st.session_state.allow_private_memory,
        )

    prompt = st.chat_input("What would you like help with?")
    if prompt:
        safe, message = check_safety(prompt)
        if not safe:
            st.warning(message)
        else:
            db.add(VoiceMessage(user_id=user_id, role="user", text=prompt))
            response, private_context_available = get_ai_response(
                user_id, prompt, "Student support conversation", db,
                mode=st.session_state.voice_mode,
                allow_private_memory=st.session_state.allow_private_memory,
            )
            db.add(VoiceMessage(user_id=user_id, role="assistant", text=response))
            db.commit()
            if private_context_available:
                st.info("Private Journal context was not used without permission.")
            st.rerun()

    st.markdown("### Tools")
    c1, c2 = st.columns(2)
    recent_user = [m.text for m in history if m.role == "user"][-3:]
    with c1:
        if st.button("Build today's plan from this chat ⚡"):
            st.session_state["latest_voice_intent"] = extract_voice_intent_summary(recent_user, user_timezone=user_tz) if recent_user else None
            st.session_state["open_swaps_on_missions"] = False
            st.switch_page("pages/2_Missions.py")
    with c2:
        if st.button("Suggest swaps from this chat 🔁"):
            st.session_state["latest_voice_intent"] = extract_voice_intent_summary(recent_user, user_timezone=user_tz) if recent_user else None
            st.session_state["open_swaps_on_missions"] = True
            st.switch_page("pages/2_Missions.py")
finally:
    db.close()
