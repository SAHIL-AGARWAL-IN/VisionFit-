"""End-to-end check of the video pipeline: decode → pose model → annotate → H.264 encode."""
import io

import numpy as np
import pytest

av = pytest.importorskip("av")
pytest.importorskip("mediapipe")

from services.analysis.video_analyzer import analyze_video  # noqa: E402


def make_clip(frames=45, width=1280, height=720, fps=30):
    buffer = io.BytesIO()
    container = av.open(buffer, "w", format="mp4")
    stream = container.add_stream("mpeg4", rate=fps)
    stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
    for i in range(frames):
        image = np.full((height, width, 3), 30 + i, np.uint8)
        for packet in stream.encode(av.VideoFrame.from_ndarray(image, format="bgr24")):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    buffer.seek(0)
    return buffer


def test_clip_without_a_person():
    progress = []
    result = analyze_video(make_clip(), "Squats", progress=progress.append)

    assert result.frame_count == 45
    assert result.report.rep_count == 0
    assert result.report.pose_coverage == 0
    assert len(result.inference_ms) == 45
    assert result.inference_p50 is not None
    assert progress[-1] == 1.0

    with av.open(io.BytesIO(result.video_bytes)) as out:
        stream = out.streams.video[0]
        assert stream.width == 720
        assert stream.height % 2 == 0
        assert sum(1 for _ in out.decode(stream)) == 45


def test_unknown_exercise_is_rejected():
    with pytest.raises(ValueError):
        analyze_video(make_clip(frames=2), "Deadlifts")
