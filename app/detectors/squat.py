import math
from core.base_exercise import BaseExercise


class SquatDetector(BaseExercise):
    DOWN_THRESHOLD = 100   # knee angle that counts as "deep enough"
    UP_THRESHOLD = 160     # knee angle that counts as "standing"
    REP_START_THRESHOLD = 145  # below this the user has started a rep
    MIN_VISIBILITY = 0.7

    LEFT_HIP = 23
    LEFT_KNEE = 25
    LEFT_ANKLE = 27
    RIGHT_HIP = 24
    RIGHT_KNEE = 26
    RIGHT_ANKLE = 28
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

    def __init__(self):
        super().__init__()
        self._min_knee_angle = None
        self._last_rep_status = "N/A"

    def reset(self):
        self.reps = 0
        self.stage = None
        self._min_knee_angle = None
        self._last_rep_status = "N/A"

    def process(self, landmarks):
        left_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_HIP),
            self.get_point(landmarks, self.LEFT_KNEE),
            self.get_point(landmarks, self.LEFT_ANKLE)
        )

        right_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.RIGHT_HIP),
            self.get_point(landmarks, self.RIGHT_KNEE),
            self.get_point(landmarks, self.RIGHT_ANKLE)
        )

        left_vis = landmarks[self.LEFT_KNEE].visibility
        right_vis = landmarks[self.RIGHT_KNEE].visibility

        if left_vis >= right_vis:
            knee_angle = left_knee_angle
            hip_idx, knee_idx, ankle_idx, shoulder_idx = self.LEFT_HIP, self.LEFT_KNEE, self.LEFT_ANKLE, self.LEFT_SHOULDER
        else:
            knee_angle = right_knee_angle
            hip_idx, knee_idx, ankle_idx, shoulder_idx = self.RIGHT_HIP, self.RIGHT_KNEE, self.RIGHT_ANKLE, self.RIGHT_SHOULDER

        back_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx),
            self.get_point(landmarks, hip_idx),
            self.get_point(landmarks, knee_idx)
        )

        # Torso lean measured from vertical (0° = upright). The hip angle above naturally gets
        # small at the bottom of every deep squat, so it can't be used to judge forward lean.
        dx = landmarks[shoulder_idx].x - landmarks[hip_idx].x
        dy = landmarks[shoulder_idx].y - landmarks[hip_idx].y
        torso_lean = math.degrees(math.atan2(abs(dx), abs(dy))) if (dx or dy) else 0.0

        key_landmark_visible = landmarks[hip_idx].visibility >= self.MIN_VISIBILITY and landmarks[knee_idx].visibility >= self.MIN_VISIBILITY and landmarks[ankle_idx].visibility >= self.MIN_VISIBILITY

        if key_landmark_visible:
            # Track the deepest point of each rep, then judge the rep once the user stands back up.
            if knee_angle < self.REP_START_THRESHOLD:
                self.stage = "down"
                if self._min_knee_angle is None or knee_angle < self._min_knee_angle:
                    self._min_knee_angle = knee_angle

            if knee_angle >= self.UP_THRESHOLD and self.stage == "down":
                self.stage = "up"

                if self._min_knee_angle is not None and self._min_knee_angle <= self.DOWN_THRESHOLD:
                    self.reps += 1
                    self._last_rep_status = "GOOD DEPTH"
                else:
                    self._last_rep_status = "TOO HIGH"

                self._min_knee_angle = None

        if self.stage == "down":
            reached_depth = self._min_knee_angle is not None and self._min_knee_angle <= self.DOWN_THRESHOLD
            depth_status = "GOOD DEPTH" if reached_depth else "GO LOWER"
        elif self.stage == "up":
            depth_status = self._last_rep_status
        else:
            depth_status = "N/A"

        return {
            "reps": self.reps,
            "knee_angle": int(knee_angle),
            "back_angle": int(back_angle),
            "torso_lean": int(torso_lean),
            "depth_status": depth_status
        }
