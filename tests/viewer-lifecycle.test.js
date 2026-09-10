"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

// Model the browser invariant: losing a context permanently affects that
// canvas until restoration. A new canvas receives an independent context.
let mounted;
function canvas(attributes = { id: "sceneCanvas", tabindex: "0", "aria-label": "3D scene" }) {
  const gl = {
    lost: false,
    getExtension: () => ({ loseContext: () => { gl.lost = true; } }),
  };
  return {
    attributes,
    getContext: () => gl,
    cloneNode: () => canvas({ ...attributes }),
    replaceWith: (replacement) => { mounted = replacement; },
  };
}
const scope = {
  window: {}, AbortController,
  ResizeObserver: class { observe() {} disconnect() {} },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,
  "../lingbot_map/workspace/static/viewer.js"), "utf8"), scope);
const Viewer = scope.window.PointCloudViewer;
Viewer.prototype.initializeGraphics = function () {
  assert.equal(this.gl.lost, false, "A new scene must not reuse a lost context");
};
Viewer.prototype.bindControls = function () {};
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
const secondCanvas = mounted;
first.destroy();
assert.equal(mounted, secondCanvas, "Repeated teardown must not replace the active scene");
second.destroy();
assert.doesNotThrow(() => new Viewer(mounted, status));
console.log("viewer lifecycle passed");
