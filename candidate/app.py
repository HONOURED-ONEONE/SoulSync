import streamlit as st
from soulsync.db import init_db, SessionLocal
from soulsync.models import User
from soulsync.ui.theme import load_css
from soulsync.services.stats import init_stats
from soulsync.services.profile_service import get_or_create_profile

st.set_page_config(page_title="SoulSync", page_icon="✨", layout="wide")

if "db_init" not in st.session_state:
    init_db()
    st.session_state.db_init = True

load_css()

if "user" not in st.session_state:
    st.markdown("<div style='text-align: center; margin-top: 50px;'>", unsafe_allow_html=True)
    st.title("SoulSync ✨")
    st.subheader("Your Student Life RPG")
    st.caption("Local MVP demo login. Do not expose this build as a public multi-user service.")

    with st.form("login_form"):
        email = st.text_input("Email")
        handle = st.text_input("Handle / Name")
        submitted = st.form_submit_button("Start Journey")

        if submitted and email and handle:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.email == email.strip()).first()
                if not user:
                    user = User(email=email.strip(), handle=handle.strip())
                    db.add(user)
                    db.flush()
                    init_stats(user.id, db)
                profile = get_or_create_profile(user.id, db)
                db.commit()
                db.refresh(user)
                db.refresh(profile)
                st.session_state.user = {
                    "id": user.id,
                    "handle": user.handle,
                    "timezone": profile.timezone,
                }
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown(f"### Welcome back, {st.session_state.user['handle']}! 👋")
    st.write("Navigate using the sidebar to check your Missions, Journal, or chat with Your Voice.")
    st.info("👈 Open the sidebar to get started!")
