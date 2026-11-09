/**
 * VisionFit landing page
 * - sticky nav border on scroll
 * - stick-figure simulator that runs the same rep rules and thresholds as the real detectors
 */
"use strict";

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initSimulator();
});

function initNav() {
  const nav = document.querySelector(".nav");
  if (!nav) return;

  const update = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
  window.addEventListener("scroll", update, { passive: true });
  update();
}

/* ----------------------------------------------------
   Geometry helpers (design space is 400 x 300)
---------------------------------------------------- */
const W = 400;
const H = 300;
const GROUND = 272;

const COLORS = {
  ink: "#0F1012",
  inkSoft: "#B9BBC0",
  accent: "#FF4F12",
  ground: "#E4E4DF",
  grid: "#ECECE7",
  gear: "#C9CAC4",
  white: "#FFFFFF",
};

const rad = (deg) => (deg * Math.PI) / 180;
const lerp = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });

// Point at `len` from origin, `deg` measured clockwise from straight up (toward +x).
function polar(origin, len, deg) {
  return { x: origin.x + len * Math.sin(rad(deg)), y: origin.y - len * Math.cos(rad(deg)) };
}

function angleAt(a, b, c) {
  const v1 = { x: a.x - b.x, y: a.y - b.y };
  const v2 = { x: c.x - b.x, y: c.y - b.y };
  const dot = v1.x * v2.x + v1.y * v2.y;
  const mag = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y);
  if (!mag) return 0;
  return (Math.acos(Math.max(-1, Math.min(1, dot / mag))) * 180) / Math.PI;
}

// Two-bone inverse kinematics: middle joint between a and c. side = +1 / -1 picks the bend direction.
function ik(a, c, l1, l2, side) {
  const dx = c.x - a.x;
  const dy = c.y - a.y;
  const dist = Math.hypot(dx, dy) || 1;
  const d = Math.min(dist, l1 + l2 - 0.001);
  const along = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(l1 * l1 - along * along, 0));
  const ux = dx / dist;
  const uy = dy / dist;
  return {
    x: a.x + along * ux - side * h * uy,
    y: a.y + along * uy + side * h * ux,
  };
}

/* ----------------------------------------------------
   Poses: t = 0 at the start of the rep, 1 at the far end.
   `fault` makes this rep show the mistake the detector looks for.
---------------------------------------------------- */
const POSES = {
  squat(t, fault) {
    const depth = fault ? t * 0.5 : t; // shallow rep
    const ankle = { x: 214, y: GROUND };
    const knee = polar(ankle, 62, 5 + 33 * depth);
    const hip = polar(knee, 62, -55 * depth);
    const lean = 12 + 28 * depth;
    const shoulder = polar(hip, 74, lean);
    return {
      head: polar(shoulder, 24, lean - 6),
      shoulder,
      elbow: { x: shoulder.x - 16, y: shoulder.y + 20 },
      wrist: { x: shoulder.x - 6, y: shoulder.y - 2 },
      hip, knee, ankle,
      gear: { type: "plate", at: { x: shoulder.x - 4, y: shoulder.y - 6 }, r: 18 },
      measure: ["hip", "knee", "ankle"],
    };
  },

  pushup(t, fault) {
    const wrist = { x: 292, y: GROUND };
    const elbowDeg = 165 - 83 * t;
    const reach = 2 * 40 * Math.sin(rad(elbowDeg / 2));
    const shoulder = { x: wrist.x - 4, y: GROUND - reach };
    const elbow = ik(shoulder, wrist, 40, 40, -1);
    const ankle = { x: 92, y: GROUND - 6 };
    const hip = lerp(ankle, shoulder, 0.55);
    if (fault) hip.y += 18 * t; // hips sag
    const knee = lerp(ankle, hip, 0.5);
    const dir = { x: shoulder.x - ankle.x, y: shoulder.y - ankle.y };
    const len = Math.hypot(dir.x, dir.y);
    return {
      head: { x: shoulder.x + (dir.x / len) * 24, y: shoulder.y + (dir.y / len) * 24 - 4 },
      shoulder, elbow, wrist, hip, knee, ankle,
      measure: ["shoulder", "elbow", "wrist"],
    };
  },

  curl(t, fault) {
    const ankle = { x: 200, y: GROUND };
    const knee = { x: 202, y: GROUND - 64 };
    const hip = { x: 200, y: GROUND - 128 };
    const lean = fault ? -18 * t : 0; // torso swings back
    const shoulder = polar(hip, 74, lean);
    const elbow = { x: shoulder.x + 4, y: shoulder.y + 44 };
    const elbowDeg = 165 - 128 * t;
    const a = rad(180 - elbowDeg);
    const wrist = { x: elbow.x + 40 * Math.sin(a), y: elbow.y + 40 * Math.cos(a) };
    return {
      head: polar(shoulder, 24, lean),
      shoulder, elbow, wrist, hip, knee, ankle,
      gear: { type: "dumbbell", at: wrist },
      measure: ["shoulder", "elbow", "wrist"],
    };
  },

  press(t, fault) {
    // Slightly smaller figure so the arms stay in frame at lockout.
    const ankle = { x: 200, y: GROUND };
    const knee = { x: 201, y: GROUND - 52 };
    const hip = { x: fault ? 200 + 9 * t : 200, y: GROUND - 104 };
    const lean = fault ? -16 * t : 0; // lower back arches
    const shoulder = polar(hip, 62, lean);
    const start = { x: shoulder.x + 26, y: shoulder.y - 46 };
    const lockout = { x: shoulder.x + 5, y: shoulder.y - 83 };
    const wrist = lerp(start, lockout, t);
    const elbow = ik(shoulder, wrist, 42, 42, -1);
    return {
      head: polar(shoulder, 21, lean),
      shoulder, elbow, wrist, hip, knee, ankle,
      gear: { type: "plate", at: wrist, r: 16 },
      measure: ["shoulder", "elbow", "wrist"],
    };
  },

  lunge(t, fault) {
    const front = { x: 256, y: GROUND };
    const back = { x: 126, y: GROUND - 8 };
    const hip = { x: 196, y: GROUND - 128 + 56 * t };
    const knee = ik(hip, front, 64, 64, -1);
    const knee2 = ik(hip, back, 64, 64, 1);
    const drift = fault ? 26 * t : 0; // shoulders drift off the hips
    const shoulder = { x: hip.x + 2 + drift, y: hip.y - 74 + Math.abs(drift) * 0.2 };
    return {
      head: polar(shoulder, 24, drift * 0.6),
      shoulder,
      elbow: { x: shoulder.x + 3, y: shoulder.y + 38 },
      wrist: { x: shoulder.x + 5, y: shoulder.y + 74 },
      hip, knee, ankle: front, knee2, ankle2: back,
      measure: ["hip", "knee", "ankle"],
    };
  },
};

/* ----------------------------------------------------
   Exercise rules — thresholds mirror app/detectors/*.py
---------------------------------------------------- */
const EXERCISES = {
  squat: {
    joint: "Knee",
    statusLabel: "Depth",
    rep: { start: (a) => a < 145, reached: (a) => a <= 100, done: (a) => a >= 160 },
    status(ctx) {
      if (ctx.inRep) return ctx.reached ? ["Good depth", "good"] : ["Go lower", "neutral"];
      if (ctx.lastRepShallow) return ["Too high", "warn"];
      return ctx.reps ? ["Good depth", "good"] : ["Standing", "neutral"];
    },
    faultCue: "Sit deeper. Get your hips below your knees on this next one.",
  },
  pushup: {
    joint: "Elbow",
    statusLabel: "Hips",
    rep: { start: (a) => a < 150, reached: (a) => a < 90, done: (a) => a > 160 },
    status: (ctx) => (ctx.fault && ctx.t > 0.35 ? ["Sagging", "bad"] : ["Level", "good"]),
    faultCue: "Hips are dropping. Squeeze your glutes and hold a straight line.",
  },
  curl: {
    joint: "Elbow",
    statusLabel: "Torso",
    rep: { start: (a) => a < 150, reached: (a) => a < 50, done: (a) => a > 160 },
    status: (ctx) => (ctx.fault && ctx.t > 0.3 ? ["Swinging", "bad"] : ["No swing", "good"]),
    faultCue: "Keep your body still. Let your biceps do the lifting, not your back.",
  },
  press: {
    joint: "Elbow",
    statusLabel: "Lower back",
    rep: { start: (a) => a > 100, reached: (a) => a > 160, done: (a) => a < 90 },
    status: (ctx) => (ctx.fault && ctx.t > 0.4 ? ["Excessive arch", "bad"] : ["Neutral", "good"]),
    faultCue: "Brace your core and tuck your ribs. Don't lean back to finish the press.",
  },
  lunge: {
    joint: "Front knee",
    statusLabel: "Balance",
    rep: { start: (a) => a < 150, reached: (a) => a < 100, done: (a) => a > 160 },
    status: (ctx) => (ctx.fault && ctx.t > 0.35 ? ["Off balance", "bad"] : ["Balanced", "good"]),
    faultCue: "Stay tall. Stack your shoulders right over your hips.",
  },
};

const SET_SIZE = 5;
const REP_SECONDS = 2.6;
const SET_CUE = "Set done. Shake it out and get ready for the next one.";
const INTRO_CUE = "Every fourth rep in this preview has a deliberate mistake. Watch the coach catch it.";

/* ----------------------------------------------------
   Simulator
---------------------------------------------------- */
function initSimulator() {
  const canvas = document.getElementById("sim-canvas");
  if (!canvas) return;

  const ctx2d = canvas.getContext("2d");
  const els = {
    joint: document.getElementById("sim-joint"),
    angle: document.getElementById("sim-angle"),
    reps: document.getElementById("sim-reps"),
    statusLabel: document.getElementById("sim-status-label"),
    status: document.getElementById("sim-status"),
    cue: document.getElementById("sim-cue"),
    toggle: document.getElementById("sim-toggle"),
    tabs: document.querySelectorAll(".sim-tab"),
  };

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const state = {
    exercise: "squat",
    playing: !reducedMotion,
    visible: true,
    phase: 0,
    repIndex: 0,
    lastTime: null,
    rafId: null,
    shown: {},
  };

  let tracker;

  function resetTracker() {
    tracker = { reps: 0, inRep: false, reached: false, lastRepShallow: false, faultCued: false };
    state.phase = 0;
    state.repIndex = 0;
    setText("cue", `“${INTRO_CUE}”`);
  }

  function setText(key, value) {
    if (state.shown[key] === value) return;
    state.shown[key] = value;
    els[key].textContent = value;
  }

  function setStatus([text, tone]) {
    const key = `${text}|${tone}`;
    if (state.shown.status === key) return;
    state.shown.status = key;
    els.status.className = `chip chip-${tone}`;
    els.status.innerHTML = `<i></i>${text}`;
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    draw();
  }

  function currentFrame() {
    const t = (1 - Math.cos(2 * Math.PI * state.phase)) / 2;
    const fault = state.repIndex % 4 === 3;
    const pose = POSES[state.exercise](t, fault);
    const [a, b, c] = pose.measure;
    const angle = Math.round(angleAt(pose[a], pose[b], pose[c]));
    return { t, fault, pose, angle };
  }

  function updateRules(frame) {
    const rules = EXERCISES[state.exercise];
    const { angle, fault } = frame;

    if (!tracker.inRep && rules.rep.start(angle)) {
      tracker.inRep = true;
      tracker.reached = false;
      tracker.faultCued = false;
      tracker.lastRepShallow = false;
    }

    if (tracker.inRep && rules.rep.reached(angle)) tracker.reached = true;

    if (tracker.inRep && fault && !tracker.faultCued && frame.t > 0.45 && state.exercise !== "squat") {
      tracker.faultCued = true;
      setText("cue", `“${rules.faultCue}”`);
    }

    if (tracker.inRep && rules.rep.done(angle)) {
      tracker.inRep = false;

      if (tracker.reached) {
        tracker.reps += 1;
        if (tracker.reps % SET_SIZE === 0) setText("cue", `“${SET_CUE}”`);
      } else {
        tracker.lastRepShallow = true;
        setText("cue", `“${rules.faultCue}”`);
      }
    }

    const status = rules.status({ ...tracker, t: frame.t, fault });
    setText("angle", `${angle}°`);
    setText("reps", String(tracker.reps));
    setText("joint", rules.joint);
    setText("statusLabel", rules.statusLabel);
    setStatus(status);
  }

  function draw(frame = currentFrame()) {
    const dpr = window.devicePixelRatio || 1;
    const cw = canvas.width / dpr;
    const ch = canvas.height / dpr;
    const scale = Math.min(cw / W, ch / H);
    const ox = (cw - W * scale) / 2;
    const oy = (ch - H * scale) / 2;

    ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx2d.clearRect(0, 0, cw, ch);
    ctx2d.setTransform(scale * dpr, 0, 0, scale * dpr, ox * dpr, oy * dpr);

    drawGrid(ctx2d);
    drawFigure(ctx2d, frame.pose, frame.angle);
  }

  function tick(now) {
    state.rafId = null;
    if (state.lastTime !== null) {
      const dt = Math.min((now - state.lastTime) / 1000, 0.1);
      state.phase += dt / REP_SECONDS;
      if (state.phase >= 1) {
        state.phase -= 1;
        state.repIndex += 1;
      }
    }
    state.lastTime = now;

    const frame = currentFrame();
    updateRules(frame);
    draw(frame);
    schedule();
  }

  function schedule() {
    if (state.rafId === null && state.playing && state.visible) {
      state.rafId = requestAnimationFrame(tick);
    }
  }

  function stop() {
    if (state.rafId !== null) cancelAnimationFrame(state.rafId);
    state.rafId = null;
    state.lastTime = null;
  }

  function showStill() {
    // Reduced motion / paused: show the bottom of a clean rep.
    state.phase = 0.5;
    const frame = currentFrame();
    updateRules(frame);
    draw(frame);
  }

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      els.tabs.forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
      state.exercise = tab.dataset.exercise;
      resetTracker();
      if (!state.playing) showStill();
    });
  });

  els.toggle.addEventListener("click", () => {
    state.playing = !state.playing;
    els.toggle.textContent = state.playing ? "Pause" : "Play";
    els.toggle.setAttribute("aria-pressed", String(!state.playing));
    if (state.playing) schedule();
    else stop();
  });

  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      state.visible = entries[0].isIntersecting;
      if (state.visible) schedule();
      else stop();
    }).observe(canvas);
  }

  window.addEventListener("resize", resize);

  resetTracker();
  if (reducedMotion) {
    els.toggle.textContent = "Play";
    els.toggle.setAttribute("aria-pressed", "true");
  }
  resize();
  if (state.playing) schedule();
  else showStill();
}

/* ----------------------------------------------------
   Drawing
---------------------------------------------------- */
function drawGrid(ctx) {
  ctx.save();
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  for (let x = 20; x < W; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, GROUND);
    ctx.stroke();
  }
  for (let y = GROUND - 40; y > 0; y -= 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }
  ctx.strokeStyle = COLORS.ground;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(0, GROUND + 2);
  ctx.lineTo(W, GROUND + 2);
  ctx.stroke();
  ctx.restore();
}

function line(ctx, a, b, color, width) {
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
}

function drawGear(ctx, gear) {
  if (!gear) return;
  ctx.save();
  if (gear.type === "plate") {
    ctx.fillStyle = COLORS.gear;
    ctx.beginPath();
    ctx.arc(gear.at.x, gear.at.y, gear.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLORS.ink;
    ctx.beginPath();
    ctx.arc(gear.at.x, gear.at.y, 3, 0, Math.PI * 2);
    ctx.fill();
  } else if (gear.type === "dumbbell") {
    ctx.fillStyle = COLORS.gear;
    ctx.beginPath();
    ctx.roundRect(gear.at.x - 9, gear.at.y - 9, 18, 18, 4);
    ctx.fill();
  }
  ctx.restore();
}

function drawFigure(ctx, p, angle) {
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  drawGear(ctx, p.gear);

  // Far leg (lunge) in a softer tone
  if (p.knee2) {
    line(ctx, p.hip, p.knee2, COLORS.inkSoft, 7);
    line(ctx, p.knee2, p.ankle2, COLORS.inkSoft, 7);
  }

  const bones = [
    [p.shoulder, p.hip],
    [p.hip, p.knee],
    [p.knee, p.ankle],
    [p.shoulder, p.elbow],
    [p.elbow, p.wrist],
  ];
  bones.forEach(([a, b]) => line(ctx, a, b, COLORS.ink, 7));

  // Neck + head
  line(ctx, p.shoulder, p.head, COLORS.ink, 7);
  ctx.fillStyle = COLORS.ink;
  ctx.beginPath();
  ctx.arc(p.head.x, p.head.y, 11, 0, Math.PI * 2);
  ctx.fill();

  if (p.gear && p.gear.type === "dumbbell") drawGear(ctx, p.gear);

  // Measured angle
  const [a, b, c] = p.measure;
  drawAngle(ctx, p[a], p[b], p[c], angle);

  // Joints
  [p.shoulder, p.elbow, p.wrist, p.hip, p.knee, p.ankle, p.knee2, p.ankle2]
    .filter(Boolean)
    .forEach((j) => {
      ctx.fillStyle = COLORS.white;
      ctx.beginPath();
      ctx.arc(j.x, j.y, 6.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = COLORS.accent;
      ctx.beginPath();
      ctx.arc(j.x, j.y, 4.5, 0, Math.PI * 2);
      ctx.fill();
    });

  ctx.restore();
}

function drawAngle(ctx, a, vertex, c, angle) {
  const a1 = Math.atan2(a.y - vertex.y, a.x - vertex.x);
  const a2 = Math.atan2(c.y - vertex.y, c.x - vertex.x);
  let diff = a2 - a1;
  while (diff > Math.PI) diff -= 2 * Math.PI;
  while (diff < -Math.PI) diff += 2 * Math.PI;

  ctx.save();
  ctx.fillStyle = "rgba(255, 79, 18, 0.12)";
  ctx.strokeStyle = COLORS.accent;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(vertex.x, vertex.y);
  ctx.arc(vertex.x, vertex.y, 26, a1, a1 + diff, diff < 0);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.arc(vertex.x, vertex.y, 26, a1, a1 + diff, diff < 0);
  ctx.stroke();

  // Label sits outside the angle, opposite the bisector.
  const mid = a1 + diff / 2;
  const lx = vertex.x - Math.cos(mid) * 30;
  const ly = vertex.y - Math.sin(mid) * 30;
  ctx.font = "800 15px Archivo, Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = COLORS.ink;
  ctx.fillText(`${angle}°`, lx, ly);
  ctx.restore();
}
