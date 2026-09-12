"use strict";

const byId = (id) => document.getElementById(id);
const state = {
  csrf: "", jobs: [], assets: [], shares: [], selectedId: null, engine: null, viewer: null,
  viewerArtifact: null, pollTimer: null, toastTimer: null, epoch: 0, controllers: new Set(),
  principal: "", principalMarker: "", jobCursor: null, assetCursor: null, shareCursor: null,
  selectedJobs: new Set(), selectedAssets: new Set(), selectedShares: new Set(),
  jobsRenderKey: "", accountType: "operator", config: null,
  reconstructionAllowance: null, accountRefresh: null, uploading: false, captureCheck: null,
  capturePreviewUrl: null,
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
  renderRequestStatus();
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
    const result = await response.json();
    if (requestEpoch !== state.epoch) throw new DOMException("Stale session response", "AbortError");
    return result;
  } catch (error) {
    if (timedOut) throw new Error("The request timed out. Refresh to check its status before trying again.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    state.controllers.delete(controller);
    renderRequestStatus();
  }
}

const dialogOrder = new Set();

function activeDialog() {
  return Array.from(dialogOrder).filter((dialog) => dialog.open).at(-1);
}

function openDialog(dialog) {
  if (!dialog.open) {
    dialog.showModal();
    dialogOrder.delete(dialog);
    dialogOrder.add(dialog);
  }
  renderRequestStatus();
}

function renderRequestStatus() {
  const node = byId("requestStatus");
  const dialog = activeDialog();
  const host = dialog || document.body;
  if (node.parentNode !== host) {
    if (dialog) host.prepend(node); else host.append(node);
  }
  node.classList.toggle("dialog-request-status", Boolean(dialog));
  node.hidden = state.controllers.size === 0;
  document.body.setAttribute("aria-busy", String(state.controllers.size > 0));
}

function broadcastSession(type) {
  const event = { type, at: Date.now() };
  sessionChannel?.postMessage(event);
  try {
    localStorage.setItem("lingbot-workspace-session-event", JSON.stringify(event));
    localStorage.removeItem("lingbot-workspace-session-event");
  } catch (_) { /* storage can be disabled */ }
}

function refreshAccount({ fresh = false } = {}) {
  const epoch = state.epoch;
  if (state.accountRefresh) {
    if (!fresh) return state.accountRefresh;
    // A job transition needs a snapshot requested after that transition.
    return state.accountRefresh.then(() => {
      if (epoch !== state.epoch) throw new DOMException("Stale account refresh", "AbortError");
      return refreshAccount();
    });
  }
  const pending = (async () => {
    try {
      const [result, engines] = await Promise.all([api("/api/me"), api("/api/engines")]);
      if (epoch !== state.epoch) throw new DOMException("Stale account response", "AbortError");
      showApp(result.user, result.csrfToken, result.reconstructionAllowance);
      state.engine = engines.engines.find((engine) => engine.id === "lingbot-research-v1");
      renderReconstructionStatus();
      return result;
    } catch (error) {
      if (epoch === state.epoch) {
        state.engine = null;
        if (state.accountType === "google") state.reconstructionAllowance = null;
        renderReconstructionStatus();
      }
      throw error;
    } finally {
      if (state.accountRefresh === pending) state.accountRefresh = null;
    }
  })();
  state.accountRefresh = pending;
  return pending;
}

async function revalidateSession(options) {
  if (byId("appView").hidden) return;
  try {
    await refreshAccount(options);
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
  byId("downloadLink").hidden = true;
  byId("shareButton").hidden = true;
  delete byId("shareButton").dataset.artifactId;
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
  cancelCaptureCheck();
  releaseCapturePreview();
  state.reconstructionAllowance = null;
  state.accountRefresh = null;
  state.uploading = false;
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
  byId("managementJobList").replaceChildren();
  byId("emptyManagedJobs").hidden = false;
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
  byId("captureMessage").textContent = "";
  byId("video").removeAttribute("aria-invalid");
  byId("shareUrl").value = "";
  document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  renderRequestStatus();
  byId("emptyJobs").hidden = false;
  byId("emptyAssets").hidden = false;
  byId("emptyShares").hidden = false;
  byId("loadMoreJobs").hidden = true;
  byId("loadMoreManagedJobs").hidden = true;
  byId("loadMoreAssets").hidden = true;
  byId("loadMoreShares").hidden = true;
  updateSelectionSummary();
  clearDetail();
}

function showLogin() {
  secureReset();
  byId("appView").hidden = true;
  byId("mobileWorkspaceCta").hidden = true;
  renderPublicRoute();
}

function renderPublicRoute({ focus = false } = {}) {
  const route = location.hash;
  const account = route === "#signup" || route === "#signin";
  byId("loginView").hidden = account;
  byId("accountView").hidden = !account;
  document.body.dataset.surface = account ? "account" : "landing";
  byId("skipLink").href = account ? "#accountTitle" : "#loginTitle";
  renderSignInOptions();
  if (focus) {
    byId(account ? "accountTitle" : "loginTitle").focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }
}

function openAccount(mode) {
  if (!byId("appView").hidden) { openCreateScene(); return; }
  history.pushState(null, "", mode === "login" ? "#signin" : "#signup");
  renderPublicRoute({ focus: true });
}

function renderSignInOptions() {
  const returning = location.hash === "#signin";
  const config = state.config;
  const full = Boolean(config?.googleSignIn && !config.newAccountsAvailable);
  byId("accountTitle").textContent = returning ? "Welcome back." : full ? "The preview is full right now." : "Your own space starts here.";
  byId("accountDescription").textContent = returning ? "Your spaces are right where you left them."
    : full ? "We’re keeping the preview small while we improve reconstruction."
      : "Two videos to start. A new way to see it.";
  byId("accountSwitch").hidden = returning;
  byId("googleLogin").hidden = !config?.googleSignIn || (full && !returning);
  byId("googleLoginLabel").textContent = "Continue with Google";
  byId("trialButton").hidden = true;
  if (!config) return;
  byId("onboardingStatus").textContent = !config.googleSignIn
    ? "Google sign-in is not available on this installation yet."
    : full && !returning ? "Already have an account? Sign in below to open your spaces."
      : returning ? "Sign in securely with your Google account." : "A private workspace. Two videos to start. No card needed.";
}

function openCreateScene({ refresh = true } = {}) {
  if (byId("appView").hidden) { openAccount("signup"); return; }
  const dialog = byId("createDialog");
  openDialog(dialog);
  renderReconstructionStatus();
  if (refresh) refreshAccount({ fresh: true }).catch(report);
}

function showApp(user, csrfToken, allowance = null) {
  const principal = `${user.tenantName}\u0000${user.displayName}`;
  if (state.principal && state.principal !== principal) secureReset();
  state.principal = principal;
  state.csrf = csrfToken || "";
  state.accountType = user.accountType || "operator";
  state.reconstructionAllowance = allowance;
  byId("shareButton").hidden = state.accountType === "trial" || !byId("shareButton").dataset.artifactId;
  renderAccountActions();
  byId("loginView").hidden = true;
  byId("accountView").hidden = true;
  byId("appView").hidden = false;
  byId("mobileWorkspaceCta").hidden = true;
  document.body.dataset.surface = "workspace";
  byId("skipLink").href = "#workspaceMain";
  byId("workspaceName").textContent = `${user.tenantName} · ${user.displayName}`;
}

function renderAccountActions() {
  byId("saveWorkspace").hidden = state.accountType !== "trial" || !state.config?.googleSignIn;
  byId("saveWorkspace").textContent = state.config?.newAccountsAvailable
    ? "Sign in with Google" : "Returning Google sign-in";
  byId("researchForm").hidden = state.accountType === "trial";
  renderReconstructionStatus();
}

function toast(message) {
  const node = byId("toast");
  const dialog = activeDialog();
  (dialog || document.body).append(node);
  node.classList.toggle("dialog-toast", Boolean(dialog));
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
  byId("emptyTitle").textContent = state.jobs.length ? "Your spaces." : "Create your first scene.";
  byId("emptyDescription").textContent = state.jobs.length
    ? "Open a scene from your library, or start with a new capture."
    : "A short walkthrough becomes a space you can look around and return to.";
  state.jobs.forEach((job) => {
    const item = document.createElement("li");
    item.className = "job-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "job-button";
    button.setAttribute("aria-current", String(job.id === state.selectedId));
    const name = document.createElement("span");
    name.className = "job-name";
    name.textContent = job.displayName;
    const jobState = document.createElement("span");
    jobState.className = "job-state";
    jobState.textContent = job.state;
    const timestamp = document.createElement("span");
    timestamp.className = "job-time";
    timestamp.textContent = formatDate(job.createdAt);
    button.append(name, jobState, timestamp);
    button.addEventListener("click", () => selectJob(job.id).catch(report));
    item.append(button);
    list.append(item);
  });
  renderManagedJobs();
}

function renderManagedJobs() {
  const list = byId("managementJobList");
  list.replaceChildren();
  const jobs = state.jobs.filter((job) => terminalStates.has(job.state));
  byId("emptyManagedJobs").hidden = jobs.length > 0;
  jobs.forEach((job) => list.append(inventoryRow({
    id: job.id,
    name: job.displayName,
    meta: `${job.state} · ${formatDate(job.createdAt)}`,
    selected: state.selectedJobs.has(job.id),
    actionLabel: "Delete",
    onSelect: (checked) => {
      if (checked) state.selectedJobs.add(job.id); else state.selectedJobs.delete(job.id);
      updateSelectionSummary();
    },
    onAction: () => deleteJob(job.id),
  })));
}

async function loadJobs({ selectNewest = false, append = false, preserveLoaded = false } = {}) {
  const epoch = state.epoch;
  const activeResearch = new Set(state.jobs.filter((job) => job.engineId === "lingbot-research-v1"
    && !terminalStates.has(job.state)).map((job) => job.id));
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
  byId("loadMoreManagedJobs").hidden = !state.jobCursor;
  if (selectNewest && state.jobs.length) state.selectedId = state.jobs[0].id;
  if (state.selectedId && !state.jobs.some((job) => job.id === state.selectedId)) state.selectedId = null;
  const jobIds = new Set(state.jobs.map((job) => job.id));
  state.selectedJobs.forEach((id) => { if (!jobIds.has(id) && !append) state.selectedJobs.delete(id); });
  renderJobs();
  updateSelectionSummary();
  const unobservedCompletion = state.reconstructionAllowance?.state === "processing"
    && !state.jobs.some((job) => job.engineId === "lingbot-research-v1" && !terminalStates.has(job.state));
  if (state.accountType !== "trial" && (unobservedCompletion
      || result.jobs.some((job) => activeResearch.has(job.id) && terminalStates.has(job.state)))) {
    await revalidateSession({ fresh: true });
  }
  if (epoch !== state.epoch) return;
  if (state.selectedId) await renderJobDetail(); else clearDetail();
  if (epoch === state.epoch) schedulePoll();
}

function updateSelectionSummary() {
  const counts = [state.selectedJobs.size, state.selectedAssets.size, state.selectedShares.size];
  const total = counts.reduce((sum, value) => sum + value, 0);
  const labels = ["scene", "upload", "share"];
  const selected = counts.flatMap((count, index) => count
    ? [`${count} ${labels[index]}${count === 1 ? "" : "s"}`] : []);
  byId("selectionSummary").textContent = total
    ? `${selected.join(" · ")} selected`
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
  if (!await confirmAction("Delete this upload?", `“${asset.name}” will be permanently removed.`, "Delete upload")) return;
  try {
    await api(`/api/assets/${encodeURIComponent(asset.id)}`, { method: "DELETE", idempotent: true });
    state.selectedAssets.delete(asset.id);
    await loadAssets();
    toast("Upload deletion accepted.");
  } catch (error) { toast(error.message); }
}

async function revokeShare(share) {
  if (!await confirmAction("Revoke this link?", `The link to “${share.filename}” will stop working immediately.`, "Revoke link")) return;
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
  if (window.matchMedia("(max-width: 860px)").matches) byId("workspaceMain").scrollIntoView({ block: "start" });
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
  byId("detailEngine").textContent = job.engineId === "synthetic-sample-v1" ? "Synthetic sample" : "Research reconstruction";
  byId("detailTitle").textContent = job.displayName;
  byId("detailMeta").textContent = `Created ${formatDate(job.createdAt)}`;
  const percent = Math.round(job.progress * 100);
  document.querySelector(".progress-section").classList.toggle("is-ready", job.state === "ready");
  byId("progressSection").hidden = job.state === "ready";
  byId("progressPercent").textContent = `${percent}%`;
  byId("progressBar").value = percent;
  byId("progressBar").textContent = `${percent}%`;
  byId("progressTitle").textContent = job.state === "ready" ? "Complete" : job.stage.replaceAll("_", " ");
  updateStages(job);
  byId("cancelButton").hidden = terminalStates.has(job.state);
  byId("deleteButton").hidden = !terminalStates.has(job.state);
  byId("jobMessage").textContent = job.error?.message || (job.state === "cancelled" ? "Scene creation was cancelled." : "");
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
  byId("downloadLink").hidden = !scene;
  byId("shareButton").hidden = !scene || state.accountType === "trial";
  if (!scene) {
    delete byId("shareButton").dataset.artifactId;
    byId("downloadLink").removeAttribute("href");
  }
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

function renderReconstructionStatus() {
  const trial = state.accountType === "trial";
  const google = state.accountType === "google";
  const allowance = state.reconstructionAllowance;
  const allowed = !trial && (!google || allowance?.state === "available");
  const enabled = allowed && Boolean(state.engine?.available);
  const canChoose = enabled && Boolean(state.config) && !state.uploading;
  byId("video").disabled = !canChoose;
  byId("sampleButton").disabled = state.uploading;
  byId("sampleFps").disabled = !canChoose;
  byId("frameLimit").disabled = !canChoose;
  byId("capturePicker").classList.toggle("unavailable", !canChoose);
  byId("researchButton").disabled = !canChoose || !["valid", "fallback"].includes(state.captureCheck?.status);
  const titles = { available: `${allowance?.remaining ?? 2} of ${allowance?.limit ?? 2} videos remaining`, processing: "Reconstruction in progress",
    used: "Both videos used", retry_later: "Try again later" };
  const unavailableReason = state.engine?.unavailableReasons?.join(" ")
    || "Reconstruction availability could not be confirmed. Refresh to try again.";
  byId("researchStatus").textContent = trial ? "Synthetic playground"
    : google && !allowed ? (titles[allowance?.state] || "Checking your video allowance")
      : enabled ? (google ? titles.available : "Ready to reconstruct") : "Reconstruction unavailable";
  byId("researchStatus").classList.toggle("available", enabled);
  byId("researchReason").textContent = trial
    ? (state.config?.googleSignIn ? (state.config.newAccountsAvailable
      ? "Sign in with Google to reconstruct your own capture."
      : "New video accounts are currently full. Existing accounts can still sign in with Google.")
      : "This private, one-hour playground creates synthetic scenes. Video signup is still being connected.")
    : google && !allowed ? (allowance?.message || "Refresh your account to check availability before uploading.")
      : enabled ? (google ? allowance.message : "Your capture is processed privately. Research preview; no payment required.")
        : `${unavailableReason}${google && allowed ? " Your remaining videos will be available when capacity returns." : ""}`;
}

function cancelCaptureCheck() {
  state.captureCheck?.cancel?.();
  state.captureCheck = null;
}

function releaseCapturePreview() {
  const preview = byId("capturePreview");
  preview.pause();
  preview.removeAttribute("src");
  preview.load();
  if (state.capturePreviewUrl) URL.revokeObjectURL(state.capturePreviewUrl);
  state.capturePreviewUrl = null;
  byId("capturePreviewPanel").hidden = true;
  byId("capturePreviewMeta").textContent = "";
}

function showCapturePreview(file, duration) {
  releaseCapturePreview();
  try {
    state.capturePreviewUrl = URL.createObjectURL(file);
    byId("capturePreview").src = state.capturePreviewUrl;
    byId("capturePreviewMeta").textContent = `${file.name} · ${formatBytes(file.size)}${duration ? ` · ${duration.toFixed(1)} seconds` : ""}`;
    byId("capturePreviewPanel").hidden = false;
  } catch (_) { /* server validation remains available when local playback is unsupported */ }
}

function validateSelectedCapture() {
  cancelCaptureCheck();
  releaseCapturePreview();
  const file = byId("video").files[0];
  byId("selectedFilename").textContent = file ? file.name : "Choose a video";
  byId("video").removeAttribute("aria-invalid");
  byId("captureMessage").textContent = "";
  byId("researchMessage").textContent = "";
  if (!file) { renderReconstructionStatus(); return; }
  const check = { file, status: "checking", cancel: null };
  state.captureCheck = check;
  const epoch = state.epoch;
  const current = () => epoch === state.epoch && state.captureCheck === check;
  const display = (status, message) => {
    if (!current()) return;
    check.status = status;
    byId("captureMessage").textContent = message;
    byId("captureMessage").classList.toggle("invalid", status === "invalid");
    if (status === "invalid") byId("video").setAttribute("aria-invalid", "true");
    renderReconstructionStatus();
  };
  if (state.config && file.size > state.config.maxUploadBytes) {
    display("invalid", `Choose a video no larger than ${formatBytes(state.config.maxUploadBytes)}.`);
    return;
  }
  display("checking", "Checking clip length…");
  const video = document.createElement("video");
  let url = null, timer = null, finished = false;
  const finish = (duration, cancelled = false) => {
    if (finished) return;
    finished = true;
    window.clearTimeout(timer);
    video.onloadedmetadata = null;
    video.onerror = null;
    video.removeAttribute("src");
    video.load();
    if (url) URL.revokeObjectURL(url);
    if (cancelled || !current()) return;
    if (Number.isFinite(duration) && duration > 0) {
      if (state.config && duration > state.config.maxVideoSeconds) {
        display("invalid", `Choose a clip up to ${state.config.maxVideoSeconds} seconds. This clip is ${Math.ceil(duration)} seconds.`);
      } else {
        display("valid", `${formatBytes(file.size)} · ${duration.toFixed(1)} seconds · ready to upload`);
        showCapturePreview(file, duration);
      }
    } else {
      display("fallback", `${formatBytes(file.size)} · clip length will be checked after upload`);
      showCapturePreview(file, null);
    }
  };
  check.cancel = () => finish(null, true);
  video.preload = "metadata";
  video.onloadedmetadata = () => finish(video.duration);
  video.onerror = () => finish(null);
  timer = window.setTimeout(() => finish(null), 10000);
  try {
    url = URL.createObjectURL(file);
    video.src = url;
  } catch (_) { finish(null); }
}

async function initialize() {
  try {
    await refreshAccount();
    await Promise.all([loadJobs({ selectNewest: true }), loadInventory()]);
    if (state.accountType === "google" && !state.jobs.length) openCreateScene({ refresh: false });
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
    await Promise.all([refreshAccount(), loadJobs({ selectNewest: true }), loadInventory()]);
    byId("workspaceMain").focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  } catch (error) {
    byId("loginMessage").textContent = error.message;
    byId("token").setAttribute("aria-invalid", "true");
  } finally {
    button.disabled = false;
    button.textContent = "Continue";
  }
});

byId("logoutButton").addEventListener("click", async () => {
  const button = byId("logoutButton");
  if (button.disabled) return;
  button.disabled = true;
  button.textContent = "Signing out…";
  try {
    await api("/api/session", { method: "DELETE" });
    broadcastSession("signed-out");
    history.replaceState(null, "", location.pathname);
    showLogin();
  } catch (error) {
    if (!byId("appView").hidden) toast(`Sign out failed: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Sign out";
  }
});

byId("sampleButton").addEventListener("click", async () => {
  const button = byId("sampleButton"), epoch = state.epoch;
  if (state.uploading || button.disabled) return;
  state.uploading = true;
  renderReconstructionStatus();
  button.textContent = "Creating scene…";
  try {
    const job = await api("/api/jobs/sample", { method: "POST", idempotent: true });
    state.selectedId = job.id;
    await loadJobs();
    byId("createDialog").close();
    toast("Synthetic scene queued.");
  } catch (error) {
    toast(error.message);
  } finally {
    if (epoch === state.epoch) {
      state.uploading = false;
      button.textContent = "Create synthetic scene";
      renderReconstructionStatus();
    }
  }
});

byId("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.uploading || byId("researchButton").disabled) return;
  const file = byId("video").files[0];
  const selection = state.captureCheck, epoch = state.epoch;
  if (!file || selection?.file !== file) return;
  const assertCurrent = () => {
    if (epoch !== state.epoch || state.captureCheck !== selection) throw new DOMException("Capture changed", "AbortError");
  };
  const params = { extractFps: Number(byId("sampleFps").value), maxFrames: Number(byId("frameLimit").value) };
  let asset = null;
  state.uploading = true;
  renderReconstructionStatus();
  byId("researchMessage").textContent = "Checking your account before upload…";
  try {
    await refreshAccount({ fresh: true });
    assertCurrent();
    if (state.accountType === "google" && state.reconstructionAllowance?.state !== "available") {
      byId("researchMessage").textContent = state.reconstructionAllowance?.message || "Your video allowance could not be checked. Refresh to try again.";
      return;
    }
    if (state.accountType === "trial" || !state.engine?.available) {
      byId("researchMessage").textContent = "";
      return;
    }
    byId("researchMessage").textContent = "Uploading video…";
    const body = new FormData();
    body.append("file", file);
    asset = await api("/api/assets", { method: "POST", body, idempotent: true, timeoutMs: 15 * 60 * 1000 });
    assertCurrent();
    byId("researchMessage").textContent = "Video uploaded. Queuing reconstruction…";
    const job = await api("/api/jobs/research", {
      method: "POST",
      idempotent: true,
      json: {
        assetId: asset.id,
        ...params,
        rotate: false,
        maskSky: false,
        memoryGuard: true,
        mode: "streaming",
      },
    });
    assertCurrent();
    state.selectedId = job.id;
    asset = null;
    await Promise.all([refreshAccount({ fresh: true }), loadJobs(), loadAssets()]);
    assertCurrent();
    byId("researchMessage").textContent = "Reconstruction queued.";
    byId("createDialog").close();
    byId("video").value = "";
    byId("selectedFilename").textContent = "Choose a video";
    cancelCaptureCheck();
    releaseCapturePreview();
    byId("detailTitle").focus({ preventScroll: true });
  } catch (error) {
    if (epoch !== state.epoch || error?.name === "AbortError") return;
    if (asset) {
      try { await api(`/api/assets/${encodeURIComponent(asset.id)}`, { method: "DELETE", idempotent: true }); }
      catch (_) { /* a submitted job owns the asset or the server will reclaim it */ }
    }
    if (epoch === state.epoch) {
      toast(error.message);
      byId("researchMessage").textContent = error.message;
      await revalidateSession({ fresh: true });
    }
  } finally {
    if (epoch === state.epoch) {
      state.uploading = false;
      renderReconstructionStatus();
    }
  }
});

byId("refreshButton").addEventListener("click", () => Promise.all([loadJobs(), revalidateSession({ fresh: true })]).catch(report));
["loadMoreJobs", "loadMoreManagedJobs"].forEach((id) =>
  byId(id).addEventListener("click", () => loadJobs({ append: true }).catch(report)));
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
async function deleteJob(jobId) {
  if (!jobId || !await confirmAction("Delete this scene?", "Its source video, artifacts, and share links will also be removed. This cannot be undone.", "Delete scene")) return;
  try {
    await api(`/api/jobs/${encodeURIComponent(jobId)}`, { method: "DELETE", idempotent: true });
    state.jobs = state.jobs.filter((job) => job.id !== jobId);
    state.selectedJobs.delete(jobId);
    const deletedSelection = state.selectedId === jobId;
    if (deletedSelection) { state.selectedId = null; clearDetail(); }
    await Promise.all([loadJobs({ selectNewest: deletedSelection, preserveLoaded: true }), loadInventory()]);
    toast("Deletion accepted. Stored objects are being removed.");
  } catch (error) { toast(error.message); }
}
byId("deleteButton").addEventListener("click", () => deleteJob(state.selectedId));

byId("shareButton").addEventListener("click", async () => {
  const artifactId = byId("shareButton").dataset.artifactId;
  if (!artifactId) return;
  try {
    const result = await api(`/api/artifacts/${encodeURIComponent(artifactId)}/shares`, {
      method: "POST", json: { ttlSeconds: 86400 },
      idempotent: true,
    });
    byId("shareUrl").value = new URL(result.url, window.location.origin).href;
    openDialog(byId("shareDialog"));
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
  if (!total || !await confirmAction("Remove selected items?", `${total} selected item${total === 1 ? "" : "s"} will be permanently removed, including linked files and shares.`, "Remove selected")) return;
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
byId("video").addEventListener("change", validateSelectedCapture);
byId("trialButton").addEventListener("click", async () => {
  const button = byId("trialButton"); button.disabled = true;
  byId("trialMessage").textContent = "Opening your private playground…";
  try {
    const result = await api("/api/trial", { method: "POST" });
    showApp(result.user, result.csrfToken); broadcastSession("session-changed");
    await Promise.all([refreshAccount(), loadJobs(), loadInventory()]);
    byId("sampleButton").click();
    byId("workspaceMain").focus({ preventScroll: true });
  } catch (error) { byId("trialMessage").textContent = error.message; }
  finally { button.disabled = false; }
});
async function loadPublicConfig() {
  const messages = { cancelled: "Google sign-in was cancelled. You can try again.",
    capacity: "New video accounts are currently full. Existing accounts can still sign in.",
    failed: "Google sign-in did not finish. Please try again.",
    expired: "Your sign-in expired. Please start again." };
  const signin = new URLSearchParams(location.search).get("signin");
  if (Object.hasOwn(messages, signin)) {
    byId("signinNotice").textContent = messages[signin];
    byId("signinNotice").hidden = false;
    history.replaceState(null, "", `${location.pathname}#signin`);
  }
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("Sign-in options could not be loaded. Refresh to retry.");
    state.config = await response.json();
    renderAccountActions();
    byId("captureLimits").textContent = `Up to ${state.config.maxVideoSeconds} seconds · ${formatBytes(state.config.maxUploadBytes)} maximum`;
    if (byId("video").files[0] && !state.uploading) validateSelectedCapture();
    renderSignInOptions();
  } catch (error) { byId("onboardingStatus").textContent = error.message; }
}

function confirmAction(title, message, label) {
  const dialog = byId("confirmDialog");
  if (dialog.open) return Promise.resolve(false);
  const epoch = state.epoch;
  byId("confirmTitle").textContent = title;
  byId("confirmMessage").textContent = message;
  byId("confirmAccept").textContent = label;
  dialog.returnValue = "";
  openDialog(dialog);
  byId("confirmCancel").focus();
  return new Promise((resolve) => dialog.addEventListener("close", () => {
    resolve(dialog.returnValue === "confirm" && epoch === state.epoch);
  }, { once: true }));
}

byId("confirmAccept").addEventListener("click", () => byId("confirmDialog").close("confirm"));
byId("confirmCancel").addEventListener("click", () => byId("confirmDialog").close("cancel"));
byId("createDialog").addEventListener("cancel", (event) => {
  if (state.uploading) { event.preventDefault(); toast("Your scene is being submitted. Wait for it to finish before closing."); }
});
byId("createDialog").addEventListener("close", () => byId("capturePreview").pause());
["createDialog", "managementDialog", "shareDialog", "confirmDialog"].forEach((id) => {
  const dialog = byId(id);
  dialog.addEventListener("close", () => {
    if (!dialog.open) dialogOrder.delete(dialog);
    renderRequestStatus();
  });
});
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-account-entry], [data-public-home], [data-workspace-home], [data-create-scene], [data-manage-workspace], [data-dialog-close]");
  if (!target) return;
  event.preventDefault();
  if (target.hasAttribute("data-account-entry")) openAccount(target.dataset.accountEntry);
  else if (target.hasAttribute("data-public-home")) {
    history.pushState(null, "", location.pathname);
    renderPublicRoute({ focus: true });
  } else if (target.hasAttribute("data-workspace-home")) {
    state.selectedId = null;
    clearDetail();
    renderJobs();
    byId("workspaceMain").focus({ preventScroll: true });
  } else if (target.hasAttribute("data-create-scene")) openCreateScene();
  else if (target.hasAttribute("data-manage-workspace")) {
    openDialog(byId("managementDialog"));
    Promise.all([loadInventory(), loadJobs({ preserveLoaded: true })]).catch(report);
  } else if (target.dataset.dialogClose === "createDialog" && state.uploading) {
    toast("Your scene is being submitted. Wait for it to finish before closing.");
  } else byId(target.dataset.dialogClose).close();
});
byId("skipLink").addEventListener("click", (event) => {
  event.preventDefault();
  const target = byId(!byId("appView").hidden ? "workspaceMain"
    : !byId("accountView").hidden ? "accountTitle" : "loginTitle");
  target.focus();
});
window.addEventListener("popstate", () => { if (byId("appView").hidden) renderPublicRoute({ focus: true }); });
window.addEventListener("hashchange", () => { if (byId("appView").hidden) renderPublicRoute(); });
window.addEventListener("pagehide", () => { releaseCapturePreview(); cancelCaptureCheck(); });
window.addEventListener("pageshow", (event) => {
  if (event.persisted && byId("video").files[0] && !state.uploading) validateSelectedCapture();
});
loadPublicConfig();
initialize();
