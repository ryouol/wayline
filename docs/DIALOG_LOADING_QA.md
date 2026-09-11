# Dialog loading feedback — 2026-09-11

Source `fe07999` keeps the existing Working… indicator inside the active native
dialog. It uses the existing request-controller set, so overlapping requests,
errors and session changes do not create a second busy-state counter. A bounded
dialog-order set records actual opening order for both pending and error feedback.

## Local browser evidence

An isolated Chromium fixture used a precomputed scene derived from CC BY 4.0 TUM data and a
12-second delay on inventory requests. A later check also delayed the local Share
POST. Neither exercise used a Google account, production scene or GPU invocation.

1. **Management loading — healthy after fix.** At 390×844/light, the pending strip
   was inside the dialog at x19–371 and y25–71. Document width stayed 390px.
   Closing while requests remained pending moved feedback to BODY; completion hid it.
2. **Narrow scrolling — healthy after fix.** At 320×568/dark, the strip stayed at
   y25–71 while dialog scrollTop changed from 0 to 332.5 of 333. Document width
   stayed 320px. These captures preceded the later opening-order helper; that
   helper changed ownership only, and the CSS stayed identical.
3. **Asynchronous modal order — fixed and verified.** Share was clicked, then
   Delete scene opened confirmation while Share waited. The late response opened
   shareDialog above confirmDialog even though the share element occurs first in
   the DOM. Browser focus and the pending indicator both belonged to shareDialog.
   Done restored confirmation ownership. Keep it preserved the scene. At the end,
   there were no open dialogs and the hidden status was attached to BODY.

All five screenshots were saved and inspected in the ignored
`.lingbot-workspace/dialog-loading-qa/report.md` illustrated report. The temporary
server, tabs, data and token were removed; the local share is consequently invalid.
Viewport overrides were reset. No physical-mobile, screen-reader announcement or
full accessibility claim follows from these checks.

## Regression and review scope

The actual app-script harness exercises overlapping inventory requests, rejection
while another request remains pending, closing/nesting, session reset and late
old-session completion. The reverse-order regression invokes the real Share and
Delete handlers; it verifies status/error ownership and that Keep it sends no
DELETE. Existing direct-dialog test setup now uses the production opening helper.

All 11 Node suites passed after the final fix. The local Python suite passed
255 tests in 27.05 seconds; the final subsequent delta was JavaScript/tests only.
JavaScript syntax, Modal Ruff/format checks and diff checks passed. Three simplify
passes and all four code-review subskills completed; the two independent reports
of the modal-order defect were fixed and re-reviewed. Model-context was N/A.
The aggregate PR-size finding remains open.

The separate `abd3f43` commit adds existing project license/notices/provenance
files to the Modal image recipe and clarifies unresolved hosted-use rights.
It changes no inference model, checkpoint, admission limit or enablement setting.
See [model provenance](../MODEL_PROVENANCE.md).

## Release verification

[Exact-source CI](https://github.com/ryouol/lingbot-map/actions/runs/34637277544)
passed for `abd3f4329209e1d046603f8fa311d81166a5636c`: 255 Python tests in
32.20 seconds, all 11 Node suites, lint/type/format, wheel and production-container
checks. The constrained 512MiB/0.5CPU smoke peaked at 200.8MiB and passed its
64MiB multipart upload/shared-delivery checks.

Render deployment `dep-dai55llg1s2s73cgvmfg` became live at
`2026-09-11T19:14:07.166720Z`. The post-deployment inspection verified all 64
static assets and eight backend modules against source, SQLite integrity, health
200 and all 14 saved artifact files, including the newly completed account scene.
Seven READY jobs, five remote runs, no active jobs or pending remote cleanup,
configured limits and recovery reservations were preserved. A fresh public
browser loaded the new app/CSS fingerprints. This was not another live private
management-flow test.

The existing `royluo05/main/wayline-reconstruction` Modal app also deployed with
all three notice files. Build/import checks passed; deployment exited zero.
Provider statistics were zero backlog, zero inputs and zero runners both before
and afterward. No inference/checkpoint preparation ran. Model/checkpoint selection,
limits, service plans, secrets and analytics enablement were unchanged; analytics
remains off. Complete derived-code licensing remains unresolved.

The next automatic recovery admission remains September 12 at 02:24:37 UTC. No
extra backup retry or ledger reset was made. The full product goal remains open;
see [launch readiness](launch-readiness.md).
