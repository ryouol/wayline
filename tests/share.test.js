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
  webglFailure = false, renderFailure = false, contextLossOnLoad = false, pendingDownload = false, licenseId = "NOASSERTION",
  metadataFailure = null, ignoreMetadataAbort = false, ignoreDownloadAbort = false, downloadStatus = 200,
  previewResponses = [], pendingPreviewStatus = 200, ignorePreviewAbort = false } = {}) {
  const ids = ["sharedStatus", "sharedDownload", "sharedTimeline", "shareLicense", "shareTitle",
    "shareUnavailableMessage", "shareUnavailableTitle", "shareUnavailable", "sharedZoomIn",
    "sharedZoomOut", "sharedReset", "shareExpiry", "shareCommercialWarning", "sharedCanvas", "sharedSkipLink", "reloadSharedScene", "retrySharedPreview", "cancelSharedPreview"];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements.shareUnavailable.hidden = true;
  elements.sharedDownload.hidden = true;
  elements.reloadSharedScene.hidden = true;
  elements.retrySharedPreview.hidden = true;
  elements.cancelSharedPreview.hidden = true;
  const selectors = Object.fromEntries([".shared-viewer", ".shared-viewer .viewport-wrap", ".shared-viewer .viewer-help"].map(selector => [selector, element()]));
  const requests = [], viewers = [], timelineAttachments = [], downloads = [], createdUrls = [], revokedUrls = [];
  const timers = new Map();
  let nextTimer = 0, contentRequests = 0, releaseMetadata, releaseDownload, releasePreview;
  const metadata = {
    artifact: { filename: "office.glb", licenseId, contentUrl: "/api/public/share/content" },
    expiresAt: Math.ceil(Date.now() / 1000) + 60,
    researchOnly: true, commercialWarning: "Research preview.",
  };
  const location = { hash, reloadCount: 0, reload() { this.reloadCount += 1; } };
  const stall = (signal, value) => new Promise((resolve, reject) => {
    releaseMetadata = () => resolve(value);
    if (!ignoreMetadataAbort) signal.addEventListener("abort", () => reject(new Error("Aborted")));
  });
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
        await options.prefetchedResponse.arrayBuffer();
        if (renderFailure) throw new Error("Unsupported geometry.");
        this.contextLost = contextLossOnLoad;
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
    setTimeout(callback, delay) { const id = ++nextTimer; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    async fetch(url, options) {
      requests.push({ url, options });
      if (url === "/api/public/share") {
        if (metadataFailure === "network") throw new Error("Failed to fetch");
        const response = { ok: metadataStatus === 200, status: metadataStatus, json: async () => {
          if (metadataFailure === "json") throw new SyntaxError("Truncated JSON");
          if (metadataFailure === "body") return stall(options.signal, metadata);
          return metadata;
        } };
        return metadataFailure === "headers" ? stall(options.signal, response) : response;
      }
      assert.equal(url, "/api/public/share/content");
      contentRequests += 1;
      if (pendingDownload && contentRequests === 2) {
        const hold = value => new Promise((resolve, reject) => {
          releaseDownload = () => resolve(value);
          if (!ignoreDownloadAbort) options.signal.addEventListener("abort", () => reject(new Error("Aborted")));
        });
        const response = { ok: downloadStatus === 200, status: downloadStatus,
          blob: async () => pendingDownload === "body" ? hold({ kind: "artifact" }) : { kind: "artifact" } };
        return pendingDownload === "body" ? response : hold(response);
      }
      const outcome = previewResponses[contentRequests - 1];
      if (outcome === "network") throw new Error("Failed to fetch");
      const holdPreview = value => new Promise((resolve, reject) => {
        releasePreview = () => resolve(value);
        if (!ignorePreviewAbort) options.signal.addEventListener("abort", () => reject(new Error("Aborted")));
      });
      const responseStatus = typeof outcome === "number" ? outcome : outcome === "headers" ? pendingPreviewStatus : contentStatus;
      const response = { ok: responseStatus === 200, status: responseStatus,
        blob: async () => ({ kind: "artifact" }),
        arrayBuffer: async () => {
          if (outcome === "body-failure") throw new Error("Truncated body");
          if (outcome === "body") return holdPreview(new ArrayBuffer(0));
          return new ArrayBuffer(0);
        } };
      return outcome === "headers" ? holdPreview(response) : response;
    },
  };
  const run = vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/share.js"), "utf8"), scope);
  return { run, window, location, elements, selectors, requests, viewers, timelineAttachments, downloads, createdUrls, revokedUrls,
    timers, releaseMetadata: () => releaseMetadata(), releaseDownload: () => releaseDownload(), releasePreview: () => releasePreview(),
    capturePreviewRelease: () => releasePreview,
    deadline() { Array.from(timers.values()).filter(timer => timer.delay === 15000).forEach(timer => timer.callback()); },
    expire() { Array.from(timers.values()).filter(timer => timer.delay !== 15000).forEach(timer => timer.callback()); } };
}

(async () => {
  const invalid = fixture({ hash: "#invalid" });
  await invalid.run;
  assert.equal(invalid.requests.length, 0, "Malformed capabilities never reach the server");
  assert.equal(invalid.elements.shareUnavailable.hidden, false);
  assert.equal(invalid.elements.sharedDownload.hidden, true);
  assert.equal(invalid.selectors[".shared-viewer"].hidden, true);
  assert.equal(invalid.elements.reloadSharedScene.hidden, true);

  for (const metadataStatus of [401, 403, 404, 410]) {
    const closed = fixture({ metadataStatus }); await closed.run;
    assert.equal(closed.elements.reloadSharedScene.hidden, true, "Denied capabilities do not offer temporary-failure recovery");
    assert.equal(closed.timers.size, 0);
  }
  for (const metadataFailure of ["network", "json", "headers", "body"]) {
    const failed = fixture({ metadataFailure });
    await settle();
    if (["headers", "body"].includes(metadataFailure)) failed.deadline();
    await failed.run;
    assert.equal(failed.elements.shareUnavailable.hidden, false);
    assert.equal(failed.elements.reloadSharedScene.hidden, false);
    assert.equal(failed.elements.shareUnavailableTitle.textContent, "Unable to load this scene.");
    assert.equal(failed.requests[0].options.signal.aborted, true);
    assert.equal(failed.timers.size, 0);
    assert.equal(failed.requests.length, 1, "Failures never automatically retry or fetch content");
    failed.elements.reloadSharedScene.click();
    assert.equal(failed.location.reloadCount, 1);
    assert.equal(failed.location.hash, `#${token}`, "Reload retains the capability fragment");
    assert.equal(failed.requests[0].url.includes(token), false);
    assert.equal(failed.requests[0].options.headers.Authorization, `Bearer ${token}`);
    assert.equal(failed.requests[0].options.credentials, "omit");
  }
  for (const [metadataFailure, exit] of [["body", false], ["body", true], ["headers", false], ["headers", true]]) {
    const late = fixture({ metadataFailure, metadataStatus: metadataFailure === "headers" ? 410 : 200, ignoreMetadataAbort: true });
    await settle();
    if (exit) late.window.listeners.pagehide(); else late.deadline();
    late.releaseMetadata(); await late.run;
    assert.equal(late.elements.shareUnavailable.hidden, exit, "Late responses must not change a timeout or page-exit result");
    assert.equal(late.viewers.length, 0);
    assert.equal(late.elements.sharedDownload.hidden, true);
    assert.equal(late.timers.size, 0);
  }

  const revoked = fixture({ metadataStatus: 410 });
  await revoked.run;
  assert.equal(revoked.elements.shareUnavailable.hidden, false);
  assert.equal(revoked.viewers.length, 0);
  assert.equal(revoked.requests[0].options.signal.aborted, true);
  const serverFailure = fixture({ metadataStatus: 503 });
  await serverFailure.run;
  assert.equal(serverFailure.elements.shareUnavailableTitle.textContent, "Unable to load this scene.", "A server failure must not claim the link expired");
  assert.equal(serverFailure.elements.reloadSharedScene.hidden, false);

  const unsupported = fixture({ webglFailure: true });
  await unsupported.run;
  assert.equal(unsupported.elements.shareUnavailable.hidden, true, "A valid share remains valid without WebGL");
  assert.equal(unsupported.elements.shareTitle.textContent, "office.glb");
  assert.equal(unsupported.elements.shareLicense.hidden, false);
  assert.equal(unsupported.elements.shareLicense.textContent, "Usage rights unconfirmed");
  assert.equal(unsupported.elements.sharedDownload.hidden, false);
  assert.equal(unsupported.selectors[".shared-viewer .viewport-wrap"].hidden, true);
  assert.equal(unsupported.requests.length, 1, "WebGL failure doesn't waste a preview transfer");
  unsupported.deadline();
  assert.equal(unsupported.elements.shareUnavailable.hidden, true, "Successful metadata clears its deadline");
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
  const firstDraw = fixture({ contextLossOnLoad: true }); await firstDraw.run;
  assert.equal(firstDraw.elements.retrySharedPreview.hidden, false, "Context loss during the first draw cannot hide recovery");
  assert.equal(firstDraw.viewers[0].destroyed, true);
  assert.equal(firstDraw.timelineAttachments.at(-1), null);

  for (const failure of [502, "network", "body-failure"]) {
    const recoverable = fixture({ previewResponses: [failure, 200] }); await recoverable.run;
    assert.equal(recoverable.elements.retrySharedPreview.hidden, false, "A failed preview offers recovery without reloading the page");
    assert.equal(recoverable.requests.length, 2, "Failed previews never retry automatically");
    assert.equal(recoverable.viewers[0].destroyed, true);
    await recoverable.elements.retrySharedPreview.click();
    assert.equal(recoverable.requests.length, 3, "An explicit retry requests only the artifact");
    assert.equal(recoverable.location.reloadCount, 0);
    assert.equal(recoverable.location.hash, `#${token}`);
    assert.equal(recoverable.elements.retrySharedPreview.hidden, true);
    assert.equal(recoverable.selectors[".shared-viewer .viewport-wrap"].hidden, false);
    assert.equal(recoverable.selectors[".shared-viewer .viewer-help"].hidden, false);
    assert.equal(recoverable.elements.sharedCanvas.focused, true, "Keyboard focus moves into the restored viewer");
    assert.equal(recoverable.timelineAttachments.at(-1), recoverable.viewers[1]);
    assert.equal(recoverable.elements.sharedDownload.hidden, false);
    assert.equal(recoverable.elements.shareCommercialWarning.textContent, "Research preview.");
    for (const r of recoverable.requests) {
      assert.equal(r.url.includes(token), false);
      assert.equal(r.options.credentials, "omit");
      assert.equal(r.options.headers.Authorization, `Bearer ${token}`);
    }
  }
  for (const stage of ["headers", "body"]) {
    const cancellable = fixture({ previewResponses: [stage, 200] }); await settle();
    assert.equal(cancellable.elements.cancelSharedPreview.hidden, false, "Pending artifact headers and bodies need a cancel action");
    await cancellable.elements.cancelSharedPreview.click();
    await cancellable.elements.cancelSharedPreview.click();
    await cancellable.run;
    assert.equal(cancellable.requests[1].options.signal.aborted, true);
    assert.equal(cancellable.requests[0].options.signal.aborted, false, "Cancelling preview preserves the share");
    assert.equal(cancellable.viewers[0].destroyed, true);
    assert.equal(cancellable.timelineAttachments.at(-1), null);
    assert.equal(cancellable.elements.cancelSharedPreview.hidden, true);
    assert.equal(cancellable.elements.retrySharedPreview.hidden, false);
    assert.equal(cancellable.elements.retrySharedPreview.disabled, false);
    assert.equal(cancellable.elements.retrySharedPreview.focused, true);
    assert.match(cancellable.elements.sharedStatus.textContent, /Preview cancelled/);
    assert.equal(cancellable.elements.sharedDownload.hidden, false);
    assert.equal(cancellable.requests.length, 2, "Cancel never retries automatically");
    await cancellable.elements.retrySharedPreview.click();
    assert.equal(cancellable.requests.length, 3);
    assert.equal(cancellable.elements.cancelSharedPreview.hidden, true);
    assert.equal(cancellable.elements.retrySharedPreview.hidden, true);
    assert.equal(cancellable.elements.sharedCanvas.focused, true);
    assert.equal(cancellable.timelineAttachments.at(-1), cancellable.viewers[1]);
    assert.equal(cancellable.location.reloadCount, 0);
  }
  for (const stage of ["headers", "body"]) {
    const late = fixture({ previewResponses: [stage, "body"], ignorePreviewAbort: true, pendingPreviewStatus: 410 });
    await settle();
    const releaseOld = late.capturePreviewRelease();
    await late.elements.cancelSharedPreview.click();
    const newer = late.elements.retrySharedPreview.click(); await settle();
    releaseOld(); await late.run;
    assert.equal(late.elements.shareUnavailable.hidden, true, "A cancelled late 410 cannot close a valid newer attempt");
    assert.equal(late.elements.cancelSharedPreview.hidden, false, "Old completion cannot clear the newer cancel action");
    assert.equal(late.elements.retrySharedPreview.disabled, true);
    assert.equal(late.viewers[1].destroyed, undefined);
    late.releasePreview(); await newer;
    assert.equal(late.timelineAttachments.at(-1), late.viewers[1]);
    assert.equal(late.elements.cancelSharedPreview.hidden, true);
  }
  {
    const independent = fixture({ previewResponses: ["body"], pendingDownload: "body" }); await settle();
    const downloading = independent.elements.sharedDownload.click(); await settle();
    await independent.elements.cancelSharedPreview.click(); await independent.run;
    assert.equal(independent.requests[2].options.signal.aborted, false, "Preview cancellation must not abort an explicit download");
    independent.releaseDownload(); await downloading;
    assert.equal(independent.downloads.length, 1);
    assert.equal(independent.elements.retrySharedPreview.hidden, false);
  }
  for (const exit of [false, true]) {
    const closed = fixture({ previewResponses: ["body"], ignorePreviewAbort: true }); await settle();
    if (exit) closed.window.listeners.pagehide(); else closed.expire();
    const status = closed.elements.sharedStatus.textContent;
    closed.releasePreview(); await closed.run;
    assert.equal(closed.requests[1].options.signal.aborted, true);
    assert.equal(closed.elements.cancelSharedPreview.hidden, true);
    assert.equal(closed.elements.retrySharedPreview.hidden, true);
    assert.equal(closed.elements.sharedStatus.textContent, status);
  }
  for (const recovery of ["retry", "revoked", "expired", "exit"]) {
    const interrupted = fixture({ previewResponses: [200, recovery === "revoked" ? 410 : 200] });
    await interrupted.run;
    const lost = interrupted.elements.sharedCanvas.listeners["wayline-viewer-unavailable"];
    assert.equal(typeof lost, "function", "Loaded shared previews must expose graphics-interruption recovery");
    interrupted.viewers[0].contextLost = true;
    lost();
    assert.equal(interrupted.viewers[0].destroyed, true);
    assert.equal(interrupted.timelineAttachments.at(-1), null);
    assert.equal(interrupted.elements.retrySharedPreview.hidden, false);
    assert.equal(interrupted.elements.sharedDownload.hidden, false);
    assert.match(interrupted.elements.sharedStatus.textContent, /interrupted.*Retry/);
    assert.equal(interrupted.requests.length, 2, "Graphics loss cannot silently repeat a capability transfer");
    if (recovery === "expired") interrupted.expire();
    if (recovery === "exit") interrupted.window.listeners.pagehide();
    await interrupted.elements.retrySharedPreview.click();
    assert.equal(interrupted.elements.retrySharedPreview.hidden, true);
    assert.equal(interrupted.location.reloadCount, 0);
    assert.equal(interrupted.location.hash, `#${token}`);
    const status = interrupted.elements.sharedStatus.textContent;
    lost();
    assert.equal(interrupted.elements.sharedStatus.textContent, status, "Stale graphics events cannot overwrite recovered or closed shares");
    if (recovery === "retry") {
      assert.equal(interrupted.elements.sharedCanvas.focused, true);
      assert.equal(interrupted.timelineAttachments.at(-1), interrupted.viewers[1]);
      interrupted.elements.sharedCanvas.listeners["wayline-viewer-unavailable"]();
      assert.equal(interrupted.elements.retrySharedPreview.hidden, false);
    } else {
      assert.equal(interrupted.elements.sharedDownload.hidden, true);
      assert.equal(interrupted.timelineAttachments.at(-1), null);
    }
    assert.equal(interrupted.requests.length, ["retry", "revoked"].includes(recovery) ? 3 : 2);
  }
  for (const stage of ["headers", "body"]) {
    const busy = fixture({ previewResponses: [502, stage] }); await busy.run;
    const attempt = busy.elements.retrySharedPreview.click(); await settle();
    assert.equal(busy.elements.retrySharedPreview.disabled, true);
    await busy.elements.retrySharedPreview.click();
    assert.equal(busy.requests.length, 3, "Repeated clicks cannot overlap preview transfers");
    await busy.elements.sharedDownload.click();
    assert.equal(busy.downloads.length, 1, "Downloads remain usable during preview recovery");
    busy.releasePreview(); await attempt;
    assert.equal(busy.elements.retrySharedPreview.hidden, true);
  }
  for (const code of [401, 403, 404, 410]) {
    const denied = fixture({ previewResponses: [502, code] }); await denied.run;
    await denied.elements.retrySharedPreview.click();
    assert.equal(denied.elements.shareUnavailable.hidden, false);
    assert.equal(denied.elements.retrySharedPreview.hidden, true);
    assert.equal(denied.elements.sharedDownload.hidden, true);
    assert.equal(denied.timelineAttachments.at(-1), null);
    await denied.elements.retrySharedPreview.click();
    assert.equal(denied.requests.length, 3);
  }
  for (const stage of ["headers", "body"]) {
    for (const exit of [false, true]) {
      const late = fixture({ previewResponses: [502, stage], ignorePreviewAbort: true,
        pendingPreviewStatus: 410 }); await late.run;
      const attempt = late.elements.retrySharedPreview.click(); await settle();
      if (exit) late.window.listeners.pagehide(); else late.expire();
      const finalStatus = late.elements.sharedStatus.textContent;
      late.releasePreview(); await attempt;
      assert.equal(late.requests.at(-1).options.signal.aborted, true);
      assert.equal(late.viewers[1].destroyed, true);
      assert.equal(late.timelineAttachments.at(-1), null);
      assert.equal(late.elements.retrySharedPreview.hidden, true);
      assert.equal(late.elements.sharedDownload.hidden, true);
      assert.equal(late.elements.sharedStatus.textContent, finalStatus, "Late completion cannot revive a closed preview");
      assert.equal(late.elements.sharedCanvas.focused, undefined);
    }
  }
  await rendering.elements.retrySharedPreview.click();
  assert.equal(rendering.elements.retrySharedPreview.hidden, false, "Repeated rendering failure keeps manual recovery available");
  assert.equal(rendering.viewers[1].destroyed, true);
  assert.equal(rendering.elements.sharedDownload.hidden, false);
  const html = fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/share.html"), "utf8");
  assert.match(html, /<button[^>]+id="retrySharedPreview"[^>]+type="button"[^>]+hidden>Retry preview<\/button>/);
  assert.match(html, /<button[^>]+id="cancelSharedPreview"[^>]+type="button"[^>]+hidden>Cancel preview<\/button>/);
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

  for (const pendingDownload of [true, "body"]) {
    const cancellable = fixture({ pendingDownload }); await cancellable.run;
    const pending = cancellable.elements.sharedDownload.click(); await settle();
    assert.equal(cancellable.elements.sharedDownload.textContent, "Cancel download");
    assert.notEqual(cancellable.elements.sharedDownload.disabled, true);
    assert.notEqual(cancellable.requests.at(-1).options.signal, cancellable.requests[1].options.signal,
      "Downloads have their own cancellation signal");
    await cancellable.elements.sharedDownload.click(); await pending;
    assert.equal(cancellable.requests.at(-1).options.signal.aborted, true);
    assert.equal(cancellable.requests[1].options.signal.aborted, false, "Cancelling a download preserves the preview request");
    assert.equal(cancellable.viewers[0].destroyed, undefined);
    assert.equal(cancellable.elements.shareUnavailable.hidden, true);
    assert.equal(cancellable.elements.sharedDownload.textContent, "Download GLB");
    assert.match(cancellable.elements.sharedStatus.textContent, /Download cancelled/);
    assert.equal(cancellable.downloads.length, 0);
    assert.equal(cancellable.createdUrls.length, 0);
    assert.equal(cancellable.requests.length, 3, "Cancel does not send a retry or a separate cancellation request");
    await cancellable.elements.sharedDownload.click();
    assert.equal(cancellable.requests.length, 4, "Only an explicit retry starts a new transfer");
    assert.equal(cancellable.downloads.length, 1);
    assert.match(cancellable.elements.sharedStatus.textContent, /Download ready/);
    for (const r of cancellable.requests) {
      assert.equal(r.url.includes(token), false);
      assert.equal(r.options.credentials, "omit");
      assert.equal(r.options.headers.Authorization, `Bearer ${token}`);
    }
  }
  for (const pendingDownload of [true, "body"]) {
    const late = fixture({ pendingDownload, ignoreDownloadAbort: true, downloadStatus: pendingDownload === true ? 410 : 200 });
    await late.run;
    const pending = late.elements.sharedDownload.click(); await settle();
    await late.elements.sharedDownload.click(); late.releaseDownload(); await pending;
    assert.equal(late.downloads.length, 0, "A cancelled response never becomes a browser download");
    assert.equal(late.createdUrls.length, 0);
    assert.equal(late.elements.shareUnavailable.hidden, true, "A cancelled request's late 410 does not close the preview");
    assert.equal(late.viewers[0].destroyed, undefined);
  }
  const leaving = fixture({ pendingDownload: "body" }); await leaving.run;
  const leavingDownload = leaving.elements.sharedDownload.click(); await settle();
  leaving.window.listeners.pagehide(); await leavingDownload;
  assert.equal(leaving.requests.at(-1).options.signal.aborted, true);
  assert.equal(leaving.elements.sharedDownload.hidden, true);
  assert.equal(leaving.downloads.length, 0);

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
  assert.equal(expiring.elements.reloadSharedScene.hidden, true, "Expiry does not offer temporary-failure recovery");
  assert.equal(expiring.selectors[".shared-viewer"].hidden, true);
  assert.equal(expiring.downloads.length, 0, "An expired request cannot produce a downloadable blob");
  assert.deepEqual(expiring.revokedUrls, expiring.createdUrls);
  console.log("shared scene failure and expiry behavior passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
