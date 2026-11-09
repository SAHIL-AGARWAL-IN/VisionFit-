import pytest

from conftest import expand, sequence_ids
from detectors import DETECTOR_CLASSES, create_detectors
from detectors.squat import SquatDetector


def run(sequence, default):
    detector = DETECTOR_CLASSES[sequence["exercise"]]()
    return [detector.process(expand(f, default)) for f in sequence["frames"]]


def by_name(pose_fixtures, name):
    return next(s for s in pose_fixtures["sequences"] if s["name"] == name)


@pytest.mark.parametrize("name", sequence_ids())
def test_rep_count_matches_construction(pose_fixtures, name):
    sequence = by_name(pose_fixtures, name)
    outputs = run(sequence, pose_fixtures["default_landmark"])
    assert outputs[-1]["reps"] == sequence["expected_reps"]


@pytest.mark.parametrize("name", sequence_ids())
def test_outputs_match_stored_fixture(pose_fixtures, name):
    """Guards against silent behaviour changes: regenerate the fixture if a change is intended."""
    sequence = by_name(pose_fixtures, name)
    assert run(sequence, pose_fixtures["default_landmark"]) == sequence["python_outputs"]


def test_rep_counter_never_decreases(pose_fixtures):
    for sequence in pose_fixtures["sequences"]:
        counts = [o["reps"] for o in run(sequence, pose_fixtures["default_landmark"])]
        assert counts == sorted(counts), sequence["name"]


def test_squat_good_rep_is_never_called_too_high_on_the_way_up(pose_fixtures):
    """Regression: the old detector said "TOO HIGH" while rising from a deep squat."""
    outputs = run(by_name(pose_fixtures, "squat_clean"), pose_fixtures["default_landmark"])
    assert "TOO HIGH" not in {o["depth_status"] for o in outputs}


def test_squat_shallow_rep_is_flagged_and_not_counted(pose_fixtures):
    outputs = run(by_name(pose_fixtures, "squat_shallow_rep_not_counted"), pose_fixtures["default_landmark"])
    statuses = [o["depth_status"] for o in outputs]
    first_too_high = statuses.index("TOO HIGH")
    assert outputs[first_too_high]["reps"] == 1
    assert outputs[first_too_high]["knee_angle"] >= SquatDetector.UP_THRESHOLD


@pytest.mark.parametrize("name,key,value", [
    ("pushup_hips_sag", "hip_status", "SAGGING"),
    ("curl_torso_swing", "swing_status", "SWINGING"),
    ("press_back_arch", "back_arch_status", "Excessive Arch"),
    ("lunge_off_balance", "balance_status", "OFF BALANCE"),
])
def test_form_faults_are_detected(pose_fixtures, name, key, value):
    outputs = run(by_name(pose_fixtures, name), pose_fixtures["default_landmark"])
    assert value in {o[key] for o in outputs}


@pytest.mark.parametrize("name,key,value", [
    ("pushup_clean", "hip_status", "SAGGING"),
    ("curl_clean", "swing_status", "SWINGING"),
    ("press_clean", "back_arch_status", "Excessive Arch"),
    ("lunge_clean", "balance_status", "OFF BALANCE"),
])
def test_clean_reps_raise_no_faults(pose_fixtures, name, key, value):
    outputs = run(by_name(pose_fixtures, name), pose_fixtures["default_landmark"])
    assert value not in {o[key] for o in outputs}


def test_reset_clears_progress(pose_fixtures):
    for name, detector in create_detectors().items():
        sequence = next(s for s in pose_fixtures["sequences"] if s["exercise"] == name)
        for frame in sequence["frames"]:
            detector.process(expand(frame, pose_fixtures["default_landmark"]))
        detector.reset()
        assert detector.reps == 0 and detector.stage is None, name
