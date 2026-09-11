"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../lingbot_map/workspace/static/app.js"), "utf8");
const user = { tenantName: "Private space", displayName: "Visitor", accountType: "google" };
const allowance = (state) => ({ state, message: `Allowance: ${state}` });
const account = (state) => ({ user, csrfToken: "csrf", reconstructionAllowance: allowance(state) });
const config = { googleSignIn: true, newAccountsAvailable: true, trialEnabled: true,
  maxVideoSeconds: 30, maxUploadBytes: 10 * 1024 * 1024 };
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

function harness(search = "") {
  const nodes = new Map(), timers = new Map(), windowEvents = new Map();
  const videos = [], createdUrls = [], revokedUrls = [], requests = [];
  let timerId = 0;
  function element() {
    const classes = new Set(), attributes = new Map(), events = new Map();
    let value = "";
    return {
      hidden: false, disabled: false, textContent: "", files: [], dataset: {}, children: [], events,
      get value() { return value; },
      set value(next) { value = next; if (next === "") this.files = []; },
      classList: { toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }, contains: (name) => classes.has(name) },
      setAttribute: (name, next) => attributes.set(name, next),
      removeAttribute: (name) => attributes.delete(name),
      getAttribute: (name) => attributes.get(name),
      addEventListener: (name, callback) => events.set(name, callback),
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      querySelectorAll: () => [], focus() {}, load() {}, close() {},
    };
  }
  const node = (id) => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
  const setTimeout = (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; };
  const clearTimeout = (id) => timers.delete(id);
  class TestURL extends URL {
    static createObjectURL(file) { const url = `blob:test-${createdUrls.length}`; createdUrls.push({ file, url }); return url; }
    static revokeObjectURL(url) { revokedUrls.push(url); }
  }
  const location = { search, origin: "https://example.test", reload() {} };
  const context = vm.createContext({
    URL: TestURL, URLSearchParams, Headers, AbortController, DOMException, Date,
    crypto: { randomUUID: () => "request-id" }, location, setTimeout, clearTimeout,
    localStorage: { setItem() {}, removeItem() {} },
    FormData: class { append() {} },
    window: { location, setTimeout, clearTimeout, addEventListener: (name, callback) => windowEvents.set(name, callback),
      SceneTimeline: class { attach() {} stop() {} wholeSpace() {} },
      WorkspaceSessionEvents: { dispatch() {} } },
    document: { getElementById: node, body: element(), addEventListener() {},
      querySelector: node, createElement(tag) { const created = element(); if (tag === "video") videos.push(created); return created; } },
    fetch: async (path, options = {}) => {
      requests.push({ path, method: options.method || "GET", options });
      const result = await context.respond(path, options);
      return { ok: true, status: 200, headers: new Headers(), json: async () => result };
    },
    respond: async (path) => {
      if (path === "/api/me") return account("available");
      if (path === "/api/config") return { ...config };
      throw new Error(`Unexpected request: ${path}`);
    },
  });
  vm.runInContext(`${source.slice(0, source.lastIndexOf("\nloadPublicConfig();"))}\nglobalThis.appState = state;`, context);
  // Keep real account, form, polling, and inventory behavior; scene rendering has its own suite.
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
  return { context, state, node, select, submit, videos, createdUrls, revokedUrls, timers, requests, windowEvents };
}

async function main() {
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
    assert.deepEqual(h.requests.map((request) => request.path), ["/api/me"], "fresh used allowance stops before bytes are uploaded");
    assert.equal(h.node("researchButton").disabled, true);
    assert.match(h.node("researchMessage").textContent, /used/);
  }
  {
    const h = harness(), response = deferred();
    h.select().onerror();
    h.context.respond = () => response.promise;
    const pending = h.submit();
    const focused = h.windowEvents.get("focus")();
    assert.equal(h.requests.length, 1, "focus and pre-upload share one account refresh");
    assert.equal(h.node("video").disabled, true);
    assert.equal(h.node("researchButton").disabled, true);
    response.resolve(account("used"));
    await Promise.all([pending, focused]);
    assert.equal(h.requests.length, 1);
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
    assert.equal(h.requests.length, 1, "stale preflight never uploads");
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
    assert.equal(h.node("googleLogin").classList.contains("secondary"), true);
    assert.equal(h.node("trialButton").classList.contains("primary"), true);
    assert.match(h.node("googleLoginLabel").textContent, /Returning/);
    assert.match(h.node("onboardingStatus").textContent, /currently full/);
    assert.equal(h.node("loginView").hidden, true);
    assert.equal(h.node("signinNotice").hidden, false, "capacity notice survives restoring an existing trial session");
    assert.match(h.node("signinNotice").textContent, /currently full/);
    assert.match(h.node("captureLimits").textContent, /30 seconds.*10.0 MiB/);
    h.context.respond = async () => ({ ...config });
    await h.context.loadPublicConfig();
    assert.equal(h.node("googleLogin").classList.contains("primary"), true);
    assert.equal(h.node("trialButton").classList.contains("secondary"), true);
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
  console.log("Capture allowance, onboarding, metadata, and session behavior passed");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
