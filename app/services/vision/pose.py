"""Pose model setup and frame drawing shared by the live camera and the video analyzer."""
import os
import cv2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from services.config.workout_config import POSE_CONNECTIONS


# Overlay colours (BGR) matching the app's palette.
BONE_COLOR = (255, 255, 255)
JOINT_COLOR = (18, 79, 255)      # signal orange #FF4F12
JOINT_RING_COLOR = (255, 255, 255)
BANNER_COLOR = (18, 16, 15)      # ink #0F1012
VISIBILITY_THRESHOLD = 0.7

_APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(_APP_DIR, "ml_models", "pose_landmarker_full.task")


def create_pose_landmarker():
    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=vision.RunningMode.VIDEO,
        min_pose_detection_confidence=0.7,
        min_pose_presence_confidence=0.7,
        min_tracking_confidence=0.7,
        output_segmentation_masks=False
    )

    return vision.PoseLandmarker.create_from_options(options)


def draw_skeleton(img, landmarks):
    h, w = img.shape[:2]
    thickness = max(2, w // 320)
    radius = max(4, w // 160)

    for start_idx, end_idx in POSE_CONNECTIONS:
        p1 = landmarks[start_idx]
        p2 = landmarks[end_idx]

        if p1.visibility > VISIBILITY_THRESHOLD and p2.visibility > VISIBILITY_THRESHOLD:
            cv2.line(
                img,
                (int(p1.x * w), int(p1.y * h)),
                (int(p2.x * w), int(p2.y * h)),
                BONE_COLOR,
                thickness,
                cv2.LINE_AA,
            )

    # Only draw joints that are part of the skeleton (skip face landmarks).
    joint_ids = {idx for pair in POSE_CONNECTIONS for idx in pair}

    for idx in joint_ids:
        lm = landmarks[idx]
        if lm.visibility > VISIBILITY_THRESHOLD:
            center = (int(lm.x * w), int(lm.y * h))
            cv2.circle(img, center, radius + 2, JOINT_RING_COLOR, -1, cv2.LINE_AA)
            cv2.circle(img, center, radius, JOINT_COLOR, -1, cv2.LINE_AA)


def draw_banner(img, text):
    """Semi-transparent ink bar across the bottom of the frame with centred white text."""
    h, w = img.shape[:2]
    bar_h = max(48, h // 9)

    overlay = img.copy()
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), BANNER_COLOR, -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    scale = max(0.5, w / 1100)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, 1)
    cv2.putText(
        img,
        text,
        ((w - tw) // 2, h - (bar_h - th) // 2),
        cv2.FONT_HERSHEY_DUPLEX,
        scale,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def draw_no_pose_warning(img):
    draw_banner(img, "STEP INTO FRAME - FULL BODY VISIBLE")


def draw_rep_badge(img, reps, angle, angle_label):
    """Top-left badge used on analysed videos: rep count and the primary joint angle."""
    h, w = img.shape[:2]
    scale = max(0.6, w / 900)
    pad = int(14 * scale)
    box_w = int(210 * scale)
    box_h = int(78 * scale)

    overlay = img.copy()
    cv2.rectangle(overlay, (pad, pad), (pad + box_w, pad + box_h), BANNER_COLOR, -1)
    cv2.addWeighted(overlay, 0.8, img, 0.2, 0, img)
    cv2.rectangle(img, (pad, pad), (pad + int(5 * scale), pad + box_h), JOINT_COLOR, -1)

    cv2.putText(img, f"REP {reps}", (pad + int(18 * scale), pad + int(34 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.95 * scale, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, f"{angle_label} {angle} deg", (pad + int(18 * scale), pad + int(64 * scale)),
                cv2.FONT_HERSHEY_DUPLEX, 0.55 * scale, (200, 200, 200), 1, cv2.LINE_AA)
