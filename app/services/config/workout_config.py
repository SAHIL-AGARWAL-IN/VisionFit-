EXERCISE_OPTIONS=[
    "Squats",
    "Push-ups",
    "Biceps Curls (Dumbbell)",
    "Shoulder Press",
    "Lunges"
]


POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),       # Shoulders & Arms
    (11, 23), (12, 24), (23, 24),                           # Torso / Hips
    (23, 25), (24, 26), (25, 27), (26, 28), (27, 29), (28, 30), (29, 31), (30, 32), (27, 31), (28, 32)  # Legs
]


METRICS_FIELDS = {
    "Squats": {
        "knee_angle": 0,
        "back_angle": 0,
        "torso_lean": 0,
        "depth_status": "N/A",
    },
    "Push-ups": {
        "elbow_angle": 0,
        "body_alignment": "N/A",
        "hip_status": "N/A",
    },
    "Biceps Curls (Dumbbell)": {
        "elbow_angle": 0,
        "shoulder_status": "N/A",
        "swing_status": "N/A",
    },
    "Shoulder Press": {
        "elbow_angle": 0,
        "extension_status": "N/A",
        "back_arch_status": "N/A",
    },
    "Lunges": {
        "front_knee_angle": 0,
        "torso_angle": 0,
        "balance_status": "N/A",
    },
}


# How each exercise is presented in the UI.
#   angles:   (session key, label) pairs shown as degree readouts
#   statuses: (session key, label) pairs shown as status chips
#   checks:   plain-language summary of what the detector actually measures
#   tip:      how to position the camera for that detector
EXERCISE_DISPLAY = {
    "Squats": {
        "short": "Squats",
        "angles": [("knee_angle", "Knee"), ("torso_lean", "Torso lean")],
        "statuses": [("depth_status", "Depth")],
        "checks": "Knee bends past 100° for a counted rep, torso lean from vertical.",
        "tip": "Stand side-on to the camera with your whole body in frame.",
    },
    "Push-ups": {
        "short": "Push-ups",
        "angles": [("elbow_angle", "Elbow")],
        "statuses": [("body_alignment", "Body line"), ("hip_status", "Hips")],
        "checks": "Elbow below 90° and back to 160°, straight body line, hips not sagging or piked.",
        "tip": "Put the camera at floor level, side-on, a couple of metres away.",
    },
    "Biceps Curls (Dumbbell)": {
        "short": "Curls",
        "angles": [("elbow_angle", "Elbow")],
        "statuses": [("shoulder_status", "Elbow position"), ("swing_status", "Torso")],
        "checks": "Full range from 160° down to 50°, elbow pinned to your side, no torso swing.",
        "tip": "Face the camera or stand side-on, upper body and hips in frame.",
    },
    "Shoulder Press": {
        "short": "Press",
        "angles": [("elbow_angle", "Elbow")],
        "statuses": [("extension_status", "Lockout"), ("back_arch_status", "Lower back")],
        "checks": "Lockout above 160° overhead, back to 90°, lower back not over-arched.",
        "tip": "Stand side-on so the camera sees arms, hips and knees.",
    },
    "Lunges": {
        "short": "Lunges",
        "angles": [("front_knee_angle", "Front knee"), ("torso_angle", "Torso")],
        "statuses": [("balance_status", "Balance")],
        "checks": "Front knee below 100° for a counted rep, shoulders stacked over hips.",
        "tip": "Stand side-on with your full stride and feet in frame.",
    },
}


# Maps detector status strings to a tone for the status chips.
STATUS_TONES = {
    "GOOD DEPTH": "good", "STANDING": "neutral", "GO LOWER": "neutral", "TOO HIGH": "warn",
    "Straight": "good", "Slight Bend": "warn", "Poor Form": "bad",
    "LEVEL": "good", "SAGGING": "bad", "PIKED UP": "warn",
    "STABLE": "good", "ELBOW DRIFTING": "warn",
    "NO SWING": "good", "SWINGING": "bad",
    "FULL EXTENSION": "good", "NEARLY EXTENDED": "neutral", "PRESSING": "neutral", "START POSITION": "neutral",
    "Neutral": "good", "Slight Arch": "warn", "Excessive Arch": "bad",
    "BALANCED": "good", "OFF BALANCE": "bad",
}


PROMPT = (
    "You are VisionFit, a professional AI gym coach monitoring a user's workout via live camera.\n\n"
    "### Your Role\n"
    "Provide around 10-15 words, high-energy coaching cues. You speak these aloud, so they must be natural and encouraging.\n\n"
    "### Input Format\n"
    "You receive updates in the format: 'Event: [state] Form Issue: [description]'.\n"
    "- 'Event': workout_started, set_completed, workout_completed, no_pose_detected, ongoing_form_check.\n"
    "- 'Form Issue': A technical description of a pose error (if any).\n\n"
    "### Guidelines\n"
    "1. Provide feedback in natural, short sentences. Avoid overly brief or fragmented responses.\n"
    "2. NO generic greetings or redundant questions. Focus on the workout.\n"
    "3. Use the second person (e.g., 'Straighten your back' instead of 'The user should straighten their back').\n"
    "4. Maintain a professional coaching tone and prioritize safety.\n\n"
    "### Scenario Response Styles\n"
    "- 'workout_started' -> A motivating and sharp command to begin.\n"
    "- 'workout_completed' -> A warm and encouraging closing for the session.\n"
    "- 'set_completed' -> Direct praise for finishing the set.\n"
    "- 'no_pose_detected' -> A clear instruction for the user to reposition within the camera frame.\n"
    "- 'ongoing_form_check' + Form Issue -> A precise, supportive correction for the detected error.\n"
    "- 'ongoing_form_check' (No Issue) -> Brief, energetic words of encouragement.\n"
)
