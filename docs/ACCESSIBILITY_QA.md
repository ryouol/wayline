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
