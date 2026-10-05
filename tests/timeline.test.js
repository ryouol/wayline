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
    focus(options) { document.activeElement = this; this.focusOptions = options; },
    append(...children) { this.children.push(...children); },
    replaceChildren() { this.children = []; },
    getBoundingClientRect() { return { left: 0, right: 200 }; },
  };
}
const controls = Object.fromEntries([".filmstrip", 'input[type="range"]', ".frame-counter", ".play-path", ".show-all"].map(key => [key, element()]));
const modes = ["orbit", "camera", "walk"].map(mode => ({ ...element(), dataset: { viewMode: mode } }));
const viewport = element();
const help = element();
const root = { ...element(), querySelector: key => controls[key], closest: () => ({ querySelectorAll: () => modes,
  querySelector: key => key === ".viewer-help" ? help : viewport }) };
let now = 0, nextId = 0;
const scheduled = new Map();
const document = { ...element(), createElement: element };
const scope = { window: {}, document, AbortController,
  performance: {now: () => now},
  requestAnimationFrame(fn) { const id = ++nextId; scheduled.set(id, fn); return id; },
  cancelAnimationFrame(id) { scheduled.delete(id); },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/timeline.js"), "utf8"), scope);
const selected = [];
const viewer = {canvas: element(), trace: {frames: [0, 1, 3].map(time => ({time, thumbnail: "fixture"}))}, setFrame: index => selected.push(index), reset: () => selected.push("all")};
const timeline = new scope.window.SceneTimeline(root, element());
assert.ok(viewport.children.includes(timeline.walkControls), "Walk movement stays with the scene, including fullscreen");
assert.equal(timeline.walkControls.hidden, true, "Movement is hidden before any scene loads");
assert.equal(timeline.walkControls.attrs["aria-label"], "Walk movement");
function tick(time) {
  now = time;
  const callbacks = Array.from(scheduled.values());
  scheduled.clear();
  callbacks.forEach(fn => fn(time));
}
timeline.attach(viewer);
const strip = controls[".filmstrip"];
function pressFrame(index, key, modifiers = {}) {
  let prevented = false;
  strip.children[index].listeners.keydown?.({ key, ...modifiers, preventDefault() { prevented = true; } });
  return prevented;
}
assert.deepEqual(strip.children.map(button => button.tabIndex), [0, -1, -1], "A long frame strip has one Tab entry");
assert.equal(pressFrame(0, "ArrowRight"), true);
assert.equal(selected.at(-1), 1);
assert.equal(document.activeElement, strip.children[1]);
assert.equal(document.activeElement.focusOptions.preventScroll, true, "Frame navigation does not scroll the page vertically");
assert.deepEqual(strip.children.map(button => button.tabIndex), [-1, 0, -1]);
assert.match(viewer.canvas.attrs["aria-label"], /Camera view/);
assert.match(help.textContent, /return to Orbit/);
assert.equal(pressFrame(1, "End"), true);
assert.equal(selected.at(-1), 2);
assert.equal(pressFrame(2, "ArrowRight"), true);
assert.equal(selected.at(-1), 2, "Right at the last frame stays within the captured path");
assert.equal(pressFrame(2, "Home"), true);
assert.equal(selected.at(-1), 0);
assert.equal(pressFrame(0, "ArrowLeft"), true);
assert.equal(selected.at(-1), 0, "Left at the first frame stays within the captured path");
assert.equal(pressFrame(0, "End", { metaKey: true }), false, "Browser shortcuts are not captured");
assert.equal(pressFrame(0, "Tab"), false, "Tab can leave the strip normally");
timeline.wholeSpace();
assert.match(viewer.canvas.attrs["aria-label"], /Orbit view/);
assert.match(help.textContent, /zoom/);
strip.scrollLeft = 400;
strip.children.forEach((button, index) => {
  button.getBoundingClientRect = () => ({ left: index * 160 - strip.scrollLeft, right: index * 160 + 80 - strip.scrollLeft });
});
assert.equal(modes[0].attrs["aria-pressed"], "true");
assert.equal(modes[1].disabled, false);
timeline.toggle();
assert.equal(selected.at(-1), 0, "Play from whole space starts at the first captured frame");
assert.equal(strip.scrollLeft, 0, "Restart reveals the first thumbnail when the strip was scrolled late");
assert.equal(modes[1].attrs["aria-pressed"], "true");
assert.equal(controls[".play-path"].attrs["aria-pressed"], "true");
tick(1500);
assert.equal(selected.at(-1), 1, "Playback follows source timestamps, not frame count");
assert.equal(strip.scrollLeft, 40, "Advancing reveals the complete active thumbnail at the right edge");
assert.equal(document.activeElement, strip.children[0], "Playback updates selection without stealing keyboard focus");
assert.deepEqual(strip.children.map(button => button.tabIndex), [-1, 0, -1]);
assert.match(controls['input[type="range"]'].attrs["aria-valuetext"], /Frame 2 \/ 3/);
timeline.seek(1);
assert.equal(strip.scrollLeft, 40, "An already-visible thumbnail does not shift the strip");
tick(3100);
assert.equal(selected.at(-1), 2);
assert.equal(strip.scrollLeft, 200, "The last captured frame remains visible during playback");
assert.equal(scheduled.size, 0, "The final frame stops playback");
assert.equal(controls[".play-path"].attrs["aria-pressed"], "false");
timeline.toggle();
assert.equal(scheduled.size, 1);
pressFrame(0, "ArrowRight");
assert.equal(scheduled.size, 0, "Choosing a frame by keyboard stops camera playback");
assert.equal(selected.at(-1), 1);
timeline.toggle();
viewer.canvas.listeners.viewmode({detail: "FREE ORBIT"});
assert.equal(scheduled.size, 0, "Manual exploration stops camera playback");
timeline.wholeSpace();
assert.equal(selected.at(-1), "all");
assert.equal(modes[0].attrs["aria-pressed"], "true");
viewer.canvas.listeners.viewmode({detail: "WALK VIEW"});
assert.equal(modes[2].attrs["aria-pressed"], "true");
assert.equal(timeline.walkControls.hidden, false);
assert.match(help.textContent, /W A S D/);
assert.doesNotMatch(help.textContent, /arrows? keys to orbit/);
assert.match(viewer.canvas.attrs["aria-label"], /Walk view/);
timeline.toggle();
document.hidden = true;
document.listeners.visibilitychange();
assert.equal(scheduled.size, 0, "A hidden page does not keep replaying source frames");
document.hidden = false;
timeline.toggle();
timeline.attach(null);
assert.equal(scheduled.size, 0, "Changing identity or scene cancels pending animation");
assert.equal(root.hidden, true);
assert.equal(timeline.walkControls.hidden, true, "Detached scenes hide movement outside the timeline");
assert.equal(controls[".filmstrip"].children.length, 0, "Private frame thumbnails are cleared");
assert.equal(viewer.canvas.listeners.viewmode, undefined);
assert.ok(modes.every(button => button.disabled), "Detached scenes cannot leave active mode controls");
timeline.attach({ ...viewer, trace: null });
assert.equal(modes[0].disabled, false);
assert.equal(modes[1].disabled, true, "Synthetic scenes have no camera replay");
assert.equal(modes[2].disabled, true, "Synthetic scenes have no captured viewpoint for walking");
console.log("timeline behavior passed");
