/**
 * VisionFit - Interactive Showcase & Pose Simulator
 */

document.addEventListener("DOMContentLoaded", () => {
  initNavbarScroll();
  initPoseSimulator();
  initGalleryModal();
});

/* ----------------------------------------------------
   1. Navbar Scroll Effect
---------------------------------------------------- */
function initNavbarScroll() {
  const nav = document.querySelector(".nav");
  if (!nav) return;
  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      nav.classList.add("nav-scrolled");
    } else {
      nav.classList.remove("nav-scrolled");
    }
  });
}

/* ----------------------------------------------------
   2. Interactive Canvas Pose Simulator
---------------------------------------------------- */
function initPoseSimulator() {
  const canvas = document.getElementById("pose-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // Resize canvas for sharp retina displays
  function resizeCanvas() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = Math.max(380, rect.width * 0.56) * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${canvas.height / dpr}px`;
    ctx.scale(dpr, dpr);
  }

  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  let currentExercise = "squat";
  let isPlaying = true;
  let animTime = 0;
  let repCount = 0;
  let prevRepPhase = "up";

  const exerciseConfigs = {
    squat: {
      name: "Squats",
      primaryJoint: "Knee Angle",
      minAngle: 82,
      maxAngle: 172,
      depthThreshold: 90,
      cueGood: "Perfect depth! Drive through heels.",
      cueWarning: "Squat deeper to hit parallel!",
      desc: "Validates hip-to-knee parallel plane and tracks spine flexion angle."
    },
    pushup: {
      name: "Push-ups",
      primaryJoint: "Elbow Angle",
      minAngle: 85,
      maxAngle: 165,
      depthThreshold: 90,
      cueGood: "Chest to floor, clean lockout!",
      cueWarning: "Keep core tight, don't let hips sag.",
      desc: "Measures 90° elbow flexion and validates straight spine-to-ankle vector."
    },
    bicep: {
      name: "Biceps Curl",
      primaryJoint: "Elbow Flexion",
      minAngle: 42,
      maxAngle: 160,
      depthThreshold: 55,
      cueGood: "Great peak contraction! Squeeze biceps.",
      cueWarning: "Pin elbows to ribs, prevent torso swing.",
      desc: "Full range of motion detector with anti-momentum torso drift guard."
    },
    press: {
      name: "Shoulder Press",
      primaryJoint: "Arm Extension",
      minAngle: 85,
      maxAngle: 175,
      depthThreshold: 160,
      cueGood: "Solid overhead lockout, neutral neck.",
      cueWarning: "Engage glutes to prevent lower-back arch.",
      desc: "Tracks vertical barbell line and protects lumbar spine from over-arching."
    }
  };

  // Wire exercise selector buttons
  const tabBtns = document.querySelectorAll(".sim-tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentExercise = btn.getAttribute("data-exercise");
      repCount = 0;
      prevRepPhase = "up";
      updateSimTelemetry(exerciseConfigs[currentExercise], 0, "READY");
    });
  });

  // Play / Pause button
  const playBtn = document.getElementById("sim-play-btn");
  if (playBtn) {
    playBtn.addEventListener("click", () => {
      isPlaying = !isPlaying;
      playBtn.innerHTML = isPlaying
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg> Pause`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Play`;
    });
  }

  // Simulation Render Loop
  function render() {
    if (isPlaying) {
      animTime += 0.035;
    }

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;

    ctx.clearRect(0, 0, w, h);

    // Subtle digital grid background
    drawGrid(ctx, w, h);

    // Compute cycle progress: 0 (top/start) -> 1 (bottom/inflection) -> 0
    const rawCycle = (Math.sin(animTime) + 1) / 2;
    const config = exerciseConfigs[currentExercise];
    const currentAngle = Math.round(config.maxAngle - (config.maxAngle - config.minAngle) * rawCycle);

    // Rep Counting logic
    const repPhase = rawCycle > 0.85 ? "down" : (rawCycle < 0.15 ? "up" : "mid");
    if (prevRepPhase === "down" && repPhase === "up") {
      repCount++;
    }
    prevRepPhase = repPhase;

    // Determine status and cue
    let statusText = "MEASURING...";
    let statusClass = "status-good";
    let cueMessage = config.cueGood;

    if (currentExercise === "squat") {
      if (currentAngle <= config.depthThreshold) {
        statusText = "GOOD DEPTH";
        statusClass = "status-good";
        cueMessage = config.cueGood;
      } else if (rawCycle > 0.6) {
        statusText = "SQUAT LOWER";
        statusClass = "status-warn";
        cueMessage = config.cueWarning;
      }
    } else if (currentExercise === "pushup") {
      if (currentAngle <= config.depthThreshold) {
        statusText = "FULL RANGE";
        statusClass = "status-good";
        cueMessage = config.cueGood;
      } else if (rawCycle > 0.6) {
        statusText = "CHEST LOWER";
        statusClass = "status-warn";
        cueMessage = config.cueWarning;
      }
    } else if (currentExercise === "bicep") {
      if (currentAngle <= config.depthThreshold) {
        statusText = "PEAK CONTRACTION";
        statusClass = "status-good";
        cueMessage = config.cueGood;
      }
    } else if (currentExercise === "press") {
      if (currentAngle >= config.depthThreshold) {
        statusText = "FULL LOCKOUT";
        statusClass = "status-good";
        cueMessage = config.cueGood;
      }
    }

    // Draw the animated skeleton based on exercise
    drawSkeleton(ctx, w, h, currentExercise, rawCycle, currentAngle);

    // Update HUD display
    updateSimTelemetry(config, currentAngle, statusText, statusClass, cueMessage, repCount);

    requestAnimationFrame(render);
  }

  requestAnimationFrame(render);
}

/* ----------------------------------------------------
   3. Procedural Skeleton Drawing
---------------------------------------------------- */
function drawGrid(ctx, w, h) {
  ctx.save();
  ctx.strokeStyle = "rgba(0, 245, 212, 0.04)";
  ctx.lineWidth = 1;
  const step = 40;
  for (let x = 0; x < w; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.restore();
}

function drawSkeleton(ctx, w, h, exercise, t, angle) {
  ctx.save();

  const cx = w * 0.42;
  const groundY = h * 0.85;

  let head, shoulder, elbow, wrist, hip, knee, ankle;

  if (exercise === "squat") {
    // Squat: hips sink down and back, knees bend forward
    const hipDrop = t * 65;
    const hipBack = t * 30;
    const kneeFwd = t * 25;

    ankle = { x: cx, y: groundY };
    knee = { x: cx + 45 + kneeFwd, y: groundY - 70 + hipDrop * 0.4 };
    hip = { x: cx - 20 - hipBack, y: groundY - 145 + hipDrop };
    shoulder = { x: hip.x + 25, y: hip.y - 80 };
    head = { x: shoulder.x + 10, y: shoulder.y - 30 };
    elbow = { x: shoulder.x + 20, y: shoulder.y + 35 };
    wrist = { x: shoulder.x + 35, y: shoulder.y + 10 };

    // Draw Barbell
    ctx.strokeStyle = "#8892b0";
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(shoulder.x - 35, shoulder.y - 5);
    ctx.lineTo(shoulder.x + 55, shoulder.y - 5);
    ctx.stroke();

    // Draw Angle Arc on Knee
    drawAngleArc(ctx, knee, hip, ankle, `${angle}°`, "#00f5d4");

  } else if (exercise === "pushup") {
    // Pushup in plank orientation
    const drop = t * 50;
    ankle = { x: cx - 110, y: groundY - 10 };
    wrist = { x: cx + 70, y: groundY };
    elbow = { x: cx + 85 + t * 20, y: groundY - 50 + drop * 0.7 };
    shoulder = { x: cx + 60, y: groundY - 70 + drop };
    hip = { x: cx - 30, y: groundY - 45 + drop * 0.8 };
    head = { x: shoulder.x + 30, y: shoulder.y - 15 };
    knee = { x: cx - 70, y: groundY - 25 + drop * 0.4 };

    // Spine Vector (Spine alignment check line)
    ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(ankle.x, ankle.y);
    ctx.lineTo(shoulder.x, shoulder.y);
    ctx.stroke();
    ctx.setLineDash([]);

    drawAngleArc(ctx, elbow, shoulder, wrist, `${angle}°`, "#ff9f1c");

  } else if (exercise === "bicep") {
    // Standing Biceps Curl
    ankle = { x: cx, y: groundY };
    knee = { x: cx + 5, y: groundY - 80 };
    hip = { x: cx, y: groundY - 160 };
    shoulder = { x: cx + 10, y: groundY - 240 };
    head = { x: cx + 12, y: groundY - 280 };
    elbow = { x: shoulder.x + 10, y: shoulder.y + 70 };

    // Curl motion: wrist rotates around elbow
    const curlAngle = 0.5 + t * 2.1;
    const armLen = 65;
    wrist = {
      x: elbow.x + Math.sin(curlAngle) * armLen,
      y: elbow.y + Math.cos(curlAngle) * armLen
    };

    // Draw Dumbbell
    ctx.fillStyle = "#8892b0";
    ctx.beginPath();
    ctx.arc(wrist.x, wrist.y - 8, 12, 0, Math.PI * 2);
    ctx.arc(wrist.x, wrist.y + 8, 12, 0, Math.PI * 2);
    ctx.fill();

    drawAngleArc(ctx, elbow, shoulder, wrist, `${angle}°`, "#00f5d4");

  } else {
    // Overhead Shoulder Press
    ankle = { x: cx, y: groundY };
    knee = { x: cx, y: groundY - 80 };
    hip = { x: cx, y: groundY - 160 };
    shoulder = { x: cx, y: groundY - 240 };
    head = { x: cx, y: groundY - 280 };

    // Press upwards
    const pressY = shoulder.y + 30 - t * 80;
    elbow = { x: shoulder.x + 35 - t * 15, y: shoulder.y + 35 - t * 50 };
    wrist = { x: shoulder.x + 25, y: pressY };

    // Overhead Barbell
    ctx.strokeStyle = "#8892b0";
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(wrist.x - 55, wrist.y);
    ctx.lineTo(wrist.x + 55, wrist.y);
    ctx.stroke();

    drawAngleArc(ctx, elbow, shoulder, wrist, `${angle}°`, "#00bbf9");
  }

  // Draw Bones (Connections)
  ctx.strokeStyle = "rgba(0, 245, 212, 0.85)";
  ctx.lineWidth = 4;
  ctx.lineCap = "round";

  const bones = [
    [head, shoulder],
    [shoulder, hip],
    [shoulder, elbow],
    [elbow, wrist],
    [hip, knee],
    [knee, ankle]
  ];

  bones.forEach(([p1, p2]) => {
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  });

  // Draw Joints (MediaPipe landmark nodes)
  const joints = [head, shoulder, elbow, wrist, hip, knee, ankle];
  joints.forEach((joint, idx) => {
    ctx.beginPath();
    ctx.arc(joint.x, joint.y, idx === 0 ? 9 : 6, 0, Math.PI * 2);
    ctx.fillStyle = idx === 0 ? "#ff9f1c" : "#00f5d4";
    ctx.shadowColor = "#00f5d4";
    ctx.shadowBlur = 10;
    ctx.fill();

    // Outer glow ring
    ctx.beginPath();
    ctx.arc(joint.x, joint.y, idx === 0 ? 14 : 10, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(0, 245, 212, 0.4)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;
  });

  ctx.restore();
}

function drawAngleArc(ctx, vertex, p1, p2, label, color) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 2;

  const a1 = Math.atan2(p1.y - vertex.y, p1.x - vertex.x);
  const a2 = Math.atan2(p2.y - vertex.y, p2.x - vertex.x);

  ctx.beginPath();
  ctx.arc(vertex.x, vertex.y, 32, Math.min(a1, a2), Math.max(a1, a2));
  ctx.stroke();

  // Label badge
  ctx.font = "bold 13px 'JetBrains Mono', monospace";
  ctx.fillText(label, vertex.x + 36, vertex.y + 4);

  ctx.restore();
}

function updateSimTelemetry(config, angle, statusText, statusClass = "status-good", cueMessage = "", repCount = 0) {
  const angleEl = document.getElementById("sim-angle-val");
  const jointLabelEl = document.getElementById("sim-joint-label");
  const statusEl = document.getElementById("sim-status-badge");
  const cueEl = document.getElementById("sim-cue-text");
  const repEl = document.getElementById("sim-rep-val");

  if (angleEl) angleEl.textContent = `${angle}°`;
  if (jointLabelEl) jointLabelEl.textContent = config.primaryJoint;
  if (repEl) repEl.textContent = repCount;
  if (statusEl) {
    statusEl.textContent = statusText;
    statusEl.className = `sim-status-badge ${statusClass}`;
  }
  if (cueEl && cueMessage) {
    cueEl.textContent = `"${cueMessage}"`;
  }
}

/* ----------------------------------------------------
   4. Gallery Modal / Lightbox
---------------------------------------------------- */
function initGalleryModal() {
  const cards = document.querySelectorAll(".gallery-card");
  const modal = document.getElementById("gallery-modal");
  const modalImg = document.getElementById("modal-img");
  const modalCaption = document.getElementById("modal-caption");
  const closeBtn = document.querySelector(".modal-close");

  if (!cards.length || !modal) return;

  cards.forEach(card => {
    card.addEventListener("click", () => {
      const img = card.querySelector("img");
      const title = card.querySelector(".gallery-title");
      if (img && modalImg) {
        modalImg.src = img.src;
        modalCaption.textContent = title ? title.textContent : "";
        modal.classList.add("open");
      }
    });
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", () => modal.classList.remove("open"));
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("open");
  });
}
