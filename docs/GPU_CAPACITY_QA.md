# Shared GPU capacity verification — 2026-09-11

The preview has two independent limits: a Google account's included successful
video and Wayline's shared Modal allowance. A free personal video does not imply
that shared GPU capacity is currently available. The UI now checks both before
upload, on focus, after queuing/completion and on manual refresh. A failed status
check disables upload for operators as well as Google accounts.

## Admission policy

Each recorded remote attempt reserves 600 seconds for a rolling 30 days. Pending
research jobs also hold 600 seconds. Fresh uploads and jobs stop when those
charges and holds fill the configured allowance. New job admission and remote
reservation run inside SQLite write transactions, so concurrent requests cannot
both take the last slot. Remote dispatch excludes its own pending hold while
inserting the durable charge. Another charged running job can temporarily be
counted twice; this deliberately understates availability until it settles.

A queued cancellation frees its hold. Once a remote attempt is recorded, failure,
cancellation, cleanup and scene deletion do not refund its charge. Recovery needs
another slot. If a worker is denied capacity before any remote attempt for that
job, its personal retry reservation is reclassified in the fenced failure
transaction, retaining the ledger's amounts and timestamps. That exemption
survives scene deletion. A prior charged or uncertain attempt prevents exemption.

Completed idempotent uploads and job submissions still return the original
response; changed payloads still conflict. Upload capacity is checked before
multipart parsing and again before creating a new asset. The static engine
descriptor remains unchanged; only its serialized availability includes current
capacity. Synthetic samples and local research engines do not use this gate.

## Local evidence

The full local suite passes 226 Python tests and six Node suites, together with
strict Ruff, formatting and mypy checks. Fourteen Python cases are dedicated to
shared capacity; the browser suite includes both operator and trial entry races.

`tests/test_modal_capacity.py` covers concurrent last-slot admission, hold
conversion/cancellation, durable charges, crash recovery, the rolling window,
both upload gates, replay/conflicts, worker retry settlement/deletion, stale
worker fencing and sample/local-engine isolation. Tests use disposable databases
and mocked Modal transport; no provider jobs or live limit changes are needed.

`tests/capture-onboarding.test.js` exercises delayed engine responses, no upload
when full, reopening on focus, fresh-response ordering, logout races, operator
completion and a single initial engine fetch alongside the account check.

These checks establish application admission behavior. They do not create a
provider invoice cap, measure additional compute/storage/traffic charges, or
replace the outstanding provider-isolation and recovery acceptance work.
See [operating costs](operating-costs.md) for the unchanged $20 monthly target.

## Deployed verification

Render deploy `dep-dahnr4fqj5pc739q5i50` is live on
`1fbfe9a557dcc1e5799814d46590f364ef699e71` after
[CI passed](https://github.com/ryouol/wayline/actions/runs/34560538161),
including the production container smoke test. The existing Starter service,
single instance, disk and environment were preserved; Modal's validated GPU
worker did not need redeployment.

- HTTPS health returned 200. Public app.js and all four changed server modules
  matched the reviewed source by SHA-256. Authenticated engine availability was
  true, consistent with four of six admissions used and no queued/running jobs.
- All six existing jobs remained READY; pending remote cleanup was zero. The
  sole Google account still had zero consumed reconstruction units.
- The real browser retained the owner's Google session after reload, showed one
  video available and the 60-second/64 MiB limits, and loaded its saved 5,908-point
  synthetic scene. This is a session/persistence check, not another inference.
- GPU seconds (3,600), scene delivery (2,000,000,000 bytes), Google signup (one),
  and recovery upload (10 GiB) allowances were rechecked unchanged.

No upload or GPU invocation was submitted and live capacity was never forced to
exhaustion. Exhaustion, races and reopening were exercised in isolated tests.
The private receipt is retained under .lingbot-workspace/capacity-release/.
