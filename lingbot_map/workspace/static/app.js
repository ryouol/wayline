"use strict";

const byId = (id) => document.getElementById(id);
const state = { csrf: "", jobs: [], selectedId: null, engine: null, viewer: null, pollTimer: null };
const terminalStates = new Set(["ready", "failed", "cancelled"]);
const stageOrder = ["queued", "validating", "generating", "reconstructing", "exporting", "storing", "ready"];

function formatBytes(value) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function formatDate(value) {
  if (!value) return "Not started";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value * 1000));
}

async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (method !== "GET" && method !== "HEAD" && state.csrf) headers.set("X-CSRF-Token", state.csrf);
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    options.body = JSON.stringify(options.json);
  }
  const response = await fetch(path, { ...options, method, headers, credentials: "same-origin" });
  if (response.status === 401) {
    showLogin();
    throw new Error("Your session ended. Sign in again.");
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* response was not JSON */ }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showLogin() {
  byId("loginView").hidden = false;
  byId("appView").hidden = true;
  state.csrf = "";
  if (state.pollTimer) clearTimeout(state.pollTimer);
  byId("token").focus();
}

function showApp(user) {
  byId("loginView").hidden = true;
  byId("appView").hidden = false;
  byId("workspaceName").textContent = `${user.tenantName} · ${user.displayName}`;
}

function toast(message) {
  const node = byId("toast");
  node.textContent = message;
  node.hidden = false;
  window.setTimeout(() => { node.hidden = true; }, 4000);
}

function addFact(list, label, value) {
  const container = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = String(value ?? "Not recorded");
  container.append(term, detail);
  list.append(container);
}

function renderJobs() {
  const list = byId("jobList");
  list.replaceChildren();
  byId("emptyJobs").hidden = state.jobs.length > 0;
  state.jobs.forEach((job) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "job-button";
    button.setAttribute("aria-current", String(job.id === state.selectedId));
    const name = document.createElement("span");
    name.className = "job-name";
    name.textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic studio" : "Research reconstruction";
    const jobState = document.createElement("span");
    jobState.className = "job-state";
    jobState.textContent = job.state;
    const timestamp = document.createElement("span");
    timestamp.className = "job-time";
    timestamp.textContent = formatDate(job.createdAt);
    button.append(name, jobState, timestamp);
    button.addEventListener("click", () => selectJob(job.id));
    item.append(button);
    list.append(item);
  });
}

async function loadJobs({ selectNewest = false } = {}) {
  const result = await api("/api/jobs");
  state.jobs = result.jobs;
  if (selectNewest && state.jobs.length) state.selectedId = state.jobs[0].id;
  if (state.selectedId && !state.jobs.some((job) => job.id === state.selectedId)) state.selectedId = null;
  renderJobs();
  if (state.selectedId) await renderJobDetail();
  schedulePoll();
}

function schedulePoll() {
  if (state.pollTimer) clearTimeout(state.pollTimer);
  const hasActive = state.jobs.some((job) => !terminalStates.has(job.state));
  state.pollTimer = window.setTimeout(() => loadJobs().catch((error) => toast(error.message)), hasActive ? 900 : 5000);
}

async function selectJob(jobId) {
  state.selectedId = jobId;
  renderJobs();
  await renderJobDetail();
}

function updateStages(job) {
  const currentIndex = stageOrder.indexOf(job.stage);
  const ready = job.state === "ready";
  byId("stageList").querySelectorAll("li").forEach((item) => {
    const index = stageOrder.indexOf(item.dataset.stage);
    item.classList.toggle("complete", ready || (currentIndex >= 0 && index < currentIndex));
    item.classList.toggle("current", item.dataset.stage === job.stage || (item.dataset.stage === "generating" && job.stage === "reconstructing"));
  });
}

async function renderJobDetail() {
  if (!state.selectedId) return;
  const job = await api(`/api/jobs/${encodeURIComponent(state.selectedId)}`);
  byId("emptyDetail").hidden = true;
  byId("jobDetail").hidden = false;
  byId("detailEngine").textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic sample engine" : "LingBot research adapter";
  byId("detailTitle").textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic studio" : "Research reconstruction";
  byId("detailMeta").textContent = `Created ${formatDate(job.createdAt)} · attempt ${job.attempt}`;
  const percent = Math.round(job.progress * 100);
  byId("progressPercent").textContent = `${percent}%`;
  byId("progressBar").value = percent;
  byId("progressBar").textContent = `${percent}%`;
  byId("progressTitle").textContent = job.state === "ready" ? "Complete" : job.stage.replaceAll("_", " ");
  updateStages(job);
  byId("cancelButton").hidden = terminalStates.has(job.state);
  byId("deleteButton").hidden = !terminalStates.has(job.state);
  byId("jobMessage").textContent = job.error?.message || (job.state === "cancelled" ? "This job was cancelled and its reservation was released." : "");

  const provenance = byId("provenanceList");
  provenance.replaceChildren();
  addFact(provenance, "Engine", job.provenance.engine);
  addFact(provenance, "Commercial clearance", job.provenance.commerciallyCleared === false ? "Not cleared" : "Sample only");
  addFact(provenance, "License", job.provenance.license || "NOASSERTION");
  addFact(provenance, "Source imagery", job.provenance.sourceImages === false ? "None" : "User upload");
  addFact(provenance, "Model inference", job.provenance.modelInference === false ? "None" : "Research-only");
  addFact(provenance, "Compute units", `${job.usedUnits} used · ${job.reservedUnits} reserved initially`);

  const scene = job.artifacts?.find((artifact) => artifact.kind === "scene");
  byId("viewerSection").hidden = !scene;
  if (scene) {
    byId("downloadLink").href = scene.downloadUrl;
    byId("downloadLink").setAttribute("download", scene.filename);
    byId("shareButton").dataset.artifactId = scene.id;
    const facts = byId("artifactFacts");
    facts.replaceChildren();
    addFact(facts, "Artifact", scene.filename);
    addFact(facts, "Size", formatBytes(scene.sizeBytes));
    addFact(facts, "License", scene.licenseId);
    addFact(facts, "SHA-256", scene.sha256);
    addFact(facts, "Points", scene.metadata.pointCount?.toLocaleString() || "Not reported");
    addFact(facts, "Storage", "Tenant-scoped object");
    try {
      if (!state.viewer) state.viewer = new window.PointCloudViewer(byId("sceneCanvas"), byId("viewerStatus"));
      if (state.viewerArtifact !== scene.id) {
        state.viewerArtifact = scene.id;
        await state.viewer.load(scene.viewUrl);
      }
    } catch (error) {
      byId("viewerStatus").textContent = error.message;
    }
  }
}

async function loadEngines() {
  const result = await api("/api/engines");
  state.engine = result.engines.find((engine) => engine.id === "lingbot-research-v1");
  const enabled = Boolean(state.engine?.available);
  byId("researchButton").disabled = !enabled;
  byId("researchStatus").textContent = enabled ? "Enabled for research" : "Disabled";
  byId("researchStatus").classList.toggle("available", enabled);
  byId("researchReason").textContent = enabled
    ? "Research mode is explicitly enabled. Outputs remain non-commercial until rights are cleared."
    : (state.engine?.unavailableReasons.join(" · ") || "Research adapter is unavailable.");
}

async function initialize() {
  try {
    const result = await api("/api/me");
    state.csrf = result.csrfToken || "";
    showApp(result.user);
    await Promise.all([loadEngines(), loadJobs({ selectNewest: true })]);
  } catch (_) {
    showLogin();
  }
}

byId("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  byId("loginMessage").textContent = "";
  try {
    const result = await api("/api/session", { method: "POST", json: { token: byId("token").value } });
    state.csrf = result.csrfToken;
    byId("token").value = "";
    showApp(result.user);
    await Promise.all([loadEngines(), loadJobs({ selectNewest: true })]);
  } catch (error) {
    byId("loginMessage").textContent = error.message;
  }
});

byId("logoutButton").addEventListener("click", async () => {
  try { await api("/api/session", { method: "DELETE" }); } finally { showLogin(); }
});

byId("sampleButton").addEventListener("click", async () => {
  const button = byId("sampleButton");
  button.disabled = true;
  try {
    const job = await api("/api/jobs/sample", { method: "POST" });
    state.selectedId = job.id;
    await loadJobs();
    toast("Synthetic scene queued.");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});

byId("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = byId("video").files[0];
  if (!file) return;
  const button = byId("researchButton");
  let asset = null;
  button.disabled = true;
  try {
    const body = new FormData();
    body.append("file", file);
    asset = await api("/api/assets", { method: "POST", body });
    const job = await api("/api/jobs/research", {
      method: "POST",
      json: {
        assetId: asset.id,
        extractFps: Number(byId("sampleFps").value),
        maxFrames: Number(byId("frameLimit").value),
        rotate: false,
        maskSky: false,
        memoryGuard: true,
        mode: "streaming",
      },
    });
    state.selectedId = job.id;
    asset = null;
    await loadJobs();
  } catch (error) {
    if (asset) {
      try { await api(`/api/assets/${encodeURIComponent(asset.id)}`, { method: "DELETE" }); }
      catch (_) { /* a submitted job owns the asset or the server will reclaim it */ }
    }
    toast(error.message);
  } finally {
    button.disabled = !state.engine?.available;
  }
});

byId("refreshButton").addEventListener("click", () => loadJobs().catch((error) => toast(error.message)));
byId("cancelButton").addEventListener("click", async () => {
  if (!state.selectedId) return;
  try {
    await api(`/api/jobs/${encodeURIComponent(state.selectedId)}/cancel`, { method: "POST" });
    await loadJobs();
  } catch (error) { toast(error.message); }
});
byId("deleteButton").addEventListener("click", async () => {
  if (!state.selectedId || !window.confirm("Delete this job, its source upload, artifacts, and shares? This cannot be undone.")) return;
  try {
    await api(`/api/jobs/${encodeURIComponent(state.selectedId)}`, { method: "DELETE" });
    state.selectedId = null;
    state.viewerArtifact = null;
    byId("jobDetail").hidden = true;
    byId("emptyDetail").hidden = false;
    await loadJobs({ selectNewest: true });
    toast("Scene and stored objects deleted.");
  } catch (error) { toast(error.message); }
});

byId("shareButton").addEventListener("click", async () => {
  const artifactId = byId("shareButton").dataset.artifactId;
  if (!artifactId) return;
  try {
    const result = await api(`/api/artifacts/${encodeURIComponent(artifactId)}/shares`, {
      method: "POST", json: { ttlSeconds: 86400 },
    });
    byId("shareUrl").value = new URL(result.url, window.location.origin).href;
    byId("shareDialog").showModal();
  } catch (error) { toast(error.message); }
});
byId("copyShare").addEventListener("click", async () => {
  await navigator.clipboard.writeText(byId("shareUrl").value);
  toast("Share URL copied.");
});

initialize();
