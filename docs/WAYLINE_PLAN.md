# Wayline delivery plan

The requested result is a real mobile-ready video-to-3D web application using the original LingBot-Map model, with Google sign-up, private scenes, traceable reconstruction stages, camera-path/frame replay, a final whole-scene view, deployment, local and remote QA, simplify/code-review, and a pushed branch. A synthetic demo is not acceptance evidence for reconstruction.

## Architecture decision

User selected Render + Modal on 2026-09-10. Keep the tested FastAPI/SQLite/object-store transaction boundaries for the initial single-instance Render service with a persistent disk. Serve frontend and API from the same Render origin to keep large uploads and Google session cookies straightforward. Modal runs bounded GPU jobs using private durable object references. Provide a reproducible Docker image and Render Blueprint with health checks, private environment secrets, storage/DB backup and restore. No Vercel or GCP hosting is planned. Original model package identifiers and attribution remain LingBot; all product branding becomes Wayline.

## Sequence and acceptance

1. Security: inventory endpoints, secret scan, private data boundaries, no shared-owner public onboarding. Add bounded isolated trials and Google identities. Test cross-user isolation, CSRF and OAuth state/replay handling.
2. Real engine: pinned original weights, private per-attempt staging, cancellation, timeouts, deterministic scene/camera export. Run an owned video on Modal and retain measured acceptance evidence.
3. Product: upload-first studio, mobile layout, truthful progress, source-frame timeline, camera-path playback, free exploration, final-scene mode, download and share. Product direction: dark editorial studio, warm neutral text, lime accent, large viewport and restrained controls.
4. Operations: reproducible build, health/TLS, storage/DB/secret backup and restore, bounded queue and GPU budget, Google OAuth configuration, deployed smoke tests.
5. Attached brief phases: metadata, icons, errors, consent, actual contact/legal placeholders only where owner inputs are absent, form/loading/error states, mobile/accessibility and visual QA.
6. Finish: simplify's three review agents, all code-review skill agents, fix findings, run required checks, push and inspect CI, audit every requirement.

## Current delivery status — 2026-09-11

[Wayline is live](https://wayline-9ten.onrender.com) as a restricted research
preview. The Render runtime is `1fbfe9a557dcc1e5799814d46590f364ef699e71`;
later documentation commits do not require a runtime deployment. The original
LingBot worker is deployed on Modal with its pinned, hash-verified checkpoint.
Google owner signup, returning login, logout and saved-scene persistence passed.
Signup remains capped at one account while the wider release checks are open.

A licensed real-camera TUM office clip passed the corrected pipeline: upload,
original-model inference, coherent 750,000-point scene, 30-frame replay, walking,
whole-scene view and matching browser download. The initial run exposed a
world-to-camera export defect; the fix was independently tested and verified
with a fresh deployed inference. The synthetic sample remains clearly labelled.
See [real-capture QA](REAL_CAPTURE_QA.md) for results and quality limitations.

## Operating allowance

The user accepts $20/month as a target with some flexibility. The approved
Render Starter instance and 5 GB disk cost $8.25/month before tax and usage.
Keep Hobby, one instance, manual deployments and no preview instances. Preserve
UNRENDER and RUSHES; do not change their resources or shared billing limits.

Wayline limits GPU admission to six 600-second reservations per rolling 30 days,
including queued work; four are used. The owner's included video is unused.
Scene delivery and recovery uploads have separate durable allowances. These
controls reduce exposure; they are not a provider invoice cap. See
[operating costs](operating-costs.md) and [capacity QA](GPU_CAPACITY_QA.md).

## Remaining acceptance and inputs

- The dedicated Modal workspace still needs its $0.50 verification completed
  in the owner's checkout. The production worker remains in the shared
  workspace; independent provider limits and credential isolation are unverified.
- Test an owned phone capture, a physical mobile browser and a second Google
  account. The TUM benchmark and desktop viewport emulation do not establish
  these results. Google credentials are already configured.
- Obtain approved public operator/contact and privacy/terms information.
  Keep the brief's explicit TODO scaffolds and analytics disabled until supplied;
  do not invent business details or assert commercial hosted-use clearance.
- Verify a complete automatic recovery set and restore. The manual encrypted
  backup restored successfully, but both admitted automatic attempts failed.
  The next normal admission opens September 12 at 02:24:37 UTC; stage diagnostics
  are deployed. Preserve failed-attempt reservations and the daily gate.
- Complete the remaining release checks recorded in
  [launch readiness](launch-readiness.md), including provider/logging and recovery
  boundaries. The full product goal is not complete and public signup is not open.

## Verification and review

- Original hardening and the fresh-canvas viewer fix are preserved in `027d338`.
- Current local and runtime CI gates passed: 226 Python tests, six Node suites,
  strict Ruff/formatting, mypy for 20 modules, wheel build and container smoke.
  [Runtime CI](https://github.com/ryouol/lingbot-map/actions/runs/34560538161)
  validates the deployed commit.
- Secret scanning included reachable Git history and exact live-credential
  matching; the recorded scan found no credential matches. Endpoint, identity,
  CSRF, storage and security scope are documented in
  [the production audit](PRODUCTION_UX_AUDIT.md).
- Desktop QA covers repeated samples, the corrected real scene, replay, walking,
  download, sharing/revocation/expiry and layouts at 390 pixels. This is not a
  physical-phone performance or touch test.
- Simplify's three passes and all four final code-review passes completed.
  [REVIEW.md](REVIEW.md) retains 90 numbered findings and dispositions; aggregate
  change-size concerns 19, 66 and 83 remain open. The branch is pushed and
  [PR #10](https://github.com/ryouol/lingbot-map/pull/10) remains a draft.
