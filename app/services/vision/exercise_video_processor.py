import time
import uuid
import cv2
import av
import numpy as np
import mediapipe as mp
import threading
from streamlit_webrtc import VideoProcessorBase
from detectors import create_detectors
from services.vision.pose import create_pose_landmarker, draw_skeleton, draw_no_pose_warning


class VideoProcessorClass(VideoProcessorBase):
    def __init__(self):
        self.instance_id = uuid.uuid4().hex
        self._lock = threading.Lock()
        self._latest_metrics = None
        self._exercise_type = "Squats"
        self._landmarker = create_pose_landmarker()
        self._detectors = create_detectors()
        self._last_timestamp_ms = 0

    def set_latest_metrics(self, metrics):
        with self._lock:
            self._latest_metrics = metrics.copy()

    def get_latest_metrics(self):
        with self._lock:
            return None if self._latest_metrics is None else self._latest_metrics.copy()

    def set_exercise(self, exercise_type):
        with self._lock:
            self._exercise_type = exercise_type

    def get_exercise(self):
        with self._lock:
            return self._exercise_type

    def _next_timestamp_ms(self):
        # MediaPipe VIDEO mode needs strictly increasing timestamps.
        now_ms = int(time.monotonic() * 1000)
        self._last_timestamp_ms = max(now_ms, self._last_timestamp_ms + 1)
        return self._last_timestamp_ms

    def recv(self, frame):
        image = np.asarray(
            cv2.flip(frame.to_ndarray(format="bgr24"), 1),
            dtype=np.uint8
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        )

        result = self._landmarker.detect_for_video(mp_image, self._next_timestamp_ms())

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]

            draw_skeleton(image, landmarks)

            detector = self._detectors.get(self.get_exercise())

            if detector:
                metrics = detector.process(landmarks)

                metrics["pose_detected"] = True

                self.set_latest_metrics(metrics)
        else:
            draw_no_pose_warning(image)

            with self._lock:
                if self._latest_metrics is not None:
                    self._latest_metrics["pose_detected"] = False
                else:
                    self._latest_metrics = {"pose_detected": False}

        return av.VideoFrame.from_ndarray(image, format="bgr24")
