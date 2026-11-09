"""Generates tests/fixtures/pose_sequences.json.

Each sequence is a list of synthetic pose frames (normalised x, y, visibility per landmark)
built from known joint angles, plus the rep count it should produce by construction.
The Python detectors' per-frame outputs are stored too, so the JavaScript port in
LandingPage/detectors.js can be checked against them frame by frame.

Run from the repo root:  python tests/fixtures/generate_pose_fixtures.py
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from detectors import DETECTOR_CLASSES  # noqa: E402

OUT = Path(__file__).with_name("pose_sequences.json")
FPS = 30
STEP = 5
USED = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
DEFAULT = (0.5, 0.5, 0.99)


class Landmark:
    def __init__(self, x, y, visibility):
        self.x, self.y, self.visibility = x, y, visibility


def blank():
    return {i: list(DEFAULT) for i in range(33)}


def bend(origin, length, degrees):
    """Point `length` from `origin` so the angle at `origin` between straight up and it is `degrees`."""
    a = math.radians(degrees)
    return [origin[0] + length * math.sin(a), origin[1] - length * math.cos(a)]


def squat(knee_deg, lean=0.0):
    p = blank()
    for hip, knee, ankle, shoulder in ((23, 25, 27, 11), (24, 26, 28, 12)):
        p[ankle][:2] = [0.5, 0.9]
        p[knee][:2] = [0.5, 0.7]
        a = math.radians(knee_deg)
        p[hip][:2] = [0.5 + 0.2 * math.sin(a), 0.7 + 0.2 * math.cos(a)]
        p[shoulder][:2] = [p[hip][0] + 0.25 * math.sin(math.radians(lean)), p[hip][1] - 0.25 * math.cos(math.radians(lean))]
    return p


def arm(p, elbow_deg, shoulder_xy):
    for shoulder, elbow, wrist in ((11, 13, 15), (12, 14, 16)):
        p[shoulder][:2] = list(shoulder_xy)
        p[elbow][:2] = [shoulder_xy[0], shoulder_xy[1] + 0.12]
        p[wrist][:2] = bend(p[elbow], 0.12, elbow_deg)


def pushup(elbow_deg, sag=0.0):
    p = blank()
    arm(p, elbow_deg, (0.3, 0.5))
    for hip, knee, ankle in ((23, 25, 27), (24, 26, 28)):
        p[ankle][:2] = [0.9, 0.5]
        p[hip][:2] = [0.6, 0.5 + sag]
        p[knee][:2] = [0.75, 0.5 + sag / 2]
    return p


def curl(elbow_deg, swing=0.0):
    p = blank()
    arm(p, elbow_deg, (0.5 + swing, 0.3))
    for hip, knee, ankle in ((23, 25, 27), (24, 26, 28)):
        p[hip][:2] = [0.5, 0.6]
        p[knee][:2] = [0.5, 0.75]
        p[ankle][:2] = [0.5, 0.9]
    return p


def press(elbow_deg, arch=0.0):
    p = blank()
    arm(p, elbow_deg, (0.5, 0.3))
    for hip, knee, ankle in ((23, 25, 27), (24, 26, 28)):
        p[hip][:2] = [0.5, 0.6]
        p[knee][:2] = [0.5 + arch, 0.8]
        p[ankle][:2] = [0.5 + arch, 0.95]
    return p


def lunge(front_knee_deg, drift=0.0):
    p = blank()
    p[23][:2], p[25][:2] = [0.5, 0.5], [0.5, 0.7]
    p[27][:2] = bend(p[25], 0.2, front_knee_deg)
    p[24][:2], p[26][:2], p[28][:2] = [0.5, 0.5], [0.45, 0.7], [0.4, 0.9]
    p[11][:2] = [0.5 + drift, 0.25]
    p[12][:2] = [0.5 + drift, 0.25]
    return p


def sweep(start, end):
    step = STEP if end > start else -STEP
    return list(range(start, end, step)) + [end]


def reps(pose_fn, rest, peak, count, fault_reps=(), fault_kwargs=None, visibility=None):
    frames = []
    for rep in range(count):
        kwargs = fault_kwargs if rep in fault_reps else {}
        for angle in sweep(rest, peak) + sweep(peak, rest)[1:]:
            frame = pose_fn(angle, **kwargs)
            if visibility is not None:
                for lm in frame.values():
                    lm[2] = visibility
            frames.append(frame)
    return frames


def shallow_then(pose_fn, rest, peak, shallow_peak, pattern):
    frames = []
    for kind in pattern:
        target = peak if kind == "full" else shallow_peak
        frames += [pose_fn(a) for a in sweep(rest, target) + sweep(target, rest)[1:]]
    return frames


SEQUENCES = [
    ("squat_clean", "Squats", reps(squat, 175, 85, 3), 3),
    ("squat_shallow_rep_not_counted", "Squats", shallow_then(squat, 175, 85, 120, ["full", "shallow", "full"]), 2),
    ("squat_low_visibility", "Squats", reps(squat, 175, 85, 2, visibility=0.3), 0),
    ("pushup_clean", "Push-ups", reps(pushup, 170, 80, 3), 3),
    ("pushup_hips_sag", "Push-ups", reps(pushup, 170, 80, 3, fault_reps=(1,), fault_kwargs={"sag": 0.12}), 3),
    ("curl_clean", "Biceps Curls (Dumbbell)", reps(curl, 170, 40, 3), 3),
    ("curl_torso_swing", "Biceps Curls (Dumbbell)", reps(curl, 170, 40, 2, fault_reps=(1,), fault_kwargs={"swing": 0.12}), 2),
    ("press_clean", "Shoulder Press", reps(press, 80, 170, 3), 3),
    ("press_back_arch", "Shoulder Press", reps(press, 80, 170, 2, fault_reps=(0,), fault_kwargs={"arch": 0.2}), 2),
    ("lunge_clean", "Lunges", reps(lunge, 175, 85, 3), 3),
    ("lunge_off_balance", "Lunges", reps(lunge, 175, 85, 2, fault_reps=(1,), fault_kwargs={"drift": 0.15}), 2),
]


def rounded(frame):
    # Round before running the detectors so Python and JS see exactly the same numbers.
    return {i: [round(v, 5) for v in frame[i]] for i in range(33)}


def to_landmarks(frame):
    return [Landmark(*frame[i]) for i in range(33)]


def build():
    sequences = []

    for name, exercise, frames, expected in SEQUENCES:
        detector = DETECTOR_CLASSES[exercise]()
        frames = [rounded(f) for f in frames]
        outputs = [detector.process(to_landmarks(f)) for f in frames]
        sequences.append({
            "name": name,
            "exercise": exercise,
            "fps": FPS,
            "expected_reps": expected,
            "frames": [[[i, *f[i]] for i in USED] for f in frames],
            "python_outputs": outputs,
        })

    return {"default_landmark": list(DEFAULT), "sequences": sequences}


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(data['sequences'])} sequences)")
