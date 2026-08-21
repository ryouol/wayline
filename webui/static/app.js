/* LingBot-Map console */

const $ = (id) => document.getElementById(id);

const state = {
  clip: null,          // {path, name, duration, fps, frames, sizeBytes}
  runId: null,
  stream: null,
  paused: false,
  secPerFrame: 5.0,    // replaced by the live figure once a run is under way
  snapshot: null,
};

/* ── viridis ─────────────────────────────────────────────────
   The ramp the repo itself uses to colour camera trajectories.  */
const VIRIDIS = [
  [68, 1, 84], [65, 68, 135], [42, 120, 142],
  [34, 168, 132], [122, 209, 81], [253, 231, 37],
];

function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const s = t * (VIRIDIS.length - 1);
  const i = Math.min(VIRIDIS.length - 2, Math.floor(s));
  const f = s - i;
  const a = VIRIDIS[i], b = VIRIDIS[i + 1];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(
    a[1] + (b[1] - a[1]) * f)},${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

/* ── formatting ─────────────────────────────────────────────── */

function clock(sec) {
  if (sec == null || !isFinite(sec)) return "—";
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function coarse(sec) {
  if (sec == null || !isFinite(sec)) return "—";
  if (sec < 90) return `${Math.round(sec)}s`;
  const m = Math.round(sec / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h}h ${String(m % 60).padStart(2, "0")}m`;
}

const bytes = (n) => n > 1 << 30
  ? `${(n / (1 << 30)).toFixed(1)} GB`
  : `${Math.round(n / (1 << 20))} MB`;

/* ── the ribbon ──────────────────────────────────────────────
   Each tick is one frame. Completed frames take their colour from
   their position in the sequence, so a finished run reads as the
   full viridis ramp. The bracket marks the frames still held in the
   attention window — the sliding cache this model streams through. */

const WINDOW = 32;

function drawRibbon() {
  const cv = $("ribbon");
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = 72;
  if (!w) return;
  cv.width = w * dpr; cv.height = h * dpr;
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);

  const snap = state.snapshot;
  const total = snap?.total || state.plannedFrames || 0;
  const done = snap?.frame || 0;
  const barTop = 4, barH = 44, axisY = barTop + barH + 10;

  // axis
  g.strokeStyle = "#242B39";
  g.lineWidth = 1;
  g.beginPath(); g.moveTo(0, axisY + 0.5); g.lineTo(w, axisY + 0.5); g.stroke();

  if (!total) {
    g.fillStyle = "#5C6577";
    g.font = '10px "JetBrains Mono", monospace';
    g.fillText("no sequence loaded", 0, barTop + barH / 2 + 4);
    return;
  }

  const slot = w / total;
  const bw = Math.max(1, Math.min(slot - (slot > 3 ? 1 : 0), 10));

  for (let i = 0; i < total; i++) {
    const x = i * slot;
    if (i < done) {
      g.fillStyle = viridis(i / Math.max(1, total - 1));
      g.fillRect(x, barTop, bw, barH);
    } else {
      g.fillStyle = "#1B212C";
      g.fillRect(x, barTop + barH * 0.62, bw, barH * 0.38);
    }
  }

  // attention window: the frames still resident in the KV cache
  if (done > 0 && snap?.stage === "inference") {
    const from = Math.max(0, done - WINDOW);
    const x0 = from * slot, x1 = done * slot;
    g.strokeStyle = "#FDE725";
    g.lineWidth = 1;
    g.strokeRect(x0 + 0.5, barTop - 1.5, Math.max(2, x1 - x0) - 1, barH + 3);

    g.fillStyle = "#FDE725";
    g.fillRect(Math.min(w - 1.5, x1), barTop - 4, 1.5, barH + 8);
  }

  // scale
  g.fillStyle = "#5C6577";
  g.font = '9px "JetBrains Mono", monospace';
  const step = total <= 120 ? 25 : total <= 400 ? 50 : total <= 1200 ? 200 : 500;
  for (let i = step; i < total; i += step) {
    const x = i * slot;
    g.fillRect(x, axisY + 1, 1, 4);
    g.fillText(String(i), x + 4, axisY + 12);
  }
}

window.addEventListener("resize", drawRibbon);

/* ── estimate ────────────────────────────────────────────────── */

function plannedFrames() {
  if (!state.clip) return 0;
  const sampled = Math.ceil(state.clip.duration * Number($("fps").value));
  return Math.max(1, Math.min(Number($("maxFrames").value), sampled, state.clip.frames));
}

function refreshEstimate() {
  const note = $("estNote");
  if (!state.clip) {
    $("estFrames").textContent = "—";
    $("estTime").textContent = "—";
    note.textContent = "Load a clip to see the cost.";
    note.classList.remove("hot");
    $("start").disabled = true;
    return;
  }
  const frames = plannedFrames();
  state.plannedFrames = frames;
  const seconds = frames * state.secPerFrame;

  $("estFrames").textContent = frames.toLocaleString();
  $("estTime").textContent = coarse(seconds);
  $("start").disabled = !!state.runId;

  const sampled = Math.ceil(state.clip.duration * Number($("fps").value));
  let msg;
  if (frames < sampled) {
    msg = `Frame limit stops this at ${frames} of ${sampled.toLocaleString()} sampled frames — the last ${coarse((sampled - frames) * state.secPerFrame)} of the clip won't be reconstructed.`;
  } else {
    msg = `Every sampled frame is reconstructed.`;
  }
  if (seconds > 1200) {
    msg += ` A rented L4 would take about ${coarse(seconds / 10)}.`;
    note.classList.add("hot");
  } else {
    note.classList.remove("hot");
  }
  if (frames > 320 && $("memoryGuard").checked) {
    msg += " Past 320 frames the model subsamples keyframes; expect some drift.";
  }
  note.textContent = msg;
  // Preview the run in the ribbon so the sequence header agrees with it.
  if (!state.runId) {
    $("frameNow").textContent = "0";
    $("frameTotal").textContent = frames.toLocaleString();
  }
  drawRibbon();
}

/* ── upload ──────────────────────────────────────────────────── */

async function handleFile(file) {
  if (!file) return;
  const drop = $("drop"), note = $("uploadNote");
  note.hidden = true;
  drop.classList.add("busy");
  $("dropIdle").hidden = false;
  $("dropIdle").querySelector(".drop-title").textContent = "Reading clip…";

  const body = new FormData();
  body.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");

    state.clip = { ...data, name: data.name || file.name };
    $("clipName").textContent = state.clip.name;
    $("clipDur").textContent = clock(data.duration);
    $("clipFps").textContent = `${data.fps} fps`;
    $("clipFrames").textContent = data.frames.toLocaleString();
    $("clipSize").textContent = bytes(data.sizeBytes);
    $("dropIdle").hidden = true;
    $("dropLoaded").hidden = false;
    drop.classList.add("loaded");

    // Portrait footage reconstructs sideways without the rotation flag.
    if (data.height > data.width) $("rotate").checked = true;
    refreshEstimate();
  } catch (err) {
    note.textContent = err.message;
    note.hidden = false;
    $("dropIdle").querySelector(".drop-title").textContent = "Drop a video";
  } finally {
    drop.classList.remove("busy");
  }
}

/* ── run ─────────────────────────────────────────────────────── */

const STAGE_TEXT = {
  queued: ["Starting", "Spawning the model process"],
  extracting: ["Extracting", "Pulling frames out of the clip"],
  loading: ["Loading", "Reading the 4.3 GB checkpoint"],
  inference: ["Reconstructing", "Streaming frames through the model"],
  finishing: ["Masking sky", "Segmenting sky out of the point cloud"],
  ready: ["Ready", "Reconstruction complete"],
  stopped: ["Stopped", "Run ended early"],
  failed: ["Failed", "The run did not complete"],
};

function applySnapshot(s) {
  state.snapshot = s;
  state.paused = s.paused;

  const [eyebrow, line] = STAGE_TEXT[s.stage] || ["Running", s.stage];
  $("stageEyebrow").textContent = s.paused ? "Paused" : eyebrow;
  $("stageLine").textContent = s.paused ? "Held — memory still reserved" : line;
  $("stageLine").classList.toggle("dim", s.stage === "stopped");

  $("frameNow").textContent = s.frame.toLocaleString();
  $("frameTotal").textContent = (s.total || 0).toLocaleString();

  $("mElapsed").textContent = clock(s.elapsed);
  $("mEta").textContent = s.stage === "inference" && s.eta ? s.eta : "—";
  $("mRate").textContent = s.secPerFrame ? `${s.secPerFrame.toFixed(1)}s` : "—";
  $("mMasks").textContent = s.masksTotal
    ? `${s.masksDone}/${s.masksTotal}`
    : (s.stage === "ready" ? "done" : "—");

  if (s.secPerFrame) state.secPerFrame = s.secPerFrame;

  const live = ["queued", "extracting", "loading", "inference", "finishing"].includes(s.stage);
  $("pause").disabled = !live;
  $("stop").disabled = !live;
  $("pause").textContent = s.paused ? "Resume" : "Pause";

  $("rig").className = "rig" + (live && !s.paused ? " live" : s.paused ? " warn" : "");
  $("rigLabel").textContent = live
    ? (s.paused ? "Paused" : "CPU · fp32 · SDPA · running")
    : "CPU · fp32 · SDPA";

  if (s.viewerUrl) {
    $("result").hidden = false;
    $("openViewer").href = s.viewerUrl;
    const took = s.inferenceSeconds ? coarse(s.inferenceSeconds) : coarse(s.elapsed);
    $("resultLine").textContent =
      `${s.frame.toLocaleString()} frames reconstructed in ${took}. The viewer stays live at ${s.viewerUrl} until you stop the run.`;
  }

  if (s.error) {
    $("stageEyebrow").textContent = "Failed";
    $("stageLine").textContent = s.error.slice(0, 120);
  }

  const log = $("log");
  if (s.log?.length) {
    log.textContent = s.log.slice(-120).join("\n");
    log.scrollTop = log.scrollHeight;
  }

  if (!live) {
    $("start").disabled = !state.clip;
    if (state.stream) { state.stream.close(); state.stream = null; }
    state.runId = null;
  }
  drawRibbon();
}

async function startRun() {
  if (!state.clip) return;
  $("start").disabled = true;
  $("result").hidden = true;

  const payload = {
    video: state.clip.path,
    extractFps: Number($("fps").value),
    maxFrames: Number($("maxFrames").value),
    rotate: $("rotate").checked,
    maskSky: $("maskSky").checked,
    memoryGuard: $("memoryGuard").checked,
  };

  try {
    const res = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not start the run.");
    state.runId = data.id;
    $("log").textContent = "";
    state.stream = new EventSource(`/api/runs/${data.id}/stream`);
    state.stream.onmessage = (e) => applySnapshot(JSON.parse(e.data));
    state.stream.onerror = () => { state.stream.close(); state.stream = null; };
  } catch (err) {
    $("stageEyebrow").textContent = "Failed";
    $("stageLine").textContent = err.message;
    $("start").disabled = false;
  }
}

async function command(path) {
  if (!state.runId) return;
  await fetch(`/api/runs/${state.runId}/${path}`, { method: "POST" });
}

/* ── wiring ──────────────────────────────────────────────────── */

$("drop").addEventListener("click", () => {
  if (!state.clip) $("file").click();
});
$("drop").addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && !state.clip) { e.preventDefault(); $("file").click(); }
});
$("file").addEventListener("change", (e) => handleFile(e.target.files[0]));

["dragenter", "dragover"].forEach((t) =>
  $("drop").addEventListener(t, (e) => { e.preventDefault(); $("drop").classList.add("over"); }));
["dragleave", "drop"].forEach((t) =>
  $("drop").addEventListener(t, (e) => { e.preventDefault(); $("drop").classList.remove("over"); }));
$("drop").addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));

$("clearClip").addEventListener("click", (e) => {
  e.stopPropagation();
  state.clip = null;
  $("file").value = "";
  $("dropLoaded").hidden = true;
  $("dropIdle").hidden = false;
  $("dropIdle").querySelector(".drop-title").textContent = "Drop a video";
  $("drop").classList.remove("loaded");
  refreshEstimate();
});

$("fps").addEventListener("input", (e) => { $("fpsOut").textContent = e.target.value; refreshEstimate(); });
$("maxFrames").addEventListener("input", (e) => { $("maxOut").textContent = e.target.value; refreshEstimate(); });
$("memoryGuard").addEventListener("change", refreshEstimate);

$("start").addEventListener("click", startRun);
$("pause").addEventListener("click", () => command(state.paused ? "resume" : "pause"));
$("stop").addEventListener("click", () => command("stop"));

fetch("/api/baseline").then((r) => r.json()).then((d) => {
  state.secPerFrame = d.secPerFrame;
  if (!d.hasCheckpoint) {
    $("estNote").textContent = "lingbot-map.pt is missing. Run ./download_weights.sh first.";
    $("estNote").classList.add("hot");
  }
  refreshEstimate();
});

drawRibbon();
