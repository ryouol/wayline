"use strict";

(async function loadSharedScene() {
  const status = document.getElementById("sharedStatus");
  const download = document.getElementById("sharedDownload");
  const retry = document.getElementById("reloadSharedScene");
  const retryPreview = document.getElementById("retrySharedPreview");
  const cancelPreview = document.getElementById("cancelSharedPreview");
  const controller = new AbortController();
  const timeline = new window.SceneTimeline(document.getElementById("sharedTimeline"));
  let viewer = null, expiryTimer = null, metadataTimer = null, downloadUrl = null, activeDownload = null;
  let activePreview = null;
  function unavailable(message, title = "This link is no longer available.", canRetry = false) {
    close();
    document.querySelector(".shared-viewer").hidden = true;
    document.getElementById("shareLicense").hidden = true;
    document.getElementById("shareTitle").textContent = "Shared scene";
    document.getElementById("shareUnavailableTitle").textContent = title;
    document.getElementById("shareUnavailableMessage").textContent = message;
    document.getElementById("shareUnavailable").hidden = false;
    retry.hidden = !canRetry;
  }
  function close() {
    controller.abort();
    activeDownload?.abort();
    clearTimeout(expiryTimer);
    clearTimeout(metadataTimer);
    closePreview();
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
    download.hidden = true;
    retryPreview.hidden = true;
  }
  function closePreview() {
    activePreview?.abort();
    activePreview = null;
    cancelPreview.hidden = true;
    retryPreview.disabled = false;
    timeline.attach(null);
    viewer?.destroy();
    viewer = null;
  }
  window.addEventListener("pagehide", close, { once: true });
  retry.addEventListener("click", () => {
    retry.disabled = true;
    location.reload();
  });
  document.getElementById("sharedSkipLink").addEventListener("click", (event) => {
    event.preventDefault();
    document.getElementById("shareTitle").focus();
  });
  document.getElementById("sharedZoomIn").addEventListener("click", () => viewer?.zoom(0.8), { signal: controller.signal });
  document.getElementById("sharedZoomOut").addEventListener("click", () => viewer?.zoom(1.25), { signal: controller.signal });
  document.getElementById("sharedReset").addEventListener("click", () => timeline.wholeSpace(), { signal: controller.signal });
  try {
    // Fragments stay in the browser. The capability never enters a request URL.
    const token = location.hash.slice(1);
    if (!/^[A-Za-z0-9_-]{32,64}$/.test(token)) {
      unavailable("This link is invalid or has expired.");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };
    metadataTimer = setTimeout(() => {
      if (!controller.signal.aborted) unavailable("Loading took too long. Reload this scene to try again.", "Unable to load this scene.", true);
    }, 15000);
    const response = await fetch("/api/public/share", { headers, credentials: "omit", signal: controller.signal });
    if (controller.signal.aborted) return;
    if (!response.ok) {
      if ([401, 403, 404, 410].includes(response.status)) unavailable("This link is invalid or has expired.");
      else unavailable("The shared scene could not be loaded. Reload this scene to try again.", "Unable to load this scene.", true);
      return;
    }
    const data = await response.json();
    clearTimeout(metadataTimer);
    if (controller.signal.aborted) return;
    if (data.expiresAt * 1000 <= Date.now()) {
      unavailable("This link has expired. Ask the person who shared it for a new link.");
      return;
    }
    document.getElementById("shareTitle").textContent = data.artifact.filename;
    document.getElementById("shareLicense").textContent = data.artifact.licenseId === "NOASSERTION"
      ? "Usage rights unconfirmed" : data.artifact.licenseId;
    document.getElementById("shareExpiry").textContent = `Link expires ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.expiresAt * 1000))}.`;
    const warning = document.getElementById("shareCommercialWarning");
    warning.hidden = !data.researchOnly;
    warning.textContent = data.commercialWarning || "";
    expiryTimer = setTimeout(() => unavailable("This link has expired. Ask the person who shared it for a new link."), Math.max(0, data.expiresAt * 1000 - Date.now()));
    async function fetchArtifact(signal) {
      const result = await fetch(data.artifact.contentUrl, { headers, credentials: "omit", signal });
      signal.throwIfAborted();
      if (!result.ok) {
        if ([401, 403, 404, 410].includes(result.status)) unavailable("This link is no longer available. Ask the person who shared it for a new link.");
        throw new Error("The scene could not be downloaded. Please try again.");
      }
      return result;
    }
    // Download access depends on the share, not on this browser's WebGL support.
    download.hidden = false;
    download.addEventListener("click", async () => {
      if (controller.signal.aborted) return;
      if (activeDownload) {
        activeDownload.abort();
        status.textContent = "Download cancelled. You can try again.";
        return;
      }
      const request = activeDownload = new AbortController();
      download.textContent = "Cancel download";
      status.textContent = "Preparing download…";
      try {
        const response = await fetchArtifact(request.signal);
        const blob = await response.blob();
        if (controller.signal.aborted || request.signal.aborted) return;
        if (downloadUrl) URL.revokeObjectURL(downloadUrl);
        downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = data.artifact.filename;
        link.click();
        status.textContent = "Download ready. Check your browser's downloads.";
      } catch (error) {
        if (!controller.signal.aborted && !request.signal.aborted) status.textContent = error.message;
      } finally {
        activeDownload = null;
        download.textContent = "Download GLB";
      }
    }, { signal: controller.signal });
    function previewFailed(message) {
      closePreview();
      document.querySelector(".shared-viewer .viewport-wrap").hidden = true;
      document.querySelector(".shared-viewer .viewer-help").hidden = true;
      retryPreview.hidden = false;
      status.textContent = `${message} Retry the preview or download this scene.`;
    }
    async function loadPreview(focus = false) {
      if (controller.signal.aborted || retryPreview.disabled) return;
      const request = activePreview = new AbortController();
      retryPreview.disabled = true;
      cancelPreview.hidden = false;
      document.querySelector(".shared-viewer .viewport-wrap").hidden = false;
      document.querySelector(".shared-viewer .viewer-help").hidden = false;
      status.textContent = "Loading preview…";
      try {
        const loadedViewer = viewer = new window.PointCloudViewer(document.getElementById("sharedCanvas"), status);
        const response = await fetchArtifact(request.signal);
        if (controller.signal.aborted || activePreview !== request) return;
        await loadedViewer.load(data.artifact.contentUrl, { prefetchedResponse: response });
        if (controller.signal.aborted || activePreview !== request) return;
        if (loadedViewer.contextLost) throw new Error("The 3D preview was interrupted.");
        document.getElementById("sharedCanvas").addEventListener("wayline-viewer-unavailable", () => {
          if (!controller.signal.aborted && viewer === loadedViewer) previewFailed("The 3D preview was interrupted.");
        }, { once: true });
        timeline.attach(viewer);
        retryPreview.hidden = true;
        if (focus) document.getElementById("sharedCanvas").focus();
      } catch (error) {
        if (controller.signal.aborted || activePreview !== request) return;
        previewFailed("The 3D preview couldn't be loaded.");
      } finally {
        if (activePreview === request) {
          activePreview = null;
          cancelPreview.hidden = true;
          retryPreview.disabled = false;
        }
      }
    }
    cancelPreview.addEventListener("click", () => {
      if (controller.signal.aborted || !activePreview) return;
      previewFailed("Preview cancelled.");
      retryPreview.focus();
    }, { signal: controller.signal });
    retryPreview.addEventListener("click", () => loadPreview(true), { signal: controller.signal });
    await loadPreview();
  } catch (error) {
    if (!controller.signal.aborted) unavailable("The shared scene could not be loaded. Reload this scene to try again.", "Unable to load this scene.", true);
  }
}());
