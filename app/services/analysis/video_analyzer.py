"""Offline analysis of an uploaded workout clip.

Runs the same pose model and detectors as the live camera over every frame, draws the
skeleton and a rep badge onto the video, and builds a per-rep report.
"""
import io
import time
from dataclasses import dataclass, field
import av
import cv2
import mediapipe as mp
from detectors import DETECTOR_CLASSES
from services.analysis.rep_report import RepReport, summarize_reps, primary_angle_key
from services.config.workout_config import EXERCISE_DISPLAY
from services.vision.pose import create_pose_landmarker, draw_skeleton, draw_no_pose_warning, draw_rep_badge


MAX_SECONDS = 90
TARGET_WIDTH = 720
OUTPUT_CODECS = ("libx264", "h264", "mpeg4")


@dataclass
class VideoAnalysis:
    exercise: str
    fps: float
    duration: float
    frame_count: int
    timeline: list
    report: RepReport
    video_bytes: bytes
    video_codec: str
    inference_ms: list = field(default_factory=list)
    worst_frame_jpeg: bytes = None
    truncated: bool = False

    @property
    def inference_p50(self):
        return _percentile(self.inference_ms, 50)

    @property
    def inference_p95(self):
        return _percentile(self.inference_ms, 95)


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[index], 1)


def _even(value):
    return value - (value % 2)


def _resize(image):
    h, w = image.shape[:2]
    if w <= TARGET_WIDTH:
        new_w, new_h = _even(w), _even(h)
    else:
        new_w = TARGET_WIDTH
        new_h = _even(int(h * TARGET_WIDTH / w))

    if (new_w, new_h) == (w, h):
        return image

    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _open_output(width, height, fps):
    buffer = io.BytesIO()
    container = av.open(buffer, mode="w", format="mp4")

    for codec in OUTPUT_CODECS:
        try:
            stream = container.add_stream(codec, rate=max(1, round(fps)))
            break
        except Exception:
            continue
    else:
        raise RuntimeError("No usable video encoder found in PyAV.")

    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    if stream.codec_context.name in ("libx264", "h264"):
        stream.options = {"crf": "26", "preset": "veryfast", "movflags": "+faststart"}

    return buffer, container, stream


def analyze_video(source, exercise, progress=None):
    """Analyze a clip. `source` is a path or a binary file-like object.

    `progress(fraction)` is called as frames are processed, if given.
    """
    if exercise not in DETECTOR_CLASSES:
        raise ValueError(f"Unknown exercise: {exercise}")

    detector = DETECTOR_CLASSES[exercise]()
    landmarker = create_pose_landmarker()
    angle_key = primary_angle_key(exercise)
    angle_label = EXERCISE_DISPLAY[exercise]["angles"][0][1].upper()

    timeline = []
    inference_ms = []
    truncated = False

    with av.open(source) as container:
        in_stream = container.streams.video[0]
        in_stream.thread_type = "AUTO"
        fps = float(in_stream.average_rate or 30)
        expected = float(in_stream.duration * in_stream.time_base) if in_stream.duration else None
        total_seconds = min(expected, MAX_SECONDS) if expected else MAX_SECONDS

        out_buffer = out_container = out_stream = None
        last_ts_ms = -1
        frame_index = 0

        for frame in container.decode(in_stream):
            t = float(frame.time) if frame.time is not None else frame_index / fps

            if t > MAX_SECONDS:
                truncated = True
                break

            image = _resize(frame.to_ndarray(format="bgr24"))

            if out_container is None:
                out_buffer, out_container, out_stream = _open_output(image.shape[1], image.shape[0], fps)

            ts_ms = max(int(t * 1000), last_ts_ms + 1)
            last_ts_ms = ts_ms

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            started = time.perf_counter()
            result = landmarker.detect_for_video(mp_image, ts_ms)
            inference_ms.append((time.perf_counter() - started) * 1000)

            if result.pose_landmarks:
                landmarks = result.pose_landmarks[0]
                metrics = detector.process(landmarks)
                draw_skeleton(image, landmarks)
                draw_rep_badge(image, metrics.get("reps", 0), metrics.get(angle_key, 0), angle_label)
                timeline.append({"t": round(t, 3), "frame": frame_index, "pose_detected": True, **metrics})
            else:
                draw_no_pose_warning(image)
                timeline.append({"t": round(t, 3), "frame": frame_index, "pose_detected": False})

            out_frame = av.VideoFrame.from_ndarray(image, format="bgr24")
            for packet in out_stream.encode(out_frame):
                out_container.mux(packet)

            frame_index += 1
            if progress and frame_index % 5 == 0:
                progress(min(t / total_seconds, 1.0) if total_seconds else 0.0)

    landmarker.close()

    if out_container is None:
        raise ValueError("The file has no readable video frames.")

    for packet in out_stream.encode():
        out_container.mux(packet)
    codec = out_stream.codec_context.name
    out_container.close()
    video_bytes = out_buffer.getvalue()

    report = summarize_reps(timeline, exercise)
    duration = timeline[-1]["t"] if timeline else 0.0

    worst_frame = None
    worst = report.worst_rep
    if worst is not None:
        worst_frame = _grab_frame(video_bytes, worst.peak_t)

    if progress:
        progress(1.0)

    return VideoAnalysis(
        exercise=exercise,
        fps=fps,
        duration=duration,
        frame_count=frame_index,
        timeline=timeline,
        report=report,
        video_bytes=video_bytes,
        video_codec=codec,
        inference_ms=inference_ms,
        worst_frame_jpeg=worst_frame,
        truncated=truncated,
    )


def _grab_frame(video_bytes, at_seconds):
    """JPEG of the annotated frame closest to `at_seconds`."""
    best = None
    best_gap = None

    with av.open(io.BytesIO(video_bytes)) as container:
        for frame in container.decode(video=0):
            gap = abs((frame.time or 0) - at_seconds)
            if best_gap is None or gap < best_gap:
                best, best_gap = frame.to_ndarray(format="bgr24"), gap
            elif gap > best_gap:
                break

    if best is None:
        return None

    ok, encoded = cv2.imencode(".jpg", best, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return encoded.tobytes() if ok else None
