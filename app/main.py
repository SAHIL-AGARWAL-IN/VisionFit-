import streamlit as st
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv()
load_dotenv(BASE_DIR / ".env")

from services.auth.login_wall import render_login_wall, sign_out
from services.state.session_defaults import initial_session_defaults, reset_workout_progress
from services.config.workout_config import EXERCISE_OPTIONS, EXERCISE_DISPLAY
from services.ui.style_loader import load_css, inject_webrtc_styles
from services.ui import components as ui
from services.persistence.exercise_repository import init_db, get_users_exercises
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from services.vision.exercise_video_processor import VideoProcessorClass
from services.tracking.metrics import sync_metrics_update
from groq import Groq
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio
from services.ui.analysis_screen import render_analysis_screen


APP_MODES = ["Live workout", "Analyse a video"]

WEBRTC_TRANSLATIONS = {
    "start": "Start camera",
    "stop": "Stop camera",
    "select_device": "Switch camera",
    "media_api_not_available": "Camera access isn't available in this browser.",
    "device_ask_permission": "Allow camera access to start tracking.",
    "device_not_available": "No camera found.",
    "device_access_denied": "Camera access was blocked. Allow it in your browser settings.",
}


def _get_groq_api_key():
    api_key = os.environ.get("GROQ_API_KEY", "")

    if not api_key:
        try:
            api_key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            api_key = ""

    return api_key


def init_voice_pipeline():
    if "voice_pipeline" in st.session_state:
        return

    llm_coach = None
    api_key = _get_groq_api_key()

    if api_key:
        try:
            llm_coach = LLMCoach(Groq(api_key=api_key))
        except Exception as e:
            print(f"[VoicePipeline Init Error]: {e}")

    st.session_state.voice_pipeline = VoicePipeline(llm_coach, TextToSpeech())


def collect_voice_cue():
    pipeline = st.session_state.get("voice_pipeline")
    result = pipeline.poll() if pipeline else None

    if result:
        audio, text, cue_id = result
        st.session_state.audio_to_play = audio
        st.session_state.coach_feedback = text
        st.session_state.audio_cue_id = cue_id


def start_workout():
    exercise = st.session_state.get("plan_exercise") or EXERCISE_OPTIONS[0]

    reset_workout_progress()
    st.session_state.exercise_type = exercise
    st.session_state.target_sets = int(st.session_state.plan_sets)
    st.session_state.reps_per_set = int(st.session_state.plan_reps)
    st.session_state.workout_started = True

    pipeline = st.session_state.get("voice_pipeline")
    if pipeline:
        pipeline.submit(event="workout_started", exercise=exercise, metrics={})


def end_workout():
    st.session_state.workout_started = False

    # Workouts that hit their target already got a closing cue.
    already_notified = st.session_state.get("last_notified_workout_complete", False)
    pipeline = st.session_state.get("voice_pipeline")

    if pipeline and not already_notified and st.session_state.get("reps", 0) > 0:
        pipeline.submit(event="workout_completed", exercise=st.session_state.get("exercise_type"), metrics={})


def render_topbar():
    with st.container(horizontal=True, vertical_alignment="center", key="topbar"):
        ui.html(ui.wordmark())
        st.space("stretch")
        ui.html(f'<div class="vf-topbar-user"><span class="vf-hide-sm">Training as </span><strong>{ui.escape(st.session_state.username)}</strong></div>')
        st.button("Sign out", type="tertiary", on_click=sign_out, key="sign_out_button")

    ui.html('<hr class="vf-rule">')


def render_plan_screen():
    plan, history = st.columns([1.05, 1], gap="large")

    with plan:
        ui.html(ui.eyebrow("New workout"))
        ui.html('<div class="vf-page-title" role="heading" aria-level="1">Pick a lift</div>')

        exercise = st.pills(
            "Exercise",
            options=EXERCISE_OPTIONS,
            format_func=lambda e: EXERCISE_DISPLAY[e]["short"],
            key="plan_exercise",
            label_visibility="collapsed",
        )

        if exercise:
            ui.html(ui.info_card("What gets checked", EXERCISE_DISPLAY[exercise]["checks"]))

        sets_col, reps_col = st.columns(2)

        with sets_col:
            st.number_input("Sets", min_value=1, max_value=20, step=1, key="plan_sets")

        with reps_col:
            st.number_input("Reps per set", min_value=1, max_value=50, step=1, key="plan_reps")

        st.button(
            "Start workout",
            type="primary",
            width="stretch",
            key="start_session_button",
            on_click=start_workout,
            disabled=not exercise,
        )

        if exercise:
            ui.html(ui.info_card("Camera tip", EXERCISE_DISPLAY[exercise]["tip"]))

    with history:
        render_history()

    # Plays the closing cue after "End workout" sends the user back here.
    render_coach_audio()


@st.fragment(run_every=1)
def render_coach_audio():
    collect_voice_cue()

    if st.session_state.get("audio_to_play"):
        autoplay_audio(st.session_state.audio_to_play)


def render_workout_screen():
    exercise = st.session_state.get("exercise_type")
    display = EXERCISE_DISPLAY.get(exercise, {})

    head, actions = st.columns([3, 1], vertical_alignment="bottom")

    with head:
        ui.html(ui.eyebrow("Live workout"))
        ui.html(f'<div class="vf-page-title" role="heading" aria-level="1">{ui.escape(exercise)}</div>')
        ui.html(
            f'<div class="vf-muted">{st.session_state.target_sets} sets × {st.session_state.reps_per_set} reps'
            f' · {ui.escape(display.get("tip", ""))}</div>'
        )

    with actions:
        st.button("End workout", key="end_session_button", width="stretch", on_click=end_workout)

    st.write("")

    camera, panel = st.columns([1.55, 1], gap="large")

    with camera:
        ice_servers = [{"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}]
        try:
            if "rtc_configuration" in st.secrets:
                ice_servers = st.secrets["rtc_configuration"].get("iceServers", ice_servers)
        except Exception:
            pass

        with st.container(key="camera-frame"):
            context = webrtc_streamer(
                key="exercise-analysis",
                mode=WebRtcMode.SENDRECV,
                video_processor_factory=VideoProcessorClass,
                rtc_configuration={"iceServers": ice_servers},
                media_stream_constraints={
                    "video": True,
                    "audio": False
                },
                translations=WEBRTC_TRANSLATIONS,
                async_processing=True
            )

    with panel:
        render_live_panel(context)

    inject_webrtc_styles()


@st.fragment(run_every=0.5)
def render_live_panel(context):
    sync_metrics_update(context)
    collect_voice_cue()

    state = st.session_state
    exercise = state.exercise_type
    pipeline = state.get("voice_pipeline")
    playing = bool(context and context.state.playing)

    if state.get("workout_completed"):
        ui.html(ui.complete_card(exercise, state.target_sets, state.reps_per_set, state.workout_active_seconds))

        if st.button("Finish & see history", type="primary", width="stretch", key="finish_workout_button"):
            end_workout()
            st.rerun(scope="app")
    else:
        ui.html(ui.rep_counter(
            state.current_set_reps,
            state.reps_per_set,
            state.sets_completed,
            state.target_sets,
            state.reps,
        ))

    if not playing and not state.get("workout_completed"):
        ui.html(ui.info_card("Ready when you are", "Press Start camera and step back until your whole body is in view."))
    else:
        ui.html(ui.form_panel(exercise, state, pose_detected=state.get("pose_detected", True)))

    ui.html(ui.coach_card(state.get("coach_feedback"), has_llm=bool(pipeline and pipeline.has_llm)))

    if state.get("audio_to_play"):
        autoplay_audio(state.audio_to_play)


def render_history():
    ui.html(ui.eyebrow("Your training"))
    ui.html('<div class="vf-page-title" role="heading" aria-level="2">History</div>')

    user_id = st.session_state.get("user_id", 0)
    rows = get_users_exercises(user_id) if isinstance(user_id, int) else []

    if not rows:
        ui.html(ui.empty_state("No workouts yet", "Finish a set and it shows up here."))
        return

    df = pd.DataFrame(
        [
            {
                "Exercise": row["exercise_name"],
                "Reps": row["reps"],
                "Sets": row["sets"],
                "Seconds": int(row["time"] or 0),
                "Date": row["created_at"],
            }
            for row in rows
        ]
    )
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    week = df[df["Date"] >= date.today() - timedelta(days=6)]
    ui.html(ui.stat_tiles([
        (int(week["Reps"].sum()), "reps this week"),
        (int(week["Sets"].sum()), "sets this week"),
        (int(week["Date"].nunique()), "active days"),
    ]))

    agg_df = (
        df.groupby(["Date", "Exercise"], as_index=False)
        .agg({"Reps": "sum", "Sets": "sum", "Seconds": "sum"})
        .sort_values("Date", ascending=False)
    )
    agg_df["Time"] = agg_df["Seconds"].map(ui.format_duration)

    st.dataframe(
        agg_df[["Date", "Exercise", "Sets", "Reps", "Time"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Date": st.column_config.DateColumn("Date", format="D MMM", width="small"),
            "Sets": st.column_config.NumberColumn("Sets", width="small"),
            "Reps": st.column_config.NumberColumn("Reps", width="small"),
            "Time": st.column_config.TextColumn("Time", width="small"),
        },
    )


def main():
    st.set_page_config(
        page_icon="🏋️",
        page_title="VisionFit — AI Gym Coach",
        initial_sidebar_state="collapsed",
        layout="wide"
    )

    load_css(str(BASE_DIR / "static" / "style.css"))

    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()
    init_voice_pipeline()

    render_topbar()

    if st.session_state.get("workout_started", False):
        render_workout_screen()
        return

    st.segmented_control(
        "Mode",
        options=APP_MODES,
        key="app_mode",
        label_visibility="collapsed",
    )

    if st.session_state.get("app_mode") == "Analyse a video":
        render_analysis_screen()
    else:
        render_plan_screen()


if __name__ == "__main__":
    main()
