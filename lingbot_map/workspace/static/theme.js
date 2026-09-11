"use strict";

(() => {
  const key = "wayline-appearance-v1";
  const choices = ["light", "dark", "system"];
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const root = document.documentElement;
  const read = () => {
    try {
      const saved = localStorage.getItem(key);
      return choices.includes(saved) ? saved : "light";
    } catch (_) { return "light"; }
  };
  let choice = read();

  function renderControls() {
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const name = choice[0].toUpperCase() + choice.slice(1);
      const next = choices[(choices.indexOf(choice) + 1) % choices.length];
      button.setAttribute("aria-label", `Appearance: ${name}. Switch to ${next}.`);
      button.title = `Appearance: ${name}`;
      button.dataset.appearance = choice;
    });
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === choice));
    });
  }

  function apply() {
    const theme = choice === "system" ? (system.matches ? "dark" : "light") : choice;
    const changed = root.dataset.theme !== theme;
    root.dataset.theme = theme;
    root.dataset.themeChoice = choice;
    renderControls();
    if (changed) window.dispatchEvent(new CustomEvent("wayline-theme-change", { detail: { theme } }));
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle], [data-theme-choice]");
    if (!button) return;
    const requested = button.dataset.themeChoice;
    choice = choices.includes(requested) ? requested : choices[(choices.indexOf(choice) + 1) % choices.length];
    try { localStorage.setItem(key, choice); } catch (_) { /* appearance still works for this page */ }
    apply();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) { choice = read(); apply(); }
  });
  system.addEventListener("change", () => { if (choice === "system") apply(); });
  document.addEventListener("DOMContentLoaded", renderControls, { once: true });
  apply();
})();
