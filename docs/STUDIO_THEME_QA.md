# Private studio and management footer QA — 2026-09-11

The current app was inspected in the in-app Chromium browser with an isolated
local workspace and the precomputed, licensed 750,000-point TUM reference.
This did not run new inference, use a Google account or access production scenes.
The source increment is `b8ac0fc`; initial captures preceded its two-file fix.

## Findings and correction

- At 390×844, the management dialog ended at y=820 but its bulk-action button
  ended at y=825: 5px was clipped. The footer now sticks at bottom zero. Review
  caught the separate mobile negative offset, which was removed too.
- At 320×568, a selected-state button shrank to 90px and its label overflowed.
  The footer button now resists flex shrinking and remains about 151×44px.
- Selection text now omits empty categories and uses singular/plural correctly.
  Actual browser states were `Nothing selected` (disabled), `1 scene selected`
  and `1 scene · 1 share selected` (both enabled). Selection and deletion
  behavior were preserved.

## Captured flow

1. Light/dark desktop studio: the real viewer rendered the reference; sampled
   text passed contrast checks.
2. Creation and expanded capture settings: the phone-width number fields were
   144×44.5px; Escape returned focus to New scene.
3. Light mobile studio: document width matched 390px, with a 390×438.875px canvas.
4. Share dialog: expiry/access wording, readable field and visible focus;
   Escape returned to Share. The link belonged only to the disposable fixture.
5. Management and confirmation: before/after captures show the clipping fix;
   Keep it preserved the scene and restored the invoking action.
6. Phone-width footer: final 320px single selection passed at top, intermediate
   and bottom scroll; mixed selection passed near the bottom (382/397px). Final
   390px mixed selection passed at top and bottom. The earlier 390px intermediate
   sample preceded the final button-width change. All recorded final samples
   kept the whole 44px-high button inside the dialog.
7. Short desktop, 1280×600: the same containment checks passed with a 117px scroll
   range. Document width stayed within each tested viewport.

The final narrow checks measured a button bottom at or above y=525 within the
320×568 dialog ending at y=544, and y=801 within the 390×844 dialog ending at
y=820. The short-desktop button ended at or above y=557 within the dialog ending
at y=576. The initial/interim and final measurements are distinguished in the
local geometry record.

## Contrast and verification limits

Nine sampled states covered desktop studio, mobile studio, capture, share,
management and confirmation. Eligible solid-color text passed the applicable
pre-rounding thresholds; the lowest recorded ratio was 4.607:1. Disabled
controls, opacity effects, canvas/image text, pseudo-elements and placeholders
are excluded. This does not certify every state, assistive technology, physical
touch behavior or mobile performance. Form values were measured explicitly in
the share dialog; the capture field dimensions/colors were observed separately.

Only the open dialog controls appeared in the accessibility tree. Reverse Tab from
the first control reached browser chrome/body; forward Tab returned to the
dialog. No strict in-document keyboard wrap claim is made. Escape and
confirmation-cancel focus restoration were observed.

All eleven existing Node suites and JavaScript syntax checks passed. The
inventory suite stubs selection-summary rendering, so its pass does not prove
the new wording; actual browser observations provide that evidence. Simplify
and all code-review subskill passes completed; the aggregate PR-size issue
remains open. No new automated test was added for this small reversible fix.

The illustrated seven-step report, fourteen inspected screenshots, contrast
data and geometry/selection receipts are retained under the ignored local
`.lingbot-workspace/studio-theme-qa/` directory. The local server was stopped,
its tab closed, viewport reset and disposable database/objects/token removed.

## Deployment

[Exact-commit CI](https://github.com/ryouol/lingbot-map/actions/runs/34633462356) passed all checks, including 255 Python tests in 31.31 seconds and the 512 MiB / 0.5 CPU container smoke at a 201.2 MiB peak. Runtime
`b8ac0fc2eafb123349f8369ede6b7779cd5bc037` became live on the existing Render service at
`2026-09-11T18:40:07.818394Z`; deployment `dep-dai4lm1594qs73eegks0`.

HTTPS health returned 200. All 64 packaged static files and the eight checked
backend modules matched source. All 12 saved artifact files matched their recorded
sizes/hashes. SQLite integrity, six READY jobs, one Google identity, four remote
runs and zero active jobs/pending remote cleanups were preserved.

Account, GPU, storage, delivery and recovery-upload allowances were unchanged.
Analytics remains off with zero aggregate rows. Recovery reservations remained
18,141,370 bytes and the normal next admission is still 2026-09-12 02:24:37 UTC;
this does not establish a completed scheduled backup. No service, plan, GPU
invocation or extra backup retry was added by this release.

A fresh live public page loaded the new fingerprinted stylesheet and app script;
their fingerprints matched source hashes. Its computed footer bottom and button
shrink values were zero. This verifies fresh asset delivery, not a second live
private-management flow.
