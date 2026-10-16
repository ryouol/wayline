"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../lingbot_map/workspace/static/app.js"), "utf8");
const markup = fs.readFileSync(require.resolve("../lingbot_map/workspace/static/index.html"), "utf8");
const documentOrder = new Map([...markup.matchAll(/\bid="([^"]+)"/g)].map((match, index) => [match[1], index]));
const user = { tenantName: "Private space", displayName: "Visitor", accountType: "google" };
const allowance = (state, remaining = state === "used" ? 0 : 2) => ({ state, remaining, limit: 2, message: `Allowance: ${state}` });
const account = (state) => ({ user, csrfToken: "csrf", reconstructionAllowance: allowance(state) });
const capacityMessage = "Reconstruction is temporarily paused because preview capacity is full. Please try again later.";
const engines = (available = true) => ({ engines: [{ id: "lingbot-research-v1", available,
  unavailableReasons: available ? [] : [capacityMessage] }] });
const config = { googleSignIn: true, newAccountsAvailable: true, trialEnabled: true,
  maxVideoSeconds: 30, maxUploadBytes: 10 * 1024 * 1024 };
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};

function harness(search = "") {
  const nodes = new Map(), timers = new Map(), windowEvents = new Map(), documentEvents = new Map();
  const videos = [], createdUrls = [], revokedUrls = [], requests = [];
  const historyEntries = [], scrolls = [], submissionTimings = [];
  let clock = 0;
  let timerId = 0;
  function element() {
    const classes = new Set(), attributes = new Map(), events = new Map();
    const listeners = new Map();
    let value = "";
    return {
      hidden: false, disabled: false, textContent: "", files: [], dataset: {}, style: {}, children: [], events,
      dispatchEvent(event) { if (event.type === "wayline-submission-timing") submissionTimings.push(event.detail); },
      open: false, returnValue: "", pauseCount: 0, focusCount: 0,
      get value() { return value; },
      set value(next) { value = next; if (next === "") this.files = []; },
      get src() { return attributes.get("src") || ""; },
      set src(next) { attributes.set("src", next); },
      get href() { return attributes.get("href") || ""; },
      set href(next) { attributes.set("href", next); },
      classList: { toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }, contains: (name) => classes.has(name) },
      setAttribute(name, next) {
        attributes.set(name, next);
        if (name.startsWith("data-")) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = next;
      },
      removeAttribute: (name) => attributes.delete(name),
      getAttribute: (name) => attributes.get(name),
      hasAttribute(name) { return attributes.has(name) || (name.startsWith("data-") &&
        Object.hasOwn(this.dataset, name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()))); },
      closest(selector) { return selector.split(",").some((part) => this.hasAttribute(part.trim().slice(1, -1))) ? this : null; },
      addEventListener(name, callback, options = {}) {
        if (!listeners.has(name)) {
          listeners.set(name, []);
          events.set(name, (event = {}) => {
            let result;
            for (const listener of [...listeners.get(name)]) {
              if (listener.once) listeners.get(name).splice(listeners.get(name).indexOf(listener), 1);
              result = listener.callback(event);
            }
            return result;
          });
        }
        listeners.get(name).push({ callback, once: options.once });
      },
      append(...children) {
        for (const child of children) {
          if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
          child.parentNode = this;
          this.children.push(child);
        }
      },
      prepend(child) {
        this.append(child);
        this.children.unshift(this.children.pop());
      },
      replaceChildren(...children) {
        for (const child of this.children) child.parentNode = null;
        this.children = [];
        this.append(...children);
      },
      querySelectorAll: () => [], focus() { this.focusCount++; }, load() {},
      pause() { this.pauseCount++; },
      showModal() { assert.equal(this.open, false, "do not reopen an open native dialog"); this.open = true; },
      close(returnValue) {
        if (!this.open) return;
        this.open = false;
        if (returnValue !== undefined) this.returnValue = returnValue;
        queueMicrotask(() => events.get("close")?.());
      },
    };
  }
  const node = (id) => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  const setTimeout = (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; };
  const clearTimeout = (id) => timers.delete(id);
  class TestURL extends URL {
    static createObjectURL(file) { const url = `blob:test-${createdUrls.length}`; createdUrls.push({ file, url }); return url; }
    static revokeObjectURL(url) { revokedUrls.push(url); }
  }
  const location = new URL(`https://example.test/${search}`);
  location.reload = () => {};
  const history = Object.fromEntries(["pushState", "replaceState"].map((method) => [method,
    (_state, _unused, next) => {
      location.href = new URL(next, location).href;
      historyEntries.push({ method, url: location.href });
    }]));
  const context = vm.createContext({
    URL: TestURL, URLSearchParams, Headers, AbortController, DOMException, Date,
    performance: { now: () => clock },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    crypto: { randomUUID: () => "request-id" }, location, history, setTimeout, clearTimeout,
    localStorage: { setItem() {}, removeItem() {} },
    FormData: class { append() {} },
    window: { location, setTimeout, clearTimeout, addEventListener: (name, callback) => windowEvents.set(name, callback),
      scrollTo: (options) => scrolls.push(options),
      SceneTimeline: class { attach() {} stop() {} wholeSpace() {} },
      WorkspaceSessionEvents: { dispatch() {} } },
    document: { visibilityState: "visible", getElementById: node, body: element(), addEventListener: (name, callback) => documentEvents.set(name, callback),
      querySelectorAll(selector) {
        assert.equal(selector, "dialog[open]");
        return [...nodes].filter(([id, target]) => id.endsWith("Dialog") && target.open)
          .sort(([left], [right]) => documentOrder.get(left) - documentOrder.get(right))
          .map(([, target]) => target);
      },
      querySelector: node, createElement(tag) { const created = element(); if (tag === "video") videos.push(created); return created; } },
    fetch: async (path, options = {}) => {
      requests.push({ path, method: options.method || "GET", options });
      const result = await (path === "/api/engines" ? context.engineResponse() : context.respond(path, options));
      if (result instanceof Response) return result;
      return { ok: true, status: 200, headers: new Headers(), json: async () => result };
    },
    engineResponse: async () => engines(),
    respond: async (path) => {
      if (path === "/api/me") return account("available");
      if (path === "/api/config") return { ...config };
      throw new Error(`Unexpected request: ${path}`);
    },
  });
  vm.runInContext(`${source.slice(0, source.lastIndexOf("\nloadPublicConfig();"))}\nglobalThis.appState = state;`, context);
  // Keep real account, form, polling, and inventory behavior; scene rendering has its own suite.
  const renderRealJobDetail = context.renderJobDetail;
  context.renderJobDetail = async () => {};
  const state = context.appState;
  state.config = { ...config };
  state.engine = { available: true };
  context.showApp(user, "csrf", allowance("available"));
  node("signinNotice").hidden = true;
  node("sampleFps").value = "1";
  node("frameLimit").value = "12";
  function select(file = { name: "room.mp4", size: 1024 }) {
    node("video").files = [file];
    node("video").events.get("change")();
    return videos.at(-1);
  }
  const submit = () => node("researchForm").events.get("submit")({ preventDefault() {} });
  const click = (dataset) => {
    const target = element();
    Object.assign(target.dataset, dataset);
    return documentEvents.get("click")({ target, preventDefault() {} });
  };
  return { context, state, node, select, submit, click, videos, createdUrls, revokedUrls, timers,
    requests, windowEvents, documentEvents, historyEntries, scrolls, renderRealJobDetail, submissionTimings,
    advance: (milliseconds) => { clock += milliseconds; } };
}

async function main() {
  for (const [sent, received] of [['W/"same"', '"same"'], ['"same"', 'W/"same"']]) {
    const h = harness(), value = { id: "same-scene" };
    h.context.respond = async () => new Response(null, { status: 304, headers: { ETag: received } });
    assert.equal(await h.context.api("/api/jobs/same-scene", { conditional: { etag: sent, value } }), value,
      "GET validation compares opaque tags independently of a proxy's weak prefix");
  }
  {
    const h = harness();
    const scene = { id: "scene", kind: "scene", filename: "scene.glb", sizeBytes: 100,
      metadata: {}, viewUrl: "/scene", downloadUrl: "/download" };
    let job = { id: "validated", state: "ready", stage: "ready", displayName: "Studio",
      provenance: {}, createdAt: 100, expiresAt: Date.now() / 1000 + 100, artifacts: [scene] };
    let etag = 'W/"first"', loads = 0, destroyed = 0, unchanged = 0;
    h.context.window.PointCloudViewer = class {
      async load() { loads++; if (loads === 1) throw new Error("Temporary artifact failure"); }
      destroy() { destroyed++; }
    };
    h.context.renderTimeline = () => {};
    h.state.selectedId = job.id;
    h.context.respond = async (_path, options) => {
      if (options.headers.get("If-None-Match") === etag) {
        unchanged++;
        return new Response(null, { status: 304, headers: { ETag: etag.replace(/^W\//, "") } });
      }
      return new Response(JSON.stringify(job), { headers: { ETag: etag } });
    };
    await h.renderRealJobDetail();
    await h.renderRealJobDetail({ background: true });
    assert.equal(unchanged, 1, "A ready scene is revalidated without retransferring its details");
    assert.equal(loads, 2, "An unchanged detail still retries an unsuccessful viewer load");
    assert.equal(h.node("downloadLink").href, "/download");
    assert.equal(h.node("requestStatus").hidden, true);
    h.context.Date = class extends Date { static now() { return (job.expiresAt + 1) * 1000; } };
    await h.renderRealJobDetail({ background: true });
    assert.equal(unchanged, 2);
    assert.match(h.node("detailMeta").textContent, /Removal due/, "Time-based labels advance even on 304");
    job = { ...job, expiresAt: 100 };
    etag = '"deadline-changed"';
    await h.renderRealJobDetail({ background: true });
    assert.match(h.node("detailMeta").textContent, /Removal due/);
    job = { ...job, artifacts: [] };
    etag = '"artifacts-removed"';
    await h.renderRealJobDetail({ background: true });
    assert.equal(h.node("viewerSection").hidden, true);
    assert.equal(h.node("downloadLink").href, "");
    assert.equal(destroyed, 1);
    await h.renderRealJobDetail();
    assert.equal(h.requests.at(-1).options.headers.has("If-None-Match"), false, "Direct refresh fetches full details");
    h.context.secureReset();
    assert.equal(h.state.detailCache, null);
  }
  for (const changed of ["selection", "session", "principal"]) {
    const h = harness(), pending = deferred();
    const job = { id: "private", state: "ready", stage: "ready", displayName: "Private",
      provenance: {}, createdAt: 100, artifacts: [] };
    h.state.selectedId = job.id;
    h.context.respond = async () => new Response(JSON.stringify(job), { headers: { ETag: '"private"', "X-Workspace-Principal": "old" } });
    await h.renderRealJobDetail();
    h.context.respond = async () => pending.promise;
    const refresh = h.renderRealJobDetail({ background: true });
    if (changed === "selection") {
      h.state.selectedId = "another";
      h.node("detailTitle").textContent = "Another scene";
    }
    if (changed === "session") h.context.secureReset();
    pending.resolve(new Response(null, { status: 304, headers: { ETag: '"private"',
      "X-Workspace-Principal": changed === "principal" ? "new" : "old" } }));
    await refresh;
    if (changed !== "selection") {
      assert.equal(h.state.detailCache, null);
      assert.equal(h.node("jobDetail").hidden, true);
    } else {
      assert.equal(h.state.selectedId, "another");
      assert.equal(h.node("detailTitle").textContent, "Another scene");
    }
  }
  {
    const h = harness();
    const snapshot = { etag: '"old"', value: { private: true } };
    h.context.respond = async () => new Response(null, { status: 304, headers: { ETag: '"different"' } });
    await assert.rejects(h.context.api("/api/jobs/private", { conditional: snapshot }), /Request failed \(304\)/);
    await assert.rejects(h.context.api("/api/jobs/private"), /Request failed \(304\)/);
    h.context.respond = async () => new Response(null, { status: 401 });
    await assert.rejects(h.context.api("/api/jobs/private", { conditional: snapshot }), /session ended/);
    assert.equal(h.state.detailCache, null);
  }
  {
    const h = harness();
    const job = id => ({ id, state: "ready", displayName: id });
    const newest = job("new"), older = job("older"), gone = job("gone");
    h.state.jobs = [older, gone];
    h.state.selectedJobs = new Set([older.id, gone.id]);
    h.state.jobCursor = "older-page";
    let checked;
    h.context.respond = async path => {
      const query = new URL(path, "https://example.test").searchParams;
      checked = query.getAll("knownId");
      return { jobs: [newest], nextCursor: "first-page", missingIds: [gone.id] };
    };
    await h.context.pollJobs();
    assert.deepEqual(Array.from(h.state.jobs, item => item.id), [newest.id, older.id]);
    assert.deepEqual(checked, [older.id, gone.id]);
    assert.deepEqual(Array.from(h.state.selectedJobs), [older.id]);
    assert.equal(h.state.jobCursor, "older-page");
    assert.equal(h.node("selectionSummary").textContent, "1 scene selected");
    assert.equal(h.requests.length, 1, "Presence checks ride on the existing list request");
    assert.equal(h.node("toast").textContent, "", "Unselected removals stay quiet");
  }
  {
    const h = harness(), checked = [];
    const jobs = Array.from({ length: 250 }, (_, index) => ({ id: `scene-${index}`, state: "ready" }));
    h.state.jobs = jobs;
    h.context.respond = async path => {
      const ids = new URL(path, "https://example.test").searchParams.getAll("knownId");
      assert.ok(ids.length <= 100 && ids.length > 0);
      checked.push(...ids);
      return { jobs: jobs.slice(0, 25), nextCursor: "more", missingIds: [] };
    };
    for (let poll = 0; poll < 3; poll++) await h.context.pollJobs();
    assert.equal(new Set(checked).size, 250, "Larger libraries rotate through every loaded row");
    assert.equal(checked.length, 250);
    const offset = h.state.jobCheckOffset;
    h.context.respond = async () => { throw new Error("Connection lost."); };
    await h.context.pollJobs();
    assert.equal(h.state.jobCheckOffset, offset, "Failed polls do not skip a batch");
    assert.equal(h.state.jobs.length, 250);
    h.context.secureReset();
    assert.equal(h.state.jobCheckOffset, 0);
  }
  {
    const h = harness(), pending = deferred();
    const job = { id: "selected-during-refresh", state: "ready", displayName: "Scene" };
    h.state.jobs = [job];
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = async path => path.startsWith("/api/jobs?") ? pending.promise
      : new Response(JSON.stringify({ detail: "Job not found." }), { status: 404 });
    const polling = h.context.pollJobs();
    h.state.selectedId = job.id;
    pending.resolve({ jobs: [], nextCursor: null, missingIds: [job.id] });
    await polling;
    assert.equal(h.requests.length, 2, "A newly selected missing row still uses detail confirmation");
    assert.equal(h.state.selectedId, null);
    assert.equal(h.state.jobs.length, 0);
    assert.match(h.node("toast").textContent, /no longer available/);
  }
  {
    const h = harness();
    const job = { id: "expired", displayName: "Old scene", engineId: "synthetic-sample-v1",
      state: "ready", stage: "ready", progress: 1, provenance: {}, createdAt: 100 };
    const other = { ...job, id: "other", displayName: "Other scene" };
    const artifact = { id: "artifact", kind: "scene", filename: "scene.glb", sizeBytes: 100,
      viewUrl: "/scene", downloadUrl: "/download", metadata: {} };
    let missing = false, destroyed = 0, exits = 0;
    h.context.window.PointCloudViewer = class {
      async load() {}
      destroy() { destroyed++; }
    };
    h.context.document.exitFullscreen = async () => { exits++; };
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.state.jobs = [job, other];
    h.state.selectedId = job.id;
    h.state.selectedJobs = new Set([job.id, other.id]);
    h.state.jobCursor = "older-page";
    h.context.respond = async (path) => {
      if (path.startsWith("/api/jobs?")) return { jobs: [other], nextCursor: "fresh-page" };
      assert.equal(path, "/api/jobs/expired");
      return missing ? new Response(JSON.stringify({ detail: "Job not found." }), { status: 404 })
        : { ...job, artifacts: [artifact] };
    };
    await h.renderRealJobDetail();
    h.context.document.fullscreenElement = h.node("viewerSection");
    missing = true;
    await h.context.pollJobs();
    assert.equal(h.state.selectedId, null, "A confirmed missing scene is no longer selected");
    assert.deepEqual(Array.from(h.state.jobs, item => item.id), [other.id]);
    assert.deepEqual(Array.from(h.state.selectedJobs), [other.id], "Only the missing bulk selection is removed");
    assert.equal(h.state.jobCursor, "older-page", "Older-page navigation remains intact");
    assert.equal(destroyed, 1);
    assert.equal(exits, 1, "Unavailable scene leaves full screen");
    assert.equal(h.state.viewer, null);
    assert.equal(h.state.viewerArtifact, null);
    assert.equal(h.node("jobDetail").hidden, true);
    assert.equal(h.node("emptyDetail").hidden, false);
    assert.equal(h.node("downloadLink").href, "");
    assert.equal(h.node("shareButton").dataset.artifactId, undefined);
    assert.equal(h.node("selectionSummary").textContent, "1 scene selected");
    assert.equal(h.state.reconstructionAllowance.remaining, 2, "Removal does not change processing credits");
    assert.match(h.node("toast").textContent, /no longer available/);
    const noticeTimer = h.state.toastTimer, before = h.requests.length;
    await h.context.pollJobs();
    assert.equal(h.requests.length - before, 1, "Following polls no longer fetch missing details");
    assert.equal(h.state.toastTimer, noticeTimer, "The missing-scene notice is not repeated");
    assert.equal(h.node("emptyTitle").focusCount, 0, "Background removal does not steal focus");
  }
  for (const status of [403, 500]) {
    const h = harness();
    const job = { id: "existing", state: "ready", displayName: "Existing" };
    const viewer = { destroy() { assert.fail("A temporary failure must not discard the viewer"); } };
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.state.jobs = [job];
    h.state.selectedId = job.id;
    h.state.viewer = viewer;
    h.context.respond = async path => path.startsWith("/api/jobs?") ? { jobs: [job], nextCursor: null }
      : new Response(JSON.stringify({ detail: "Try again later." }), { status });
    await h.context.pollJobs();
    assert.equal(h.state.selectedId, job.id);
    assert.equal(h.state.jobs.length, 1);
    assert.equal(h.state.viewer, viewer);
    assert.equal(h.node("toast").textContent, "Try again later.");
    assert.equal(h.timers.get(h.state.pollTimer).delay, 5000);
  }
  for (const resetSession of [false, true]) {
    const h = harness(), pending = deferred();
    h.state.jobs = [{ id: "old", state: "ready" }];
    h.state.selectedId = "old";
    h.context.respond = () => pending.promise;
    const detail = h.renderRealJobDetail();
    if (resetSession) h.context.secureReset();
    const current = { id: resetSession ? "old" : "new", state: "ready" };
    const viewer = { destroy() { assert.fail("A late 404 cannot dispose a different scene"); } };
    h.state.selectedId = current.id;
    h.state.jobs = [current];
    h.state.viewer = viewer;
    pending.resolve(new Response(JSON.stringify({ detail: "Job not found." }), { status: 404 }));
    await detail;
    assert.equal(h.state.selectedId, current.id);
    assert.equal(h.state.jobs[0], current);
    assert.equal(h.state.viewer, viewer);
    assert.equal(h.node("toast").textContent, "", "Late errors do not report a stale selection");
  }
  {
    const h = harness();
    h.state.jobs = [{ id: "gone", state: "ready" }];
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = async () => new Response(JSON.stringify({ detail: "Job not found." }), { status: 404 });
    await h.context.selectJob("gone");
    assert.equal(h.state.selectedId, null);
    assert.equal(h.node("emptyTitle").focusCount, 1, "A failed direct selection focuses the visible empty state");
    assert.equal(h.node("detailTitle").focusCount, 0, "Do not focus a hidden scene heading");
    assert.match(markup.match(/<h1\b[^>]*\bid="emptyTitle"[^>]*>/)?.[0] || "", /tabindex="-1"/,
      "The visible recovery heading can receive keyboard focus");
  }
  {
    const h = harness();
    let job = { id: "processing", displayName: "Studio", engineId: "synthetic-sample-v1",
      state: "queued", stage: "queued", progress: 0, provenance: {}, createdAt: 100,
      expiresAt: null, usedUnits: 0, reservedUnits: 1 };
    h.state.selectedId = job.id;
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = async (path) => {
      assert.ok(path.startsWith("/api/jobs?"), "Non-ready polling needs only the fresh list response");
      return { jobs: [{ ...job }], nextCursor: null };
    };
    for (const update of [
      {}, { state: "running", stage: "generating", progress: 0.3 },
      { progress: 0.7 }, { cancellationRequested: true },
      { state: "cancelled", stage: "cancelled", expiresAt: 200 },
      { state: "failed", stage: "failed", error: { message: "Capture could not be processed." } },
    ]) {
      job = { ...job, ...update };
      const before = h.requests.length;
      await h.context.pollJobs();
      assert.equal(h.requests.length - before, 1, "Each non-ready refresh uses one request");
      assert.equal(h.node("progressBar").getAttribute("aria-valuenow"), String(job.progress * 100));
      assert.equal(h.node("cancelButton").hidden, ["cancelled", "failed"].includes(job.state));
      assert.equal(h.node("requestStatus").hidden, true);
      assert.equal(h.node("toast").textContent, "");
      if (job.cancellationRequested && job.state === "running") assert.equal(h.node("progressTitle").textContent, "Stopping safely");
      if (job.expiresAt) assert.match(h.node("detailMeta").textContent, /Removal due/);
    }
    assert.equal(h.node("jobMessage").textContent, "Capture could not be processed.");
  }
  {
    const h = harness();
    const job = { id: "selected", displayName: "Studio", engineId: "synthetic-sample-v1",
      state: "running", stage: "generating", progress: 0.3, provenance: {}, createdAt: 100,
      expiresAt: null, usedUnits: 0, reservedUnits: 1 };
    let rows = [job];
    h.state.jobs = rows;
    h.state.selectedId = job.id;
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = async (path) => path.startsWith("/api/jobs?")
      ? { jobs: rows, nextCursor: null } : { ...job, progress: 0.8, artifacts: [] };
    await h.context.loadJobs();
    assert.equal(h.requests.length, 2, "Manual refresh always fetches current selected details");
    assert.equal(h.node("progressBar").getAttribute("aria-valuenow"), "80");
    rows = [];
    await h.context.pollJobs();
    assert.equal(h.requests.length, 4, "An older selected scene outside the refreshed page still needs details");
    assert.equal(h.state.selectedId, job.id);
    h.context.respond = async (path) => {
      if (path.startsWith("/api/jobs?")) return { jobs: [], nextCursor: null };
      throw new Error("Job not found.");
    };
    await h.context.pollJobs();
    assert.equal(h.node("toast").textContent, "Job not found.", "A missing selected scene is revalidated, not reused from loaded pages");
  }
  {
    const h = harness();
    let job = { id: "transition", displayName: "Studio", engineId: "synthetic-sample-v1",
      state: "running", stage: "generating", progress: 0.3, provenance: {}, createdAt: 100,
      expiresAt: null, usedUnits: 0, reservedUnits: 1 };
    const scene = { id: "scene", kind: "scene", filename: "scene.glb", sizeBytes: 100, metadata: {},
      viewUrl: "/scene", downloadUrl: "/download" };
    let published = [scene], loads = 0, destroyed = 0;
    h.context.window.PointCloudViewer = class {
      async load() { loads++; }
      destroy() { destroyed++; }
    };
    h.context.renderTimeline = () => {};
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.state.selectedId = job.id;
    h.context.respond = async (path) => path.startsWith("/api/jobs?")
      ? { jobs: [job], nextCursor: null } : { ...job, artifacts: published };
    await h.context.pollJobs();
    assert.equal(h.requests.length, 1);
    job = { ...job, state: "ready", stage: "ready", progress: 1, expiresAt: 200 };
    await h.context.pollJobs();
    assert.equal(h.requests.length, 3, "Completion fetches newly published artifacts immediately");
    assert.equal(loads, 1);
    assert.equal(h.node("viewerSection").hidden, false);
    published = [];
    await h.context.pollJobs();
    assert.equal(h.requests.length, 5, "Ready details refresh even with an unchanged summary");
    assert.equal(h.node("viewerSection").hidden, true);
    assert.equal(destroyed, 1, "Artifact cleanup is reflected without a job-version change");
  }
  {
    const h = harness(), list = deferred();
    const previous = { id: "previous", state: "running" };
    const selected = { id: "selected", displayName: "Selected scene", state: "running",
      stage: "generating", progress: 0.6, provenance: {}, artifacts: [] };
    h.state.jobs = [previous, selected];
    h.state.selectedId = previous.id;
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = async (path) => {
      if (path.startsWith("/api/jobs?")) return list.promise;
      assert.equal(path, "/api/jobs/selected");
      return selected;
    };
    const polling = h.context.pollJobs();
    h.state.selectedId = selected.id;
    list.resolve({ jobs: [previous], nextCursor: null });
    await polling;
    assert.equal(h.node("detailTitle").textContent, "Selected scene", "Selection changes during a refresh never render another scene's summary");
  }
  for (const background of [true, false]) {
    const h = harness(), list = deferred(), detail = deferred();
    const job = { id: "processing", displayName: "Studio", engineId: "lingbot-research-v1",
      state: "ready", stage: "ready", progress: 1, provenance: {}, artifacts: [],
      usedUnits: 0, reservedUnits: 0 };
    h.state.jobs = [job];
    h.state.selectedId = job.id;
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.context.respond = (path) => path.startsWith("/api/jobs?") ? list.promise : detail.promise;
    const refresh = background ? h.context.pollJobs() : h.context.loadJobs();
    const assertFeedback = () => {
      assert.equal(h.node("requestStatus").hidden, background, "Only foreground scene reads show Working feedback");
      assert.equal(h.context.document.body.getAttribute("aria-busy"), String(!background));
    };
    assertFeedback();
    list.resolve({ jobs: [job], nextCursor: null });
    await new Promise(setImmediate);
    assert.equal(h.requests.at(-1).path, "/api/jobs/processing");
    assertFeedback();
    detail.resolve(job);
    await refresh;
    assert.equal(h.node("detailTitle").textContent, "Studio", "Quiet detail reads still render completed scenes");
    assert.equal(h.node("requestStatus").hidden, true);
    assert.equal(h.context.document.body.getAttribute("aria-busy"), "false");
    assert.equal(h.timers.get(h.state.pollTimer).delay, 5000);
  }
  for (const backgroundFinishesFirst of [true, false]) {
    const h = harness(), jobs = deferred(), accountResult = deferred();
    h.context.respond = (path) => path.startsWith("/api/jobs?") ? jobs.promise : accountResult.promise;
    const polling = h.context.pollJobs();
    const foreground = h.context.api("/api/me");
    assert.equal(h.node("requestStatus").hidden, false, "Foreground work remains visible alongside polling");
    const finishPoll = async () => { jobs.resolve({ jobs: [], nextCursor: null }); await polling; };
    const finishForeground = async () => { accountResult.resolve(account("available")); await foreground; };
    await (backgroundFinishesFirst ? finishPoll() : finishForeground());
    assert.equal(h.node("requestStatus").hidden, !backgroundFinishesFirst, "Only outstanding foreground work owns feedback");
    assert.equal(h.context.document.body.getAttribute("aria-busy"), String(backgroundFinishesFirst));
    await (backgroundFinishesFirst ? finishForeground() : finishPoll());
    assert.equal(h.node("requestStatus").hidden, true);
  }
  {
    const h = harness(), oldJobs = deferred(), newAccount = deferred();
    h.context.respond = () => oldJobs.promise;
    const polling = h.context.pollJobs();
    h.context.secureReset();
    assert.equal(h.requests[0].options.signal.aborted, true, "Quiet requests remain abortable on session reset");
    h.context.respond = () => newAccount.promise;
    const foreground = h.context.api("/api/me");
    oldJobs.resolve({ jobs: [{ id: "private", state: "ready" }], nextCursor: null });
    await polling;
    assert.equal(h.state.jobs.length, 0);
    assert.equal(h.node("requestStatus").hidden, false, "Late quiet cleanup cannot hide new foreground work");
    newAccount.resolve(account("available"));
    await foreground;
    assert.equal(h.node("requestStatus").hidden, true);
  }
  for (const jobState of ["running", "ready"]) {
    const h = harness();
    h.state.jobs = [{ id: "scene", state: jobState }];
    h.context.schedulePoll();
    const scheduled = h.timers.get(h.state.pollTimer);
    assert.equal(scheduled.delay, jobState === "running" ? 900 : 5000);
    h.context.document.visibilityState = "hidden";
    await h.documentEvents.get("visibilitychange")();
    assert.equal(h.state.pollTimer, null, "Hiding the workspace cancels its scheduled refresh");
    assert.equal(h.timers.size, 0);
    await scheduled.callback();
    assert.equal(h.requests.length, 0, "An already queued timer cannot start a hidden refresh");
    h.context.schedulePoll();
    assert.equal(h.timers.size, 0, "Hidden workspaces never schedule scene polling");
  }
  {
    const h = harness(), waiting = deferred();
    h.state.jobs = [{ id: "older", state: "ready" }];
    h.state.selectedId = "older";
    h.state.jobCursor = "older-page";
    h.context.respond = async (path) => path.startsWith("/api/jobs?") ? waiting.promise : account("available");
    h.context.document.visibilityState = "hidden";
    await h.documentEvents.get("visibilitychange")();
    h.context.document.visibilityState = "visible";
    const resumed = h.documentEvents.get("visibilitychange")();
    const repeated = h.documentEvents.get("visibilitychange")();
    assert.equal(h.requests.filter(r => r.path.startsWith("/api/jobs?")).length, 1,
      "Returning starts one immediate refresh, even across repeated visibility events");
    assert.equal(h.requests.filter(r => r.path === "/api/me").length, 1, "Session revalidation is retained");
    waiting.resolve({ jobs: [{ id: "new", state: "ready" }], nextCursor: "new-page" });
    await Promise.all([resumed, repeated]);
    assert.deepEqual(Array.from(h.state.jobs, job => job.id), ["new", "older"]);
    assert.equal(h.state.selectedId, "older", "Returning preserves the selected older scene");
    assert.equal(h.state.jobCursor, "older-page");
    assert.equal(h.timers.size, 1, "One polling timer remains after the refresh");
    assert.equal(h.timers.get(h.state.pollTimer).delay, 5000);
  }
  {
    const h = harness(), waiting = deferred();
    h.context.respond = async () => waiting.promise;
    h.context.schedulePoll();
    const timer = h.timers.get(h.state.pollTimer);
    h.timers.delete(h.state.pollTimer);
    const polling = timer.callback();
    h.context.document.visibilityState = "hidden";
    await h.documentEvents.get("visibilitychange")();
    waiting.resolve({ jobs: [], nextCursor: null });
    await polling;
    assert.equal(h.state.pollTimer, null, "A refresh that finishes hidden does not restart polling");
    assert.equal(h.timers.size, 0);
  }
  {
    const h = harness();
    let attempts = 0;
    h.state.jobs = [{ id: "active", state: "running" }];
    h.context.respond = async () => {
      if (++attempts === 1) throw new Error("Temporary network failure");
      return { jobs: [{ id: "active", state: "running" }], nextCursor: null };
    };
    h.context.schedulePoll();
    let timer = h.timers.get(h.state.pollTimer);
    h.timers.delete(h.state.pollTimer);
    await timer.callback();
    assert.equal(h.node("toast").textContent, "Temporary network failure", "Quiet polling still reports failures");
    assert.equal(h.timers.get(h.state.pollTimer).delay, 5000, "A failed refresh retries at a slower pace");
    timer = h.timers.get(h.state.pollTimer);
    h.timers.delete(h.state.pollTimer);
    await timer.callback();
    assert.equal(attempts, 2);
    assert.equal(h.timers.get(h.state.pollTimer).delay, 900, "Successful processing refresh restores the active cadence");
  }
  {
    const h = harness(), waiting = deferred();
    h.context.respond = async () => waiting.promise;
    h.context.schedulePoll();
    const timer = h.timers.get(h.state.pollTimer);
    h.timers.delete(h.state.pollTimer);
    const polling = timer.callback();
    h.context.renderJobDetail = h.renderRealJobDetail;
    h.state.selectedId = "private";
    h.context.showLogin();
    waiting.resolve({ jobs: [{ id: "private", state: "ready" }], nextCursor: null });
    await polling;
    assert.equal(h.state.jobs.length, 0, "A late polling response cannot restore signed-out private data");
    assert.equal(h.state.pollTimer, null);
    assert.equal(h.timers.size, 0);
    await h.documentEvents.get("visibilitychange")();
    assert.equal(h.requests.length, 1, "Returning to a signed-out page does not poll or revalidate");
  }
  {
    const h = harness(), oldResponse = deferred(), newResponse = deferred();
    h.context.respond = async () => oldResponse.promise;
    const oldPoll = h.context.pollJobs();
    h.context.secureReset();
    h.context.showApp(user, "new-csrf", allowance("available"));
    h.context.respond = async () => newResponse.promise;
    const newPoll = h.context.pollJobs();
    oldResponse.resolve({ jobs: [{ id: "old-private", state: "ready" }], nextCursor: null });
    await oldPoll;
    assert.equal(h.state.pollRefresh, newPoll, "Old cleanup cannot clear a new session's refresh");
    assert.equal(h.state.pollTimer, null);
    newResponse.resolve({ jobs: [{ id: "new-private", state: "ready" }], nextCursor: null });
    await newPoll;
    assert.deepEqual(Array.from(h.state.jobs, job => job.id), ["new-private"]);
    assert.equal(h.timers.size, 1);
  }
  {
    const h = harness(), section = h.node("viewerSection"), button = h.node("fullScreen");
    const doc = h.context.document;
    const changed = () => h.documentEvents.get("fullscreenchange")();
    section.hidden = false;
    let entries = 0, exits = 0;
    section.requestFullscreen = async () => { entries++; doc.fullscreenElement = section; changed(); };
    doc.exitFullscreen = async () => { exits++; doc.fullscreenElement = null; changed(); };
    await button.events.get("click")();
    assert.equal(entries, 1, "Fullscreen targets the complete viewer section, including its timeline");
    assert.equal(button.getAttribute("aria-label"), "Exit full screen");
    assert.equal(button.getAttribute("title"), "Exit full screen");
    assert.equal(h.node("fullScreenIcon").getAttribute("src"), "/static/icons/x.svg");
    await button.events.get("click")();
    assert.equal(exits, 1);
    assert.equal(button.getAttribute("aria-label"), "Full screen");
    assert.equal(h.node("fullScreenIcon").getAttribute("src"), "/static/icons/arrows-out.svg");
    assert.equal(button.focusCount, 1, "Exiting returns keyboard focus to the fullscreen control");
    await button.events.get("click")();
    doc.fullscreenElement = null;
    changed();
    assert.equal(button.getAttribute("aria-label"), "Full screen", "Browser Escape updates the control too");
    assert.equal(button.focusCount, 2);
    doc.fullscreenElement = {};
    changed();
    assert.equal(button.focusCount, 2, "Other fullscreen changes do not move viewer focus");
    await button.events.get("click")();
    assert.equal(entries, 3, "An unrelated fullscreen element is not mistaken for the viewer");
    h.context.clearDetail();
    assert.equal(doc.fullscreenElement, null, "Removing the selected scene exits fullscreen");
    assert.equal(button.focusCount, 2, "Clearing private content does not focus its hidden controls");
  }
  {
    const h = harness(), section = h.node("viewerSection"), button = h.node("fullScreen");
    section.hidden = false;
    await button.events.get("click")();
    assert.match(h.node("toast").textContent, /unavailable/, "Unsupported browsers get a useful message");
    section.requestFullscreen = async () => { throw new Error("User activation denied"); };
    await button.events.get("click")();
    assert.match(h.node("toast").textContent, /unavailable/, "Denied fullscreen requests leave the viewer usable");
  }
  {
    const h = harness(), section = h.node("viewerSection"), waiting = deferred();
    section.hidden = false;
    section.requestFullscreen = async () => {
      await waiting.promise;
      h.context.document.fullscreenElement = section;
      h.documentEvents.get("fullscreenchange")();
    };
    h.context.document.exitFullscreen = async () => {
      h.context.document.fullscreenElement = null;
      h.documentEvents.get("fullscreenchange")();
    };
    const entering = h.node("fullScreen").events.get("click")();
    h.context.secureReset();
    waiting.resolve();
    await entering;
    assert.equal(h.context.document.fullscreenElement, null, "Late entry cannot reopen a reset session in fullscreen");
    assert.equal(h.node("fullScreen").focusCount, 0);
  }
  for (const failRefresh of [false, true]) {
    const h = harness();
    let checks = 0;
    h.context.respond = async (path) => {
      if (path === "/api/me") {
        h.advance(++checks === 1 ? 2000 : 9000);
        if (failRefresh && checks === 2) throw new Error("Post-queue refresh failed");
        return account("available");
      }
      if (path === "/api/assets") { h.advance(5000); return { id: "private-upload" }; }
      if (path === "/api/jobs/research") { h.advance(3000); return { id: "private-job" }; }
      if (path.startsWith("/api/jobs?")) return { jobs: [], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      throw new Error(path);
    };
    h.select({ name: "private-location.mp4", size: 1024 }).onerror();
    await h.submit();
    assert.ok(h.state.submissionTiming, "The browser must expose the missing submission measurement");
    assert.deepEqual(JSON.parse(JSON.stringify(h.state.submissionTiming)), {
      preflightSeconds: 2, uploadRequestSeconds: 5, queueRequestSeconds: 3,
      totalSeconds: 10, outcome: "queued", endedAtStage: "queueRequest",
    }, "Submission timings separate preflight, upload and queue and exclude post-queue refreshes");
    assert.equal(h.submissionTimings.length, 1);
    assert.equal(h.state.submissionTiming.outcome, "queued", "A failed UI refresh cannot reclassify an acknowledged submission");
    assert.equal(h.submissionTimings[0], h.state.submissionTiming);
    assert.equal(Object.isFrozen(h.state.submissionTiming), true);
    assert.equal(h.requests.filter(request => request.method === "POST").length, 2, "Timing adds no telemetry requests");
    assert.doesNotMatch(JSON.stringify(h.state.submissionTiming), /private-|csrf|request-id/);
    h.context.secureReset();
    assert.equal(h.state.submissionTiming, null, "Sign-out clears local diagnostic state");
  }
  {
    const h = harness();
    h.context.respond = async () => { h.advance(2500); return account("used"); };
    h.select().onerror();
    await h.submit();
    assert.equal(h.state.submissionTiming.outcome, "blocked");
    assert.equal(h.state.submissionTiming.endedAtStage, "preflight");
    assert.equal(h.state.submissionTiming.preflightSeconds, 2.5);
    assert.equal(h.state.submissionTiming.uploadRequestSeconds, null, "An unattempted stage is unknown, not zero");
    assert.equal(h.state.submissionTiming.queueRequestSeconds, null);
  }
  for (const failure of ["uploadRequest", "queueRequest"]) {
    const h = harness(), fetch = h.context.fetch;
    let checks = 0;
    h.context.respond = async (path) => {
      if (path === "/api/me") { h.advance(++checks === 1 ? 1000 : 9000); return account("available"); }
      if (path === "/api/assets") { h.advance(4000); return { id: "private-upload" }; }
      if (path === "/api/assets/private-upload") { h.advance(7000); return null; }
      throw new Error(path);
    };
    h.context.fetch = async (path, options) => {
      const target = failure === "uploadRequest" ? "/api/assets" : "/api/jobs/research";
      if (path !== target) return fetch(path, options);
      h.advance(failure === "uploadRequest" ? 4000 : 3000);
      return { ok: false, status: 503, headers: new Headers(), json: async () => ({ detail: "Private error details" }) };
    };
    h.select().onerror();
    await h.submit();
    const timing = h.state.submissionTiming;
    assert.equal(timing.outcome, "failed");
    assert.equal(timing.endedAtStage, failure);
    assert.equal(timing.uploadRequestSeconds, 4);
    assert.equal(timing.queueRequestSeconds, failure === "uploadRequest" ? null : 3);
    assert.equal(timing.totalSeconds, failure === "uploadRequest" ? 5 : 8, "Cleanup and recovery requests are outside the measured submission");
    assert.equal(h.submissionTimings.length, 1);
    assert.doesNotMatch(JSON.stringify(timing), /private|Private/);
  }
  {
    const h = harness(), upload = deferred();
    h.context.respond = async (path) => path === "/api/me" ? account("available") : upload.promise;
    h.select().onerror();
    const submitting = h.submit();
    await new Promise(setImmediate);
    h.context.secureReset();
    h.state.submissionTiming = { outcome: "new-session" };
    h.advance(5000);
    upload.resolve({ id: "old-private-upload" });
    await submitting;
    assert.equal(h.state.submissionTiming.outcome, "new-session", "A late old upload cannot overwrite the current account's diagnostics");
    assert.equal(h.submissionTimings.length, 0, "Stale sessions publish no diagnostic event");
  }
  {
    const h = harness(), fetch = h.context.fetch;
    let attempts = 0;
    h.context.respond = async (path) => {
      if (path === "/api/me") return account("available");
      if (path === "/api/assets") { h.advance(1000); return { id: "upload" }; }
      if (path === "/api/jobs/research") return { id: "job" };
      if (path.startsWith("/api/jobs?")) return { jobs: [], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      throw new Error(path);
    };
    h.context.fetch = async (path, options) => {
      if (path === "/api/assets" && ++attempts === 1) { h.advance(2000); throw new Error("Connection interrupted"); }
      return fetch(path, options);
    };
    h.select().onerror();
    const submitting = h.submit();
    await new Promise(setImmediate);
    const retry = [...h.timers.values()].find(timer => timer.delay === 250);
    assert.ok(retry);
    h.advance(250);
    retry.callback();
    await submitting;
    assert.equal(attempts, 2);
    assert.equal(h.state.submissionTiming.uploadRequestSeconds, 3.25, "Upload timing includes existing transport retry and backoff");
    assert.equal(h.submissionTimings.length, 1, "A transport retry still produces one submission receipt");
  }
  {
    const h = harness();
    const retention = { terminalJobSeconds: 7 * 86400, unattachedUploadSeconds: 3600, workspaceExpiresAt: null };
    h.context.respond = async () => ({ ...account("available"), retention });
    await h.context.refreshAccount();
    assert.match(h.node("creationRetention").textContent, /7 days after processing finishes/);
    assert.match(h.node("creationRetention").textContent, /does not restore video processing credits/);
    assert.match(h.node("managementRetention").textContent, /Unused uploads are removed after 1 hour/);
    const expiry = Date.now() / 1000 + 600;
    h.context.showApp({ ...user, accountType: "trial" }, "csrf", null, { ...retention, workspaceExpiresAt: expiry });
    assert.match(h.node("creationRetention").textContent, /This playground and its scenes expire/);
    assert.ok(h.node("creationRetention").textContent.includes(h.context.formatDate(expiry)));
    assert.doesNotMatch(h.node("creationRetention").textContent, /7 days|credits/);
    h.context.showApp(user, "csrf", allowance("available"), retention);
    assert.doesNotMatch(h.node("creationRetention").textContent, /This playground/);
    const job = { id: "expiry-test", displayName: "Test scene", engineId: "synthetic-sample-v1", state: "ready",
      expiresAt: expiry, createdAt: expiry - 86400, stage: "ready", progress: 1, provenance: {}, artifacts: [],
      usedUnits: 0, reservedUnits: 0 };
    h.state.jobs = [job];
    h.state.selectedId = job.id;
    h.context.renderJobs();
    assert.ok(h.node("jobList").children[0].children[0].children[2].textContent.includes(h.context.formatDate(expiry)));
    assert.ok(h.node("managementJobList").children[0].children[1].children[1].textContent.includes(h.context.formatDate(expiry)));
    h.context.respond = async () => job;
    await h.renderRealJobDetail();
    assert.ok(h.node("detailMeta").textContent.includes(`Expires ${h.context.formatDate(expiry)}`));
    assert.match(h.context.expiryLabel({ expiresAt: 100 }), /^Removal due /);
    assert.equal(h.context.expiryLabel({ expiresAt: null }), "");
  }
  {
    const h = harness();
    const steps = Array.from({ length: 5 }, (_, i) => h.node(`step-${i}`));
    h.node("stageList").querySelectorAll = () => steps;
    let job = { id: "processing-a", displayName: "Studio", engineId: "lingbot-research-v1",
      state: "running", stage: "reconstructing", progress: 0.3, provenance: {}, artifacts: [],
      usedUnits: 0, reservedUnits: 0 };
    h.state.selectedId = job.id;
    h.context.respond = async () => job;
    await h.renderRealJobDetail();
    assert.equal(h.node("progressTitle").textContent, "Building your space");
    assert.equal(h.node("progressBar").getAttribute("aria-valuenow"), "30");
    assert.equal(h.node("progressFill").style.transform, "scaleX(0.3)");
    assert.equal(h.node("progressFill").style.transition, "none", "first render does not animate from another scene");
    assert.equal(steps[2].getAttribute("aria-current"), "step");
    assert.equal(steps[1].classList.contains("complete"), true);
    job = { ...job, stage: "storing", progress: 0.92 };
    await h.renderRealJobDetail();
    assert.equal(h.node("progressTitle").textContent, "Saving your scene");
    assert.equal(h.node("progressFill").style.transform, "scaleX(0.92)");
    assert.equal(h.node("progressFill").style.transition, "", "same-job updates use the CSS transition");
    assert.equal(steps[3].getAttribute("aria-current"), "step", "storing stays in the finishing step");
    assert.equal(steps[2].getAttribute("aria-current"), undefined);
    let mutations = 0;
    for (const node of [h.node("progressSection"), h.node("progressBar"), ...steps]) {
      const original = node.setAttribute;
      node.setAttribute = function (...args) { mutations++; return original.apply(this, args); };
    }
    await h.renderRealJobDetail();
    assert.equal(mutations, 0, "unchanged polling does not rewrite progress accessibility attributes");
    for (const [stage, expectedStep] of [["queued", 0], ["validating", 1], ["uploading_to_gpu", 1], ["generating", 2], ["exporting", 3]]) {
      job = { ...job, stage, state: stage === "queued" ? "queued" : "running" };
      await h.renderRealJobDetail();
      assert.equal(steps[expectedStep].getAttribute("aria-current"), "step", stage);
    }
    job = { ...job, state: "running", stage: "reconstructing", cancellationRequested: true };
    await h.renderRealJobDetail();
    assert.equal(h.node("progressTitle").textContent, "Stopping safely", "late worker stage updates cannot hide pending cancellation");
    assert.equal(steps.some((step) => step.hasAttribute("aria-current")), false);
    for (const [state, title] of [["failed", "We couldn't finish this scene"], ["cancelled", "Scene creation cancelled"]]) {
      job = { ...job, state, stage: state };
      await h.renderRealJobDetail();
      assert.equal(h.node("progressTitle").textContent, title, "terminal state wins over the cancellation flag");
      assert.equal(h.node("cancelButton").hidden, true);
      assert.equal(h.node("progressSection").dataset.status, state);
    }
    job = { ...job, state: "queued", stage: "recovered", progress: 0, cancellationRequested: false };
    await h.renderRealJobDetail();
    assert.match(h.node("progressDescription").textContent, /queued to resume/);
    for (const [progress, value] of [[NaN, "0"], [-0.5, "0"], [1.5, "100"]]) {
      job = { ...job, state: "running", stage: "new-stage", progress };
      await h.renderRealJobDetail();
      assert.equal(h.node("progressBar").getAttribute("aria-valuenow"), value);
      assert.equal(steps.some((step) => step.hasAttribute("aria-current")), false);
    }
    job = { ...job, id: "processing-b", stage: "validating", progress: 0.05 };
    h.state.selectedId = job.id;
    await h.renderRealJobDetail();
    assert.equal(h.node("progressFill").style.transition, "none");
    job = { ...job, state: "ready", stage: "ready", progress: 1 };
    await h.renderRealJobDetail();
    assert.equal(h.node("progressSection").hidden, true, "finished scenes hand over to the viewer");
    h.context.clearDetail();
    assert.equal(h.node("progressSection").hidden, true);
    assert.equal(h.node("progressSection").dataset.jobId, undefined);
  }

  {
    const h = harness();
    for (const remaining of [2, 1, 0]) {
      h.context.showApp(user, "csrf", allowance(remaining ? "available" : "used", remaining));
      assert.equal(h.node("researchStatus").textContent,
        remaining ? `${remaining} of 2 videos remaining` : "Both videos used");
      assert.equal(h.node("video").disabled, remaining === 0);
    }
  }
  {
    const h = harness();
    h.context.showApp({ ...user, accountType: "owner" }, "csrf", null);
    assert.equal(h.node("video").disabled, false);
    assert.equal(h.node("researchStatus").textContent, "Owner account · No video limit");
    assert.match(h.node("researchReason").textContent, /Project spending/);
  }
  for (const fails of [false, true]) {
    const h = harness(), pending = deferred(), button = h.node("logoutButton");
    h.select();
    h.context.respond = (path, options) => {
      assert.equal(path, "/api/session");
      assert.equal(options.method, "DELETE");
      return pending.promise;
    };
    const signingOut = button.events.get("click")();
    assert.equal(button.disabled, true);
    assert.equal(button.textContent, "Signing out…");
    assert.equal(h.node("appView").hidden, false, "keep the session visible until revocation succeeds");
    await button.events.get("click")();
    assert.equal(h.requests.length, 1, "a repeated click cannot submit another logout");
    if (fails) pending.reject(new Error("Connection unavailable"));
    else pending.resolve({});
    await signingOut;
    assert.equal(button.disabled, false);
    assert.equal(button.textContent, "Sign out");
    assert.equal(h.node("appView").hidden, !fails);
    if (fails) {
      assert.equal(h.node("toast").textContent, "Sign out failed: Connection unavailable");
      h.context.respond = async () => ({});
      await button.events.get("click")();
      assert.equal(h.node("appView").hidden, true, "logout can be retried after failure");
    }
    assert.equal(h.node("video").files.length, 0, "logout clears the private capture selection");
    assert.equal(h.state.controllers.size, 0);
  }
  {
    const h = harness();
    const pending = Object.fromEntries(["assets", "shares", "jobs"].map((name) => [name, deferred()]));
    h.context.respond = (path) => pending[path.split("/").at(-1).split("?")[0]].promise;
    h.click({ manageWorkspace: "" });
    const status = h.node("requestStatus"), dialog = h.node("managementDialog");
    assert.equal(status.parentNode, dialog, "management loading feedback belongs to the active modal");
    assert.equal(dialog.children[0], status, "pending feedback precedes the scrollable inventory");
    assert.equal(status.hidden, false);
    assert.equal(h.state.controllers.size, 3);
    pending.assets.resolve({ assets: [], nextCursor: null });
    await new Promise(setImmediate);
    assert.equal(status.hidden, false, "one completed request cannot hide other pending requests");
    pending.shares.reject(new Error("Shares unavailable"));
    await new Promise(setImmediate);
    assert.equal(h.node("toast").textContent, "Shares unavailable");
    assert.equal(h.node("toast").parentNode, dialog);
    assert.equal(status.hidden, false, "an inventory error cannot hide the pending scene request");
    pending.jobs.resolve({ jobs: [], nextCursor: null });
    await new Promise(setImmediate);
    assert.equal(status.hidden, true);
    assert.equal(h.context.document.body.getAttribute("aria-busy"), "false");
  }
  {
    const h = harness(), pending = deferred();
    h.context.respond = () => pending.promise;
    const request = h.context.api("/api/me");
    const status = h.node("requestStatus"), body = h.context.document.body;
    assert.equal(status.parentNode, body);
    h.context.openCreateScene({ refresh: false });
    assert.equal(status.parentNode, h.node("createDialog"), "opening a dialog carries existing pending feedback into it");
    const confirmation = h.context.confirmAction("Continue?", "Test confirmation", "Continue");
    assert.equal(status.parentNode, h.node("confirmDialog"), "only the front modal owns the indicator");
    h.node("confirmCancel").events.get("click")();
    assert.equal(await confirmation, false);
    assert.equal(status.parentNode, h.node("createDialog"), "closing a nested dialog restores the underlying dialog's feedback");
    h.node("createDialog").close();
    await Promise.resolve();
    assert.equal(status.parentNode, body, "native Escape/close returns ongoing feedback to the page");
    assert.equal(status.classList.contains("dialog-request-status"), false);
    assert.equal(status.hidden, false);
    pending.resolve(account("available"));
    await request;
    assert.equal(status.hidden, true);
  }
  {
    const h = harness(), oldPending = deferred(), currentPending = deferred();
    h.context.respond = () => oldPending.promise;
    h.context.openCreateScene({ refresh: false });
    const oldRequest = h.context.api("/api/me");
    const stale = assert.rejects(oldRequest, { name: "AbortError" });
    const status = h.node("requestStatus"), body = h.context.document.body;
    h.context.secureReset();
    assert.equal(h.requests[0].options.signal.aborted, true);
    assert.equal(status.hidden, true, "session reset clears feedback before an aborted transport settles");
    assert.equal(status.parentNode, body);
    assert.equal(body.getAttribute("aria-busy"), "false");
    h.context.respond = () => currentPending.promise;
    const currentRequest = h.context.api("/api/me");
    oldPending.resolve(account("available"));
    await stale;
    assert.equal(status.hidden, false, "late old-session cleanup cannot clear a new request's indicator");
    assert.equal(body.getAttribute("aria-busy"), "true");
    currentPending.resolve(account("available"));
    await currentRequest;
    assert.equal(status.hidden, true);
    assert.equal(body.getAttribute("aria-busy"), "false");
  }
  {
    const h = harness(), sharePost = deferred(), shares = deferred();
    h.node("shareButton").dataset.artifactId = "art-test";
    h.state.selectedId = "job-test";
    h.context.respond = (path, options) => {
      if (path === "/api/artifacts/art-test/shares" && options.method === "POST") return sharePost.promise;
      if (path.startsWith("/api/shares")) return shares.promise;
      throw new Error(`Unexpected request: ${path}`);
    };
    const sharing = h.node("shareButton").events.get("click")();
    const deleting = h.node("deleteButton").events.get("click")();
    assert.equal(h.node("confirmDialog").open, true);
    sharePost.resolve({ url: "/s#local-test" });
    await new Promise(setImmediate);
    assert.equal(h.node("shareDialog").open, true);
    assert.equal(h.node("requestStatus").parentNode, h.node("shareDialog"),
      "a late Share response opens above confirmation despite its earlier DOM position");
    assert.equal(h.node("requestStatus").hidden, false);
    shares.reject(new Error("Share inventory unavailable"));
    await sharing;
    assert.equal(h.node("toast").parentNode, h.node("shareDialog"), "errors use the same front dialog");
    assert.equal(h.node("requestStatus").hidden, true);
    h.node("shareDialog").close();
    await Promise.resolve();
    assert.equal(h.node("requestStatus").parentNode, h.node("confirmDialog"));
    h.node("confirmCancel").events.get("click")();
    await deleting;
    assert.equal(h.requests.some((request) => request.method === "DELETE"), false);
    assert.equal(h.node("requestStatus").parentNode, h.context.document.body);
  }
  {
    const h = harness();
    const video = h.select();
    assert.equal(h.node("researchButton").disabled, true, "wait for metadata before upload");
    video.duration = 12;
    video.onloadedmetadata();
    assert.equal(h.node("researchButton").disabled, false);
    for (const state of [null, "processing", "used", "retry_later"]) {
      h.context.showApp(user, "csrf", state && allowance(state));
      assert.equal(h.node("video").disabled, true, `block picker for ${state}`);
      assert.equal(h.node("researchButton").disabled, true, `block submit for ${state}`);
    }
    h.context.showApp(user, "csrf");
    assert.equal(h.node("video").disabled, true, "missing Google allowance fails closed");
    h.context.showApp({ ...user, accountType: "operator" }, "csrf", null);
    assert.equal(h.node("researchButton").disabled, false, "operator has no one-video allowance");
  }
  {
    const h = harness();
    h.select({ name: "large.mp4", size: config.maxUploadBytes + 1 });
    assert.equal(h.videos.length, 0, "reject size before creating a metadata URL");
    assert.equal(h.node("video").getAttribute("aria-invalid"), "true");
    let video = h.select();
    video.duration = 30.1;
    video.onloadedmetadata();
    assert.equal(h.node("researchButton").disabled, true);
    assert.match(h.node("captureMessage").textContent, /up to 30 seconds/);
    assert.equal(h.revokedUrls.length, 1);
    video = h.select();
    video.onerror();
    assert.equal(h.node("researchButton").disabled, false, "unsupported metadata falls back to server validation");
    assert.match(h.node("captureMessage").textContent, /checked after upload/);
    video = h.select();
    const staleCallback = video.onloadedmetadata;
    const replacement = h.select({ name: "replacement.mov", size: 2048 });
    video.duration = 100;
    staleCallback();
    assert.equal(h.state.captureCheck.status, "checking", "old selection cannot reject the replacement");
    replacement.duration = 5;
    replacement.onloadedmetadata();
    assert.equal(h.state.captureCheck.status, "valid");
    video = h.select();
    const afterLogout = video.onloadedmetadata;
    h.context.showLogin();
    afterLogout();
    assert.equal(h.state.captureCheck, null);
    assert.equal(h.node("captureMessage").textContent, "");
    assert.equal(h.createdUrls.length, h.revokedUrls.length, "every metadata URL is released, including replacement and logout");
    assert.equal(h.timers.size, 0, "metadata checks leave no timeout after teardown");
  }
  {
    const h = harness();
    h.select();
    const timeout = [...h.timers.values()].find((timer) => timer.delay === 10000);
    timeout.callback();
    assert.equal(h.state.captureCheck.status, "fallback", "a stalled decoder cannot block upload indefinitely");
    assert.equal(h.revokedUrls.length, 1);
  }
  {
    const h = harness();
    h.select().onerror();
    h.context.respond = async () => account("used");
    await h.submit();
    assert.deepEqual(h.requests.map((request) => request.path), ["/api/me", "/api/engines"], "fresh used allowance stops before bytes are uploaded");
    assert.equal(h.node("researchButton").disabled, true);
    assert.match(h.node("researchMessage").textContent, /used/);
  }
  {
    const h = harness(), response = deferred();
    h.select().onerror();
    h.context.respond = () => response.promise;
    const pending = h.submit();
    const focused = h.windowEvents.get("focus")();
    assert.equal(h.requests.length, 2, "focus and pre-upload share one account and capacity refresh");
    assert.equal(h.node("video").disabled, true);
    assert.equal(h.node("researchButton").disabled, true);
    response.resolve(account("used"));
    await Promise.all([pending, focused]);
    assert.equal(h.requests.length, 2);
    assert.equal(h.state.uploading, false);
  }
  {
    const h = harness();
    let checks = 0;
    h.context.respond = async (path) => {
      if (path === "/api/me") return account(++checks === 1 ? "available" : "processing");
      if (path === "/api/assets") return { id: "upload-1" };
      if (path === "/api/jobs/research") return { id: "job-1" };
      if (path.startsWith("/api/jobs?")) return { jobs: [{ id: "job-1", engineId: "lingbot-research-v1", state: "queued" }], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      throw new Error(path);
    };
    h.select().onerror();
    await h.submit();
    assert.equal(checks, 2, "refresh allowance before upload and after queue");
    assert.equal(h.state.reconstructionAllowance.state, "processing");
    assert.equal(h.node("researchButton").disabled, true);
    assert.equal(h.requests.filter((request) => request.method === "POST").length, 2);
    const submission = h.requests.find((request) => request.path === "/api/jobs/research");
    assert.equal(JSON.parse(submission.options.body).assetId, "upload-1");
    await h.context.loadJobs();
    assert.equal(checks, 2, "unchanged job polls do not poll the account");
    h.context.respond = async (path) => path === "/api/me" ? account("used")
      : { jobs: [{ id: "job-1", engineId: "lingbot-research-v1", state: "ready" }], nextCursor: null };
    await h.context.loadJobs();
    assert.equal(h.state.reconstructionAllowance.state, "used", "terminal transition refreshes included-video status");
    const requests = h.requests.length;
    await h.context.loadJobs();
    assert.equal(h.requests.length, requests + 1, "terminal job is not a perpetual account poll");
  }
  {
    const h = harness(), response = deferred();
    h.select().onerror();
    h.context.respond = () => response.promise;
    const oldUpload = h.submit();
    h.context.showLogin();
    h.state.uploading = true; // A later session owns this lock.
    response.resolve(account("available"));
    await oldUpload;
    assert.equal(h.state.principal, "", "stale account response does not restore a signed-out identity");
    assert.equal(h.state.captureCheck, null);
    assert.equal(h.state.uploading, true, "old submit cleanup cannot unlock the next session");
    assert.equal(h.requests.length, 2, "stale preflight never uploads");
  }
  {
    const h = harness(), body = deferred(), responseReady = deferred();
    h.context.fetch = async () => {
      responseReady.resolve();
      return { ok: true, status: 200, headers: new Headers(), json: () => body.promise };
    };
    const refresh = h.context.refreshAccount();
    await responseReady.promise;
    await Promise.resolve();
    h.context.showLogin();
    body.resolve(account("available"));
    await assert.rejects(refresh, { name: "AbortError" });
    assert.equal(h.node("appView").hidden, true, "logout during JSON decoding keeps the private view closed");
  }
  {
    const h = harness("?signin=capacity");
    h.context.showApp({ ...user, accountType: "trial" }, "csrf");
    h.context.respond = async () => ({ ...config, newAccountsAvailable: false });
    await h.context.loadPublicConfig();
    assert.equal(h.node("googleLogin").hidden, false, "returning Google accounts can still sign in");
    assert.equal(h.context.location.hash, "#signin", "callback failures route to returning sign-in");
    assert.equal(h.context.location.search, "", "callback feedback is consumed from the URL");
    assert.equal(h.node("trialButton").hidden, true, "full signup never promotes the synthetic playground");
    assert.equal(h.node("googleLoginLabel").textContent, "Continue with Google");
    assert.match(h.node("onboardingStatus").textContent, /Sign in securely/);
    assert.equal(h.node("loginView").hidden, true);
    assert.equal(h.node("signinNotice").hidden, false, "capacity notice survives restoring an existing trial session");
    assert.match(h.node("signinNotice").textContent, /currently full/);
    assert.match(h.node("captureLimits").textContent, /30 seconds.*10.0 MiB/);
    h.context.respond = async () => ({ ...config });
    await h.context.loadPublicConfig();
    assert.equal(h.node("googleLogin").hidden, false);
    assert.equal(h.node("trialButton").hidden, true, "open signup also keeps the sample CTA hidden");
    const unknown = harness("?signin=toString");
    await unknown.context.loadPublicConfig();
    assert.equal(unknown.node("signinNotice").hidden, true);
  }
  {
    const h = harness(), response = deferred(), started = deferred();
    h.state.jobs = [{ id: "job-1", engineId: "lingbot-research-v1", state: "queued" }];
    h.context.respond = async (path) => {
      if (path === "/api/me") { started.resolve(); return response.promise; }
      return { jobs: [{ id: "job-1", engineId: "lingbot-research-v1", state: "ready" }], nextCursor: null };
    };
    const loading = h.context.loadJobs();
    await started.promise;
    h.context.showLogin();
    response.resolve(account("used"));
    await loading;
    assert.equal(h.node("appView").hidden, true);
    assert.equal(h.state.pollTimer, null, "terminal refresh cannot restart polling after logout");
    assert.equal(h.timers.size, 0);
  }
  {
    const h = harness(), snapshot = deferred();
    let checks = 0;
    h.state.jobs = [{ id: "job-1", engineId: "lingbot-research-v1", state: "queued" }];
    h.context.respond = async (path) => path === "/api/me"
      ? (++checks === 1 ? snapshot.promise : account("used"))
      : { jobs: [{ id: "job-1", engineId: "lingbot-research-v1", state: "ready" }], nextCursor: null };
    const focus = h.context.revalidateSession();
    const terminal = h.context.loadJobs();
    await new Promise(setImmediate);
    snapshot.resolve(account("processing"));
    await Promise.all([focus, terminal]);
    assert.equal(checks, 2, "completion requests a snapshot after the transition");
    assert.equal(h.state.reconstructionAllowance.state, "used");
    await h.context.loadJobs();
    assert.equal(checks, 2, "unchanged terminal polls do not keep refreshing the account");
  }
  {
    const h = harness("?signin=capacity");
    h.context.showApp({ ...user, accountType: "trial" }, "csrf");
    h.context.fetch = async () => { throw new Error("Offline"); };
    await h.context.loadPublicConfig();
    assert.equal(h.node("loginView").hidden, true);
    assert.equal(h.node("signinNotice").hidden, false, "callback feedback is independent of config");
    assert.match(h.node("signinNotice").textContent, /currently full/);
  }
  {
    const h = harness();
    h.context.showApp(user, "csrf", allowance("processing"));
    let checks = 0;
    h.context.respond = async (path) => {
      if (path === "/api/me") { checks++; return account("available"); }
      return { jobs: [{ id: "missed-job", engineId: "lingbot-research-v1", state: "failed" }], nextCursor: null };
    };
    await h.context.loadJobs();
    assert.equal(checks, 1, "initial job snapshot reconciles a missed terminal transition");
    assert.equal(h.state.reconstructionAllowance.state, "available", "failed capture can be retried");
    await h.context.loadJobs();
    assert.equal(checks, 1, "reconciled state does not add recurring account polls");
  }
  {
    const h = harness(), capacity = deferred();
    h.select().onerror();
    h.context.engineResponse = () => capacity.promise;
    const upload = h.submit();
    await new Promise(setImmediate);
    assert.deepEqual(h.requests.map((request) => request.path), ["/api/me", "/api/engines"]);
    assert.equal(h.node("researchButton").disabled, true, "account success cannot unlock a pending capacity check");
    assert.equal(h.node("video").disabled, true);
    capacity.resolve(engines(false));
    await upload;
    assert.equal(h.requests.some((request) => request.method === "POST"), false,
      "full global capacity stops before uploading any bytes");
    assert.equal(h.state.reconstructionAllowance.state, "available");
    assert.equal(h.node("video").disabled, true);
    assert.match(h.node("researchReason").textContent, /preview capacity is full/);
    assert.match(h.node("researchReason").textContent, /remaining videos.*capacity returns/);
    assert.equal(h.node("researchMessage").textContent, "", "the live capacity status owns the pause message");
    h.context.engineResponse = async () => engines();
    await h.windowEvents.get("focus")();
    assert.equal(h.node("researchButton").disabled, false, "focus can observe capacity reopening");
    assert.equal(h.node("video").disabled, false);
  }
  {
    const h = harness();
    h.state.engine = engines(false).engines[0];
    for (const state of ["used", "processing", "retry_later"]) {
      h.context.showApp(user, "csrf", allowance(state));
      assert.equal(h.node("researchReason").textContent, `Allowance: ${state}`,
        "global capacity does not overwrite the user's existing restriction");
    }
  }
  {
    const h = harness();
    const operator = { user: { ...user, accountType: "operator" }, csrfToken: "csrf", reconstructionAllowance: null };
    h.context.showApp(operator.user, "csrf");
    h.context.respond = async () => operator;
    h.select().onerror();
    h.context.engineResponse = async () => { throw new Error("Capacity check offline"); };
    await h.submit();
    assert.equal(h.requests.some((request) => request.method === "POST"), false);
    assert.equal(h.state.engine, null);
    assert.equal(h.node("video").disabled, true, "operator upload also fails closed on a failed capacity check");
    assert.equal(h.node("researchButton").disabled, true);
    assert.match(h.node("researchReason").textContent, /could not be confirmed/);
    h.context.engineResponse = async () => engines();
    await h.windowEvents.get("focus")();
    assert.equal(h.node("researchButton").disabled, false, "a successful check restores operator upload");
  }
  {
    const h = harness(), snapshot = deferred();
    let checks = 0;
    h.context.engineResponse = async () => ++checks === 1 ? snapshot.promise : engines(false);
    const oldRefresh = h.context.refreshAccount();
    const freshRefresh = h.context.refreshAccount({ fresh: true });
    await new Promise(setImmediate);
    assert.equal(checks, 1, "the fresh refresh waits for the entire preceding account/capacity pair");
    snapshot.resolve(engines());
    await Promise.all([oldRefresh, freshRefresh]);
    assert.equal(checks, 2);
    assert.equal(h.requests.filter((request) => request.path === "/api/me").length, 2);
    assert.equal(h.state.engine.available, false, "the later capacity snapshot wins");
    assert.equal(h.node("video").disabled, true);
  }
  {
    const h = harness(), capacity = deferred();
    h.context.engineResponse = () => capacity.promise;
    h.select().onerror();
    const oldUpload = h.submit();
    await new Promise(setImmediate);
    h.context.showLogin();
    h.state.uploading = true;
    capacity.resolve(engines());
    await oldUpload;
    assert.equal(h.state.engine, null, "late engine response cannot restore signed-out state");
    assert.equal(h.state.uploading, true, "late preflight cannot unlock a new session's upload");
    assert.equal(h.requests.some((request) => request.method === "POST"), false);
  }
  {
    const h = harness();
    const operator = { user: { ...user, accountType: "operator" }, csrfToken: "csrf", reconstructionAllowance: null };
    h.context.showApp(operator.user, "csrf");
    h.state.jobs = [{ id: "operator-job", engineId: "lingbot-research-v1", state: "queued" }];
    h.context.respond = async (path) => path === "/api/me" ? operator
      : { jobs: [{ id: "operator-job", engineId: "lingbot-research-v1", state: "ready" }], nextCursor: null };
    h.context.engineResponse = async () => engines(false);
    await h.context.loadJobs();
    assert.equal(h.state.engine.available, false, "operator job completion also refreshes global capacity");
    assert.equal(h.node("researchReason").textContent, capacityMessage);
  }
  {
    const h = harness();
    h.context.respond = async (path) => {
      if (path === "/api/me") return account("available");
      if (path.startsWith("/api/jobs?")) return { jobs: [], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      if (path.startsWith("/api/shares?")) return { shares: [], nextCursor: null };
      throw new Error(path);
    };
    await h.context.initialize();
    assert.equal(h.requests.filter((request) => request.path === "/api/engines").length, 1,
      "initialization fetches capacity once");
    h.context.engineResponse = async () => engines(false);
    await h.node("refreshButton").events.get("click")();
    assert.equal(h.state.engine.available, false, "manual refresh updates account and capacity together");
  }
  for (const accountType of ["operator", "trial"]) {
    const h = harness(), capacity = deferred();
    const identity = { user: { ...user, accountType }, csrfToken: "csrf", reconstructionAllowance: null };
    let checks = 0;
    h.context.engineResponse = async () => ++checks === 1 ? capacity.promise : engines(false);
    h.context.respond = async (path) => {
      if (["/api/session", "/api/trial", "/api/me"].includes(path)) return identity;
      if (path.startsWith("/api/jobs?")) return { jobs: [], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      if (path.startsWith("/api/shares?")) return { shares: [], nextCursor: null };
      throw new Error(path);
    };
    h.node("sampleButton").click = () => {};
    const entry = accountType === "operator"
      ? h.node("loginForm").events.get("submit")({ preventDefault() {},
        currentTarget: { querySelector: () => h.node("loginButton") } })
      : h.node("trialButton").events.get("click")();
    await new Promise(setImmediate);
    const newer = h.context.refreshAccount({ fresh: true });
    await new Promise(setImmediate);
    assert.equal(checks, 1, `${accountType} entry participates in the shared refresh coordinator`);
    capacity.resolve(engines());
    await Promise.all([entry, newer]);
    assert.equal(checks, 2);
    assert.equal(h.state.engine.available, false, "older entry response cannot overwrite newer capacity");
    assert.equal(h.node("video").disabled, true);
  }
  {
    const h = harness();
    h.context.showLogin();
    assert.equal(h.node("loginView").hidden, false, "first arrival shows the public landing");
    assert.equal(h.node("accountView").hidden, true);
    h.click({ accountEntry: "signup" });
    assert.equal(h.context.location.hash, "#signup");
    assert.equal(h.node("loginView").hidden, true);
    assert.equal(h.node("accountView").hidden, false);
    assert.equal(h.node("appView").hidden, true);
    assert.equal(h.node("googleLogin").hidden, false);
    assert.equal(h.node("trialButton").hidden, true);
    assert.match(h.node("accountTitle").textContent, /Your own space/);
    assert.equal(h.node("accountTitle").focusCount, 1);
    assert.equal(h.node("skipLink").href, "#accountTitle");
    assert.equal(h.requests.length, 0, "Get started opens the account step before contacting Google");
    assert.equal(h.context.location.pathname, "/");

    h.click({ accountEntry: "login" });
    assert.equal(h.context.location.hash, "#signin");
    assert.equal(h.node("accountTitle").textContent, "Welcome back.");
    assert.equal(h.node("accountSwitch").hidden, true);
    assert.equal(h.requests.length, 0, "returning sign-in navigation also waits for explicit Google continuation");
    h.click({ publicHome: "" });
    assert.equal(h.context.location.hash, "");
    assert.equal(h.node("loginView").hidden, false);
    assert.equal(h.node("accountView").hidden, true);
    assert.equal(h.node("skipLink").href, "#loginTitle");
    assert.equal(h.node("loginTitle").focusCount, 1);

    h.context.location.hash = "#signup";
    h.windowEvents.get("popstate")();
    assert.equal(h.node("accountView").hidden, false, "browser back/forward restores the account route");
    h.context.location.hash = "#how-it-works";
    h.windowEvents.get("hashchange")();
    assert.equal(h.node("loginView").hidden, false, "landing section anchors do not enter authentication");
    assert.equal(h.node("accountView").hidden, true);
  }
  {
    const h = harness();
    h.context.showLogin();
    h.state.config = { ...config, newAccountsAvailable: false };
    h.click({ accountEntry: "signup" });
    assert.match(h.node("accountTitle").textContent, /preview is full/);
    assert.equal(h.node("googleLogin").hidden, true, "full capacity does not offer a new-account action");
    assert.equal(h.node("accountSwitch").hidden, false, "existing accounts retain a visible sign-in path");
    assert.equal(h.node("trialButton").hidden, true, "full capacity cannot turn signup into a sample promotion");
    h.click({ accountEntry: "login" });
    assert.equal(h.node("googleLogin").hidden, false);
    assert.equal(h.node("accountTitle").textContent, "Welcome back.");
    h.state.config = { ...config, googleSignIn: false };
    h.context.renderSignInOptions();
    assert.equal(h.node("googleLogin").hidden, true);
    assert.equal(h.node("trialButton").hidden, true, "disabled Google sign-in also does not advertise the sample");
  }
  for (const [surface, targetId] of [
    ["signup", "accountTitle"], ["login", "accountTitle"],
    ["landing", "loginTitle"], ["workspace", "workspaceMain"],
  ]) {
    const h = harness();
    if (surface !== "workspace") h.context.showLogin();
    if (surface === "signup" || surface === "login") h.click({ accountEntry: surface });
    const route = h.context.location.hash;
    const focusCount = h.node(targetId).focusCount;
    let prevented = false;
    h.node("skipLink").events.get("click")({ preventDefault() { prevented = true; } });
    // The anchor's normal default would change the hash and invoke the public router.
    if (!prevented) {
      h.context.location.hash = h.node("skipLink").href;
      h.windowEvents.get("hashchange")();
    }
    assert.equal(prevented, true, `${surface} skip navigation prevents a route-changing fragment jump`);
    assert.equal(h.context.location.hash, route);
    assert.equal(h.node(targetId).focusCount, focusCount + 1, `${surface} skip navigation focuses its visible main content`);
    assert.equal(h.node("accountView").hidden, targetId !== "accountTitle");
    assert.equal(h.node("appView").hidden, surface !== "workspace");
    assert.equal(h.node("loginView").hidden, surface !== "landing");
  }
  for (const signin of ["cancelled", "capacity", "failed", "expired"]) {
    const h = harness(`?signin=${signin}`);
    h.context.showLogin();
    const configReady = deferred();
    h.context.respond = () => configReady.promise;
    const loading = h.context.loadPublicConfig();
    // Startup's account request may finish while the independent config fetch is pending.
    h.context.showLogin();
    assert.equal(h.context.location.hash, "#signin");
    assert.equal(h.node("accountView").hidden, false);
    assert.equal(h.node("signinNotice").hidden, false);
    configReady.resolve({ ...config });
    await loading;
    assert.equal(h.node("googleLogin").hidden, false);
    assert.equal(h.node("trialButton").hidden, true);
  }
  {
    const h = harness();
    h.context.openCreateScene({ refresh: false });
    const video = h.select();
    video.duration = 12;
    video.onloadedmetadata();
    const previewUrl = h.state.capturePreviewUrl;
    assert.equal(h.node("capturePreview").src, previewUrl);
    assert.equal(h.node("capturePreviewPanel").hidden, false);
    assert.match(h.node("capturePreviewMeta").textContent, /room.mp4.*12.0 seconds/);
    assert.equal(h.revokedUrls.includes(previewUrl), false, "the visible preview keeps its object URL");
    const pauses = h.node("capturePreview").pauseCount;
    h.click({ dialogClose: "createDialog" });
    await Promise.resolve();
    assert.equal(h.node("createDialog").open, false);
    assert.equal(h.node("capturePreview").pauseCount, pauses + 1, "closing a capture pauses local playback");
    h.context.openCreateScene({ refresh: false });
    assert.equal(h.node("capturePreview").src, previewUrl, "reopening preserves the selected capture");
    h.select({ name: "next.mp4", size: 2048 });
    assert.equal(h.revokedUrls.filter((url) => url === previewUrl).length, 1, "replacement revokes the prior preview once");
    assert.equal(h.node("capturePreviewPanel").hidden, true);
    h.windowEvents.get("pagehide")();
    assert.equal(h.state.capturePreviewUrl, null);
    assert.equal(h.state.captureCheck, null);
    assert.equal(h.node("capturePreview").src, "");
    assert.deepEqual([...h.revokedUrls].sort(), h.createdUrls.map(({ url }) => url).sort(),
      "page exit releases both active metadata and preview URLs without duplicate revocation");
    assert.equal(h.timers.size, 0);
  }
  {
    const h = harness();
    h.context.openCreateScene({ refresh: false });
    h.context.openDialog(h.node("managementDialog"));
    h.state.jobs = [{ id: "private-job", displayName: "Private customer room", state: "ready" }];
    h.context.renderJobs();
    assert.equal(h.node("managementJobList").children.length, 1);
    const confirmation = h.context.confirmAction("Delete scene?", "Private customer room", "Delete");
    assert.equal(h.node("confirmDialog").open, true);
    assert.equal(await h.context.confirmAction("Duplicate", "Do not replace", "Delete"), false);
    assert.equal(h.node("confirmMessage").textContent, "Private customer room");
    h.context.showLogin();
    assert.equal(await confirmation, false, "logout cancels a pending confirmation");
    for (const id of ["createDialog", "managementDialog", "confirmDialog"]) assert.equal(h.node(id).open, false);
    assert.equal(h.node("managementJobList").children.length, 0, "reset removes previous-account names from storage management");
    assert.equal(h.node("emptyManagedJobs").hidden, false);
    h.context.showApp(user, "csrf", allowance("available"));
    const accepted = h.context.confirmAction("Delete scene?", "Current account", "Delete");
    h.node("confirmAccept").events.get("click")();
    assert.equal(await accepted, true, "a fresh confirmation can complete after reset");
    const signedOut = h.context.confirmAction("Delete scene?", "Current account", "Delete");
    h.node("confirmAccept").events.get("click")();
    h.context.showLogin();
    assert.equal(await signedOut, false, "a close event delivered after logout cannot authorize an old mutation");
  }
  {
    const h = harness();
    const file = { name: "retained.mp4", size: 2048 };
    h.select(file).onerror();
    const oldPreview = h.state.capturePreviewUrl;
    const decoders = h.videos.length;
    h.windowEvents.get("pagehide")();
    assert.equal(h.node("video").files[0], file, "the browser retains the selected File in its page cache");
    assert.equal(h.state.captureCheck, null);
    assert.equal(h.state.capturePreviewUrl, null);
    assert.equal(h.revokedUrls.filter((url) => url === oldPreview).length, 1);
    h.windowEvents.get("pageshow")({ persisted: false });
    assert.equal(h.videos.length, decoders, "ordinary pageshow does not duplicate capture validation");
    h.windowEvents.get("pageshow")({ persisted: true });
    assert.equal(h.videos.length, decoders + 1, "returning from the page cache revalidates the retained File");
    assert.equal(h.state.captureCheck.status, "checking");
    assert.equal(h.node("researchButton").disabled, true);
    const restored = h.videos.at(-1);
    restored.duration = 8;
    restored.onloadedmetadata();
    assert.equal(h.state.captureCheck.status, "valid");
    assert.equal(h.node("researchButton").disabled, false);
    assert.notEqual(h.state.capturePreviewUrl, oldPreview);
    assert.equal(h.node("capturePreview").src, h.state.capturePreviewUrl);
    assert.equal(h.node("capturePreviewPanel").hidden, false);
    h.state.uploading = true;
    h.windowEvents.get("pageshow")({ persisted: true });
    assert.equal(h.videos.length, decoders + 1, "a submission retains ownership of its capture snapshot");
    h.context.showLogin();
    h.windowEvents.get("pageshow")({ persisted: true });
    assert.equal(h.videos.length, decoders + 1, "returning after logout cannot restore a private selection");
  }
  {
    const h = harness(), queued = deferred();
    h.context.openCreateScene({ refresh: false });
    h.select().onerror();
    h.context.respond = async (path) => {
      if (path === "/api/jobs/sample") return queued.promise;
      if (path.startsWith("/api/jobs?")) return { jobs: [{
        id: "sample-job", displayName: "Synthetic studio", engineId: "synthetic-sample-v1", state: "queued",
      }], nextCursor: null };
      throw new Error(path);
    };
    const sample = h.node("sampleButton").events.get("click")();
    assert.equal(h.state.uploading, true);
    assert.equal(h.node("sampleButton").disabled, true);
    assert.equal(h.node("video").disabled, true);
    assert.equal(h.node("researchButton").disabled, true);
    await h.submit();
    await h.node("sampleButton").events.get("click")();
    assert.deepEqual(h.requests.map(({ path }) => path), ["/api/jobs/sample"],
      "a pending sample excludes both a second sample and a video submission");
    h.click({ dialogClose: "createDialog" });
    assert.equal(h.node("createDialog").open, true, "the close button cannot hide a pending sample submission");
    let cancelled = false;
    h.node("createDialog").events.get("cancel")({ preventDefault() { cancelled = true; } });
    assert.equal(cancelled, true, "Escape also waits for sample submission to finish");
    assert.match(h.node("toast").textContent, /being submitted/);
    assert.equal(h.node("toast").parentNode, h.node("createDialog"), "submission feedback is inside the native top layer");
    queued.resolve({ id: "sample-job" });
    await sample;
    assert.equal(h.node("createDialog").open, false);
    assert.equal(h.state.uploading, false);
    assert.equal(h.node("sampleButton").disabled, false);
    assert.equal(h.node("toast").parentNode, h.context.document.body, "completion feedback returns to the page after the dialog closes");
    assert.equal(h.node("toast").classList.contains("dialog-toast"), false);
  }
  {
    const h = harness(), checked = deferred();
    h.select().onerror();
    h.context.respond = () => checked.promise;
    const upload = h.submit();
    assert.equal(h.node("sampleButton").disabled, true, "video submission also disables synthetic creation");
    await h.node("sampleButton").events.get("click")();
    assert.equal(h.requests.some(({ path }) => path === "/api/jobs/sample"), false);
    checked.resolve(account("used"));
    await upload;
    assert.equal(h.node("sampleButton").disabled, false, "a stopped video submission releases the sample action");
  }
  {
    const h = harness();
    const toast = h.node("toast");
    h.context.openDialog(h.node("managementDialog"));
    h.context.toast("Storage refreshed");
    assert.equal(toast.parentNode, h.node("managementDialog"));
    assert.equal(toast.classList.contains("dialog-toast"), true);
    h.context.openDialog(h.node("confirmDialog"));
    h.context.toast("Confirmation feedback");
    assert.equal(toast.parentNode, h.node("confirmDialog"), "feedback moves to the later open dialog");
    assert.equal(h.node("managementDialog").children.includes(toast), false, "moving feedback leaves no duplicate in the previous dialog");
    h.node("confirmDialog").close();
    h.context.toast("Storage feedback");
    assert.equal(toast.parentNode, h.node("managementDialog"));
    h.node("managementDialog").close();
    h.context.toast("Workspace feedback");
    assert.equal(toast.parentNode, h.context.document.body);
    assert.equal(toast.classList.contains("dialog-toast"), false);
    assert.equal(h.context.document.body.children.filter((child) => child === toast).length, 1);
    assert.equal([...h.timers.values()].filter(({ delay }) => delay === 4000).length, 1,
      "moving the existing toast retains only the latest dismissal timer");
  }
  {
    const h = harness();
    const job = (id) => ({ id, displayName: id, state: "ready", engineId: "synthetic-sample-v1" });
    const newest = job("newest"), current = job("current"), removed = job("removed");
    h.state.jobs = [newest, current, removed];
    h.state.selectedId = current.id;
    h.state.selectedJobs.add(removed.id);
    let destroyed = 0;
    const viewer = { destroy() { destroyed++; } };
    h.state.viewer = viewer;
    h.context.respond = async (path, options) => {
      if (path === "/api/jobs/removed" && options.method === "DELETE") return { state: "deleting" };
      if (path.startsWith("/api/jobs?")) return { jobs: [newest, current], nextCursor: null };
      if (path.startsWith("/api/assets?")) return { assets: [], nextCursor: null };
      if (path.startsWith("/api/shares?")) return { shares: [], nextCursor: null };
      throw new Error(path);
    };
    const deletion = h.context.deleteJob(removed.id);
    h.node("confirmAccept").events.get("click")();
    await deletion;
    assert.equal(h.state.selectedId, current.id, "deleting another scene does not jump to the newest scene");
    assert.equal(h.state.viewer, viewer);
    assert.equal(destroyed, 0, "an unrelated deletion does not dispose the active viewport");
    assert.equal(h.state.jobs.some(({ id }) => id === removed.id), false, "an accepted deletion is removed even while preserving older loaded pages");
    assert.equal(h.state.selectedJobs.has(removed.id), false);
    assert.equal(h.requests.filter(({ method }) => method === "DELETE").length, 1);
  }
  {
    const h = harness(), loaded = [], destroyed = [];
    h.context.window.PointCloudViewer = class {
      async load(url) { loaded.push(url); }
      destroy() { destroyed.push(this); }
    };
    const artifact = { id: "artifact-a", kind: "scene", filename: "a.glb", sizeBytes: 1024,
      downloadUrl: "/api/artifacts/artifact-a/download", viewUrl: "/api/artifacts/artifact-a/content",
      licenseId: "CC0-1.0", sha256: "a".repeat(64), metadata: { pointCount: 100 } };
    const job = { id: "ready-a", displayName: "Scene A", engineId: "synthetic-sample-v1", state: "ready",
      stage: "ready", progress: 1, provenance: {}, usedUnits: 0, reservedUnits: 0, artifacts: [artifact] };
    h.context.respond = async (path) => {
      if (path === "/api/jobs/ready-a") return job;
      if (path === "/api/jobs/processing-b") return { ...job, id: "processing-b", displayName: "Scene B",
        state: "running", stage: "generating", progress: 0.25, artifacts: [] };
      if (path === "/api/me") return account("available");
      throw new Error(path);
    };
    h.state.selectedId = job.id;
    await h.renderRealJobDetail();
    assert.equal(h.node("shareButton").hidden, false);
    assert.equal(h.node("shareButton").dataset.artifactId, artifact.id);
    assert.equal(h.node("downloadLink").href, artifact.downloadUrl);
    assert.deepEqual(loaded, [artifact.viewUrl], "the ready artifact is actually loaded through the detail renderer");

    h.state.selectedId = "processing-b";
    await h.renderRealJobDetail();
    assert.equal(h.node("shareButton").hidden, true);
    assert.equal(h.node("shareButton").dataset.artifactId, undefined);
    assert.equal(h.node("downloadLink").hidden, true);
    assert.equal(h.node("downloadLink").href, "");
    assert.equal(h.state.viewer, null);
    assert.equal(destroyed.length, 1);
    await h.windowEvents.get("focus")();
    assert.equal(h.node("shareButton").hidden, true, "account refresh cannot resurrect Scene A's share action while Scene B has no artifact");
    assert.equal(h.node("shareButton").dataset.artifactId, undefined);
    await h.node("shareButton").events.get("click")();
    assert.equal(h.requests.some(({ path }) => path.endsWith("/shares")), false,
      "even a programmatic stale click cannot create a share for the previous scene");

    h.state.selectedId = job.id;
    await h.renderRealJobDetail();
    h.context.clearDetail();
    h.context.showApp(user, "csrf", allowance("available"));
    assert.equal(h.node("shareButton").hidden, true, "returning to the library also clears the artifact-backed action");
    assert.equal(h.node("shareButton").dataset.artifactId, undefined);
    assert.equal(h.node("downloadLink").href, "");
  }
  console.log("Capture allowance, onboarding, metadata, and session behavior passed");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
