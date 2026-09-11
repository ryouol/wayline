# Optional analytics QA — 2026-09-11

## What changed

The original consent adapter had no collector. The new optional first-party path
counts only four public page buckets in UTC daily aggregates. Its configuration,
validation, limits, retention and operator report are documented in
[the runbook](ANALYTICS.md). Production collection remains disabled; no tracking
provider, visitor profile or new subscription was added.

Review found a withdrawal edge case when localStorage remains readable but writes
fail. The client now retains current-document rejection and tries to remove the
old stored acceptance. Only successful explicit acceptance clears that rejection.
Tests cover failed removal too. Persistence failure can still prevent a changed
preference surviving a later document load; no cross-document guarantee is made
when both storage operations fail.

## Local verification

- 255 Python tests passed, including 19 collector/report/configuration cases.
  They cover disabled defaults, property validation, origin/consent/DNT/GPC gates,
  strict public schema, declared/streamed body ceilings, global rate limits,
  durable daily ceilings, physical retention while disabled, read-only reporting
  and selected configuration in encrypted recovery exports.
- All eleven Node suites passed. The new site suite exercises no consent,
  disabled or invalid config, private/account surfaces, blocked storage, privacy
  signals, delayed configuration, withdrawal, page exit and failed persistence.
- Strict Ruff, formatting for 40 files and mypy for 21 source files passed.
- Production image `d81b00c6577050fa65eb48e9dcb3e65695638301e70f10796612f75ebfb1275f`
  passed the non-root/read-only 512 MiB / 0.5 CPU smoke at a 208.1 MiB peak,
  including two sequential samples, a 64 MiB upload, download, share and revoke.

The real in-app browser used an isolated localhost installation with analytics
enabled under a disposable property label. Google, trials, Modal and recovery
were disabled there. Read-only CLI reports checked the actual SQLite totals:

| Step | Action | Total counts |
|---|---|---:|
| 1 | Open landing before consent | 0 |
| 2 | Explicitly allow analytics | 1 |
| 3 | Navigate to Privacy while accepted | 2 |
| 4 | Choose Essential only, then navigate to Terms | 2 |
| 5 | Opt in while viewing the account screen | 2 |
| 6 | Return to the public landing | 3 |

Final buckets were `/` = 2 and `/privacy` = 1, with no Terms or account event.
The test ended with Essential only, closed its browser tab and stopped its exact
server process. Disposable database/object/secret files were removed. The safe
aggregate report and verification receipt remain in the ignored local
`.lingbot-workspace/analytics-qa/` directory.

The separate [current-theme pass](CURRENT_THEME_QA.md) records six public-screen
contrast observations, mobile overflow and visible keyboard focus. It predates
this collector rollout and makes no private-studio or physical-device claim.

## Deployment

Runtime `b4dd89670034b7d0b0ca42c19cd0633b35b844b0` passed [exact-commit hosted CI](https://github.com/ryouol/lingbot-map/actions/runs/34631234915)
and became live on the existing [Wayline service](https://wayline-9ten.onrender.com/)
at `2026-09-11T18:10:32.618362Z`. Render deployment: `dep-dai47qmq1p3s73b22ijg`.

Read-only live verification passed:

- HTTPS health returned 200; all eight changed backend modules and all 64 static
  files matched source hashes.
- SQLite integrity was `ok`. All 12 saved artifact files matched their recorded
  sizes/hashes; the aggregate artifact metadata digest was unchanged.
- Six READY jobs, one Google identity, four remote runs, zero active jobs and
  zero pending remote cleanups were preserved.
- The analytics environment flag remained false, public configuration returned
  `analytics: null`, and the new aggregate table contained zero rows.
- Account, GPU, storage, scene-delivery and recovery-upload allowances were
  unchanged. Existing failed recovery reservations remained 18,141,370 bytes,
  with the normal next admission at 2026-09-12 02:24:37 UTC. This time is an
  eligibility gate, not evidence of a completed scheduled backup.

The release created no provider service, changed no plan or environment value,
invoked no GPU job and admitted no extra backup attempt. Independent documentation
review found no further inaccuracies. The runbook and evidence are a separate
documentation commit; the deployed runtime remains the tested commit above.
