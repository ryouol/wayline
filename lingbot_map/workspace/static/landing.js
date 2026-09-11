"use strict";

(function showLandingScene() {
  const scene = document.getElementById("landingScene");
  const landing = document.getElementById("loginView");
  const toggle = document.getElementById("motionToggle");
  if (!scene || !landing || !toggle) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const connection = navigator.connection;
  const status = document.getElementById("landingStatus") || { textContent: "" };
  let viewer = null;
  let visible = false;
  let paused = false;
  let failed = false;
  let frame = null;
  let progress = 0;
  let drawnProgress = null;

  function stop() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    drawnProgress = null;
    viewer?.destroy();
    viewer = null;
    scene.dataset.loaded = "false";
  }

  function scrollProgress() {
    return Math.max(0, Math.min(1, -scene.getBoundingClientRect().top / Math.max(1, scene.clientHeight)));
  }

  function draw() {
    frame = null;
    if (!viewer || !viewer.count) return;
    const target = scrollProgress();
    progress += (target - progress) * 0.18;
    // Native page scrolling gently changes the viewpoint; no perpetual render loop.
    if (drawnProgress !== progress) {
      const canvas = document.getElementById("landingCanvas");
      const distance = canvas.clientWidth > canvas.clientHeight * 1.5 ? 2.2 : 2.5;
      viewer.setOrbit(-0.35 + progress * 0.4, -0.18 + progress * 0.04, distance);
      drawnProgress = progress;
    }
    if (Math.abs(target - progress) > 0.001) frame = requestAnimationFrame(draw);
  }

  function scheduleDraw() {
    if (viewer?.count && frame === null) frame = requestAnimationFrame(draw);
  }

  async function sync() {
    const restricted = reducedMotion.matches || connection?.saveData;
    toggle.disabled = Boolean(restricted || failed);
    toggle.textContent = restricted || failed ? "Motion off" : paused ? "Play motion" : "Pause motion";
    toggle.setAttribute("aria-pressed", String(!restricted && !failed && !paused));
    scene.dataset.motion = restricted || paused || failed ? "paused" : "playing";
    if (restricted || paused || failed || !visible || landing.hidden || document.hidden) {
      stop();
      return;
    }
    if (viewer) return;
    let current;
    try {
      current = new window.PointCloudViewer(document.getElementById("landingCanvas"), status,
        { interactive: false, pointSize: 2.2, showPath: true });
      viewer = current;
      await current.load("/static/landing-scene.glb");
      if (viewer !== current || current.destroyed) return;
      progress = scrollProgress();
      draw();
      scene.dataset.loaded = "true";
    } catch (error) {
      if ((current && current !== viewer) || error.name === "AbortError") return;
      failed = true;
      stop();
      toggle.disabled = true;
      toggle.textContent = "Motion off";
      toggle.setAttribute("aria-pressed", "false");
      scene.dataset.motion = "paused";
      status.textContent = "Example reconstruction shown as a still image.";
    }
  }

  toggle.addEventListener("click", () => { paused = !paused; void sync(); });
  window.addEventListener("scroll", scheduleDraw, { passive: true });
  window.addEventListener("resize", () => { drawnProgress = null; scheduleDraw(); }, { passive: true });
  document.addEventListener("visibilitychange", () => { void sync(); });
  reducedMotion.addEventListener("change", () => { void sync(); });
  connection?.addEventListener("change", () => { void sync(); });
  window.addEventListener("pagehide", stop);
  window.addEventListener("pageshow", () => { void sync(); });
  new MutationObserver(() => { void sync(); }).observe(landing, { attributes: true, attributeFilter: ["hidden"] });
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    void sync();
  }, { threshold: 0 }).observe(scene);
  void sync();
}());
