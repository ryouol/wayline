"use strict";

(async function loadSharedScene() {
  const status = document.getElementById("sharedStatus");
  const download = document.getElementById("sharedDownload");
  const controller = new AbortController();
  const timeline = new window.SceneTimeline(document.getElementById("sharedTimeline"));
  let viewer = null, expiryTimer = null, downloadUrl = null;
  function close() {
    controller.abort();
    clearTimeout(expiryTimer);
    timeline.attach(null);
    viewer?.destroy();
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    download.hidden = true;
  }
  window.addEventListener("pagehide", close, { once: true });
  document.getElementById("sharedZoomIn").addEventListener("click", () => viewer?.zoom(0.8), { signal: controller.signal });
  document.getElementById("sharedZoomOut").addEventListener("click", () => viewer?.zoom(1.25), { signal: controller.signal });
  document.getElementById("sharedReset").addEventListener("click", () => timeline.wholeSpace(), { signal: controller.signal });
  try {
    // Fragments stay in the browser. The capability never enters a request URL.
    const token = location.hash.slice(1);
    if (!/^[A-Za-z0-9_-]{32,64}$/.test(token)) throw new Error("This link is invalid or has expired.");
    const headers = { Authorization: `Bearer ${token}` };
    const response = await fetch("/api/public/share", { headers, credentials: "omit", signal: controller.signal });
    if (!response.ok) throw new Error("This link is invalid or has expired.");
    const data = await response.json();
    document.getElementById("shareTitle").textContent = data.artifact.filename;
    document.getElementById("shareLicense").textContent = data.artifact.licenseId;
    document.getElementById("shareExpiry").textContent = `Link expires ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.expiresAt * 1000))}.`;
    const warning = document.getElementById("shareCommercialWarning");
    warning.hidden = !data.researchOnly;
    warning.textContent = data.commercialWarning || "";
    expiryTimer = setTimeout(() => { close(); status.textContent = "This share link has expired."; }, Math.max(0, data.expiresAt * 1000 - Date.now()));
    viewer = new window.PointCloudViewer(document.getElementById("sharedCanvas"), status);
    await viewer.load(data.artifact.contentUrl, { headers });
    if (controller.signal.aborted) return;
    timeline.attach(viewer);
    download.hidden = false;
    download.addEventListener("click", async () => {
      download.disabled = true;
      download.textContent = "Preparing download…";
      try {
        const result = await fetch(data.artifact.contentUrl, { headers, credentials: "omit", signal: controller.signal });
        if (!result.ok) throw new Error("This link is invalid or has expired.");
        const blob = await result.blob();
        if (controller.signal.aborted) return;
        if (downloadUrl) URL.revokeObjectURL(downloadUrl);
        downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = data.artifact.filename;
        link.click();
      } catch (error) {
        if (!controller.signal.aborted) status.textContent = error.message;
      } finally {
        download.disabled = false;
        download.textContent = "Download GLB";
      }
    }, { signal: controller.signal });
  } catch (error) {
    if (!controller.signal.aborted) status.textContent = error.message;
  }
}());
