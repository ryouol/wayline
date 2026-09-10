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

## Current external inputs

- No configured Modal CLI profile on 2026-09-10. User authorized Modal GPU; authentication is required for a real run.
- Google OAuth client credentials and preferred project not yet supplied.
- An owned video path is requested for the real acceptance run.
- Legal/contact identity is not supplied. Do not invent it or assert commercial clearance.

## Evidence

- Original uncommitted hardening and canvas replacement preserved in 027d338.
- Baseline: 99 Python tests and viewer lifecycle test passed in previous local run.
- Tracked-file high-confidence secret signature scan: no matches (2026-09-10); not a full history audit.
- Current local gate: 133 Python tests, strict lint/format, mypy for 18 modules, JavaScript syntax and four behavior suites passed. Wheel and Docker image built; production container smoke passed.
- Simplify and all four code-review skill passes completed; every finding/disposition is retained in `REVIEW.md`. Aggregate review size remains an open merge concern.
- New exports passed Khronos glTF validation. A synthetic VFR video verifies presentation timestamps; neither fixture proves real-model quality.
- Latest browser check could not run because the Mac is locked. Earlier 390px synthetic scene rendering predates final walk/calibration fixes.
