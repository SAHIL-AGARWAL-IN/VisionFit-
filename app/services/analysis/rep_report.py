"""Turns a per-frame metrics timeline into a per-rep report.

A timeline is a list of frames: {"t": seconds, "pose_detected": bool, **detector_metrics}.
Reps are split where the detector's rep counter goes up, so the report always agrees
with what the live coach would have counted.
"""
from dataclasses import dataclass, field
from statistics import mean
from detectors import DETECTOR_CLASSES
from services.config.workout_config import EXERCISE_DISPLAY, STATUS_TONES


# How each exercise's primary angle behaves during a rep.
#   rest:      "high" if the rep starts near a large angle (e.g. standing), "low" otherwise
#   threshold: the angle the detector requires before it will count the rep
PRIMARY_MOTION = {
    "Squats": {"rest": "high", "threshold": DETECTOR_CLASSES["Squats"].DOWN_THRESHOLD},
    "Push-ups": {"rest": "high", "threshold": DETECTOR_CLASSES["Push-ups"].DOWN_THRESHOLD},
    "Biceps Curls (Dumbbell)": {"rest": "high", "threshold": DETECTOR_CLASSES["Biceps Curls (Dumbbell)"].UP_THRESHOLD},
    "Shoulder Press": {"rest": "low", "threshold": DETECTOR_CLASSES["Shoulder Press"].UP_THRESHOLD},
    "Lunges": {"rest": "high", "threshold": DETECTOR_CLASSES["Lunges"].DOWN_THRESHOLD},
}

REST_TOLERANCE = 12        # degrees from the rest angle that still counts as "not moving yet"
FAULT_PENALTY = 50         # points lost if every frame of the rep had a form flag
SHALLOW_MARGIN = 5         # degrees past the threshold that count as "barely made it"
SHALLOW_PENALTY = 10
RUSHED_SECONDS = 1.0
RUSHED_PENALTY = 10


@dataclass
class RepSummary:
    number: int
    start_t: float
    end_t: float
    peak_t: float
    peak_angle: int
    duration: float
    fault_share: float
    faults: list = field(default_factory=list)
    score: int = 100
    notes: list = field(default_factory=list)


@dataclass
class RepReport:
    exercise: str
    reps: list
    shallow_attempts: int
    pose_coverage: float

    @property
    def rep_count(self):
        return len(self.reps)

    @property
    def average_score(self):
        return round(mean(r.score for r in self.reps)) if self.reps else None

    @property
    def average_tempo(self):
        return round(mean(r.duration for r in self.reps), 2) if self.reps else None

    @property
    def worst_rep(self):
        if not self.reps:
            return None
        return min(self.reps, key=lambda r: (r.score, -r.fault_share))


def primary_angle_key(exercise):
    return EXERCISE_DISPLAY[exercise]["angles"][0][0]


def frame_faults(exercise, frame):
    """Status values in this frame that the UI would show as a warning or a problem."""
    faults = []

    for key, label in EXERCISE_DISPLAY[exercise]["statuses"]:
        value = frame.get(key)
        if STATUS_TONES.get(value) in ("warn", "bad"):
            faults.append(f"{label}: {str(value).capitalize()}")

    return faults


def _score_rep(duration, fault_share, peak_angle, motion):
    score = 100 - FAULT_PENALTY * fault_share
    notes = []

    if fault_share > 0:
        notes.append(f"form flagged on {round(fault_share * 100)}% of the rep")

    if motion["rest"] == "high":
        margin = motion["threshold"] - peak_angle
    else:
        margin = peak_angle - motion["threshold"]

    if margin < SHALLOW_MARGIN:
        score -= SHALLOW_PENALTY
        notes.append("only just reached the counting angle")

    if duration < RUSHED_SECONDS:
        score -= RUSHED_PENALTY
        notes.append("rushed (under 1 s)")

    return int(max(0, min(100, round(score)))), notes


def summarize_reps(timeline, exercise):
    motion = PRIMARY_MOTION[exercise]
    angle_key = primary_angle_key(exercise)
    rest_is_high = motion["rest"] == "high"

    tracked = [f for f in timeline if f.get("pose_detected")]
    pose_coverage = len(tracked) / len(timeline) if timeline else 0.0

    reps = []
    segment = []
    last_count = 0
    shallow_attempts = 0
    previous_depth_status = None

    for frame in tracked:
        segment.append(frame)

        depth_status = frame.get("depth_status")
        if depth_status == "TOO HIGH" and previous_depth_status != "TOO HIGH":
            shallow_attempts += 1
        previous_depth_status = depth_status

        count = frame.get("reps", 0) or 0
        if count <= last_count:
            continue

        last_count = count
        reps.append(_summarize_segment(segment, len(reps) + 1, exercise, angle_key, rest_is_high, motion))
        segment = []

    return RepReport(exercise=exercise, reps=reps, shallow_attempts=shallow_attempts, pose_coverage=pose_coverage)


def _summarize_segment(segment, number, exercise, angle_key, rest_is_high, motion):
    angles = [f.get(angle_key, 0) for f in segment]
    pick_peak = min if rest_is_high else max
    pick_rest = max if rest_is_high else min

    peak_index = angles.index(pick_peak(angles))
    rest_angle = pick_rest(angles[: peak_index + 1])

    # The rep starts at the last frame before the peak where the joint was still at rest.
    start_index = 0
    for i in range(peak_index, -1, -1):
        if abs(angles[i] - rest_angle) <= REST_TOLERANCE:
            start_index = i
            break

    active = segment[start_index:]
    faulty_frames = [frame_faults(exercise, f) for f in active]
    fault_share = sum(1 for f in faulty_frames if f) / len(active)
    faults = sorted({label for frame in faulty_frames for label in frame})

    start_t = segment[start_index]["t"]
    end_t = segment[-1]["t"]
    duration = round(end_t - start_t, 2)
    peak_angle = int(angles[peak_index])

    score, notes = _score_rep(duration, fault_share, peak_angle, motion)

    return RepSummary(
        number=number,
        start_t=round(start_t, 2),
        end_t=round(end_t, 2),
        peak_t=round(segment[peak_index]["t"], 2),
        peak_angle=peak_angle,
        duration=duration,
        fault_share=round(fault_share, 3),
        faults=faults,
        score=score,
        notes=notes,
    )
