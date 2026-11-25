"use strict";

const assert = require("node:assert/strict");
const vm = require("node:vm");
const source = require("node:fs").readFileSync(require.resolve("../lingbot_map/workspace/static/site.js"), "utf8");
const key = "scene-workspace-analytics-consent-v1";
const configured = { analytics: { propertyId: "wayline_test", endpoint: "/analytics/page-view" } };
const flush = () => new Promise(setImmediate);

function harness({ saved, path = "/privacy", surface = "landing", config = configured,
  privacy = {}, storageBlocked = false, writeBlocked = false, removeBlocked = false, deferred = false } = {}) {
  class Element {
    constructor() { this.children = []; this.events = {}; this.dataset = {}; }
    append(...items) { this.children.push(...items); }
    setAttribute() {}
    addEventListener(name, callback) { this.events[name] = callback; }
    querySelector() { return this.children.find((item) => item.events.click); }
    focus() {}
  }
  const body = new Element(); body.dataset.surface = surface;
  const location = { pathname: path, search: "?token=private-query", hash: "#private-fragment" };
  const events = {}, storage = new Map(saved ? [[key, saved]] : []), requests = [];
  let mutation, resolveConfig;
  const configResponse = deferred ? new Promise((resolve) => { resolveConfig = resolve; })
    : Promise.resolve({ ok: true, json: async () => config });
  vm.runInNewContext(source, {
    document: { body, createElement: () => new Element() },
    window: { addEventListener: (name, callback) => { events[name] = callback; } },
    navigator: privacy,
    location,
    localStorage: {
      getItem(name) { if (storageBlocked) throw Error("blocked"); return storage.get(name) ?? null; },
      setItem(name, value) { if (storageBlocked || writeBlocked) throw Error("blocked"); storage.set(name, value); },
      removeItem(name) { if (storageBlocked || removeBlocked) throw Error("blocked"); storage.delete(name); },
    },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return url === "/api/config" ? configResponse : { ok: true };
    },
    MutationObserver: class { constructor(callback) { mutation = callback; } observe() {} },
    AbortController, setTimeout, clearTimeout,
  });
  return {
    requests, storage, events,
    posts: () => requests.filter((item) => item.options.method === "POST"),
    click(label) {
      const control = body.children.flatMap((item) => item.children).find((item) => item.textContent === label);
      assert.ok(control, label); control.events.click();
    },
    surface(value) { body.dataset.surface = value; mutation(); },
    path(value) { location.pathname = value; },
    resolve() { resolveConfig({ ok: true, json: async () => config }); },
  };
}

(async () => {
  const denied = harness(); await flush();
  assert.equal(denied.requests.length, 0, "no consent means no analytics requests");
  denied.click("Essential only"); await flush();
  assert.equal(denied.requests.length, 0);
  denied.click("Allow analytics"); await flush();
  assert.equal(denied.posts().length, 1);
  const { url, options } = denied.posts()[0];
  assert.equal(url, "/analytics/page-view");
  assert.deepEqual(JSON.parse(options.body), { propertyId: "wayline_test", event: "page_view", page: "/privacy" });
  assert.equal(options.credentials, "omit");
  assert.equal(options.referrerPolicy, "no-referrer");
  assert.equal(options.headers["X-Wayline-Analytics-Consent"], "accepted");
  denied.click("Essential only"); denied.click("Allow analytics"); await flush();
  assert.equal(denied.posts().length, 1, "a page view is counted at most once");

  for (const options of [
    { config: { analytics: null } },
    { config: { analytics: { ...configured.analytics, endpoint: "https://other.invalid/analytics/page-view" } } },
    { config: { analytics: { ...configured.analytics, propertyId: "invalid label" } } },
    { config: { analytics: { endpoint: "/analytics/page-view" } } },
    { privacy: { doNotTrack: "1" } }, { privacy: { globalPrivacyControl: true } },
    { path: "/s" }, { path: "/api/jobs/private" },
    { path: "/", surface: "workspace" }, { path: "/", surface: "account" },
    { storageBlocked: true },
  ]) {
    const h = harness({ saved: "accepted", ...options }); await flush();
    assert.equal(h.posts().length, 0, JSON.stringify(options));
  }
  const landing = harness({ saved: "accepted", path: "/", surface: "" }); await flush();
  assert.equal(landing.requests.length, 0, "wait until the app identifies a public landing");
  landing.surface("landing"); await flush();
  assert.equal(landing.posts().length, 1);

  for (const withdrawal of ["button", "storage", "privacy", "private-surface", "path", "pagehide"]) {
    const privacy = {}, h = harness({ saved: "accepted", deferred: true, privacy, path: "/" });
    await flush(); assert.equal(h.requests.length, 1);
    if (withdrawal === "button") h.click("Essential only");
    if (withdrawal === "storage") { h.storage.set(key, "rejected"); h.events.storage(); }
    if (withdrawal === "privacy") privacy.globalPrivacyControl = true;
    if (withdrawal === "private-surface") h.surface("workspace");
    if (withdrawal === "path") h.path("/contact");
    if (withdrawal === "pagehide") h.events.pagehide();
    h.resolve(); await flush();
    assert.equal(h.posts().length, 0, `withdrawal during config fetch: ${withdrawal}`);
  }
  for (const removeBlocked of [false, true]) {
    const h = harness({ saved: "accepted", path: "/", deferred: true, writeBlocked: true, removeBlocked });
    await flush(); assert.equal(h.requests.length, 1, "stored acceptance starts configuration loading");
    h.click("Essential only"); h.resolve(); await flush();
    assert.equal(h.posts().length, 0, "withdrawal cancels the pending event when persistence fails");
    h.surface("account"); await flush(); h.surface("landing"); await flush();
    assert.equal(h.posts().length, 0, "returning to the landing must preserve this document's rejection");
    assert.equal(h.storage.get(key), removeBlocked ? "accepted" : undefined,
      "remove the obsolete acceptance when storage removal is available");
    h.click("Allow analytics"); await flush();
    assert.equal(h.posts().length, 0, "a new acceptance cannot take effect unless it persists successfully");
  }
  console.log("First-party consent, configuration, privacy signals, safe buckets and withdrawal passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
