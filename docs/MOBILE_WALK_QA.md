# Mobile walking controls — 2026-09-11

These checks cover local source changes after `5ec639f`; they do not establish
production deployment. The fixture serves the existing, byte-verified account GLB
with 749,963 points and 43 frames. It has no worker or inference path. No original
video was retrieved, and no production share, allowance or GPU setting changed.
The reconstruction still fails the geometry-quality acceptance recorded in
[Google capture QA](GOOGLE_CAPTURE_QA.md).

## Observed problem and change

At 390×844, selecting Walk left the step controls below the canvas and filmstrip.
Clicking Forward brought them into view but moved most of the canvas offscreen;
the sticky scene list obscured much of the remaining portion. The controls now
belong to the existing viewport, retain their four labeled actions, and start
hidden until walking. On narrow screens, the scene list scrolls away when the
viewer is visible. The public landing keeps its sticky signup action; New scene
remains above the loaded scene and remains sticky when no viewer is visible.

The controls reuse the existing theme and 44px buttons, with a separate group
label. They sit clear of zoom/reset controls. The redundant corner badge hides
while walking. Fullscreen canvas sizing no longer inherits a 360px minimum on
short screens. No camera, playback, model or coordinate logic changed.

## Checks and limits

1. **Private 390×844 walking: passes.** After reaching Forward, the entire
   438.875px-high canvas lies between y=69.04 and y=507.91. The four 96×44px
   movement buttons remain inside it. Repeated Forward changes the scene view;
   the second observed click keeps document scroll at 333.5px. The browser tool
   scrolls to reach controls, so the first click is not claimed scroll-free.
2. **Private 320×568: passes.** The full 360px-high canvas lies between y=69.04
   and y=429.04, with 96×44px movement buttons separated from the zoom toolbar.
   No horizontal document overflow was observed. Reset switches to Orbit and
   hides movement. An initial transient resize capture was replaced with a
   stable screenshot before acceptance.
3. **Fullscreen: interaction/CSS evidence, visual capture limited.** The actual
   Full screen button enters a viewport matching `:fullscreen`; step controls
   remain within it, and the button returns to the workspace. At 568×320, the
   canvas measures exactly 568×320 with min-height 0; the movement group ends at
   y=306. The tool's `document.fullscreenElement` observation returned false even
   when the selector matched. Its fullscreen screenshots were scaled within a
   black area and are not accepted for visual-fidelity claims. Physical-device
   fullscreen and touch behavior remain unverified.
4. **Shared 390×844 dark view: passes.** After sign-out, a fresh local share
   loads all points/frames, enters Walk and moves forward. The full canvas lies
   between y=18.27 and y=507.79, with movement buttons inside and no horizontal
   document overflow. The private layout supplies light-theme evidence.
5. **Logout and revoked-share cleanup: passes locally.** Logout hides relocated
   movement, clears the filmstrip and leaves zero local sessions. After API
   revocation returns 202, clicking Download in the already-open shared view
   rechecks authorization and shows the unavailable state: viewer and movement
   hidden, zero frame buttons. This is not a successful download or elapsed-TTL
   test. No production capability was created.

Accepted screenshots, DOM receipts and the illustrated comparison remain in
`.lingbot-workspace/mobile-walk-qa/`, excluded from source distributions. The
local share was revoked; all three audit tabs were closed, viewport overrides
reset, server stopped, and temporary token/database/objects removed. The saved
source artifact remains only in its pre-existing ignored QA directory.

All eleven Node suites and 35 Python static/production-UX tests pass (1.40s).
Timeline regressions cover controls inside the viewport, hidden initial/detached
states, existing replay and viewer lifecycle. Three simplify passes and four
code-review subskills found no new actionable source issue; model-context was
N/A. Existing aggregate PR-size finding 139 remains open. These checks improve
the core narrow-screen walking flow, without certifying physical mobile,
assistive technology, model quality or full launch readiness.
