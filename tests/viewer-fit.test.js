"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let resize, uploadedPositions, boundBuffer;
const gl = new Proxy({
  bindBuffer(type, buffer) { boundBuffer = buffer; },
  bufferData(type, values) { if (boundBuffer === "positions") uploadedPositions = values; },
}, { get: (target, key) => target[key] || (() => {}) });
const canvas = {
  clientWidth: 358, clientHeight: 490,
  ownerDocument: { documentElement: { dataset: {} } },
  getContext: () => gl, addEventListener() {}, dispatchEvent() {},
};
const scope = {
  window: { addEventListener() {}, devicePixelRatio: 1 }, AbortController, TextDecoder,
  CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
  ResizeObserver: class { constructor(callback) { resize = callback; } observe() {} },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/viewer.js"), "utf8"), scope);
const Viewer = scope.window.PointCloudViewer;
Viewer.prototype.initializeGraphics = function () {
  this.locations = {};
  this.positionBuffer = "positions";
  this.colorBuffer = "colors";
  this.pathBuffer = "path";
};

function assertSceneFits(viewer) {
  let horizontal = 0, vertical = 0;
  const cy = Math.cos(viewer.yaw), sy = Math.sin(viewer.yaw);
  const cp = Math.cos(viewer.pitch), sp = Math.sin(viewer.pitch);
  const focal = 1 / Math.tan(Math.PI / 8), aspect = canvas.clientWidth / canvas.clientHeight;
  // Project the actual uploaded scene, independently of the box-fit calculation.
  for (let index = 0; index < uploadedPositions.length; index += 3) {
    const [x, y, z] = uploadedPositions.subarray(index, index + 3);
    const viewX = x*cy - z*sy;
    const viewY = -x*sp*sy + y*cp - z*sp*cy;
    const depth = viewer.distance - (x*cp*sy + y*sp + z*cp*cy);
    assert.ok(depth > 0, "Every point remains in front of the orbit camera");
    horizontal = Math.max(horizontal, Math.abs(viewX*focal/(depth*aspect)));
    vertical = Math.max(vertical, Math.abs(viewY*focal/depth));
  }
  assert.ok(horizontal < 0.9, `Scene clips horizontally: ${horizontal}`);
  assert.ok(vertical < 0.9, `Scene clips vertically: ${vertical}`);
}

(async () => {
  const viewer = new Viewer(canvas, {});
  const content = fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/landing-scene.glb"));
  await viewer.load("/static/landing-scene.glb", {
    prefetchedResponse: { ok: true, arrayBuffer: async () => content.buffer.slice(content.byteOffset, content.byteOffset + content.byteLength) },
  });
  assertSceneFits(viewer);
  const portraitDistance = viewer.distance;
  canvas.clientWidth = 1000;
  resize();
  assertSceneFits(viewer);
  assert.ok(viewer.distance < portraitDistance, "The initial fit follows the canvas aspect");

  viewer.setOrbit(0.2, -0.1, 2.5);
  const chosen = [viewer.yaw, viewer.pitch, viewer.distance];
  canvas.clientWidth = 358;
  resize();
  assert.deepEqual([viewer.yaw, viewer.pitch, viewer.distance], chosen, "Resize preserves an intentionally chosen orbit");
  viewer.reset();
  assertSceneFits(viewer);
  assert.equal(viewer.distance, portraitDistance, "Reset restores a complete portrait view");
  viewer.zoom(0.8);
  const zoomed = viewer.distance;
  canvas.clientWidth = 1000;
  resize();
  assert.equal(viewer.distance, zoomed, "Resize does not undo manual zoom");
  viewer.setFrame(5);
  const capturedFrame = viewer.cameraFrame;
  canvas.clientWidth = 358;
  resize();
  assert.equal(viewer.cameraFrame, capturedFrame, "Camera mode retains its original calibrated viewpoint");
  viewer.startWalk();
  viewer.moveWalk(1, 1);
  const position = [...viewer.cameraFrame.position];
  canvas.clientWidth = 1000;
  resize();
  assert.deepEqual([...viewer.cameraFrame.position], position, "Walking position survives a viewport resize");
  assert.equal(viewer.walking, true);
  console.log(`viewer portrait fit passed (${portraitDistance.toFixed(2)} distance)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
