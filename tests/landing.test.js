"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const settle = () => new Promise(resolve => setImmediate(resolve));

function eventTarget(values = {}) {
  return {
    ...values, listeners: {},
    addEventListener(type, listener) { this.listeners[type] = listener; },
    fire(type) { this.listeners[type]?.(); },
  };
}

function fixture({ reduced = false, saveData = false, fail = false } = {}) {
  let intersection, mutation, nextFrame = 0, top = 100;
  const animation = new Map();
  const instances = [];
  const scene = { dataset: {}, clientHeight: 600, getBoundingClientRect: () => ({ top }) };
  const landing = { hidden: false };
  const toggle = eventTarget({ attrs: {}, setAttribute(key, value) { this.attrs[key] = value; } });
  const elements = { landingScene: scene, loginView: landing, motionToggle: toggle, landingCanvas: {}, landingStatus: {} };
  const motion = eventTarget({ matches: reduced });
  const connection = eventTarget({ saveData });
  const document = eventTarget({ hidden: false, getElementById: id => elements[id] });
  const window = eventTarget({ matchMedia: () => motion, PointCloudViewer: class {
    constructor(canvas, status, options) {
      if (fail) throw new Error("WebGL unavailable");
      this.options = options;
      this.draws = [];
      this.count = 0;
      instances.push(this);
    }
    load(url) {
      assert.equal(url, "/static/landing-scene.glb");
      return new Promise((resolve, reject) => {
        this.finish = () => { this.count = 30_000; resolve(); };
        this.reject = reject;
      });
    }
    setOrbit(...camera) { this.draws.push(camera); }
    destroy() { this.destroyed = true; }
  } });
  const scope = {
    document, window, navigator: { connection },
    MutationObserver: class { constructor(callback) { mutation = callback; } observe() {} },
    IntersectionObserver: class { constructor(callback) { intersection = callback; } observe() {} },
    requestAnimationFrame(callback) { const id = ++nextFrame; animation.set(id, callback); return id; },
    cancelAnimationFrame(id) { animation.delete(id); },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/landing.js"), "utf8"), scope);
  return {
    scene, landing, toggle, motion, document, window, connection, instances, animation,
    visible(value) { intersection([{ isIntersecting: value }]); },
    hide(value) { landing.hidden = value; mutation(); },
    scroll(value) { top = value; window.fire("scroll"); },
    tick() {
      const callbacks = Array.from(animation.values());
      animation.clear();
      callbacks.forEach(callback => callback());
    },
  };
}

(async () => {
  const page = fixture();
  assert.equal(page.instances.length, 0, "No WebGL context or asset fetch before the hero is visible");
  page.visible(true);
  const abandoned = page.instances[0];
  assert.equal(abandoned.options.interactive, false, "Landing motion must leave native page scrolling alone");
  page.hide(true);
  assert.equal(abandoned.destroyed, true, "Entering the product disposes the landing context and load");
  abandoned.finish();
  await settle();
  assert.equal(page.scene.dataset.loaded, "false", "An abandoned fetch cannot reveal a stale canvas");
  page.hide(false);
  const active = page.instances[1];
  assert.notEqual(active, abandoned);
  active.finish();
  await settle();
  assert.equal(page.scene.dataset.loaded, "true");
  assert.equal(page.animation.size, 0, "A still page does not run a continuous animation loop");
  const initialDraws = active.draws.length;
  page.scroll(200);
  page.tick();
  page.scroll(1000);
  page.tick();
  assert.equal(active.draws.length, initialDraws,
    "scrolling before the hero's camera range does not redraw the same clamped viewpoint");
  assert.equal(page.animation.size, 0);
  page.window.fire("resize");
  page.tick();
  assert.equal(active.draws.length, initialDraws + 1, "resize redraws even when the viewpoint has not changed");
  assert.deepEqual(active.draws.at(-1), active.draws[0]);
  page.scroll(-300);
  for (let index = 0; index < 100 && page.animation.size; index += 1) page.tick();
  assert.equal(page.animation.size, 0, "Scroll easing settles and releases animation work");
  assert.ok(active.draws.at(-1)[0] > active.draws[0][0]);
  page.toggle.fire("click");
  assert.equal(active.destroyed, true);
  assert.equal(page.scene.dataset.loaded, "false");
  assert.equal(page.toggle.attrs["aria-pressed"], "false");
  page.scroll(-400);
  assert.equal(page.animation.size, 0, "Paused motion schedules no rendering");
  page.toggle.fire("click");
  assert.equal(page.instances.length, 3, "Resuming uses a new context instead of a disposed canvas");
  page.document.hidden = true;
  page.document.fire("visibilitychange");
  assert.equal(page.instances[2].destroyed, true);

  for (const preference of [{ reduced: true }, { saveData: true }]) {
    const restrained = fixture(preference);
    restrained.visible(true);
    assert.equal(restrained.instances.length, 0, "Motion and data preferences keep the static poster");
    assert.equal(restrained.toggle.disabled, true);
  }
  const unsupported = fixture({ fail: true });
  unsupported.visible(true);
  await settle();
  assert.equal(unsupported.scene.dataset.loaded, "false");
  assert.equal(unsupported.toggle.textContent, "Motion off");
  assert.equal(unsupported.toggle.disabled, true, "WebGL failure leaves usable static content");
  const failed = fixture();
  failed.visible(true);
  failed.instances[0].reject(new Error("Artifact unavailable"));
  await settle();
  assert.equal(failed.instances[0].destroyed, true);
  assert.equal(failed.scene.dataset.loaded, "false");
  assert.equal(failed.toggle.disabled, true);

  const beyond = fixture();
  beyond.scroll(-800);
  beyond.visible(true);
  beyond.instances[0].finish();
  await settle();
  const finalDraws = beyond.instances[0].draws.length;
  beyond.scroll(-1600);
  beyond.tick();
  assert.equal(beyond.instances[0].draws.length, finalDraws,
    "scrolling beyond the camera range also skips unchanged clamped viewpoints");
  beyond.window.fire("resize");
  beyond.tick();
  assert.equal(beyond.instances[0].draws.length, finalDraws + 1);

  const markup = fs.readFileSync(path.join(__dirname, "../lingbot_map/workspace/static/index.html"), "utf8");
  const decorative = markup.match(/<canvas\b[^>]*\bid="landingCanvas"[^>]*>/)?.[0];
  assert.ok(decorative, "the landing canvas remains present for progressive motion");
  assert.match(decorative, /aria-label="[^"]+"/, "the example has a descriptive canvas label");
  assert.match(decorative, /aria-hidden="true"/, "decorative motion does not add a duplicate screen-reader stop");
  assert.match(decorative, /tabindex="-1"/, "landing animation stays out of keyboard navigation");
  const interactive = markup.match(/<canvas\b[^>]*\bid="sceneCanvas"[^>]*>/)?.[0];
  assert.ok(interactive);
  assert.match(interactive, /aria-label="[^\"]*(?:orbit)[^\"]*(?:zoom)[^\"]*"/i,
    "the interactive viewer explains its orbit and zoom controls");
  assert.match(interactive, /tabindex="0"/, "the actual product viewer remains keyboard accessible");
  console.log("landing motion lifecycle passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
