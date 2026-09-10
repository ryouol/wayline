"use strict";

(() => {
  // TODO: provide approved analytics measurement ID and same-origin collector endpoint.
  // The collector must accept {measurementId,event,page}; do not include arbitrary URLs.
  const analytics = { measurementId: "", endpoint: "" };
  const consentKey = "scene-workspace-analytics-consent-v1";
  const readConsent = () => { try { return localStorage.getItem(consentKey); } catch (_) { return null; } };
  function track() {
    if (readConsent() !== "accepted" || !analytics.measurementId || !analytics.endpoint) return;
    const endpoint = new URL(analytics.endpoint, location.origin);
    if (endpoint.origin !== location.origin || !endpoint.pathname.startsWith("/analytics/")) return;
    const path = location.pathname;
    const page = ["/", "/privacy", "/terms", "/contact"].includes(path) ? path : "other";
    fetch(endpoint.href, { method: "POST", credentials: "omit", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ measurementId: analytics.measurementId, event: "page_view", page }),
    }).catch(() => {});
  }
  const footer = document.createElement("footer");
  footer.className = "site-footer";
  const label = document.createElement("span");
  label.textContent = `© ${new Date().getFullYear()} 3D Scene Workspace`;
  footer.append(label);
  for (const [name, href] of [["Privacy", "/privacy"], ["Terms", "/terms"], ["Contact", "/contact"]]) {
    const link = document.createElement("a"); link.textContent = name; link.href = href; footer.append(link);
  }
  const preferences = document.createElement("button");
  preferences.type = "button"; preferences.className = "text-button"; preferences.textContent = "Cookie choices";
  footer.append(preferences); document.body.append(footer);

  const banner = document.createElement("section");
  banner.className = "consent-banner"; banner.setAttribute("aria-label", "Cookie choices");
  const message = document.createElement("p");
  message.textContent = "Sign-in uses an essential cookie. Optional analytics is off unless you choose to allow it. You can change your choice at any time.";
  banner.append(message);
  for (const [name, choice] of [["Essential only", "rejected"], ["Allow analytics", "accepted"]]) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "secondary"; button.textContent = name;
    button.addEventListener("click", () => {
      try { localStorage.setItem(consentKey, choice); } catch (_) { /* fail closed */ }
      banner.hidden = true; preferences.focus(); if (choice === "accepted") track();
    });
    banner.append(button);
  }
  banner.hidden = readConsent() !== null;
  preferences.addEventListener("click", () => { banner.hidden = false; banner.querySelector("button").focus(); });
  document.body.append(banner); track();
})();
