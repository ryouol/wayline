# Wayline launch readiness

Updated 2026-09-11. This is an implementation and verification record, not a public-launch approval.

## What works locally

- Isolated, expiring visitor playgrounds generate a CC0 synthetic scene without sharing an operator token.
- Private jobs, uploads, artifacts, quota reservations, idempotency, cancellation, retention and deletion use the existing SQLite/object-store transaction boundaries.
- Request parsing has declared-length and observed-stream byte ceilings, including chunked JSON/multipart bodies. Authentication/rates/free-space checks precede the single-file parser; one upload runs at a time with a 15-minute server deadline. Streamed-body rejection, valid/truncated multipart and disconnect cleanup passed through Render; the full 900-second application deadline passed over loopback. Broader edge/load behavior remains open. See `RELIABILITY_QA.md`.
- Google OAuth has browser-bound one-use state, PKCE, nonce and signed ID-token verification. Protocol/identity tests use a mocked provider; real owner signup, returning login, logout and scene persistence now passed. The live Google-account ceiling is two, opening one additional first-come pilot slot. A fresh signed-out browser reached Google sign-in; actual second-account switching remains unverified. See [pilot onboarding QA](ONBOARDING_QA.md).
- Google accounts receive one successful video reconstruction, with bounded attempts and capacity. Scene deletion does not replenish the allowance. Synthetic jobs settle zero compute units. The UI shows authoritative allowance and configured capture limits before upload, preserves returning login at full signup capacity, and validates local file metadata. Fresh blocked uploads reject before parsing while completed idempotent replays remain valid. See [onboarding QA](ONBOARDING_QA.md).
- The original LingBot Modal deployment, pinned checkpoint preparation, private per-attempt staging, transport deadlines and durable cleanup are implemented. Disabling new submissions retains cleanup responsibilities. A licensed real-camera office benchmark exposed an exporter camera-convention defect; the corrected exporter and matching trace are deployed. The initial artifact and offline diagnostic are distinguished from fresh verification in [real-capture QA](REAL_CAPTURE_QA.md). Owned-phone quality remains unverified.
- Separate sample and research workers keep the playground responsive while reconstruction waits on the GPU. Health requires both workers; shutdown signals both.
- Reconstruction export includes glTF Y-up colored points, camera calibration/poses, actual presentation timestamps, cumulative point counts and source thumbnails.
- Viewer supports frame-by-frame camera replay, whole-scene orbit, and walk controls from a captured position. Walk navigation has no collision detection or metric-scale guarantee; the output is a point cloud, not a textured mesh.
- Shared links use `/s#capability` and fixed API paths with authorization headers. Expiry/revocation is checked on every content request. The shared viewer supports replay and exploration.
- Offline snapshots verify database integrity, referenced object sizes/hashes and the share secret; restore requires a fresh destination. The CLI prevents simultaneous runtime/snapshot access.
- Explicit online snapshots copy the running SQLite database and its referenced objects, reject missing/corrupt concurrent copies, and exclude later publications. Default snapshots still require the stopped runtime. An optional recovery worker adds scheduled age encryption, bounded multipart upload/readback verification and retention; it is enabled on Render, but its first live attempt failed and no completed automatic recovery set is verified yet. See [scheduled recovery QA](SCHEDULED_RECOVERY_QA.md).
- A Dockerfile and single-instance Starter/5 GB Render Blueprint validate. The Wayline project, Production environment, Starter service and disk exist. The user accepted $20/month as a target with flexibility. Application delivery/GPU allowances reduce exposure without guaranteeing a bill total. The root-owned disk permission issue is fixed with `/data/wayline`. [Render QA](RENDER_QA.md) records the generated-input original-model run, visitor isolation, shares and redeploy persistence; [the latest deployment receipt](DESIGN_RELEASE_QA.md) tracks runtime `9516dbf`, [onboarding QA](ONBOARDING_QA.md) records the bounded pilot, and [recovery QA](SCHEDULED_RECOVERY_QA.md) records the backup rollout.

## Verification boundary

The 2026-09-10 browser pass rendered repeat 5,908-point synthetic scenes and a separate 750,000-point/120-frame fixture. Camera replay reached the last frame; walking, reset, logout cleanup, anonymous sharing, byte-identical GLB download and automatic expiry passed. Private and shared layouts had no horizontal overflow at 390×844. See `BROWSER_QA.md` for the evidence and limits. This is desktop browser and viewport-emulation evidence, not physical mobile or real-model acceptance.

The 2026-09-11 pass adds a licensed real-camera TUM office capture through the original model, after fixing the exporter's pose convention. The fresh deployed run produced a coherent 750,000-point/30-frame scene in 80.356 seconds; replay, walking/reset, matching browser download and share revocation passed. The exact artifact also passed a 390×844 desktop Chromium view. Four of six GPU admissions are used; the owner's free video is unused. This is bounded benchmark evidence, not owned-phone, physical-mobile, metric-accuracy or commercial-use acceptance. See `REAL_CAPTURE_QA.md`.

Shared GPU capacity is also checked before fresh uploads and job admission,
including pending jobs and conservative remote charges. The UI refreshes capacity
with personal eligibility; completed request replays remain valid. Capacity-only
worker denials before any remote attempt preserve personal retries. That capacity
revision passed 226 Python tests and six Node suites; see `GPU_CAPACITY_QA.md`.
The subsequent redesign passed 229 Python tests, ten Node suites and hosted CI,
and is deployed as `9516dbf`. Live Google returning login, saved-scene rendering
and all 64 deployed static-file hashes passed; see `DESIGN_RELEASE_QA.md`.
Cost allowances are unchanged and this release invoked no GPU job.

Automated coverage includes API isolation/CSRF, identity/trial expiry, one-video allowance, mocked Modal cancellation/deadlines, sampling/export, viewer teardown/trace/timeline and backup/restore. See `REVIEW.md` for final check results. A reconstruction fixture passed the Khronos glTF Validator with zero errors and warnings. Fixtures and transport mocks are not real-model acceptance.

## Remaining acceptance and operational work

One additional first-come pilot signup is enabled with all compute, storage and
delivery budgets preserved. The attached brief permits explicit placeholders for
missing operator legal/contact/analytics details; those remain disclosures, not
approved policies. Dedicated billing isolation, full-capacity disaster recovery
and a custom domain are follow-up work, not new prerequisites for this bounded
pilot. These distinctions do not mark the outstanding product or security checks
complete.

- [x] Authenticate Modal, deploy the private worker and prepare the verified original checkpoint. Completed 2026-09-10; a generated-video diagnostic also passed.
- [ ] Run a short owned video through the actual GPU: upload → status → ready → replay → walk → whole scene → download → expiring share in another session. Record cold/warm latency, GPU/CPU/memory cost, output bytes, failure rate and quality.
- [x] Configure the Google OAuth client, exact callback and private secrets; verify owner signup, returning login and logout. Completed in `wayline-roy-20260910`; the initial account ceiling of one is now two for the bounded pilot.
- [ ] Verify a second Google account's isolated workspace, video flow and returning login; complete public brand/policy configuration before broader signup.
- [x] Deploy the reviewed commit to Render; verify HTTPS/health, private authentication, configured limits, a generated-input GPU run, shares, sampled secret/log checks and persistence across redeployment. See `RENDER_QA.md`.
- [ ] Complete deployed edge/load/shutdown testing and upstream proxy logging verification, including OAuth callback query redaction.
- [x] Exercise a generated 4096×4096 H.264 capture and its 64 MiB padded copy through the deployed upload endpoint, verify metadata, and delete both test assets. Local container and live Render evidence are in `CAPACITY_QA.md`; this does not close the remaining load/codec/deadline or real-capture gates.
- [x] Cancel one actual original-model GPU invocation through the app during inference and verify zero remaining GPU inputs/containers, no published artifact, unchanged Google allowance, and automatic physical cleanup after the full unmodified grace period. See `RELIABILITY_QA.md` for the generated-input evidence.
- [ ] Validate provider limits/alerts and the remaining failure/crash cleanup boundaries. Successful-run cleanup, due-record cleanup after restart, and the live running-inference cancellation/grace-period case passed. The app's admission budget is not a provider invoice cap.
- [x] Export the live Render database/objects/share secret and server environment encrypted; restore and serve the original artifact in an isolated Linux container. See `RECOVERY_QA.md`.
- [x] Implement scheduled encrypted offsite recovery and seven-set retention, and enable the worker on Render. Local tests and a constrained real-SDK transfer passed; implementation and enablement do not prove a completed automatic live copy. See `SCHEDULED_RECOVERY.md` and `SCHEDULED_RECOVERY_QA.md`.
- [ ] Verify a complete automatic live recovery set, its readback/restore and live retention behavior. The first attempt failed after one 8 MiB part uploaded; a later read of that part succeeded. The reviewed retry fix deployed, but its single operator retry also failed. The failing operation remains unknown; safe stage diagnostics are added for the next normally admitted attempt. See `SCHEDULED_RECOVERY_QA.md`. Existing verified manual recovery sets remain preserved.
- [ ] Validate recovery at the full workspace capacity, configure external failure/staleness alerts, escrow the recovery key separately, and run an isolated replacement-Render recovery drill. A smaller constrained-container transfer and manual Linux restore do not close these gates.
- [x] Verify the licensed real-camera benchmark on desktop: original-model reconstruction, replay, walking/reset, matching browser download and share revocation. See `REAL_CAPTURE_QA.md`; redesign fixture checks did not run new inference.
- [ ] Complete owned-capture acceptance and at least one physical mobile browser; include long uploads, real scene sizes, camera calibration, touch gestures, accessibility and contrast. Existing benchmark and desktop viewport evidence do not establish physical-device performance or owned-phone quality.
- [ ] Resolve model/checkpoint/data terms and permitted hosted use. `MODEL_PROVENANCE.md` remains authoritative; commercial clearance is not asserted.
- [ ] Supply operator identity, approved privacy/terms and contact information. Select a custom domain if desired; the Render HTTPS origin already works. Analytics stays off until an approved collector and consent policy exist.

## Scope and scale

The first promise is a private short-video reconstruction with trace replay, exploration, download and sharing. Anchored comments, collaborative editing and scene versions are future work. Billing is planned in `operating-costs.md`; no checkout or paid credit entitlement exists.

The invited beta uses one Render instance with SQLite and private persistent files. Postgres and object storage are later scaling work, not prerequisites for this bounded deployment. A Render disk prevents horizontal scaling and zero-downtime deploys. Do not advertise general availability, unlimited captures or highly available storage from this configuration.
