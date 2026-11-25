"use strict";

(() => {
  // TODO: provide WAYLINE_ANALYTICS_PROPERTY_ID and approve policy before enabling analytics.
  const consentKey = "scene-workspace-analytics-consent-v1";
  let rejectedHere = false;
  const readConsent = () => {
    if (rejectedHere) return "rejected";
    try { return localStorage.getItem(consentKey); } catch (_) { return null; }
  };
  const privacySignal = () => navigator.globalPrivacyControl === true || navigator.doNotTrack === "1"
    || window.doNotTrack === "1";
  const eligible = () => readConsent() === "accepted" && !privacySignal()
    && ["/", "/privacy", "/terms", "/contact"].includes(location.pathname)
    && (location.pathname !== "/" || document.body.dataset.surface === "landing");
  let pending = null, sent = false;
  const stop = () => { pending?.abort(); pending = null; };
  async function track() {
    if (!eligible() || pending || sent) return;
    const page = location.pathname;
    const controller = new AbortController(); pending = controller;
    const timeout = setTimeout(() => controller.abort(), 5000);
    const options = { credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store", signal: controller.signal };
    try {
      const response = await fetch("/api/config", options);
      if (!response.ok) return;
      const { analytics } = await response.json();
      if (!eligible() || location.pathname !== page || controller.signal.aborted || !analytics
        || analytics.endpoint !== "/analytics/page-view" || typeof analytics.propertyId !== "string"
        || !/^[A-Za-z0-9_-]{1,64}$/.test(analytics.propertyId)) return;
      sent = true;
      await fetch(analytics.endpoint, { ...options, method: "POST",
        headers: { "Content-Type": "application/json", "X-Wayline-Analytics-Consent": "accepted" },
        body: JSON.stringify({ propertyId: analytics.propertyId, event: "page_view", page }),
      });
    } catch (_) { /* Analytics must never interrupt the page. */ }
    finally { clearTimeout(timeout); if (pending === controller) pending = null; }
  }
  const footer = document.createElement("footer");
  footer.className = "site-footer";
  const label = document.createElement("span");
  label.textContent = `© ${new Date().getFullYear()} Wayline`;
  footer.append(label);
  for (const [name, href] of [["Privacy", "/privacy"], ["Terms", "/terms"], ["Contact", "/contact"], ["Credits", "/static/ASSET-NOTICES.txt"]]) {
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
      // A failed write must not revive a previously stored acceptance.
      rejectedHere = true;
      try { localStorage.setItem(consentKey, choice); rejectedHere = choice !== "accepted"; }
      catch (_) { try { localStorage.removeItem(consentKey); } catch (_) { /* Reject this document. */ } }
      if (choice !== "accepted") stop();
      banner.hidden = true; preferences.focus(); if (choice === "accepted") track();
    });
    banner.append(button);
  }
  banner.hidden = readConsent() !== null;
  preferences.addEventListener("click", () => { banner.hidden = false; banner.querySelector("button").focus(); });
  window.addEventListener("storage", () => { if (!eligible()) stop(); });
  window.addEventListener("pagehide", stop);
  // The homepage also hosts private/account views; wait for its public surface.
  if (location.pathname === "/") {
    new MutationObserver(() => { if (eligible()) track(); else stop(); })
      .observe(document.body, { attributes: true, attributeFilter: ["data-surface"] });
  }
  document.body.append(banner); track();
})();
