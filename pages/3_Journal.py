import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.journal import add_entry
from soulsync.services.missions import generate_daily_missions, compute_time_context
from soulsync.ui.theme import load_css

try:
    from soulsync.services.journal_signals import extract_journal_signals
except Exception:
    extract_journal_signals = None

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Daily Journal 📔")
st.caption("This is your private log. It doesn't judge you. ✅")

st.session_state.setdefault("latest_journal_signals", None)
st.session_state.setdefault("go_to_missions", False)
st.session_state.setdefault("open_swaps_on_missions", False)

with st.form("journal_form"):
    st.subheader("How are you today?")
    mood = st.slider("Mood (1-10)", 1, 10, 7)
    st.subheader("Health Check")
    col1, col2 = st.columns(2)
    sleep = col1.number_input("Sleep (hours)", 0.0, 24.0, 7.0)
    water = col2.number_input("Water (cups)", 0, 20, 5)
    col3, col4 = st.columns(2)
    study = col3.number_input("Study (mins)", 0, 600, 30)
    move = col4.number_input("Movement (mins)", 0, 600, 15)
    st.subheader("Reflection")
    text = st.text_area("What's on your mind?")
    good_thing = st.text_input("One good thing today")
    submitted = st.form_submit_button("Check In")

if submitted:
    metrics = {"sleep_hours": sleep, "water_cups": water, "study_minutes": study, "movement_minutes": move, "good_thing": good_thing}
    user_id = st.session_state.user["id"]
    db = SessionLocal()
    try:
        add_entry(user_id, text, mood, metrics, db)
        mood_label = "happy" if mood >= 8 else "neutral" if mood >= 5 else "sad"
        if extract_journal_signals is not None:
            signals = extract_journal_signals(journal_text=text or "", mood_label=mood_label, tags=None, user_timezone=st.session_state.user.get("timezone"))
        else:
            signals = {"mood":"neutral","energy":3,"focus":3,"stress":2,"wins":[good_thing] if good_thing else [],"blockers":[],"needs":[],"intent":"Have a better day tomorrow.","privacy_tags":[],"safety_flag":False,"safety_reason":""}
        st.session_state["latest_journal_signals"] = signals
        generate_daily_missions(user_id, metrics, db)
    finally:
        db.close()

    st.success("Entry saved! ✅ Signals updated for planning.")
    if st.session_state["latest_journal_signals"]:
        s = st.session_state["latest_journal_signals"]
        st.markdown("### Signals detected (for planning)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Energy", s.get("energy", 3))
        c2.metric("Focus", s.get("focus", 3))
        c3.metric("Stress", s.get("stress", 2))

    st.divider()
    st.subheader("Suggested Micro Actions (≤5 min)")
    db2 = SessionLocal()
    try:
        time_ctx = compute_time_context(user_id, db2)
    finally:
        db2.close()
    after_bedtime = time_ctx.get("effective_mins_to_bedtime", 0) == 0
    s = st.session_state["latest_journal_signals"] or {}
    energy = int(s.get("energy", 3) or 3)
    stress = int(s.get("stress", 2) or 2)
    focus = int(s.get("focus", 3) or 3)
    mood_tag = (s.get("mood") or "neutral").lower()

    micro_pool = [
        {"title": "Two-minute breathe/reset", "type": "reflection", "minutes": 2, "emoji": "🫧"},
        {"title": "Quick stretch", "type": "fitness", "minutes": 3, "emoji": "🤸"},
        {"title": "Refill water", "type": "nutrition", "minutes": 2, "emoji": "💧"},
        {"title": "Micro journal line", "type": "reflection", "minutes": 3, "emoji": "📝"},
        {"title": "Prepare sleep spot", "type": "sleep", "minutes": 5, "emoji": "🛏️"},
        {"title": "Text a friend hello", "type": "social", "minutes": 3, "emoji": "👋"},
    ]
    if after_bedtime:
        micro_pool = [m for m in micro_pool if m["type"] in ("reflection", "sleep")]

    tailored = []
    for m in micro_pool:
        if after_bedtime or stress >= 4:
            if m["type"] in ("reflection", "sleep"):
                tailored.append(m)
                continue
        if energy <= 2 and m["type"] == "fitness":
            continue
        if focus <= 2 and m["type"] in ("nutrition", "reflection"):
            tailored.append(m)
            continue
        if mood_tag in ("sad", "low"):
            if m["type"] in ("reflection", "sleep", "nutrition"):
                tailored.append(m)
                continue
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
                if st.button("Use this now →", key=f"btn_micro_sugg_{idx}"):
                    try:
                        st.switch_page("pages/1_Dashboard.py")
                    except Exception:
                        st.info("Go to the Dashboard to review your agenda.")
    else:
        st.caption("No micro suggestions right now. You can review your agenda on the Dashboard.")

    st.divider()
    st.subheader("What do you want to do next?")
    st.write("Review your agenda and take action from the Dashboard.")
    colA, colB = st.columns(2)
    with colA:
        if st.button("Open Dashboard 📊", key="btn_journal_to_dashboard"):
            try:
                st.switch_page("pages/1_Dashboard.py")
            except Exception:
                st.info("Go to the Dashboard to view your agenda.")
    with colB:
        if st.button("Continue chatting", key="btn_journal_to_voice"):
            try:
                st.switch_page("pages/4_Your_Voice.py")
            except Exception:
                st.info("Go to Your Voice to continue chatting.")
