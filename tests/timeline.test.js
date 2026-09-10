"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
function element() {
  return {
    children: [], listeners: {}, attrs: {}, value: 0,
    addEventListener(name, fn, options) {
      this.listeners[name] = fn;
      options?.signal.addEventListener("abort", () => delete this.listeners[name]);
    },
    setAttribute(key, value) { this.attrs[key] = value; },
    append(...children) { this.children.push(...children); },
    replaceChildren() { this.children = []; },
  };
}
const controls = Object.fromEntries([".filmstrip", 'input[type="range"]', ".frame-counter", ".play-path", ".show-all"].map(key => [key, element()]));
const root = { ...element(), querySelector: key => controls[key] };
let now = 0, nextId = 0;
const scheduled = new Map();
const scope = { window: {}, document: {createElement: element}, AbortController,
  performance: {now: () => now},
  requestAnimationFrame(fn) { const id = ++nextId; scheduled.set(id, fn); return id; },
  cancelAnimationFrame(id) { scheduled.delete(id); },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/timeline.js"), "utf8"), scope);
const selected = [];
const viewer = {canvas: element(), trace: {frames: [0, 1, 3].map(time => ({time, thumbnail: "fixture"}))}, setFrame: index => selected.push(index), reset: () => selected.push("all")};
const timeline = new scope.window.SceneTimeline(root, element());
function tick(time) {
  now = time;
  const callbacks = Array.from(scheduled.values());
  scheduled.clear();
  callbacks.forEach(fn => fn(time));
}
timeline.attach(viewer);
timeline.toggle();
assert.equal(selected.at(-1), 0, "Play from whole space starts at the first captured frame");
tick(1500);
assert.equal(selected.at(-1), 1, "Playback follows source timestamps, not frame count");
tick(3100);
assert.equal(selected.at(-1), 2);
assert.equal(scheduled.size, 0, "The final frame stops playback");
timeline.toggle();
assert.equal(scheduled.size, 1);
viewer.canvas.listeners.viewmode({detail: "FREE ORBIT"});
assert.equal(scheduled.size, 0, "Manual exploration stops camera playback");
timeline.wholeSpace();
assert.equal(selected.at(-1), "all");
timeline.toggle();
timeline.attach(null);
assert.equal(scheduled.size, 0, "Changing identity or scene cancels pending animation");
assert.equal(root.hidden, true);
assert.equal(controls[".filmstrip"].children.length, 0, "Private frame thumbnails are cleared");
assert.equal(viewer.canvas.listeners.viewmode, undefined);
console.log("timeline behavior passed");
