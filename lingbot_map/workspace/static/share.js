"use strict";

(async function loadSharedScene() {
  const token = decodeURIComponent(window.location.pathname.split("/").pop() || "");
  const status = document.getElementById("sharedStatus");
  let viewer = null;
  window.addEventListener("pagehide", () => viewer?.destroy(), { once: true });
  try {
    const response = await fetch(`/api/public/shares/${encodeURIComponent(token)}`);
    if (!response.ok) throw new Error("This link is invalid or has expired.");
    const data = await response.json();
    document.getElementById("shareTitle").textContent = data.artifact.filename;
    document.getElementById("shareLicense").textContent = data.artifact.licenseId;
    document.getElementById("sharedDownload").href = data.artifact.contentUrl;
    document.getElementById("sharedDownload").setAttribute("download", data.artifact.filename);
    document.getElementById("shareExpiry").textContent = `Link expires ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.expiresAt * 1000))}.`;
    const warning = document.getElementById("shareCommercialWarning");
    warning.hidden = !data.researchOnly;
    warning.textContent = data.commercialWarning || "";
    viewer = new window.PointCloudViewer(document.getElementById("sharedCanvas"), status);
    await viewer.load(data.artifact.contentUrl);
  } catch (error) {
    status.textContent = error.message;
  }
}());
