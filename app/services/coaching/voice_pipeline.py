import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import streamlit as st


MAJOR_EVENTS = ("workout_started", "set_completed", "workout_completed")

# Used when no LLM is configured (or every model call fails).
FALLBACK_CUES = {
    "workout_started": [
        "Let's go. Set up tall, brace your core, and start your first rep.",
        "Camera's on you. Smooth, controlled reps from the very first one.",
    ],
    "set_completed": [
        "Set done. Great work, shake it out and get ready for the next one.",
        "That's a full set. Breathe, reset, and keep that form sharp.",
    ],
    "workout_completed": [
        "Workout complete. Strong session, be proud of that effort.",
        "That's everything. Great job today, now recover well.",
    ],
    "no_pose_detected": [
        "I can't see you. Step back so your whole body is in the frame.",
    ],
    "ongoing_form_check": [
        "Watch your form. Slow it down and control every rep.",
    ],
}


class VoicePipeline:
    """Generates spoken coaching cues on a background thread so the UI never blocks."""

    FORM_CUE_COOLDOWN = 5
    REPEAT_ISSUE_COOLDOWN = 15

    def __init__(self, llm, tts):
        self.llm = llm
        self.tts = tts
        self.last_spoken_at = 0
        self._issue_spoken_at = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-cue")
        self._lock = threading.Lock()
        self._pending = 0
        self._result = None
        self._cue_id = 0

    @property
    def has_llm(self):
        return self.llm is not None

    def _find_form_issue(self, exercise, metrics):
        if "issue" in metrics:
            return metrics["issue"]

        if exercise == "Squats":
            depth = metrics.get("depth_status", "")
            torso_lean = metrics.get("torso_lean", 0)

            if depth == "TOO HIGH":
                return "The user's squat is not deep enough — knees are not bending sufficiently."

            if isinstance(torso_lean, (int, float)) and torso_lean > 55:
                return "The user is leaning too far forward during the squat."

        elif exercise == "Push-ups":
            alignment = metrics.get("body_alignment", "")
            hip_status = metrics.get("hip_status", "")

            if alignment == "Poor Form":
                return "The user's body is not straight during the push-up."

            if hip_status == "SAGGING":
                return "The user's hips are sagging down during the push-up."

            if hip_status == "PIKED UP":
                return "The user's hips are too high — lower them to form a straight line."

        elif exercise == "Biceps Curls (Dumbbell)":
            swing = metrics.get("swing_status", "")
            shoulder = metrics.get("shoulder_status", "")

            if swing == "SWINGING":
                return "The user is swinging their torso during the curl — keep the body still."

            if shoulder == "ELBOW DRIFTING":
                return "The user's elbow is drifting away from their side during the curl."

        elif exercise == "Shoulder Press":
            back_arch = metrics.get("back_arch_status", "")

            if back_arch == "Excessive Arch":
                return "The user is arching their lower back excessively during the press."

            if back_arch == "Slight Arch":
                return "Slight back arch detected — encourage the user to brace their core."

        elif exercise == "Lunges":
            balance = metrics.get("balance_status", "")

            if balance == "OFF BALANCE":
                return "The user is losing balance during the lunge — feet should be hip-width apart."

        return None

    def submit(self, event, exercise, metrics):
        """Queue a cue for this event. Returns immediately; collect the result with poll()."""
        issue = self._find_form_issue(exercise, metrics)
        now = time.time()
        is_major = event in MAJOR_EVENTS

        with self._lock:
            if not is_major:
                if not issue:
                    return False
                if self._pending:
                    return False
                if now - self.last_spoken_at < self.FORM_CUE_COOLDOWN:
                    return False
                if now - self._issue_spoken_at.get(issue, 0) < self.REPEAT_ISSUE_COOLDOWN:
                    return False

            self.last_spoken_at = now
            if issue:
                self._issue_spoken_at[issue] = now
            self._pending += 1

        self._executor.submit(self._generate, event, issue)
        return True

    def _generate(self, event, issue):
        try:
            text = self.llm.give_feedback(event, issue) if self.llm else None
            if not text:
                text = random.choice(FALLBACK_CUES.get(event, FALLBACK_CUES["ongoing_form_check"]))

            voice = self.tts.speak(text)

            with self._lock:
                self._cue_id += 1
                self._result = (voice, text, self._cue_id)
        except Exception as e:
            print(f"[VoicePipeline] Warning: cue generation failed: {e}")
        finally:
            with self._lock:
                self._pending -= 1

    def poll(self):
        """Return (audio_bytes, text, cue_id) for a newly finished cue, or None."""
        with self._lock:
            result, self._result = self._result, None
            return result


def autoplay_audio(audio_bytes):
    if not audio_bytes:
        return

    st.markdown("<style>[data-testid='stAudio'] {display: none;}</style>", unsafe_allow_html=True)

    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
