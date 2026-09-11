# Viewer accessibility follow-up — 2026-09-11 UTC

Scope: three source-review findings in the existing private and shared viewers.
Live baseline: Render application `351f339`. Corrected local build: changes after
`422c207`, with an isolated synthetic workspace and no Google or Modal calls.
This is a targeted browser audit, not a WCAG certification or physical-phone test.

1. **Private viewer keyboard focus — improved.** The live canvas matched
   `:focus-visible` with a 3-pixel outline and positive 3-pixel offset, while its
   parent clipped overflow. The saved baseline shows no visible ring. A negative
   4-pixel offset places the ring inside the canvas; the corrected local screenshot
   shows the complete ring while arrow-key orbiting remains functional.
2. **Processing progress — improved.** The progress element previously had no
   associated label. During a real local sample generation, the accessibility tree
   exposed “Scene processing progress”, value 92. Its name remains descriptive
   as the stage heading changes. The sample then reached READY with 5,908 points.
3. **Shared viewer controls — improved.** The live Zoom in button measured
   37.234375 pixels wide and 44 pixels high. The corrected shared control group
   enforces 44-pixel minimum width. At a 390×844 browser viewport, the button was
   44×44 pixels and document width was exactly 390 pixels. The scene rendered
   5,908 points, with download and expiry information visible.

Exact screenshots were saved and the private-before/private-after and mobile-after
files were visually inspected. Evidence directory on the QA machine:
`/Users/royluo/Documents/ChatGPT/LingBot/viewer-accessibility-2026-09-11/`.

- `02-private-keyboard-before.png`
- `05-private-keyboard-after.png`
- `06-shared-mobile-after.png`

Desktop captures used different existing tab sizes; they establish focus visibility,
not a pixel-for-pixel layout comparison. Only the explicitly measured 390×844
capture establishes the narrow viewport result. The browser viewport override was
reset after testing. No screenshot contains a share capability or account token.
The temporary live share contains only the CC0 synthetic sample and expires after
24 hours. No capture-quality or mobile-GPU performance conclusion follows from it.

The source audit also calculated the named text palette: the weakest reviewed pair
was quiet text on the second surface at 5.42:1. This does not cover every possible
image/background combination, screen reader behavior or all interactive states.

## Signup and field contrast — 2026-09-11

The full-signup state exposed a missed style interaction: app.js changed the
Google link from primary to secondary, but its unconditional Google background
stayed the same light color as secondary text (calculated contrast 1.00:1).
Scoping that background to `.google-button.primary` preserves open signup and
lets returning login use the existing secondary palette. Text/password/number
field borders now reuse `--quiet`; their former faint boundary was about 1.52:1
against the landing background. Decorative dividers and button borders are unchanged.

Actual computed colors in macOS WebKit 26.5 and Chromium 151 at 390×844 agree:

| Rendered state | Contrast |
|---|---:|
| Google signup open | 13.44:1 |
| Returning Google login when signup is full | 16.47:1 |
| Workspace-token input border against its fill | 6.19:1 |
| Same input border against the surrounding page | 6.72:1 |

Both engines rendered the actual frontend against isolated open/full config
responses. Screenshots include the expanded operator field. No Google account,
production signup limit or provider job was used for these local checks.
The source palette audit found no additional normal solid-background text issue;
this is not a claim about every image/background or a WCAG certification.

The same local WebKit run rendered the verified real TUM scene; details are in
[real-capture QA](REAL_CAPTURE_QA.md). Playwright's WebKit screenshot preparation
injects an inline `body {}` style to synchronize animations. A controlled run
completed all app interactions without screenshots and observed no CSP violations;
a final screenshot introduced exactly one `style-src-elem` event. The installed
Playwright `inPagePrepareForScreenshots` implementation confirms the injection.
Application CSP was not relaxed. The earlier selector-ambiguity and screenshot
harness failures are retained separately from the final passing receipt.

Private evidence: `.lingbot-workspace/webkit-qa/verification.json`, the retained
harness and open/full screenshots for both engines. Mobile/touch emulation runs
on macOS; iOS Safari and physical-phone validation remain unverified.
