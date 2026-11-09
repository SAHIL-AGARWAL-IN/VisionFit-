import streamlit as st
import time
from services.config.workout_config import METRICS_FIELDS
from services.persistence.exercise_repository import add_exercise


def _submit_voice_event(event, exercise, metrics):
    pipeline = st.session_state.get("voice_pipeline")

    if pipeline:
        pipeline.submit(event=event, exercise=exercise, metrics=metrics)


def sync_metrics_update(context):
    if not context or not hasattr(context, "state") or not context.state.playing:
        return

    processor = getattr(context, "video_processor", None)

    if not processor:
        return

    exercise = st.session_state.get("exercise_type")

    if not exercise:
        return

    processor.set_exercise(exercise)
    latest_metrics = processor.get_latest_metrics()

    if not latest_metrics:
        return

    now_ts = time.time()

    # Start the clock on the first analysed frame, not when "Start workout" was clicked.
    if not st.session_state.get("workout_first_frame_at"):
        st.session_state.workout_first_frame_at = now_ts
        st.session_state.set_cycle_started_at = now_ts

    # A camera restart creates a fresh processor whose rep count starts at 0.
    processor_id = getattr(processor, "instance_id", id(processor))

    if st.session_state.get("processor_id") != processor_id:
        if st.session_state.get("processor_id") is not None:
            st.session_state.rep_offset += st.session_state.get("processor_reps", 0)
        st.session_state.processor_id = processor_id
        st.session_state.processor_reps = 0

    processor_reps = latest_metrics.get("reps") or 0
    st.session_state.processor_reps = processor_reps
    reps = st.session_state.get("rep_offset", 0) + processor_reps

    st.session_state.reps = reps
    st.session_state.pose_detected = latest_metrics.get("pose_detected", True)

    fields = METRICS_FIELDS.get(exercise)

    if not fields:
        return

    for key, default in fields.items():
        st.session_state[key] = latest_metrics.get(key, default)

    reps_per_set = st.session_state.get("reps_per_set", 0)
    target_sets = st.session_state.get("target_sets", 0)

    if reps_per_set > 0 and target_sets > 0:
        sets_completed = min(reps // reps_per_set, target_sets)
        workout_completed = sets_completed >= target_sets
        current_set_reps = reps_per_set if workout_completed else reps % reps_per_set
    else:
        sets_completed = 0
        current_set_reps = 0
        workout_completed = False

    st.session_state.sets_completed = sets_completed
    st.session_state.current_set_reps = current_set_reps
    st.session_state.workout_completed = workout_completed

    last_saved_sets = st.session_state.get("last_saved_sets_completed", 0)

    if sets_completed > last_saved_sets:
        newly_completed = sets_completed - last_saved_sets
        started_at = st.session_state.get("set_cycle_started_at") or now_ts
        time_taken = int(round(now_ts - started_at))
        user_id = st.session_state.get("user_id", 0)

        add_exercise(user_id, exercise, newly_completed * reps_per_set, newly_completed, time_taken)

        if not workout_completed:
            _submit_voice_event("set_completed", exercise, latest_metrics)

        st.session_state.set_cycle_started_at = now_ts
        st.session_state.last_saved_sets_completed = sets_completed

    if workout_completed:
        if not st.session_state.get("last_notified_workout_complete", False):
            st.session_state.last_notified_workout_complete = True
            st.session_state.workout_active_seconds = int(round(now_ts - st.session_state.workout_first_frame_at))
            _submit_voice_event("workout_completed", exercise, latest_metrics)
        return

    if not st.session_state.pose_detected:
        _submit_voice_event(
            "no_pose_detected",
            exercise,
            {"issue": "No pose detected! Please step into the camera frame."},
        )
        return

    _submit_voice_event("ongoing_form_check", exercise, latest_metrics)
