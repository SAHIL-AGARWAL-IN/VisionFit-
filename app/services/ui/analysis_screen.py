"""'Video analysis' mode: upload a clip and get an annotated video plus a per-rep report."""
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from services.analysis.rep_report import PRIMARY_MOTION, primary_angle_key
from services.analysis.video_analyzer import MAX_SECONDS, analyze_video
from services.config.workout_config import EXERCISE_OPTIONS, EXERCISE_DISPLAY
from services.persistence.exercise_repository import add_exercise
from services.ui import components as ui


SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
UPLOAD_TYPES = ["mp4", "mov", "m4v", "webm", "avi", "mkv"]


def _sample_path(exercise):
    path = SAMPLES_DIR / f"{EXERCISE_DISPLAY[exercise]['short'].lower()}.mp4"
    return path if path.exists() else None


def _run_analysis(source, name, exercise):
    progress = st.progress(0.0, text="Analysing frames…")

    if hasattr(source, "seek"):
        source.seek(0)

    try:
        result = analyze_video(source, exercise, progress=lambda f: progress.progress(f, text=f"Analysing frames… {f:.0%}"))
    except Exception as e:
        progress.empty()
        st.error(f"Couldn't analyse that file: {e}")
        return

    progress.empty()
    st.session_state.analysis = result
    st.session_state.analysis_name = name
    st.session_state.analysis_saved = False


def render_analysis_screen():
    setup, results = st.columns([1, 1.65], gap="large")

    with setup:
        ui.html(ui.eyebrow("Video analysis"))
        ui.html('<div class="vf-page-title" role="heading" aria-level="1">Analyse a clip</div>')

        exercise = st.pills(
            "Exercise",
            options=EXERCISE_OPTIONS,
            format_func=lambda e: EXERCISE_DISPLAY[e]["short"],
            key="analysis_exercise",
            label_visibility="collapsed",
        )

        uploaded = st.file_uploader(
            "Workout video",
            type=UPLOAD_TYPES,
            key="analysis_upload",
            help=f"Up to {MAX_SECONDS} seconds are analysed.",
        )

        if st.button("Analyse video", type="primary", width="stretch", disabled=not (exercise and uploaded)):
            _run_analysis(uploaded, uploaded.name, exercise)

        sample = _sample_path(exercise) if exercise else None
        if sample and st.button(f"Try the sample {EXERCISE_DISPLAY[exercise]['short'].lower()} clip", width="stretch"):
            with open(sample, "rb") as f:
                _run_analysis(f, sample.name, exercise)

        tip = EXERCISE_DISPLAY[exercise]["tip"] if exercise else "Film side-on with your whole body in frame."
        ui.html(ui.info_card("Filming tip", tip))
        ui.html(ui.info_card("Privacy", "The clip is processed in memory and thrown away. Nothing is stored unless you save the result to your history."))

    with results:
        analysis = st.session_state.get("analysis")

        if analysis is None:
            ui.html(ui.empty_state(
                "Your report shows up here",
                "Upload a clip and you'll get the video back with the skeleton drawn on, a score for every rep, and the rep that needs the most work.",
            ))
            return

        render_results(analysis)


def render_results(analysis):
    report = analysis.report
    display = EXERCISE_DISPLAY[analysis.exercise]

    ui.html(ui.eyebrow(f"{display['short']} · {st.session_state.get('analysis_name', 'clip')}"))

    ui.html(ui.stat_tiles([
        (report.rep_count, "reps counted"),
        (report.average_score if report.average_score is not None else "–", "average score"),
        (f"{report.average_tempo}s" if report.average_tempo is not None else "–", "average rep time"),
    ]))

    facts = [
        f"Pose found in {report.pose_coverage:.0%} of {analysis.frame_count} frames",
        f"pose model {analysis.inference_p50} ms per frame (p95 {analysis.inference_p95} ms)",
    ]
    if report.shallow_attempts:
        facts.append(f"{report.shallow_attempts} shallow attempt{'s' if report.shallow_attempts != 1 else ''} not counted")
    ui.html(f'<div class="vf-muted vf-small vf-facts">{ui.escape(" · ".join(facts))}</div>')

    if analysis.truncated:
        st.warning(f"Only the first {MAX_SECONDS} seconds were analysed.")

    st.video(analysis.video_bytes, format="video/mp4")

    if not report.reps:
        ui.html(ui.info_card(
            "No reps counted",
            "Check the exercise matches the clip, and that the camera sees the whole body side-on. "
            "Reps only count when the joint passes the thresholds listed under 'What gets checked'.",
        ))
    else:
        render_angle_chart(analysis)
        render_rep_table(report)
        render_worst_rep(analysis)

    actions = st.columns(2)
    with actions[0]:
        st.download_button(
            "Download annotated video",
            data=analysis.video_bytes,
            file_name=f"visionfit-{display['short'].lower()}-analysis.mp4",
            mime="video/mp4",
            width="stretch",
        )
    with actions[1]:
        saved = st.session_state.get("analysis_saved", False)
        if st.button("Saved to history" if saved else "Save to history", width="stretch", disabled=saved or not report.reps):
            add_exercise(
                st.session_state.get("user_id", 0),
                analysis.exercise,
                report.rep_count,
                1,
                int(round(sum(r.duration for r in report.reps))),
            )
            st.session_state.analysis_saved = True
            st.rerun()


def render_angle_chart(analysis):
    report = analysis.report
    angle_key = primary_angle_key(analysis.exercise)
    angle_label = EXERCISE_DISPLAY[analysis.exercise]["angles"][0][1]
    threshold = PRIMARY_MOTION[analysis.exercise]["threshold"]

    points = pd.DataFrame(
        [{"t": f["t"], "angle": f.get(angle_key, 0)} for f in analysis.timeline if f.get("pose_detected")]
    )
    reps = pd.DataFrame(
        [{"start": r.start_t, "end": r.end_t, "rep": str(r.number), "score": r.score} for r in report.reps]
    )
    worst = report.worst_rep

    x = alt.X("t:Q", title="Seconds")
    bands = alt.Chart(reps).mark_rect(opacity=0.08, color="#0F1012").encode(x="start:Q", x2="end:Q")
    worst_band = alt.Chart(reps[reps["rep"] == str(worst.number)]).mark_rect(opacity=0.18, color="#FF4F12").encode(
        x="start:Q", x2="end:Q"
    )
    line = alt.Chart(points).mark_line(color="#0F1012", strokeWidth=2).encode(
        x=x,
        y=alt.Y("angle:Q", title=f"{angle_label} angle (°)", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("t:Q", title="Seconds"), alt.Tooltip("angle:Q", title="Angle")],
    )
    rule = alt.Chart(pd.DataFrame({"y": [threshold]})).mark_rule(color="#FF4F12", strokeDash=[6, 4]).encode(y="y:Q")
    labels = alt.Chart(reps).mark_text(dy=-4, baseline="bottom", fontWeight="bold", color="#5B5F66").encode(
        x="end:Q", y=alt.value(0), text="rep:N"
    )

    ui.html('<div class="vf-section-label">Joint angle over the clip</div>')
    st.altair_chart(
        (bands + worst_band + line + rule + labels).properties(height=240).configure_view(stroke=None),
        width="stretch",
    )
    ui.html(
        f'<div class="vf-muted vf-small">Grey bands are counted reps, orange is the weakest one, '
        f'and the dashed line is the {threshold}° counting threshold.</div>'
    )


def render_rep_table(report):
    rows = pd.DataFrame([
        {
            "Rep": r.number,
            "Score": r.score,
            "Deepest angle": f"{r.peak_angle}°",
            "Time": f"{r.duration:.1f}s",
            "Form flags": ", ".join(r.faults) if r.faults else "—",
        }
        for r in report.reps
    ])

    ui.html('<div class="vf-section-label">Rep by rep</div>')
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Rep": st.column_config.NumberColumn("Rep", width="small"),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d", width="small"),
            "Deepest angle": st.column_config.TextColumn("Deepest", width="small"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Form flags": st.column_config.TextColumn("Form flags", width="large"),
        },
    )


def render_worst_rep(analysis):
    worst = analysis.report.worst_rep
    if worst is None:
        return

    ui.html('<div class="vf-section-label">Rep that needs the most work</div>')

    notes = "; ".join(worst.notes) if worst.notes else "clean rep, just the lowest score in the set"

    if analysis.worst_frame_jpeg:
        image_col, text_col = st.columns([1.3, 1], vertical_alignment="center")
        with image_col:
            st.image(analysis.worst_frame_jpeg, width="stretch")
    else:
        text_col = st.container()

    with text_col:
        ui.html(f"""
        <div class="vf-card">
            <div class="vf-eyebrow">Rep {worst.number} · {worst.peak_t:.1f}s</div>
            <div class="vf-complete-title vf-ink">{worst.score}<span class="vf-reps-target"> / 100</span></div>
            <div class="vf-muted vf-small">{ui.escape(notes.capitalize())}.</div>
        </div>
        """)
