# Wayline launch readiness

Updated 2026-09-10. This is an implementation and verification record, not a public-launch approval.

## What works locally

- Isolated, expiring visitor playgrounds generate a CC0 synthetic scene without sharing an operator token.
- Private jobs, uploads, artifacts, quota reservations, idempotency, cancellation, retention and deletion use the existing SQLite/object-store transaction boundaries.
- Request parsing has declared-length and observed-stream byte ceilings, including chunked JSON/multipart bodies. Authentication/rates/free-space checks precede the single-file parser; one upload runs at a time with a 15-minute server deadline. Timeout/disconnect/storage-failure recovery is tested. Deployed edge behavior remains unverified.
- Google OAuth has browser-bound one-use state, PKCE, nonce and signed ID-token verification. Protocol/identity tests use a mocked provider; actual Google sign-in remains unverified.
- Google accounts receive one successful video reconstruction, with bounded attempts and capacity. Scene deletion does not replenish the allowance. Synthetic jobs settle zero compute units.
- The original LingBot Modal deployment, pinned checkpoint preparation, private per-attempt staging, transport deadlines and durable cleanup are implemented. Disabling new submissions retains cleanup responsibilities. A real GPU run on a generated diagnostic clip passed; owned-capture quality remains unverified. See `MODAL_QA.md`.
- Separate sample and research workers keep the playground responsive while reconstruction waits on the GPU. Health requires both workers; shutdown signals both.
- Reconstruction export includes glTF Y-up colored points, camera calibration/poses, actual presentation timestamps, cumulative point counts and source thumbnails.
- Viewer supports frame-by-frame camera replay, whole-scene orbit, and walk controls from a captured position. Walk navigation has no collision detection or metric-scale guarantee; the output is a point cloud, not a textured mesh.
- Shared links use `/s#capability` and fixed API paths with authorization headers. Expiry/revocation is checked on every content request. The shared viewer supports replay and exploration.
- Offline snapshots verify database integrity, referenced object sizes/hashes and the share secret; restore requires a fresh destination. The CLI prevents simultaneous runtime/snapshot access.
- A Dockerfile and single-instance Starter/5 GB Render Blueprint validate. The Wayline project and Production environment exist in the authenticated Render account, but no paid service has been created. The strict $20 cap is unresolved because Render does not document a per-project hard invoice limit. Application delivery/GPU allowances reduce exposure without guaranteeing a bill total.

## Verification boundary

The 2026-09-10 browser pass rendered repeat 5,908-point synthetic scenes and a separate 750,000-point/120-frame fixture. Camera replay reached the last frame; walking, reset, logout cleanup, anonymous sharing, byte-identical GLB download and automatic expiry passed. Private and shared layouts had no horizontal overflow at 390×844. See `BROWSER_QA.md` for the evidence and limits. This is desktop browser and viewport-emulation evidence, not physical mobile or real-model acceptance.

Automated coverage includes API isolation/CSRF, identity/trial expiry, one-video allowance, mocked Modal cancellation/deadlines, sampling/export, viewer teardown/trace/timeline and backup/restore. See `REVIEW.md` for final check results. A reconstruction fixture passed the Khronos glTF Validator with zero errors and warnings. Fixtures and transport mocks are not real-model acceptance.

## Required before inviting video testers

- [x] Authenticate Modal, deploy the private worker and prepare the verified original checkpoint. Completed 2026-09-10; a generated-video diagnostic also passed.
- [ ] Run a short owned video through the actual GPU: upload → status → ready → replay → walk → whole scene → download → expiring share in another session. Record cold/warm latency, GPU/CPU/memory cost, output bytes, failure rate and quality.
- [ ] Configure the Google OAuth client, approved callback origin and secrets; verify real signup, returning login, logout and account switching.
- [ ] Deploy the exact reviewed image/commit to Render and verify health, TLS, allowed host, upload limits, shutdown/recovery, logs and secrets there.
- [ ] Validate provider limits/alerts, remote cancellation and failure/crash cleanup. Successful-run physical cleanup, explicit SDK cancellation and restarted-worker cleanup of a deliberately due record passed on Modal; running-inference cancellation and the full grace-period wait remain open. The app's admission budget is not a provider invoice cap.
- [ ] Configure encrypted offsite backups and run a deployed restore drill. Local offline snapshot tests do not prove the offsite schedule or Render recovery procedure.
- [ ] Complete real-capture desktop QA and at least one physical mobile browser; include long uploads, real scene sizes, camera calibration, touch gestures, accessibility and contrast. Synthetic replay/walk/share checks have passed in the desktop browser.
- [ ] Resolve model/checkpoint/data terms and permitted hosted use. `MODEL_PROVENANCE.md` remains authoritative; commercial clearance is not asserted.
- [ ] Supply operator identity, approved privacy/terms, contact information and the final domain. Analytics stays off until an approved collector and consent policy exist.

## Scope and scale

The first promise is a private short-video reconstruction with trace replay, exploration, download and sharing. Anchored comments, collaborative editing and scene versions are future work. Billing is planned in `operating-costs.md`; no checkout or paid credit entitlement exists.

The invited beta uses one Render instance with SQLite and private persistent files. Postgres and object storage are later scaling work, not prerequisites for this bounded deployment. A Render disk prevents horizontal scaling and zero-downtime deploys. Do not advertise general availability, unlimited captures or highly available storage from this configuration.
