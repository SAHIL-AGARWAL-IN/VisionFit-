import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

FIXTURES = Path(__file__).parent / "fixtures" / "pose_sequences.json"


class Landmark:
    def __init__(self, x, y, visibility):
        self.x, self.y, self.visibility = x, y, visibility


def expand(frame, default):
    """Turn a sparse fixture frame ([index, x, y, visibility] entries) into 33 landmarks."""
    points = [Landmark(*default) for _ in range(33)]
    for index, x, y, visibility in frame:
        points[index] = Landmark(x, y, visibility)
    return points


@pytest.fixture(scope="session")
def pose_fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def sequence_ids():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return [s["name"] for s in data["sequences"]]
