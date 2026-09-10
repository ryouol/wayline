"use strict";

const byId = (id) => document.getElementById(id);
const state = {
  csrf: "", jobs: [], assets: [], shares: [], selectedId: null, engine: null, viewer: null,
  viewerArtifact: null, pollTimer: null, toastTimer: null, epoch: 0, controllers: new Set(),
  principal: "", principalMarker: "", jobCursor: null, assetCursor: null, shareCursor: null,
  selectedJobs: new Set(), selectedAssets: new Set(), selectedShares: new Set(),
  jobsRenderKey: "", accountType: "operator", config: null,
};
const timeline = new window.SceneTimeline(byId("timeline"), byId("viewModeLabel"));
const terminalStates = new Set(["ready", "failed", "cancelled"]);
const stageOrder = ["queued", "validating", "generating", "reconstructing", "exporting", "storing", "ready"];
const sessionChannel = "BroadcastChannel" in window
  ? new BroadcastChannel("lingbot-workspace-session-v1") : null;

const pause = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function formatBytes(value) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function formatDate(value) {
  if (!value) return "Not started";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value * 1000));
}

async function api(path, options = {}) {
  const requestEpoch = state.epoch;
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (method !== "GET" && method !== "HEAD" && state.csrf) headers.set("X-CSRF-Token", state.csrf);
  if (options.idempotent && !headers.has("Idempotency-Key")) {
    // This header instance is reused by transport and in-progress retries. A
    // lost response can therefore never turn one click into two mutations.
    headers.set("Idempotency-Key", crypto.randomUUID());
  }
  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }
  const controller = new AbortController();
  state.controllers.add(controller);
  byId("requestStatus").hidden = false;
  document.body.setAttribute("aria-busy", "true");
  let timedOut = false;
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, options.timeoutMs || 60000);
  try {
    let response;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        response = await fetch(path, {
          method, headers, body, credentials: "same-origin", signal: controller.signal,
        });
      } catch (error) {
        if (!options.idempotent || error?.name === "AbortError" || attempt >= 1) throw error;
        await pause(250);
        continue;
      }
      if (options.idempotent && response.status === 409 && attempt < 2) {
        let code = "";
        try { code = (await response.clone().json()).code || ""; } catch (_) { /* not JSON */ }
        if (code === "idempotency_in_progress") {
          await pause(500 * (attempt + 1));
          continue;
        }
      }
      break;
    }
    if (!response) throw new Error("The request did not receive a response.");
    if (requestEpoch !== state.epoch) throw new DOMException("Stale session response", "AbortError");
    const principalMarker = response.headers.get("X-Workspace-Principal");
    if (principalMarker && state.principalMarker && principalMarker !== state.principalMarker) {
      broadcastSession("account-changed");
      secureReset();
      window.location.reload();
      throw new DOMException("Workspace account changed", "AbortError");
    }
    if (principalMarker) state.principalMarker = principalMarker;
    if (response.status === 401) {
      broadcastSession("signed-out");
      showLogin();
      throw new Error("Your session ended. Sign in again.");
    }
    if (!response.ok) {
      let detail = `Request failed (${response.status}).`;
      try {
        const value = (await response.json()).detail;
        if (typeof value === "string") detail = value;
        else if (Array.isArray(value)) detail = value.map((item) => `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg}`).join("; ");
      } catch (_) { /* response was not JSON */ }
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return await response.json();
  } catch (error) {
    if (timedOut) throw new Error("The request timed out. Refresh to check its status before trying again.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    state.controllers.delete(controller);
    byId("requestStatus").hidden = state.controllers.size === 0;
    document.body.setAttribute("aria-busy", String(state.controllers.size > 0));
  }
}

function broadcastSession(type) {
  const event = { type, at: Date.now() };
  sessionChannel?.postMessage(event);
  try {
    localStorage.setItem("lingbot-workspace-session-event", JSON.stringify(event));
    localStorage.removeItem("lingbot-workspace-session-event");
  } catch (_) { /* storage can be disabled */ }
}

async function revalidateSession() {
  if (byId("appView").hidden) return;
  try {
    const result = await api("/api/me");
    showApp(result.user, result.csrfToken);
  } catch (error) {
    if (error?.name !== "AbortError" && !byId("appView").hidden) report(error);
  }
}

function handleSessionEvent(event) {
  window.WorkspaceSessionEvents.dispatch(event, {
    signedOut: showLogin,
    accountChanged: () => {
      secureReset();
      window.location.reload();
    },
    sessionChanged: revalidateSession,
  });
}

sessionChannel?.addEventListener("message", (event) => handleSessionEvent(event.data));
window.addEventListener("storage", (event) => {
  if (event.key !== "lingbot-workspace-session-event" || !event.newValue) return;
  try { handleSessionEvent(JSON.parse(event.newValue)); } catch (_) { /* malformed peer event */ }
});
window.addEventListener("focus", () => revalidateSession());
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") revalidateSession();
});

function clearDetail() {
  byId("jobDetail").hidden = true;
  byId("emptyDetail").hidden = false;
  byId("viewerSection").hidden = true;
  byId("downloadLink").removeAttribute("href");
  byId("shareButton").removeAttribute("data-artifact-id");
  byId("artifactFacts").replaceChildren();
  byId("provenanceList").replaceChildren();
  byId("detailEngine").textContent = "Engine";
  byId("detailTitle").textContent = "Scene";
  byId("detailMeta").textContent = "";
  byId("progressTitle").textContent = "Processing";
  byId("progressPercent").textContent = "0%";
  byId("progressBar").value = 0;
  byId("progressBar").textContent = "0%";
  byId("jobMessage").textContent = "";
  byId("viewerStatus").textContent = "Waiting for a scene.";
  byId("cancelButton").hidden = true;
  byId("deleteButton").hidden = true;
  stopPlayback();
  timeline.attach(null);
  if (state.viewer) state.viewer.destroy();
  state.viewer = null;
  state.viewerArtifact = null;
}

function secureReset() {
  state.epoch += 1;
  state.controllers.forEach((controller) => controller.abort());
  state.controllers.clear();
  if (state.pollTimer) clearTimeout(state.pollTimer);
  state.pollTimer = null;
  state.csrf = "";
  state.jobs = [];
  state.jobsRenderKey = "";
  state.assets = [];
  state.shares = [];
  state.jobCursor = null;
  state.assetCursor = null;
  state.shareCursor = null;
  state.selectedJobs.clear();
  state.selectedAssets.clear();
  state.selectedShares.clear();
  state.selectedId = null;
  state.engine = null;
  state.principal = "";
  state.principalMarker = "";
  if (state.toastTimer) clearTimeout(state.toastTimer);
  state.toastTimer = null;
  byId("toast").hidden = true;
  byId("toast").textContent = "";
  byId("jobList").replaceChildren();
  byId("assetList").replaceChildren();
  byId("shareList").replaceChildren();
  byId("workspaceName").textContent = "Workspace";
  byId("researchStatus").textContent = "Checking";
  byId("researchReason").textContent = "Research configuration is checked after sign-in.";
  byId("loginMessage").textContent = "";
  byId("token").value = "";
  byId("video").value = "";
  byId("selectedFilename").textContent = "Choose a video";
  byId("researchMessage").textContent = "";
  byId("shareUrl").value = "";
  if (byId("shareDialog").open) byId("shareDialog").close();
  byId("emptyJobs").hidden = false;
  byId("emptyAssets").hidden = false;
  byId("emptyShares").hidden = false;
  byId("loadMoreJobs").hidden = true;
  byId("loadMoreAssets").hidden = true;
  byId("loadMoreShares").hidden = true;
  updateSelectionSummary();
  clearDetail();
}

function showLogin() {
  secureReset();
  byId("loginView").hidden = false;
  byId("appView").hidden = true;
  byId("mobileWorkspaceCta").hidden = true;
  byId("skipLink").href = "#loginTitle";
  byId("trialButton").focus();
}

function showApp(user, csrfToken) {
  const principal = `${user.tenantName}\u0000${user.displayName}`;
  if (state.principal && state.principal !== principal) secureReset();
  state.principal = principal;
  state.csrf = csrfToken || "";
  state.accountType = user.accountType || "operator";
  byId("shareButton").hidden = state.accountType === "trial";
  renderAccountActions();
  byId("loginView").hidden = true;
  byId("appView").hidden = false;
  byId("mobileWorkspaceCta").hidden = false;
  byId("skipLink").href = "#workspaceMain";
  byId("workspaceName").textContent = `${user.tenantName} · ${user.displayName}`;
}

function renderAccountActions() {
  byId("saveWorkspace").hidden = state.accountType !== "trial" || !state.config?.googleSignIn;
}

function toast(message) {
  const node = byId("toast");
  if (state.toastTimer) clearTimeout(state.toastTimer);
  node.textContent = message;
  node.hidden = false;
  state.toastTimer = window.setTimeout(() => {
    node.hidden = true;
    node.textContent = "";
    state.toastTimer = null;
  }, 4000);
}

function report(error) {
  if (error?.name !== "AbortError") toast(error.message);
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
  const key = JSON.stringify([state.jobs, state.selectedId, [...state.selectedJobs]]);
  if (state.jobsRenderKey === key) return;
  state.jobsRenderKey = key;
  list.replaceChildren();
  byId("emptyJobs").hidden = state.jobs.length > 0;
  state.jobs.forEach((job) => {
    const item = document.createElement("li");
    item.className = "job-row";
    const selector = document.createElement("input");
    selector.type = "checkbox";
    selector.className = "record-selector";
    selector.checked = state.selectedJobs.has(job.id);
    selector.disabled = !terminalStates.has(job.state);
    selector.setAttribute("aria-label", `Select ${job.engineId} scene created ${formatDate(job.createdAt)}`);
    selector.addEventListener("change", () => {
      if (selector.checked) state.selectedJobs.add(job.id); else state.selectedJobs.delete(job.id);
      updateSelectionSummary();
    });
    const button = document.createElement("button");
    button.type = "button";
    button.className = "job-button";
    button.setAttribute("aria-current", String(job.id === state.selectedId));
    const name = document.createElement("span");
    name.className = "job-name";
    name.textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic studio" : "Captured space";
    const jobState = document.createElement("span");
    jobState.className = "job-state";
    jobState.textContent = job.state;
    const timestamp = document.createElement("span");
    timestamp.className = "job-time";
    timestamp.textContent = formatDate(job.createdAt);
    button.append(name, jobState, timestamp);
    button.addEventListener("click", () => selectJob(job.id).catch(report));
    const target = document.createElement("label");
    target.className = "selector-target";
    target.append(selector);
    item.append(target, button);
    list.append(item);
  });
}

async function loadJobs({ selectNewest = false, append = false, preserveLoaded = false } = {}) {
  const cursor = append ? state.jobCursor : null;
  const loadedCursor = state.jobCursor;
  const query = new URLSearchParams({ limit: "25" });
  if (cursor) query.set("cursor", cursor);
  const result = await api(`/api/jobs?${query}`);
  if (append) {
    const seen = new Set(state.jobs.map((job) => job.id));
    state.jobs.push(...result.jobs.filter((job) => !seen.has(job.id)));
  } else if (preserveLoaded) {
    const refreshed = new Set(result.jobs.map((job) => job.id));
    state.jobs = [...result.jobs, ...state.jobs.filter((job) => !refreshed.has(job.id))];
  } else {
    state.jobs = result.jobs;
  }
  state.jobCursor = preserveLoaded && loadedCursor ? loadedCursor : result.nextCursor;
  byId("loadMoreJobs").hidden = !state.jobCursor;
  if (selectNewest && state.jobs.length) state.selectedId = state.jobs[0].id;
  if (state.selectedId && !state.jobs.some((job) => job.id === state.selectedId)) state.selectedId = null;
  const jobIds = new Set(state.jobs.map((job) => job.id));
  state.selectedJobs.forEach((id) => { if (!jobIds.has(id) && !append) state.selectedJobs.delete(id); });
  renderJobs();
  updateSelectionSummary();
  if (state.selectedId) await renderJobDetail(); else clearDetail();
  schedulePoll();
}

function updateSelectionSummary() {
  const counts = [state.selectedJobs.size, state.selectedAssets.size, state.selectedShares.size];
  const total = counts.reduce((sum, value) => sum + value, 0);
  byId("selectionSummary").textContent = total
    ? `${total} selected · ${counts[0]} scenes · ${counts[1]} uploads · ${counts[2]} shares`
    : "Nothing selected";
  byId("bulkDeleteButton").disabled = total === 0;
}

function inventoryRow({ id, name, meta, selected, disabled = false, actionLabel, onSelect, onAction }) {
  const item = document.createElement("li");
  item.className = "inventory-row";
  const selector = document.createElement("input");
  selector.type = "checkbox";
  selector.className = "record-selector";
  selector.checked = selected;
  selector.disabled = disabled;
  selector.setAttribute("aria-label", `Select ${name}`);
  selector.addEventListener("change", () => onSelect(selector.checked));
  const copy = document.createElement("span");
  copy.className = "inventory-copy";
  const title = document.createElement("span");
  title.className = "inventory-name";
  title.textContent = name;
  const detail = document.createElement("span");
  detail.className = "inventory-meta";
  detail.textContent = meta;
  copy.append(title, detail);
  const action = document.createElement("button");
  action.type = "button";
  action.className = "text-button danger inventory-action";
  action.textContent = actionLabel;
  action.disabled = disabled;
  action.dataset.recordId = id;
  action.addEventListener("click", onAction);
  const target = document.createElement("label");
  target.className = "selector-target";
  target.append(selector);
  item.append(target, copy, action);
  return item;
}

function renderAssets() {
  const list = byId("assetList");
  list.replaceChildren();
  byId("emptyAssets").hidden = state.assets.length > 0;
  state.assets.forEach((asset) => {
    const deleteBlocked = !asset.deletable;
    const metadata = `${formatBytes(asset.sizeBytes)} · ${formatDate(asset.createdAt)}`;
    list.append(inventoryRow({
      id: asset.id,
      name: asset.name,
      meta: deleteBlocked ? `${metadata} · ${asset.deleteBlockedReason}` : metadata,
      selected: state.selectedAssets.has(asset.id),
      disabled: deleteBlocked,
      actionLabel: deleteBlocked ? `Linked to ${asset.linkedJobCount}` : "Delete",
      onSelect: (checked) => {
        if (checked) state.selectedAssets.add(asset.id); else state.selectedAssets.delete(asset.id);
        updateSelectionSummary();
      },
      onAction: () => deleteAsset(asset),
    }));
  });
}

function renderShares() {
  const list = byId("shareList");
  list.replaceChildren();
  byId("emptyShares").hidden = state.shares.length > 0;
  const now = Date.now() / 1000;
  state.shares.forEach((share) => {
    const inactive = Boolean(share.revokedAt) || share.expiresAt <= now;
    list.append(inventoryRow({
      id: share.id,
      name: share.filename,
      meta: inactive ? "Inactive" : `Expires ${formatDate(share.expiresAt)}`,
      selected: state.selectedShares.has(share.id),
      disabled: inactive,
      actionLabel: inactive ? "Revoked" : "Revoke",
      onSelect: (checked) => {
        if (checked) state.selectedShares.add(share.id); else state.selectedShares.delete(share.id);
        updateSelectionSummary();
      },
      onAction: () => revokeShare(share),
    }));
  });
}

function mergeInventoryRows(existing, incoming) {
  const rows = new Map(existing.map((row) => [row.id, row]));
  incoming.forEach((row) => rows.set(row.id, row));
  return [...rows.values()];
}

async function loadAssets({ append = false } = {}) {
  const query = new URLSearchParams({ limit: "25" });
  if (append && state.assetCursor) query.set("cursor", state.assetCursor);
  const result = await api(`/api/assets?${query}`);
  state.assets = append ? mergeInventoryRows(state.assets, result.assets) : result.assets;
  const deletableIds = new Set(state.assets.filter((asset) => asset.deletable).map((asset) => asset.id));
  state.selectedAssets.forEach((id) => {
    if (!deletableIds.has(id)) state.selectedAssets.delete(id);
  });
  state.assetCursor = result.nextCursor;
  byId("loadMoreAssets").hidden = !state.assetCursor;
  renderAssets();
  updateSelectionSummary();
}

async function loadShares({ append = false } = {}) {
  const query = new URLSearchParams({ limit: "25" });
  if (append && state.shareCursor) query.set("cursor", state.shareCursor);
  const result = await api(`/api/shares?${query}`);
  state.shares = append ? mergeInventoryRows(state.shares, result.shares) : result.shares;
  const now = Date.now() / 1000;
  const activeIds = new Set(state.shares.filter((share) => !share.revokedAt && share.expiresAt > now).map((share) => share.id));
  state.selectedShares.forEach((id) => {
    if (!activeIds.has(id)) state.selectedShares.delete(id);
  });
  state.shareCursor = result.nextCursor;
  byId("loadMoreShares").hidden = !state.shareCursor;
  renderShares();
  updateSelectionSummary();
}

async function loadInventory() {
  await Promise.all([loadAssets(), loadShares()]);
  updateSelectionSummary();
}

async function deleteAsset(asset) {
  if (!asset.deletable) {
    toast(asset.deleteBlockedReason);
    return;
  }
  if (!window.confirm(`Delete retained upload “${asset.name}”?`)) return;
  try {
    await api(`/api/assets/${encodeURIComponent(asset.id)}`, { method: "DELETE", idempotent: true });
    state.selectedAssets.delete(asset.id);
    await loadAssets();
    toast("Upload deletion accepted.");
  } catch (error) { toast(error.message); }
}

async function revokeShare(share) {
  if (!window.confirm(`Revoke the share for “${share.filename}”?`)) return;
  try {
    await api(`/api/shares/${encodeURIComponent(share.id)}`, { method: "DELETE", idempotent: true });
    state.selectedShares.delete(share.id);
    await loadShares();
    toast("Share revoked.");
  } catch (error) { toast(error.message); }
}

function schedulePoll() {
  if (state.pollTimer) clearTimeout(state.pollTimer);
  const hasActive = state.jobs.some((job) => !terminalStates.has(job.state));
  state.pollTimer = window.setTimeout(
    () => loadJobs({ preserveLoaded: true }).catch(report), hasActive ? 900 : 5000,
  );
}

async function selectJob(jobId) {
  state.selectedId = jobId;
  renderJobs();
  await renderJobDetail();
  byId("detailTitle").focus({ preventScroll: true });
  if (window.matchMedia("(max-width: 860px)").matches) byId("jobDetail").scrollIntoView({ block: "start" });
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
  if (!state.selectedId) { clearDetail(); return; }
  const selected = state.selectedId;
  const job = await api(`/api/jobs/${encodeURIComponent(state.selectedId)}`);
  if (selected !== state.selectedId) return;
  byId("emptyDetail").hidden = true;
  byId("jobDetail").hidden = false;
  byId("detailEngine").textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic sample engine" : "RECONSTRUCTED WITH LINGBOT-MAP";
  byId("detailTitle").textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic studio" : "Captured space";
  byId("detailMeta").textContent = `Created ${formatDate(job.createdAt)} · attempt ${job.attempt}`;
  const percent = Math.round(job.progress * 100);
  document.querySelector(".progress-section").classList.toggle("is-ready", job.state === "ready");
  byId("progressPercent").textContent = `${percent}%`;
  byId("progressBar").value = percent;
  byId("progressBar").textContent = `${percent}%`;
  byId("progressTitle").textContent = job.state === "ready" ? "Complete" : job.stage.replaceAll("_", " ");
  updateStages(job);
  byId("cancelButton").hidden = terminalStates.has(job.state);
  byId("deleteButton").hidden = !terminalStates.has(job.state);
  byId("jobMessage").textContent = job.error?.message || (job.state === "cancelled" ? "This job was cancelled and its reservation was released." : job.state === "ready" ? "Scene ready. Review the point cloud, then download or create an expiring share." : "");
  byId("jobMessage").classList.toggle("success-message", job.state === "ready");

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
        timeline.attach(null);
        const viewer = state.viewer, epoch = state.epoch;
        await viewer.load(scene.viewUrl);
        if (state.viewer !== viewer || state.epoch !== epoch || state.selectedId !== job.id) return;
        state.viewerArtifact = scene.id;
        renderTimeline();
      }
    } catch (error) {
      if (state.selectedId === job.id && error.name !== "AbortError") byId("viewerStatus").textContent = error.message;
    }
  } else if (state.viewer) {
    stopPlayback();
    timeline.attach(null);
    state.viewer.destroy();
    state.viewer = null;
    state.viewerArtifact = null;
  }
}

async function loadEngines() {
  const result = await api("/api/engines");
  state.engine = result.engines.find((engine) => engine.id === "lingbot-research-v1");
  const enabled = Boolean(state.engine?.available);
  byId("researchButton").disabled = !enabled;
  byId("researchStatus").textContent = enabled ? "GPU runner configured" : "Reconstruction unavailable";
  byId("researchStatus").classList.toggle("available", enabled);
  byId("researchReason").textContent = enabled
    ? "Your capture is processed privately. Research preview; no payment required."
    : (state.accountType === "trial" && state.config?.googleSignIn ? "Sign in with Google to reconstruct your own capture."
      : "The GPU runner is not connected yet. You can explore the sample while setup is completed.");
}

async function initialize() {
  try {
    const result = await api("/api/me");
    showApp(result.user, result.csrfToken);
    await Promise.all([loadEngines(), loadJobs({ selectNewest: true }), loadInventory()]);
  } catch (_) {
    showLogin();
  }
}

byId("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  if (button.disabled) return;
  button.disabled = true;
  button.textContent = "Signing in…";
  byId("token").removeAttribute("aria-invalid");
  byId("loginMessage").textContent = "Signing in…";
  try {
    const result = await api("/api/session", { method: "POST", json: { token: byId("token").value.trim() } });
    byId("token").value = "";
    showApp(result.user, result.csrfToken);
    broadcastSession("session-changed");
    await Promise.all([loadEngines(), loadJobs({ selectNewest: true }), loadInventory()]);
    byId("workspaceMain").focus();
    toast("Signed in. Create a synthetic scene or open a recent scene.");
  } catch (error) {
    byId("loginMessage").textContent = error.message;
    byId("token").setAttribute("aria-invalid", "true");
  } finally {
    button.disabled = false;
    button.textContent = "Continue";
  }
});

byId("logoutButton").addEventListener("click", async () => {
  try {
    await api("/api/session", { method: "DELETE" });
    broadcastSession("signed-out");
    showLogin();
  } catch (error) {
    if (!byId("appView").hidden) toast(`Sign out failed: ${error.message}`);
  }
});

byId("sampleButton").addEventListener("click", async () => {
  const button = byId("sampleButton");
  button.disabled = true;
  button.textContent = "Creating scene…";
  try {
    const job = await api("/api/jobs/sample", { method: "POST", idempotent: true });
    state.selectedId = job.id;
    await loadJobs();
    toast("Synthetic scene queued.");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Create synthetic scene ↗";
  }
});

byId("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = byId("video").files[0];
  if (!file) return;
  if (state.config && file.size > state.config.maxUploadBytes) {
    byId("researchMessage").textContent = `Choose a video smaller than ${formatBytes(state.config.maxUploadBytes)}.`;
    return;
  }
  const button = byId("researchButton");
  let asset = null;
  button.disabled = true;
  byId("researchMessage").textContent = "Uploading video…";
  try {
    const body = new FormData();
    body.append("file", file);
    asset = await api("/api/assets", { method: "POST", body, idempotent: true, timeoutMs: 15 * 60 * 1000 });
    byId("researchMessage").textContent = "Video uploaded. Queuing reconstruction…";
    const job = await api("/api/jobs/research", {
      method: "POST",
      idempotent: true,
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
    await Promise.all([loadJobs(), loadAssets()]);
    byId("researchMessage").textContent = "Reconstruction queued. Follow its progress in Scene review.";
  } catch (error) {
    if (asset) {
      try { await api(`/api/assets/${encodeURIComponent(asset.id)}`, { method: "DELETE", idempotent: true }); }
      catch (_) { /* a submitted job owns the asset or the server will reclaim it */ }
    }
    toast(error.message);
    byId("researchMessage").textContent = error.message;
  } finally {
    button.disabled = !state.engine?.available;
  }
});

byId("refreshButton").addEventListener("click", () => loadJobs().catch(report));
byId("loadMoreJobs").addEventListener("click", () => loadJobs({ append: true }).catch(report));
byId("loadMoreAssets").addEventListener("click", () => loadAssets({ append: true }).catch(report));
byId("loadMoreShares").addEventListener("click", () => loadShares({ append: true }).catch(report));
byId("refreshInventoryButton").addEventListener("click", () => loadInventory().catch(report));
byId("cancelButton").addEventListener("click", async () => {
  if (!state.selectedId) return;
  try {
    await api(`/api/jobs/${encodeURIComponent(state.selectedId)}/cancel`, { method: "POST", idempotent: true });
    await loadJobs();
  } catch (error) { toast(error.message); }
});
byId("deleteButton").addEventListener("click", async () => {
  if (!state.selectedId || !window.confirm("Delete this job, its source upload, artifacts, and shares? This cannot be undone.")) return;
  try {
    await api(`/api/jobs/${encodeURIComponent(state.selectedId)}`, { method: "DELETE", idempotent: true });
    state.selectedId = null;
    clearDetail();
    await Promise.all([loadJobs({ selectNewest: true }), loadInventory()]);
    toast("Deletion accepted. Stored objects are being removed.");
  } catch (error) { toast(error.message); }
});

byId("shareButton").addEventListener("click", async () => {
  const artifactId = byId("shareButton").dataset.artifactId;
  if (!artifactId) return;
  try {
    const result = await api(`/api/artifacts/${encodeURIComponent(artifactId)}/shares`, {
      method: "POST", json: { ttlSeconds: 86400 },
      idempotent: true,
    });
    byId("shareUrl").value = new URL(result.url, window.location.origin).href;
    byId("shareDialog").showModal();
    await loadShares();
  } catch (error) { toast(error.message); }
});
byId("copyShare").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(byId("shareUrl").value);
    toast("Share URL copied.");
  } catch (_) {
    byId("shareUrl").focus();
    byId("shareUrl").select();
    toast("Clipboard unavailable. Copy the selected link manually.");
  }
});
byId("bulkDeleteButton").addEventListener("click", async () => {
  const total = state.selectedJobs.size + state.selectedAssets.size + state.selectedShares.size;
  if (!total || !window.confirm(`Clean up ${total} selected record${total === 1 ? "" : "s"}?`)) return;
  const button = byId("bulkDeleteButton");
  button.disabled = true;
  try {
    const result = await api("/api/bulk-delete", {
      method: "POST",
      idempotent: true,
      json: {
        jobIds: [...state.selectedJobs],
        assetIds: [...state.selectedAssets],
        shareIds: [...state.selectedShares],
      },
    });
    Object.values(result.accepted).flat().forEach((id) => {
      state.selectedJobs.delete(id);
      state.selectedAssets.delete(id);
      state.selectedShares.delete(id);
    });
    await Promise.all([loadJobs({ selectNewest: true }), loadInventory()]);
    const failures = Object.keys(result.errors).length;
    toast(failures ? `Cleanup accepted with ${failures} record error${failures === 1 ? "" : "s"}.` : "Cleanup accepted.");
  } catch (error) { toast(error.message); }
  finally { updateSelectionSummary(); }
});

function stopPlayback() { timeline.stop(); }
function renderTimeline() { timeline.attach(state.viewer); }
function wholeSpace() { timeline.wholeSpace(); }
byId("resetView").addEventListener("click", wholeSpace);
byId("zoomIn").addEventListener("click", () => { stopPlayback(); state.viewer?.zoom(0.8); });
byId("zoomOut").addEventListener("click", () => { stopPlayback(); state.viewer?.zoom(1.25); });
byId("fullScreen").addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (document.querySelector(".viewport-wrap").requestFullscreen) await document.querySelector(".viewport-wrap").requestFullscreen();
    else toast("Full screen is unavailable in this browser. Rotate your phone for a wider view.");
  } catch (_) { toast("Full screen is unavailable in this browser."); }
});
byId("video").addEventListener("change", () => {
  const file = byId("video").files[0];
  byId("selectedFilename").textContent = file ? file.name : "Choose a video";
  byId("researchMessage").textContent = file ? `${formatBytes(file.size)} · ready to upload` : "";
});
byId("trialButton").addEventListener("click", async () => {
  const button = byId("trialButton"); button.disabled = true;
  byId("trialMessage").textContent = "Opening your private playground…";
  try {
    const result = await api("/api/trial", { method: "POST" });
    showApp(result.user, result.csrfToken); broadcastSession("session-changed");
    await Promise.all([loadEngines(), loadJobs(), loadInventory()]);
    byId("sampleButton").click();
    byId("workspaceMain").focus();
  } catch (error) { byId("trialMessage").textContent = error.message; }
  finally { button.disabled = false; }
});
async function loadPublicConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("Sign-in options could not be loaded. Refresh to retry.");
    state.config = await response.json();
    renderAccountActions();
    byId("googleLogin").hidden = !state.config.googleSignIn;
    byId("trialButton").hidden = !state.config.trialEnabled;
    byId("trialButton").classList.toggle("secondary", state.config.googleSignIn);
    byId("trialButton").classList.toggle("primary", !state.config.googleSignIn);
    byId("onboardingStatus").textContent = state.config.googleSignIn
      ? "A private workspace. One video to start. No card needed."
      : "Try the synthetic sample. Google sign-in is being connected.";
    if (new URLSearchParams(location.search).get("signin") === "cancelled") byId("trialMessage").textContent = "Google sign-in was cancelled. You can try again.";
  } catch (error) { byId("onboardingStatus").textContent = error.message; }
}
loadPublicConfig();
initialize();
