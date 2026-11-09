"""Small HTML building blocks for the VisionFit UI. Styles live in static/style.css."""
from html import escape
import streamlit as st
from services.config.workout_config import EXERCISE_DISPLAY, STATUS_TONES


def html(markup):
    # Markdown would treat indented lines as code and blank lines as the end of the HTML block.
    flat = "".join(line.strip() for line in markup.splitlines())
    st.markdown(flat, unsafe_allow_html=True)


def wordmark(size="md"):
    return f'<div class="vf-wordmark vf-wordmark--{size}">VISION<span>FIT</span></div>'


def eyebrow(text):
    return f'<div class="vf-eyebrow">{escape(text)}</div>'


def format_duration(seconds):
    seconds = int(seconds or 0)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def rep_counter(current_set_reps, reps_per_set, sets_completed, target_sets, total_reps):
    progress = 0 if not reps_per_set else min(current_set_reps / reps_per_set, 1)
    current_set_number = min(sets_completed + 1, target_sets) if target_sets else 0

    dots = "".join(
        f'<span class="vf-dot {"is-done" if i < sets_completed else ("is-current" if i == sets_completed else "")}"></span>'
        for i in range(target_sets)
    )

    return f"""
    <div class="vf-card vf-reps">
        <div class="vf-card-head">
            {eyebrow("Reps this set")}
            <div class="vf-muted vf-small">{total_reps} total</div>
        </div>
        <div class="vf-reps-value">
            <span class="vf-num">{current_set_reps:02d}</span><span class="vf-reps-target">/ {reps_per_set}</span>
        </div>
        <div class="vf-bar"><span style="width:{progress * 100:.0f}%"></span></div>
        <div class="vf-sets">
            <span class="vf-small vf-strong">Set {current_set_number} of {target_sets}</span>
            <span class="vf-dots">{dots}</span>
        </div>
    </div>
    """


def status_chip(label, value):
    tone = STATUS_TONES.get(value, "neutral")
    shown = "Waiting" if value in (None, "N/A") else str(value).capitalize()

    return f"""
    <div class="vf-status">
        <span class="vf-small vf-muted">{escape(label)}</span>
        <span class="vf-chip vf-chip--{tone}"><i></i>{escape(shown)}</span>
    </div>
    """


def form_panel(exercise, state, pose_detected=True):
    display = EXERCISE_DISPLAY.get(exercise, {})

    chips = "".join(status_chip(label, state.get(key, "N/A")) for key, label in display.get("statuses", []))

    angles = "".join(
        f"""
        <div class="vf-angle">
            <div class="vf-num vf-angle-value">{int(state.get(key, 0) or 0)}°</div>
            <div class="vf-small vf-muted">{escape(label)}</div>
        </div>
        """
        for key, label in display.get("angles", [])
    )

    warning = "" if pose_detected else '<div class="vf-alert">Step back so your whole body is in frame.</div>'

    return f"""
    <div class="vf-card">
        <div class="vf-card-head">{eyebrow("Form")}</div>
        {warning}
        {chips}
        <div class="vf-angles">{angles}</div>
    </div>
    """


def coach_card(text, has_llm=True):
    body = (
        f'<p class="vf-cue">“{escape(text)}”</p>'
        if text
        else '<p class="vf-muted vf-small">Cues show up here and are read out loud when the coach spots something.</p>'
    )
    mode = "" if has_llm else '<div class="vf-small vf-muted vf-mode">Basic mode: add a GROQ_API_KEY for AI-written cues.</div>'

    return f"""
    <div class="vf-card vf-coach">
        <div class="vf-card-head">
            {eyebrow("Coach")}
            <span class="vf-wave" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
        </div>
        {body}
        {mode}
    </div>
    """


def complete_card(exercise, target_sets, reps_per_set, seconds):
    return f"""
    <div class="vf-card vf-complete">
        {eyebrow("Workout complete")}
        <div class="vf-complete-title">{target_sets} × {reps_per_set}</div>
        <div class="vf-muted">{escape(exercise)} · {format_duration(seconds)} active</div>
    </div>
    """


def stat_tiles(stats):
    tiles = "".join(
        f"""
        <div class="vf-tile">
            <div class="vf-num vf-tile-value">{escape(str(value))}</div>
            <div class="vf-small vf-muted">{escape(label)}</div>
        </div>
        """
        for value, label in stats
    )

    return f'<div class="vf-tiles">{tiles}</div>'


def info_card(title, text):
    return f"""
    <div class="vf-card vf-info">
        <div class="vf-strong">{escape(title)}</div>
        <div class="vf-muted vf-small">{escape(text)}</div>
    </div>
    """


def empty_state(title, text):
    return f"""
    <div class="vf-empty">
        <div class="vf-strong">{escape(title)}</div>
        <div class="vf-muted vf-small">{escape(text)}</div>
    </div>
    """
