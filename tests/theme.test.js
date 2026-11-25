"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require.resolve("../lingbot_map/workspace/static/theme.js"), "utf8");
const key = "wayline-appearance-v1";

function harness({ saved, systemDark = false, storageBlocked = false } = {}) {
  const root = { dataset: {} }, storage = new Map(saved === undefined ? [] : [[key, saved]]);
  const documentEvents = new Map(), windowEvents = new Map(), changes = [];
  let controlsReady = false, systemChange;
  const button = (dataset = {}) => ({ dataset, attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, value); } });
  const toggles = [button(), button()];
  const choices = ["light", "dark", "system"].map((themeChoice) => button({ themeChoice }));
  const system = { matches: systemDark, addEventListener(name, callback) {
    assert.equal(name, "change"); systemChange = callback;
  } };
  const context = vm.createContext({
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    localStorage: {
      getItem(name) { if (storageBlocked) throw new Error("Storage blocked"); return storage.get(name) ?? null; },
      setItem(name, value) { if (storageBlocked) throw new Error("Storage blocked"); storage.set(name, value); },
    },
    document: {
      documentElement: root,
      addEventListener: (name, callback) => documentEvents.set(name, callback),
      querySelectorAll(selector) {
        if (!controlsReady) return [];
        if (selector === "[data-theme-toggle]") return toggles;
        if (selector === "[data-theme-choice]") return choices;
        throw new Error(`Unexpected selector: ${selector}`);
      },
    },
    window: {
      matchMedia(query) { assert.equal(query, "(prefers-color-scheme: dark)"); return system; },
      addEventListener: (name, callback) => windowEvents.set(name, callback),
      dispatchEvent: (event) => changes.push(event),
    },
  });
  vm.runInContext(source, context);
  const click = (target = toggles[0]) => documentEvents.get("click")({
    target: { closest: () => target },
  });
  return {
    root, storage, toggles, choices, changes, click,
    ready() { controlsReady = true; documentEvents.get("DOMContentLoaded")(); },
    systemChange(dark) { system.matches = dark; systemChange(); },
    storageChange(value, changedKey = key) {
      if (value === null) storage.delete(key); else storage.set(key, value);
      windowEvents.get("storage")({ key: changedKey });
    },
  };
}

{
  const h = harness({ systemDark: true });
  assert.equal(h.root.dataset.theme, "light", "first visit is light even when the device is dark");
  assert.equal(h.root.dataset.themeChoice, "light", "appearance is applied before controls exist");
  assert.equal(h.storage.has(key), false, "initial rendering does not write a user preference");
  h.ready();
  for (const toggle of h.toggles) {
    assert.equal(toggle.attributes.get("aria-label"), "Appearance: Light. Switch to dark.");
    assert.equal(toggle.dataset.appearance, "light");
  }
  assert.equal(h.choices[0].attributes.get("aria-pressed"), "true");
  assert.equal(h.choices[1].attributes.get("aria-pressed"), "false");
  h.click();
  assert.equal(h.root.dataset.theme, "dark");
  assert.equal(h.storage.get(key), "dark");
  assert.equal(h.toggles[1].attributes.get("aria-label"), "Appearance: Dark. Switch to system.");
  h.click(h.toggles[1]);
  assert.equal(h.root.dataset.themeChoice, "system", "either control advances the same persisted choice");
  assert.equal(h.root.dataset.theme, "dark");
  assert.equal(h.storage.get(key), "system");
  assert.equal(h.changes.length, 2, "changing choice without changing the rendered theme does not refresh the viewer");
  h.systemChange(false);
  assert.equal(h.root.dataset.theme, "light");
  assert.equal(h.root.dataset.themeChoice, "system");
  h.click();
  assert.equal(h.root.dataset.themeChoice, "light", "the toggle completes light, dark, system, light");
  h.systemChange(true);
  assert.equal(h.root.dataset.theme, "light", "a device change cannot override an explicit light preference");
  assert.deepEqual(h.changes.map((event) => [event.type, event.detail.theme]), [
    ["wayline-theme-change", "light"], ["wayline-theme-change", "dark"], ["wayline-theme-change", "light"],
  ]);
}

for (const [saved, expected] of [["dark", "dark"], ["system", "dark"], ["obsolete-theme", "light"]]) {
  const h = harness({ saved, systemDark: true });
  assert.equal(h.root.dataset.theme, expected, `restore ${saved} before first paint`);
}

{
  const h = harness();
  h.ready();
  h.click(h.choices[2]);
  assert.equal(h.root.dataset.themeChoice, "system", "an explicit appearance choice need not cycle");
  assert.equal(h.choices[2].attributes.get("aria-pressed"), "true");
  h.systemChange(true);
  assert.equal(h.root.dataset.theme, "dark");
  h.storageChange("light");
  assert.equal(h.root.dataset.theme, "light", "a preference changed in another tab is applied");
  assert.equal(h.root.dataset.themeChoice, "light");
  assert.equal(h.choices[2].attributes.get("aria-pressed"), "false");
  h.storageChange("dark", "unrelated-key");
  assert.equal(h.root.dataset.theme, "light", "unrelated storage events do not alter appearance");
  h.storageChange("dark");
  assert.equal(h.root.dataset.theme, "dark");
  h.storageChange(null, null);
  assert.equal(h.root.dataset.theme, "light", "clearing storage restores the light default");
  h.click(null);
  assert.equal(h.root.dataset.themeChoice, "light", "clicks outside appearance controls are ignored");
}

{
  const h = harness({ saved: "dark", storageBlocked: true, systemDark: true });
  h.ready();
  assert.equal(h.root.dataset.theme, "light", "blocked storage does not prevent the default render");
  h.click();
  assert.equal(h.root.dataset.theme, "dark", "appearance remains usable when storage writes fail");
  h.click();
  h.systemChange(false);
  assert.equal(h.root.dataset.theme, "light", "system mode also works without storage");
}

console.log("Light default, persisted appearance, system changes, and theme controls passed");
