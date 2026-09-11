"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const settle = () => new Promise(resolve => setImmediate(resolve));
const token = "a".repeat(40);

function element(values = {}) {
  return {
    hidden: false, textContent: "", ...values, listeners: {},
    addEventListener(type, listener, { signal } = {}) {
      this.listeners[type] = listener;
      signal?.addEventListener("abort", () => delete this.listeners[type]);
    },
    click(event) { return this.listeners.click?.(event); },
    focus() { this.focused = true; },
  };
}

function fixture({ hash = `#${token}`, metadataStatus = 200, contentStatus = 200,
  webglFailure = false, renderFailure = false, pendingDownload = false, licenseId = "NOASSERTION" } = {}) {
  const ids = ["sharedStatus", "sharedDownload", "sharedTimeline", "shareLicense", "shareTitle",
    "shareUnavailableMessage", "shareUnavailableTitle", "shareUnavailable", "sharedZoomIn",
    "sharedZoomOut", "sharedReset", "shareExpiry", "shareCommercialWarning", "sharedCanvas", "sharedSkipLink"];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements.shareUnavailable.hidden = true;
  elements.sharedDownload.hidden = true;
  const selectors = Object.fromEntries([".shared-viewer", ".shared-viewer .viewport-wrap", ".shared-viewer .viewer-help"].map(selector => [selector, element()]));
  const requests = [], viewers = [], timelineAttachments = [], downloads = [], createdUrls = [], revokedUrls = [];
  const timers = new Map();
  let nextTimer = 0, contentRequests = 0;
  const metadata = {
    artifact: { filename: "office.glb", licenseId, contentUrl: "/api/public/share/content" },
    expiresAt: Math.ceil(Date.now() / 1000) + 60,
    researchOnly: true, commercialWarning: "Research preview.",
  };
  const location = { hash };
  const window = element({
    SceneTimeline: class { attach(viewer) { timelineAttachments.push(viewer); } wholeSpace() {} },
    PointCloudViewer: class {
      constructor() {
        if (webglFailure) throw new Error("WebGL is unavailable in this browser.");
        this.loadController = new AbortController();
        viewers.push(this);
      }
      async load(url, options) {
        assert.equal(url, "/api/public/share/content");
        assert.equal(options.prefetchedResponse.ok, true, "Only validated capability responses are passed to the preview");
        if (renderFailure) throw new Error("Unsupported geometry.");
      }
      destroy() { this.destroyed = true; this.loadController.abort(); }
    },
  });
  const scope = {
    window, location, AbortController,
    document: {
      getElementById: id => elements[id], querySelector: selector => selectors[selector],
      createElement(tag) {
        assert.equal(tag, "a");
        return { click() { downloads.push({ href: this.href, filename: this.download }); } };
      },
    },
    URL: {
      createObjectURL(blob) { assert.equal(blob.kind, "artifact"); const url = `blob:share-fixture/${createdUrls.length}`; createdUrls.push(url); return url; },
      revokeObjectURL(url) { revokedUrls.push(url); },
    },
    setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    async fetch(url, options) {
      requests.push({ url, options });
      if (url === "/api/public/share") return { ok: metadataStatus === 200, status: metadataStatus, json: async () => metadata };
      assert.equal(url, "/api/public/share/content");
      contentRequests += 1;
      if (pendingDownload && contentRequests === 2) {
        return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("Aborted"))));
      }
      return { ok: contentStatus === 200, status: contentStatus, blob: async () => ({ kind: "artifact" }) };
    },
  };
  const run = vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/share.js"), "utf8"), scope);
  return { run, window, location, elements, selectors, requests, viewers, timelineAttachments, downloads, createdUrls, revokedUrls,
    expire() { Array.from(timers.values()).forEach(callback => callback()); } };
}

(async () => {
  const invalid = fixture({ hash: "#invalid" });
  await invalid.run;
  assert.equal(invalid.requests.length, 0, "Malformed capabilities never reach the server");
  assert.equal(invalid.elements.shareUnavailable.hidden, false);
  assert.equal(invalid.elements.sharedDownload.hidden, true);
  assert.equal(invalid.selectors[".shared-viewer"].hidden, true);

  const revoked = fixture({ metadataStatus: 410 });
  await revoked.run;
  assert.equal(revoked.elements.shareUnavailable.hidden, false);
  assert.equal(revoked.viewers.length, 0);
  assert.equal(revoked.requests[0].options.signal.aborted, true);
  const serverFailure = fixture({ metadataStatus: 503 });
  await serverFailure.run;
  assert.equal(serverFailure.elements.shareUnavailableTitle.textContent, "Unable to load this scene.", "A server failure must not claim the link expired");

  const unsupported = fixture({ webglFailure: true });
  await unsupported.run;
  assert.equal(unsupported.elements.shareUnavailable.hidden, true, "A valid share remains valid without WebGL");
  assert.equal(unsupported.elements.shareTitle.textContent, "office.glb");
  assert.equal(unsupported.elements.shareLicense.hidden, false);
  assert.equal(unsupported.elements.shareLicense.textContent, "Usage rights unconfirmed");
  assert.equal(unsupported.elements.sharedDownload.hidden, false);
  assert.equal(unsupported.selectors[".shared-viewer .viewport-wrap"].hidden, true);
  assert.equal(unsupported.requests.length, 1, "WebGL failure doesn't waste a preview transfer");
  let skipPrevented = false;
  unsupported.elements.sharedSkipLink.click({ preventDefault() { skipPrevented = true; } });
  if (!skipPrevented) unsupported.location.hash = "#shareTitle";
  assert.equal(skipPrevented, true, "Keyboard skip navigation must prevent a capability-fragment replacement");
  assert.equal(unsupported.elements.shareTitle.focused, true);
  assert.equal(unsupported.location.hash, `#${token}`, "A reload after skipping still has its share capability");
  await unsupported.elements.sharedDownload.click();
  assert.equal(unsupported.downloads.length, 1, "A valid file can still be downloaded when its preview fails");
  assert.equal(unsupported.downloads[0].filename, "office.glb");
  assert.equal(unsupported.location.hash, `#${token}`);
  for (const request of unsupported.requests) {
    assert.equal(request.url.includes(token), false, "Capabilities never enter request URLs");
    assert.equal(request.options.headers.Authorization, `Bearer ${token}`);
    assert.equal(request.options.credentials, "omit");
  }
  unsupported.window.listeners.pagehide();
  assert.equal(unsupported.elements.sharedDownload.hidden, true);
  assert.deepEqual(unsupported.revokedUrls, unsupported.createdUrls, "Private download blobs are released on page exit");

  const rendering = fixture({ renderFailure: true });
  await rendering.run;
  assert.equal(rendering.viewers[0].destroyed, true);
  assert.equal(rendering.elements.sharedDownload.hidden, false);
  assert.equal(rendering.elements.shareUnavailable.hidden, true);
  assert.deepEqual(rendering.revokedUrls, rendering.createdUrls);
  const cc0 = fixture({ licenseId: "CC0-1.0" });
  await cc0.run;
  assert.equal(cc0.elements.shareLicense.textContent, "CC0-1.0", "Known license identifiers remain unchanged");
  cc0.window.listeners.pagehide();
  const artifactRevoked = fixture({ contentStatus: 410 });
  await artifactRevoked.run;
  assert.equal(artifactRevoked.viewers[0].destroyed, true);
  assert.equal(artifactRevoked.elements.sharedDownload.hidden, true, "A revoked content response closes the share immediately");
  assert.equal(artifactRevoked.elements.shareUnavailable.hidden, false);
  assert.equal(artifactRevoked.elements.shareLicense.hidden, true);

  const expiring = fixture({ pendingDownload: true });
  await expiring.run;
  assert.equal(expiring.timelineAttachments.at(-1), expiring.viewers[0]);
  const pending = expiring.elements.sharedDownload.click();
  await settle();
  expiring.expire();
  await pending;
  assert.equal(expiring.requests.at(-1).options.signal.aborted, true, "Expiry cancels a pending capability request");
  assert.equal(expiring.viewers[0].loadController.signal.aborted, true, "Expiry also tears down the active preview");
  assert.equal(expiring.timelineAttachments.at(-1), null);
  assert.equal(expiring.elements.sharedDownload.hidden, true);
  assert.equal(expiring.elements.shareLicense.hidden, true);
  assert.equal(expiring.elements.shareUnavailable.hidden, false);
  assert.equal(expiring.selectors[".shared-viewer"].hidden, true);
  assert.equal(expiring.downloads.length, 0, "An expired request cannot produce a downloadable blob");
  assert.deepEqual(expiring.revokedUrls, expiring.createdUrls);
  console.log("shared scene failure and expiry behavior passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
