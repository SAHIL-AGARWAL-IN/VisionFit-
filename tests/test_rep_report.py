import pytest

from conftest import expand
from detectors import DETECTOR_CLASSES
from services.analysis.rep_report import RUSHED_SECONDS, summarize_reps


def timeline_for(sequence, default, fps=None, pose_gaps=()):
    fps = fps or sequence["fps"]
    detector = DETECTOR_CLASSES[sequence["exercise"]]()
    timeline = []
    for i, frame in enumerate(sequence["frames"]):
        t = i / fps
        if i in pose_gaps:
            timeline.append({"t": t, "pose_detected": False})
            continue
        timeline.append({"t": t, "pose_detected": True, **detector.process(expand(frame, default))})
    return timeline


def by_name(pose_fixtures, name):
    return next(s for s in pose_fixtures["sequences"] if s["name"] == name)


def test_report_counts_match_detector(pose_fixtures):
    for sequence in pose_fixtures["sequences"]:
        report = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"]), sequence["exercise"])
        assert report.rep_count == sequence["expected_reps"], sequence["name"]


def test_clean_squats_score_well_and_have_sane_timing(pose_fixtures):
    sequence = by_name(pose_fixtures, "squat_clean")
    report = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"], fps=15), "Squats")

    assert [r.number for r in report.reps] == [1, 2, 3]
    for rep in report.reps:
        assert rep.peak_angle <= 90
        assert rep.duration > RUSHED_SECONDS
        assert rep.start_t < rep.peak_t < rep.end_t
        assert rep.score == 100
    assert report.average_score == 100


def test_shallow_squat_attempt_is_reported(pose_fixtures):
    sequence = by_name(pose_fixtures, "squat_shallow_rep_not_counted")
    report = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"]), "Squats")
    assert report.rep_count == 2
    assert report.shallow_attempts == 1


@pytest.mark.parametrize("name,faulty_rep", [
    ("pushup_hips_sag", 2),
    ("curl_torso_swing", 2),
    ("press_back_arch", 1),
    ("lunge_off_balance", 2),
])
def test_faulty_rep_is_the_worst_rep(pose_fixtures, name, faulty_rep):
    sequence = by_name(pose_fixtures, name)
    report = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"], fps=15), sequence["exercise"])

    worst = report.worst_rep
    assert worst.number == faulty_rep
    assert worst.faults
    assert worst.score < max(r.score for r in report.reps)


def test_rushed_reps_lose_points(pose_fixtures):
    sequence = by_name(pose_fixtures, "squat_clean")
    slow = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"], fps=15), "Squats")
    fast = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"], fps=120), "Squats")
    assert all(r.duration < RUSHED_SECONDS for r in fast.reps)
    assert fast.average_score < slow.average_score


def test_pose_coverage_and_empty_timeline(pose_fixtures):
    sequence = by_name(pose_fixtures, "squat_clean")
    gaps = set(range(0, len(sequence["frames"]), 4))
    report = summarize_reps(timeline_for(sequence, pose_fixtures["default_landmark"], pose_gaps=gaps), "Squats")
    assert report.pose_coverage == pytest.approx(1 - len(gaps) / len(sequence["frames"]))

    empty = summarize_reps([], "Squats")
    assert empty.rep_count == 0 and empty.worst_rep is None and empty.average_score is None
