# Capture onboarding verification — 2026-09-11

The application now reports an authoritative Google reconstruction allowance:
available, processing, used, or temporarily exhausted. Fresh uploads are rejected
before parsing when blocked; completed idempotent replays still validate their
payload and return the original result. A transaction-time check prevents new
assets if eligibility changes while the file is being parsed.

The UI refreshes this state before upload, after queuing and completion, and on
focus. It handles a job finishing during initialization, stale account responses,
logout during terminal refresh and in-flight upload locks. Returning Google login
remains available when new-account capacity is full. The capacity callback
returns to a visible notice rather than a JSON error.

The picker shows the configured 60-second/64 MiB production limits. It checks
bytes locally and attempts metadata decoding without uploading the file. It
releases object URLs and timers on completion, reselection and logout. Unsupported
or stalled decoding allows server validation after upload. Invalid messages use
the error color; working and accepted states use neutral text.

## Evidence

- Full local Python suite: 212 passed, including scoped replay/conflict/expiry,
  transaction races, Google allowance settlement and signup-capacity callback.
- Six Node suites passed. The new behavioral suite covers account refresh
  ordering, UI gates, metadata lifecycle and stale-session cleanup.
- Real Chromium 153 reproduced the original CSP blocking blob video metadata;
  the explicit media-src directive resolved it without permitting blob scripts.
- Actual current packaged app.js with isolated fixture API responses accepted
  the licensed TUM 10-second MP4 as “3.2 MiB · 10.0 seconds · ready to upload”.
  A 64 MiB + 1 byte file and a generated 61-second MP4 were rejected locally.
  These browser checks issued GET requests only; no GPU or live account was used.
- At 390×844, document scrollWidth was 390, the picker fit, and the reconstruction
  button measured 350×48 pixels. No CSP or JavaScript errors were observed.
  This is desktop Chromium with viewport emulation, not a physical mobile test.

Private evidence is retained in .lingbot-workspace/real-capture-qa/
onboarding-browser-review.json and its screenshots. Input attribution and the
independent real reconstruction are documented in [REAL_CAPTURE_QA.md](REAL_CAPTURE_QA.md).

## Limits

Google callback tests use a mocked provider; prior real owner login evidence
remains in RENDER_QA.md. Signup capacity is still one on Render. These checks do
not prove second-account switching, physical phone decoding/touch performance,
or general reconstruction quality. Deployment verification is recorded separately.
