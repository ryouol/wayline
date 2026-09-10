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
      this.viewer = null;
      this.timer = null;
      this.viewerEvents = null;
      this.scrubber.addEventListener("input", () => { this.stop(); this.seek(Number(this.scrubber.value)); });
      this.play.addEventListener("click", () => this.toggle());
      root.querySelector(".show-all").addEventListener("click", () => this.wholeSpace());
      this.walkControls = document.createElement("div");
      this.walkControls.className = "walk-controls";
      const actions = [
        ["Walk from here", () => { this.stop(); this.viewer?.startWalk(); }],
        ["Step forward", () => this.viewer?.moveWalk(1, 0)],
        ["Step back", () => this.viewer?.moveWalk(-1, 0)],
        ["Step left", () => this.viewer?.moveWalk(0, -1)],
        ["Step right", () => this.viewer?.moveWalk(0, 1)],
      ];
      actions.forEach(([label, action], index) => {
        const button = document.createElement("button");
        button.className = "secondary";
        button.type = "button";
        button.textContent = label;
        button.hidden = index > 0;
        button.addEventListener("click", action);
        this.walkControls.append(button);
      });
      this.walkHint = document.createElement("p");
      this.walkHint.className = "muted walk-hint";
      this.walkHint.textContent = "Drag to look. Use the step buttons or focus the view and use W A S D to move; arrow keys to look. Whole space resets your view.";
      this.walkHint.hidden = true;
      root.append(this.walkControls, this.walkHint);
    }

    stop() {
      if (this.timer !== null) cancelAnimationFrame(this.timer);
      this.timer = null;
      this.play.textContent = "Play path";
    }

    attach(viewer) {
      this.stop();
      this.viewerEvents?.abort();
      this.viewer = viewer;
      this.strip.replaceChildren();
      const frames = viewer?.trace?.frames;
      this.root.hidden = !frames;
      this.showWalkControls(false);
      if (this.modeLabel) this.modeLabel.textContent = "FREE ORBIT";
      if (!viewer) return;
      this.viewerEvents = new AbortController();
      viewer.canvas.addEventListener("viewmode", (event) => {
        this.stop();
        if (this.modeLabel) this.modeLabel.textContent = event.detail;
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
      if (this.modeLabel) this.modeLabel.textContent = "CAMERA VIEW";
      this.viewer.setFrame(index);
      Array.from(this.strip.children).forEach((button, i) => button.setAttribute("aria-current", String(i === index)));
    }

    toggle() {
      if (this.timer !== null) { this.stop(); return; }
      const frames = this.viewer?.trace?.frames;
      if (!frames) return;
      let index = Number(this.scrubber.value);
      if (index >= frames.length - 1) index = 0;
      const startTime = performance.now(), firstTime = frames[index].time;
      this.play.textContent = "Pause";
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
      if (this.modeLabel) this.modeLabel.textContent = "WHOLE SPACE";
      if (!this.viewer?.trace) return;
      this.scrubber.value = this.viewer.trace.frames.length - 1;
      this.counter.textContent = `${this.viewer.trace.frames.length} source frames · whole space`;
      Array.from(this.strip.children).forEach((button) => button.setAttribute("aria-current", "false"));
    }

    showWalkControls(walking) {
      Array.from(this.walkControls.children).forEach((button, index) => {
        button.hidden = index === 0 ? walking : !walking;
      });
      this.walkHint.hidden = !walking;
    }
  }
  window.SceneTimeline = SceneTimeline;
}());
