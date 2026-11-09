/**
 * VisionFit rep detectors — a line-for-line port of app/detectors/*.py so the in-browser
 * demo counts reps exactly like the real app. tests/js/detectors.test.mjs checks both
 * implementations against the same fixtures (tests/fixtures/pose_sequences.json).
 *
 * Landmarks are MediaPipe pose landmarks: [{x, y, visibility}, ...] (33 points, normalised).
 */
(function (root) {
  "use strict";

  const L = {
    LEFT_SHOULDER: 11, RIGHT_SHOULDER: 12,
    LEFT_ELBOW: 13, RIGHT_ELBOW: 14,
    LEFT_WRIST: 15, RIGHT_WRIST: 16,
    LEFT_HIP: 23, RIGHT_HIP: 24,
    LEFT_KNEE: 25, RIGHT_KNEE: 26,
    LEFT_ANKLE: 27, RIGHT_ANKLE: 28,
  };

  const degrees = (r) => (r * 180) / Math.PI;
  const point = (lm, i) => [lm[i].x, lm[i].y];
  const vis = (lm, i) => (lm[i].visibility === undefined ? 1 : lm[i].visibility);

  function calculateAngle(a, b, c) {
    const ax = a[0] - b[0], ay = a[1] - b[1];
    const cx = c[0] - b[0], cy = c[1] - b[1];
    const dot = ax * cx + ay * cy;
    const magA = Math.sqrt(ax * ax + ay * ay);
    const magC = Math.sqrt(cx * cx + cy * cy);
    if (magA * magC === 0) return 0;
    const cos = Math.max(-1, Math.min(1, dot / (magA * magC)));
    return degrees(Math.acos(cos));
  }

  const angleAt = (lm, a, b, c) => calculateAngle(point(lm, a), point(lm, b), point(lm, c));
  const fromVertical = (dx, dy) => degrees(Math.atan2(Math.abs(dx), Math.abs(dy)));

  class Detector {
    constructor() { this.reset(); }
    reset() { this.reps = 0; this.stage = null; }
  }

  class SquatDetector extends Detector {
    static DOWN_THRESHOLD = 100;
    static UP_THRESHOLD = 160;
    static REP_START_THRESHOLD = 145;
    static MIN_VISIBILITY = 0.7;

    reset() {
      super.reset();
      this.minKneeAngle = null;
      this.lastRepStatus = "N/A";
    }

    process(lm) {
      const S = SquatDetector;
      const leftKnee = angleAt(lm, L.LEFT_HIP, L.LEFT_KNEE, L.LEFT_ANKLE);
      const rightKnee = angleAt(lm, L.RIGHT_HIP, L.RIGHT_KNEE, L.RIGHT_ANKLE);
      const left = vis(lm, L.LEFT_KNEE) >= vis(lm, L.RIGHT_KNEE);

      const kneeAngle = left ? leftKnee : rightKnee;
      const [hip, knee, ankle, shoulder] = left
        ? [L.LEFT_HIP, L.LEFT_KNEE, L.LEFT_ANKLE, L.LEFT_SHOULDER]
        : [L.RIGHT_HIP, L.RIGHT_KNEE, L.RIGHT_ANKLE, L.RIGHT_SHOULDER];

      const backAngle = angleAt(lm, shoulder, hip, knee);
      const dx = lm[shoulder].x - lm[hip].x;
      const dy = lm[shoulder].y - lm[hip].y;
      const torsoLean = dx || dy ? fromVertical(dx, dy) : 0;

      const visible = [hip, knee, ankle].every((i) => vis(lm, i) >= S.MIN_VISIBILITY);

      if (visible) {
        if (kneeAngle < S.REP_START_THRESHOLD) {
          this.stage = "down";
          if (this.minKneeAngle === null || kneeAngle < this.minKneeAngle) this.minKneeAngle = kneeAngle;
        }

        if (kneeAngle >= S.UP_THRESHOLD && this.stage === "down") {
          this.stage = "up";
          if (this.minKneeAngle !== null && this.minKneeAngle <= S.DOWN_THRESHOLD) {
            this.reps += 1;
            this.lastRepStatus = "GOOD DEPTH";
          } else {
            this.lastRepStatus = "TOO HIGH";
          }
          this.minKneeAngle = null;
        }
      }

      let depthStatus = "N/A";
      if (this.stage === "down") {
        const reached = this.minKneeAngle !== null && this.minKneeAngle <= S.DOWN_THRESHOLD;
        depthStatus = reached ? "GOOD DEPTH" : "GO LOWER";
      } else if (this.stage === "up") {
        depthStatus = this.lastRepStatus;
      }

      return {
        reps: this.reps,
        knee_angle: Math.trunc(kneeAngle),
        back_angle: Math.trunc(backAngle),
        torso_lean: Math.trunc(torsoLean),
        depth_status: depthStatus,
      };
    }
  }

  class PushUpDetector extends Detector {
    static DOWN_THRESHOLD = 90;
    static UP_THRESHOLD = 160;
    static MIN_VISIBILITY = 0.7;
    static HIP_SAG_TOLERANCE = 0.08;

    process(lm) {
      const S = PushUpDetector;
      const left = vis(lm, L.LEFT_ELBOW) >= vis(lm, L.RIGHT_ELBOW);
      const [shoulder, elbow, wrist, hip, ankle] = left
        ? [L.LEFT_SHOULDER, L.LEFT_ELBOW, L.LEFT_WRIST, L.LEFT_HIP, L.LEFT_ANKLE]
        : [L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST, L.RIGHT_HIP, L.RIGHT_ANKLE];

      const elbowAngle = angleAt(lm, shoulder, elbow, wrist);
      const bodyAngle = angleAt(lm, shoulder, hip, ankle);
      const hipDeviation = lm[hip].y - (lm[shoulder].y + lm[ankle].y) / 2;

      const visible = [shoulder, elbow, wrist, hip].every((i) => vis(lm, i) > S.MIN_VISIBILITY);

      if (visible) {
        if (elbowAngle < S.DOWN_THRESHOLD) this.stage = "down";
        if (elbowAngle > S.UP_THRESHOLD && this.stage === "down") {
          this.stage = "up";
          this.reps += 1;
        }
      }

      let bodyAlignment = "Poor Form";
      if (bodyAngle > 160) bodyAlignment = "Straight";
      else if (bodyAngle > 140) bodyAlignment = "Slight Bend";

      let hipStatus = "PIKED UP";
      if (Math.abs(hipDeviation) <= S.HIP_SAG_TOLERANCE) hipStatus = "LEVEL";
      else if (hipDeviation > S.HIP_SAG_TOLERANCE) hipStatus = "SAGGING";

      return {
        reps: this.reps,
        elbow_angle: Math.trunc(elbowAngle),
        body_alignment: bodyAlignment,
        hip_status: hipStatus,
      };
    }
  }

  class BicepsCurlDetector extends Detector {
    static UP_THRESHOLD = 50;
    static DOWN_THRESHOLD = 160;
    static MIN_VISIBILITY = 0.7;
    static ELBOW_DRIFT_TOLERANCE = 0.06;
    static SWING_THRESHOLD = 15;

    process(lm) {
      const S = BicepsCurlDetector;
      const left = vis(lm, L.LEFT_ELBOW) >= vis(lm, L.RIGHT_ELBOW);
      const [shoulder, elbow, wrist] = left
        ? [L.LEFT_SHOULDER, L.LEFT_ELBOW, L.LEFT_WRIST]
        : [L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST];

      const elbowAngle = angleAt(lm, shoulder, elbow, wrist);
      const visible = [shoulder, elbow, wrist].every((i) => vis(lm, i) > S.MIN_VISIBILITY);

      if (visible) {
        if (elbowAngle < S.UP_THRESHOLD) this.stage = "up";
        if (elbowAngle > S.DOWN_THRESHOLD && this.stage === "up") {
          this.stage = "down";
          this.reps += 1;
        }
      }

      const drift = Math.abs(lm[elbow].x - lm[shoulder].x);
      const shoulderStatus = drift <= S.ELBOW_DRIFT_TOLERANCE ? "STABLE" : "ELBOW DRIFTING";

      const dx = (lm[L.LEFT_SHOULDER].x + lm[L.RIGHT_SHOULDER].x) / 2 - (lm[L.LEFT_HIP].x + lm[L.RIGHT_HIP].x) / 2;
      const dy = (lm[L.LEFT_SHOULDER].y + lm[L.RIGHT_SHOULDER].y) / 2 - (lm[L.LEFT_HIP].y + lm[L.RIGHT_HIP].y) / 2;
      const torso = dy !== 0 ? fromVertical(dx, dy) : 0;

      return {
        reps: this.reps,
        elbow_angle: Math.trunc(elbowAngle),
        shoulder_status: shoulderStatus,
        swing_status: torso <= S.SWING_THRESHOLD ? "NO SWING" : "SWINGING",
      };
    }
  }

  class ShoulderPressDetector extends Detector {
    static UP_THRESHOLD = 160;
    static DOWN_THRESHOLD = 90;
    static MIN_VISIBILITY = 0.7;

    process(lm) {
      const S = ShoulderPressDetector;
      const left = vis(lm, L.LEFT_ELBOW) >= vis(lm, L.RIGHT_ELBOW);
      const [shoulder, elbow, wrist, hip, knee] = left
        ? [L.LEFT_SHOULDER, L.LEFT_ELBOW, L.LEFT_WRIST, L.LEFT_HIP, L.LEFT_KNEE]
        : [L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST, L.RIGHT_HIP, L.RIGHT_KNEE];

      const elbowAngle = angleAt(lm, shoulder, elbow, wrist);
      const visible = [shoulder, elbow, wrist].every((i) => vis(lm, i) > S.MIN_VISIBILITY);

      if (visible) {
        if (elbowAngle > S.UP_THRESHOLD) this.stage = "up";
        if (elbowAngle < S.DOWN_THRESHOLD && this.stage === "up") {
          this.stage = "down";
          this.reps += 1;
        }
      }

      let extension = "START POSITION";
      if (elbowAngle >= S.UP_THRESHOLD) extension = "FULL EXTENSION";
      else if (elbowAngle >= 130) extension = "NEARLY EXTENDED";
      else if (elbowAngle >= S.DOWN_THRESHOLD) extension = "PRESSING";

      const backAngle = angleAt(lm, shoulder, hip, knee);
      let backArch = "Excessive Arch";
      if (backAngle >= 160) backArch = "Neutral";
      else if (backAngle >= 140) backArch = "Slight Arch";

      return {
        reps: this.reps,
        elbow_angle: Math.trunc(elbowAngle),
        extension_status: extension,
        back_arch_status: backArch,
      };
    }
  }

  class LungesDetector extends Detector {
    static DOWN_THRESHOLD = 100;
    static UP_THRESHOLD = 160;
    static MIN_VISIBILITY = 0.7;
    static BALANCE_TOLERANCE = 0.1;

    process(lm) {
      const S = LungesDetector;
      const leftKnee = angleAt(lm, L.LEFT_HIP, L.LEFT_KNEE, L.LEFT_ANKLE);
      const rightKnee = angleAt(lm, L.RIGHT_HIP, L.RIGHT_KNEE, L.RIGHT_ANKLE);
      const leftFront = leftKnee <= rightKnee;

      const frontKnee = leftFront ? leftKnee : rightKnee;
      const [hip, knee, ankle, shoulder] = leftFront
        ? [L.LEFT_HIP, L.LEFT_KNEE, L.LEFT_ANKLE, L.LEFT_SHOULDER]
        : [L.RIGHT_HIP, L.RIGHT_KNEE, L.RIGHT_ANKLE, L.RIGHT_SHOULDER];

      const visible = [hip, knee, ankle].every((i) => vis(lm, i) > S.MIN_VISIBILITY);

      if (visible) {
        if (frontKnee < S.DOWN_THRESHOLD) this.stage = "down";
        if (frontKnee > S.UP_THRESHOLD && this.stage === "down") {
          this.stage = "up";
          this.reps += 1;
        }
      }

      const torsoAngle = angleAt(lm, shoulder, hip, knee);
      const offset = Math.abs(
        (lm[L.LEFT_SHOULDER].x + lm[L.RIGHT_SHOULDER].x) / 2 - (lm[L.LEFT_HIP].x + lm[L.RIGHT_HIP].x) / 2
      );

      return {
        reps: this.reps,
        front_knee_angle: Math.trunc(frontKnee),
        torso_angle: Math.trunc(torsoAngle),
        balance_status: offset <= S.BALANCE_TOLERANCE ? "BALANCED" : "OFF BALANCE",
      };
    }
  }

  const DETECTOR_CLASSES = {
    "Squats": SquatDetector,
    "Push-ups": PushUpDetector,
    "Biceps Curls (Dumbbell)": BicepsCurlDetector,
    "Shoulder Press": ShoulderPressDetector,
    "Lunges": LungesDetector,
  };

  const api = { DETECTOR_CLASSES, calculateAngle, LANDMARKS: L };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.VisionFitDetectors = api;
})(typeof window !== "undefined" ? window : globalThis);
