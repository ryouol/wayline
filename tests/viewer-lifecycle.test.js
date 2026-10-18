"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

// Model the browser invariant: losing a context permanently affects that
// canvas until restoration. A new canvas receives an independent context.
let mounted;
function canvas(attributes = { id: "sceneCanvas", tabindex: "0", "aria-label": "3D scene" }) {
  const events = new Map();
  const gl = {
    lost: false,
    isContextLost: () => gl.lost,
    getExtension: () => ({ loseContext: () => { gl.lost = true; events.get("webglcontextlost")?.(); } }),
  };
  return {
    attributes,
    addEventListener(name, listener, { signal } = {}) {
      events.set(name, listener);
      signal?.addEventListener("abort", () => events.delete(name));
    },
    dispatchEvent(event) { events.get(event.type)?.(event); },
    ownerDocument: { documentElement: { dataset: {} } },
    getContext: () => gl,
    cloneNode: () => canvas({ ...attributes }),
    replaceWith: (replacement) => { mounted = replacement; },
  };
}
const listeners = new Set();
const scope = {
  window: { addEventListener(name, listener, { signal }) {
    assert.equal(name, "wayline-theme-change");
    listeners.add(listener);
    signal.addEventListener("abort", () => listeners.delete(listener));
  } }, AbortController, performance,
  CustomEvent: class { constructor(type) { this.type = type; } },
  ResizeObserver: class { observe() {} disconnect() {} },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,
  "../lingbot_map/workspace/static/viewer.js"), "utf8"), scope);
const Viewer = scope.window.PointCloudViewer;
Viewer.prototype.initializeGraphics = function () {
  assert.equal(this.gl.lost, false, "A new scene must not reuse a lost context");
};
let controlsBound = 0;
Viewer.prototype.bindControls = function () { controlsBound += 1; };
mounted = canvas();
const original = mounted;
const status = { textContent: "" };
const first = new Viewer(mounted, status);
first.loadController = new AbortController();
first.destroy();
assert.equal(first.gl.lost, true, "Private graphics must still be released");
assert.equal(first.events.signal.aborted, true);
assert.equal(first.loadController.signal.aborted, true);
assert.notEqual(mounted, original);
assert.deepEqual(mounted.attributes, original.attributes);
const second = new Viewer(mounted, status);
assert.equal(second.theme, "light");
let redraws = 0;
second.draw = () => { redraws += 1; };
listeners.forEach(listener => listener({ detail: { theme: "dark" } }));
assert.equal(second.theme, "dark");
assert.equal(redraws, 1, "Only the mounted viewer responds to theme changes");
second.setOrbit(0.2, 0.1, 3);
assert.equal(second.yaw, 0.2);
second.setOrbit(NaN, 0, 3);
assert.equal(second.yaw, 0.2, "Invalid animation input cannot corrupt the camera");
const secondCanvas = mounted;
first.destroy();
assert.equal(mounted, secondCanvas, "Repeated teardown must not replace the active scene");
second.destroy();
assert.equal(listeners.size, 0, "Disposal removes global theme listeners");
assert.doesNotThrow(() => new Viewer(mounted, status, { interactive: false, pointSize: 1.8 }));
assert.equal(controlsBound, 2, "A presentation canvas never captures page scrolling or keyboard input");

(async () => {
  const interrupted = new Viewer(canvas(), status);
  interrupted.count = 100;
  status.textContent = "100 points loaded.";
  interrupted.readiness = { browserReadySeconds: 1 };
  interrupted.loadController = new AbortController();
  const pending = interrupted.loadController;
  let unavailable = 0;
  interrupted.canvas.addEventListener("wayline-viewer-unavailable", () => { unavailable += 1; });
  interrupted.gl.getExtension("WEBGL_lose_context").loseContext();
  assert.match(status.textContent, /interrupted.*Reload/i, "Lost graphics must not keep claiming points are loaded");
  assert.equal(interrupted.count, 0);
  assert.equal(interrupted.readiness, null);
  assert.equal(pending.signal.aborted, true, "Stop a pending private scene download");
  assert.equal(unavailable, 1);
  assert.doesNotThrow(() => interrupted.draw(), "A lost context receives no graphics calls");
  await assert.rejects(interrupted.load("/private-scene"), /interrupted.*Reload/i,
    "Repeated polling cannot silently download the scene into a lost context");
  assert.equal(unavailable, 1, "Repeated loss checks do not duplicate notifications");
  const duringDownload = new Viewer(canvas(), status);
  let completeBody;
  const lateLoad = duringDownload.load("/private-scene", { prefetchedResponse: {
    ok: true, arrayBuffer: () => new Promise(resolve => { completeBody = resolve; }),
  } });
  duringDownload.gl.getExtension("WEBGL_lose_context").loseContext();
  completeBody(new ArrayBuffer(0));
  await assert.rejects(lateLoad, /interrupted.*Reload/i,
    "A late body cannot parse, upload, or report success after context loss");
  assert.equal(duringDownload.count, 0);
  duringDownload.destroy();
  interrupted.destroy();
  assert.equal(status.textContent, "Viewer closed.");
  assert.doesNotThrow(() => new Viewer(mounted, status), "Selecting a new scene gets a fresh canvas");
  console.log("viewer lifecycle and context loss passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
