import time

import pytest

from services.coaching.voice_pipeline import FALLBACK_CUES, VoicePipeline
from services.config.workout_config import METRICS_FIELDS


class FakeTTS:
    def speak(self, text):
        return b"mp3:" + text.encode()


class FakeLLM:
    def __init__(self, reply="Drive through your heels."):
        self.reply = reply
        self.calls = []

    def give_feedback(self, event, issue):
        self.calls.append((event, issue))
        return self.reply


def wait_for_cue(pipeline, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = pipeline.poll()
        if result:
            return result
        time.sleep(0.01)
    return None


@pytest.mark.parametrize("exercise", list(METRICS_FIELDS))
def test_default_metrics_raise_no_issue(exercise):
    pipeline = VoicePipeline(None, FakeTTS())
    assert pipeline._find_form_issue(exercise, dict(METRICS_FIELDS[exercise])) is None


@pytest.mark.parametrize("exercise,metrics", [
    ("Squats", {"depth_status": "TOO HIGH"}),
    ("Squats", {"torso_lean": 60}),
    ("Push-ups", {"hip_status": "SAGGING"}),
    ("Push-ups", {"hip_status": "PIKED UP"}),
    ("Biceps Curls (Dumbbell)", {"swing_status": "SWINGING"}),
    ("Shoulder Press", {"back_arch_status": "Excessive Arch"}),
    ("Lunges", {"balance_status": "OFF BALANCE"}),
])
def test_form_issues_are_found(exercise, metrics):
    assert VoicePipeline(None, FakeTTS())._find_form_issue(exercise, metrics)


def test_squat_mild_lean_is_not_an_issue():
    assert VoicePipeline(None, FakeTTS())._find_form_issue("Squats", {"torso_lean": 40}) is None


def test_major_event_uses_llm_and_returns_audio():
    llm = FakeLLM()
    pipeline = VoicePipeline(llm, FakeTTS())

    assert pipeline.submit("workout_started", "Squats", {})
    audio, text, cue_id = wait_for_cue(pipeline)

    assert text == llm.reply
    assert audio == b"mp3:" + llm.reply.encode()
    assert cue_id == 1
    assert pipeline.poll() is None


def test_fallback_cue_without_llm():
    pipeline = VoicePipeline(None, FakeTTS())
    pipeline.submit("set_completed", "Squats", {})
    _, text, _ = wait_for_cue(pipeline)
    assert text in FALLBACK_CUES["set_completed"]


def test_form_cues_are_rate_limited():
    pipeline = VoicePipeline(FakeLLM(), FakeTTS())
    issue = {"depth_status": "TOO HIGH"}

    assert pipeline.submit("ongoing_form_check", "Squats", issue)
    wait_for_cue(pipeline)

    # Same issue straight away: blocked by the cooldown.
    assert not pipeline.submit("ongoing_form_check", "Squats", issue)

    # Global cooldown passed but the same issue is still inside its repeat window.
    pipeline.last_spoken_at -= VoicePipeline.FORM_CUE_COOLDOWN + 1
    assert not pipeline.submit("ongoing_form_check", "Squats", issue)

    # A different issue is allowed once the global cooldown has passed.
    assert pipeline.submit("ongoing_form_check", "Squats", {"torso_lean": 70})


def test_no_issue_means_no_cue():
    pipeline = VoicePipeline(FakeLLM(), FakeTTS())
    assert not pipeline.submit("ongoing_form_check", "Squats", {"depth_status": "GOOD DEPTH"})
