"use strict";

(function exposeTimeline() {
  class SceneTimeline {
    constructor(root, modeLabel) {
      this.root = root;
      this.modeLabel = modeLabel;
      this.strip = root.querySelector(".filmstrip");
      this.scrubber = root.querySelector('input[type="range"]');
      this.counter = root.querySelector(".frame-counter");
      this.play = root.querySelector(".play-path");
      const section = root.closest(".viewer-section, .shared-viewer");
      this.modes = section.querySelectorAll("[data-view-mode]");
      this.viewer = null;
      this.timer = null;
      this.viewerEvents = null;
      this.scrubber.addEventListener("input", () => { this.stop(); this.seek(Number(this.scrubber.value)); });
      this.play.addEventListener("click", () => this.toggle());
      root.querySelector(".show-all").addEventListener("click", () => this.wholeSpace());
      this.modes.forEach((button) => button.addEventListener("click", () => {
        this.stop();
        if (button.dataset.viewMode === "orbit") this.wholeSpace();
        else if (button.dataset.viewMode === "camera") this.seek(Number(this.scrubber.value));
        else this.viewer?.startWalk();
      }));
      document.addEventListener("visibilitychange", () => { if (document.hidden) this.stop(); });
      this.walkControls = document.createElement("div");
      this.walkControls.className = "walk-controls";
      this.walkControls.hidden = true;
      this.walkControls.setAttribute("role", "group");
      this.walkControls.setAttribute("aria-label", "Walk movement");
      const actions = [
        ["Forward", () => this.viewer?.moveWalk(1, 0)],
        ["Back", () => this.viewer?.moveWalk(-1, 0)],
        ["Left", () => this.viewer?.moveWalk(0, -1)],
        ["Right", () => this.viewer?.moveWalk(0, 1)],
      ];
      actions.forEach(([label, action]) => {
        const button = document.createElement("button");
        button.className = "secondary walk-step-button";
        button.type = "button";
        button.textContent = label;
        button.setAttribute("aria-label", `Step ${label.toLowerCase()}`);
        button.addEventListener("click", action);
        this.walkControls.append(button);
      });
      this.walkHint = document.createElement("p");
      this.walkHint.className = "muted walk-hint";
      this.walkHint.textContent = "Drag to look. Use the step buttons, or focus the view and use W A S D to move and arrow keys to look. Orbit resets your view.";
      this.walkHint.hidden = true;
      section.querySelector(".viewport-wrap").append(this.walkControls);
      root.append(this.walkHint);
    }

    stop() {
      if (this.timer !== null) cancelAnimationFrame(this.timer);
      this.timer = null;
      this.play.textContent = "Play path";
      this.play.setAttribute("aria-pressed", "false");
    }

    attach(viewer) {
      this.stop();
      this.viewerEvents?.abort();
      this.viewer = viewer;
      this.strip.replaceChildren();
      const frames = viewer?.trace?.frames;
      this.root.hidden = !frames;
      this.showWalkControls(false);
      this.setMode("orbit");
      this.modes.forEach((button) => { button.disabled = !viewer || (button.dataset.viewMode !== "orbit" && !frames); });
      if (!viewer) return;
      this.viewerEvents = new AbortController();
      viewer.canvas.addEventListener("viewmode", (event) => {
        this.stop();
        this.setMode(event.detail === "WALK VIEW" ? "walk" : "orbit");
        this.showWalkControls(event.detail === "WALK VIEW");
      }, { signal: this.viewerEvents.signal });
      if (!frames) return;
      this.scrubber.max = frames.length - 1;
      this.scrubber.value = frames.length - 1;
      this.counter.textContent = `${frames.length} source frames · whole space`;
      frames.forEach((frame, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "frame-button";
        button.setAttribute("aria-label", `View frame ${index + 1} at ${frame.time.toFixed(1)} seconds`);
        const image = document.createElement("img");
        image.src = frame.thumbnail;
        image.alt = `Source frame ${index + 1}`;
        image.loading = "lazy";
        const time = document.createElement("span");
        time.textContent = `${frame.time.toFixed(1)}s`;
        button.append(image, time);
        button.addEventListener("click", () => { this.stop(); this.seek(index); });
        this.strip.append(button);
      });
    }

    seek(index) {
      const frame = this.viewer?.trace?.frames[index];
      if (!frame) return;
      this.showWalkControls(false);
      this.scrubber.value = index;
      this.counter.textContent = `Frame ${index + 1} / ${this.viewer.trace.frames.length} · ${frame.time.toFixed(1)}s`;
      this.setMode("camera");
      this.viewer.setFrame(index);
      Array.from(this.strip.children).forEach((button, i) => button.setAttribute("aria-current", String(i === index)));
      const selected = this.strip.children[index].getBoundingClientRect();
      const visible = this.strip.getBoundingClientRect();
      if (selected.left < visible.left) this.strip.scrollLeft += selected.left - visible.left;
      else if (selected.right > visible.right) this.strip.scrollLeft += selected.right - visible.right;
    }

    toggle() {
      if (this.timer !== null) { this.stop(); return; }
      const frames = this.viewer?.trace?.frames;
      if (!frames) return;
      let index = Number(this.scrubber.value);
      if (index >= frames.length - 1) index = 0;
      const startTime = performance.now(), firstTime = frames[index].time;
      this.play.textContent = "Pause";
      this.play.setAttribute("aria-pressed", "true");
      this.seek(index);
      const step = (now) => {
        const target = firstTime + (now - startTime) / 1000;
        let next = index;
        while (next + 1 < frames.length && frames[next + 1].time <= target) next += 1;
        if (next !== index) { index = next; this.seek(index); }
        if (index >= frames.length - 1) { this.stop(); return; }
        this.timer = requestAnimationFrame(step);
      };
      this.timer = requestAnimationFrame(step);
    }

    wholeSpace() {
      this.stop();
      this.showWalkControls(false);
      this.viewer?.reset();
      this.setMode("orbit");
      if (!this.viewer?.trace) return;
      this.scrubber.value = this.viewer.trace.frames.length - 1;
      this.counter.textContent = `${this.viewer.trace.frames.length} source frames · whole space`;
      Array.from(this.strip.children).forEach((button) => button.setAttribute("aria-current", "false"));
    }

    showWalkControls(walking) {
      this.walkControls.hidden = !walking;
      this.walkHint.hidden = !walking;
    }

    setMode(mode) {
      this.modes.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.viewMode === mode)));
      if (this.modeLabel) this.modeLabel.textContent = { orbit: "Orbit", camera: "Camera", walk: "Walk" }[mode];
    }
  }
  window.SceneTimeline = SceneTimeline;
}());
