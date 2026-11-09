import streamlit as st
from services.config.workout_config import METRICS_FIELDS


def initial_session_defaults():
    defaults = {
        "reps": 0,
        "target_sets": 0,
        "reps_per_set": 0,
        "sets_completed": 0,
        "current_set_reps": 0,
        "workout_completed": False,
        "last_notified_workout_complete": False,
        "last_saved_sets_completed": 0,
        "set_cycle_started_at": 0.0,
        "workout_first_frame_at": 0.0,
        "workout_active_seconds": 0,

        # Camera restarts create a new video processor whose rep count starts at 0.
        # rep_offset carries reps from earlier processors so totals keep adding up.
        "rep_offset": 0,
        "processor_id": None,
        "processor_reps": 0,
        "pose_detected": True,

        # Workout plan (set before starting)
        "workout_started": False,
        "plan_exercise": "Squats",
        "plan_sets": 3,
        "plan_reps": 10,

        # Mode switch and video analysis
        "app_mode": "Live workout",
        "analysis_exercise": "Squats",

        # Coaching
        "coach_feedback": None,
        "audio_to_play": None,
        "audio_cue_id": 0,

        # Common Angles
        "knee_angle": 0,
        "back_angle": 0,
        "torso_lean": 0,
        "elbow_angle": 0,
        "front_knee_angle": 0,
        "torso_angle": 0,

        # Status fields
        "depth_status": "N/A",
        "body_alignment": "N/A",
        "hip_status": "N/A",
        "shoulder_status": "N/A",
        "swing_status": "N/A",
        "extension_status": "N/A",
        "back_arch_status": "N/A",
        "balance_status": "N/A",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Streamlit drops widget state for widgets not drawn in a run (the plan form is hidden
    # during a workout, the analysis form in live mode). Re-assigning keeps the plan choices alive until the user returns.
    for key in ("plan_exercise", "plan_sets", "plan_reps", "app_mode", "analysis_exercise"):
        st.session_state[key] = st.session_state[key] or defaults[key]


def reset_workout_progress():
    """Clear per-workout counters before a new workout starts."""
    st.session_state.reps = 0
    st.session_state.sets_completed = 0
    st.session_state.current_set_reps = 0
    st.session_state.workout_completed = False
    st.session_state.last_notified_workout_complete = False
    st.session_state.last_saved_sets_completed = 0
    st.session_state.set_cycle_started_at = 0.0
    st.session_state.workout_first_frame_at = 0.0
    st.session_state.workout_active_seconds = 0
    st.session_state.rep_offset = 0
    st.session_state.processor_id = None
    st.session_state.processor_reps = 0
    st.session_state.pose_detected = True
    st.session_state.coach_feedback = None
    st.session_state.audio_to_play = None

    for fields in METRICS_FIELDS.values():
        for key, default in fields.items():
            st.session_state[key] = default
