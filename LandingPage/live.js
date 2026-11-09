/**
 * "Try it live": MediaPipe pose tracking running entirely in the browser, feeding the same
 * rep rules as the app (detectors.js is a tested port of app/detectors/*.py).
 * The model and WASM runtime are only downloaded after the visitor presses "Start camera".
 */
const TASKS_VISION = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

const CONNECTIONS = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [24, 26], [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32], [27, 31], [28, 32],
];
const JOINTS = [...new Set(CONNECTIONS.flat())];

// Mirrors EXERCISE_DISPLAY / STATUS_TONES in app/services/config/workout_config.py
const EXERCISES = {
  "Squats": { angle: ["knee_angle", "Knee"], statuses: [["depth_status", "Depth"]] },
  "Push-ups": { angle: ["elbow_angle", "Elbow"], statuses: [["body_alignment", "Body line"], ["hip_status", "Hips"]] },
  "Biceps Curls (Dumbbell)": { angle: ["elbow_angle", "Elbow"], statuses: [["shoulder_status", "Elbow"], ["swing_status", "Torso"]] },
  "Shoulder Press": { angle: ["elbow_angle", "Elbow"], statuses: [["extension_status", "Lockout"], ["back_arch_status", "Lower back"]] },
  "Lunges": { angle: ["front_knee_angle", "Front knee"], statuses: [["balance_status", "Balance"]] },
};

const TONES = {
  "GOOD DEPTH": "good", "TOO HIGH": "warn",
  "Straight": "good", "Slight Bend": "warn", "Poor Form": "bad",
  "LEVEL": "good", "SAGGING": "bad", "PIKED UP": "warn",
  "STABLE": "good", "ELBOW DRIFTING": "warn",
  "NO SWING": "good", "SWINGING": "bad",
  "FULL EXTENSION": "good",
  "Neutral": "good", "Slight Arch": "warn", "Excessive Arch": "bad",
  "BALANCED": "good", "OFF BALANCE": "bad",
};

// Short spoken corrections, one per fault the detectors report.
const CUES = {
  "TOO HIGH": "That one didn't count. Sit deeper, hips below your knees.",
  "Poor Form": "Straighten your body from shoulders to heels.",
  "SAGGING": "Hips are dropping. Squeeze your glutes.",
  "PIKED UP": "Hips are too high. Lower them into a straight line.",
  "ELBOW DRIFTING": "Pin your elbow to your side.",
  "SWINGING": "Stop swinging. Keep your torso still.",
  "Excessive Arch": "Brace your core. Don't arch your lower back.",
  "OFF BALANCE": "Stay tall. Shoulders over hips.",
};

const FORM_CUE_COOLDOWN = 5000;
const REPEAT_ISSUE_COOLDOWN = 15000;

const $ = (id) => document.getElementById(id);

function initLiveDemo() {
  const els = {
    stage: $("live-stage"),
    video: $("live-video"),
    canvas: $("live-canvas"),
    placeholder: $("live-placeholder"),
    start: $("live-start"),
    stop: $("live-stop"),
    message: $("live-message"),
    perf: $("live-perf"),
    angleLabel: $("live-angle-label"),
    angle: $("live-angle"),
    reps: $("live-reps"),
    statuses: $("live-statuses"),
    cue: $("live-cue"),
    voice: $("live-voice"),
    tabs: document.querySelectorAll(".live-tab"),
  };
  if (!els.stage) return;

  const { DETECTOR_CLASSES } = window.VisionFitDetectors;
  const ctx = els.canvas.getContext("2d");

  const state = {
    exercise: "Squats",
    detector: new DETECTOR_CLASSES["Squats"](),
    landmarker: null,
    stream: null,
    running: false,
    lastVideoTime: -1,
    lastCueAt: 0,
    issueSpokenAt: {},
    lastReps: 0,
    perfSamples: [],
    frameTimes: [],
    shown: {},
  };

  function setText(el, key, value) {
    if (state.shown[key] === value) return;
    state.shown[key] = value;
    el.textContent = value;
  }

  function showMessage(text) {
    els.message.textContent = text;
    els.message.hidden = !text;
  }

  function setCue(text, speak) {
    els.cue.textContent = `“${text}”`;
    if (speak && els.voice.checked && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      window.speechSynthesis.speak(utterance);
    }
  }

  function selectExercise(name) {
    state.exercise = name;
    state.detector = new DETECTOR_CLASSES[name]();
    state.lastReps = 0;
    state.issueSpokenAt = {};
    els.tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.exercise === name)));
    setText(els.angleLabel, "angleLabel", EXERCISES[name].angle[1]);
    setText(els.reps, "reps", "0");
    setText(els.angle, "angle", "–");
    renderStatuses(null);
  }

  function renderStatuses(metrics) {
    const html = EXERCISES[state.exercise].statuses
      .map(([key, label]) => {
        const value = metrics ? metrics[key] : null;
        const tone = TONES[value] || "neutral";
        const shown = !value || value === "N/A" ? "Waiting" : value.charAt(0) + value.slice(1).toLowerCase();
        return `<div class="live-status"><span>${label}</span><span class="chip chip-${tone}"><i></i>${shown}</span></div>`;
      })
      .join("");
    if (state.shown.statuses !== html) {
      state.shown.statuses = html;
      els.statuses.innerHTML = html;
    }
  }

  function coach(metrics, now) {
    if (metrics.reps > state.lastReps) {
      state.lastReps = metrics.reps;
      if (metrics.reps % 5 === 0) {
        setCue(`${metrics.reps} reps. Strong work, keep that form.`, true);
        state.lastCueAt = now;
        return;
      }
    }

    if (now - state.lastCueAt < FORM_CUE_COOLDOWN) return;

    for (const [key] of EXERCISES[state.exercise].statuses) {
      const value = metrics[key];
      const cue = CUES[value];
      if (!cue) continue;
      if (now - (state.issueSpokenAt[value] || 0) < REPEAT_ISSUE_COOLDOWN) continue;
      state.issueSpokenAt[value] = now;
      state.lastCueAt = now;
      setCue(cue, true);
      return;
    }
  }

  function draw(landmarks) {
    const w = els.canvas.width;
    const h = els.canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (!landmarks) return;

    const line = Math.max(3, w / 220);
    const radius = Math.max(4, w / 150);
    const seen = (i) => (landmarks[i].visibility ?? 1) > 0.5;

    ctx.lineCap = "round";
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = line;
    for (const [a, b] of CONNECTIONS) {
      if (!seen(a) || !seen(b)) continue;
      ctx.beginPath();
      ctx.moveTo(landmarks[a].x * w, landmarks[a].y * h);
      ctx.lineTo(landmarks[b].x * w, landmarks[b].y * h);
      ctx.stroke();
    }

    for (const i of JOINTS) {
      if (!seen(i)) continue;
      ctx.fillStyle = "#FFFFFF";
      ctx.beginPath();
      ctx.arc(landmarks[i].x * w, landmarks[i].y * h, radius + 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#FF4F12";
      ctx.beginPath();
      ctx.arc(landmarks[i].x * w, landmarks[i].y * h, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Some tasks-vision builds report visibility as 0 for every point; treat that as "unknown".
  function normalise(landmarks) {
    const hasVisibility = landmarks.some((p) => p.visibility > 0);
    return hasVisibility ? landmarks : landmarks.map((p) => ({ ...p, visibility: 1 }));
  }

  function updatePerf(inferenceMs, now) {
    state.perfSamples.push(inferenceMs);
    state.frameTimes.push(now);
    if (state.perfSamples.length > 30) state.perfSamples.shift();
    while (state.frameTimes.length && now - state.frameTimes[0] > 1000) state.frameTimes.shift();

    if (state.frameTimes.length % 10 === 0) {
      const avg = state.perfSamples.reduce((a, b) => a + b, 0) / state.perfSamples.length;
      setText(els.perf, "perf", `${state.frameTimes.length} fps · ${avg.toFixed(0)} ms per frame · on your device`);
    }
  }

  function loop() {
    if (!state.running) return;
    const video = els.video;

    if (video.readyState >= 2 && video.currentTime !== state.lastVideoTime) {
      state.lastVideoTime = video.currentTime;

      if (els.canvas.width !== video.videoWidth) {
        els.canvas.width = video.videoWidth;
        els.canvas.height = video.videoHeight;
      }

      const now = performance.now();
      const result = state.landmarker.detectForVideo(video, now);
      updatePerf(performance.now() - now, now);

      const landmarks = result.landmarks && result.landmarks[0] ? normalise(result.landmarks[0]) : null;
      draw(landmarks);

      if (landmarks) {
        showMessage("");
        const metrics = state.detector.process(landmarks);
        setText(els.angle, "angle", `${metrics[EXERCISES[state.exercise].angle[0]]}°`);
        setText(els.reps, "reps", String(metrics.reps));
        renderStatuses(metrics);
        coach(metrics, now);
      } else {
        showMessage("Step back until your whole body is in view.");
      }
    }

    requestAnimationFrame(loop);
  }

  async function createLandmarker() {
    const [{ FilesetResolver, PoseLandmarker }, model] = await Promise.all([
      import(`${TASKS_VISION}/vision_bundle.mjs`),
      // Download the model once so a GPU → CPU fallback doesn't fetch it twice.
      fetch(MODEL_URL).then((r) => {
        if (!r.ok) throw new Error(`model download failed (${r.status})`);
        return r.arrayBuffer();
      }),
    ]);
    const fileset = await FilesetResolver.forVisionTasks(`${TASKS_VISION}/wasm`);
    const options = (delegate) => ({
      baseOptions: { modelAssetBuffer: new Uint8Array(model), delegate },
      runningMode: "VIDEO",
      numPoses: 1,
      minPoseDetectionConfidence: 0.6,
      minPosePresenceConfidence: 0.6,
      minTrackingConfidence: 0.6,
    });

    try {
      return await PoseLandmarker.createFromOptions(fileset, options("GPU"));
    } catch (e) {
      return PoseLandmarker.createFromOptions(fileset, options("CPU"));
    }
  }

  async function start() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showMessage("This browser can't access a camera here. Try Chrome, Edge or Safari over HTTPS.");
      return;
    }

    els.start.disabled = true;
    els.start.textContent = "Loading pose model…";
    showMessage("");

    try {
      const [landmarker, stream] = await Promise.all([
        state.landmarker ? Promise.resolve(state.landmarker) : createLandmarker(),
        navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 960 }, height: { ideal: 720 }, facingMode: "user" }, audio: false }),
      ]);

      state.landmarker = landmarker;
      state.stream = stream;
      els.video.srcObject = stream;
      await els.video.play();

      state.running = true;
      state.lastVideoTime = -1;
      els.stage.classList.add("is-live");
      els.placeholder.hidden = true;
      els.stop.hidden = false;
      setCue("Tracking. Start your reps whenever you're ready.", false);
      requestAnimationFrame(loop);
    } catch (e) {
      const denied = e && (e.name === "NotAllowedError" || e.name === "SecurityError");
      showMessage(
        denied
          ? "Camera access was blocked. Allow it in your browser's site settings and try again."
          : `Couldn't start the demo (${e && e.message ? e.message : e}).`
      );
      stop();
    } finally {
      els.start.disabled = false;
      els.start.textContent = "Start camera";
    }
  }

  function stop() {
    state.running = false;
    if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
    state.stream = null;
    els.video.srcObject = null;
    els.stage.classList.remove("is-live");
    els.placeholder.hidden = false;
    els.stop.hidden = true;
    ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
    setText(els.perf, "perf", "");
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }

  els.tabs.forEach((tab) => tab.addEventListener("click", () => selectExercise(tab.dataset.exercise)));
  els.start.addEventListener("click", start);
  els.stop.addEventListener("click", stop);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.running) stop();
  });

  selectExercise("Squats");
}

initLiveDemo();
