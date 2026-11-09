import streamlit as st
from services.persistence.exercise_repository import get_or_create_user
from services.ui.components import html, wordmark


def render_login_wall():
    if st.session_state.get("user_id") is not None:
        return True

    hero, side = st.columns([1.15, 1], gap="large")

    with hero:
        html(wordmark("lg"))
        html('<div class="vf-hero-title" role="heading" aria-level="1">Your webcam is<br>your <em>spotter.</em></div>')
        html(
            '<p class="vf-lede">Pick a lift, step in front of the camera, and VisionFit counts '
            'every rep, checks your form, and calls out fixes out loud.</p>'
        )

        with st.container(key="login-card"):
            with st.form("login_form", clear_on_submit=False, border=False):
                username = st.text_input("Your name", placeholder="e.g. sahil")
                submit_button = st.form_submit_button("Start training  →", type="primary", width="stretch")

            st.caption("No password, no sign-up. The same name brings back the same history.")

    with side:
        html(
            """
            <div class="vf-card vf-login-side">
                <div class="vf-eyebrow">Five lifts</div>
                <div class="vf-login-list">
                    <div><span class="vf-strong">Squats</span><span class="vf-muted vf-small">depth & torso lean</span></div>
                    <div><span class="vf-strong">Push-ups</span><span class="vf-muted vf-small">elbow depth & body line</span></div>
                    <div><span class="vf-strong">Biceps curls</span><span class="vf-muted vf-small">range & elbow drift</span></div>
                    <div><span class="vf-strong">Shoulder press</span><span class="vf-muted vf-small">lockout & back arch</span></div>
                    <div><span class="vf-strong">Lunges</span><span class="vf-muted vf-small">knee depth & balance</span></div>
                </div>
            </div>
            """
        )

    if submit_button:
        username = (username or "").strip()

        if not username:
            st.error("Enter a name to continue.")
            return False

        user = get_or_create_user(username)

        st.session_state["user_id"] = user["id"]
        st.session_state["username"] = user["username"]

        st.rerun()

    return False


def sign_out():
    for key in list(st.session_state.keys()):
        if key != "voice_pipeline":
            del st.session_state[key]
