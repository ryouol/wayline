# Security review

Review date: 2026-09-01. Scope: the supported `lingbot_map.workspace` web
application, its browser client, the research-engine boundary, dependency locks,
and adjacent model-loading utilities. This is an application-code review, not a
penetration test or infrastructure attestation.

No known Critical, High, or Medium repository-controlled finding remains open
in the synthetic demo path after the final remediation pass. The conditional
research runner, horizontal infrastructure migration, and edge/browser/legal
controls below remain explicit external launch gates.

## SEC-001 — Production metadata and Host exposure

- Rule ID: `FASTAPI-OPENAPI-001`, `FASTAPI-HOST-001`, `FASTAPI-HEADERS-001`
- Severity: Medium
- Status: Remediated
- Location: `lingbot_map/workspace/app.py`, `create_app`, lines 301–345;
  `lingbot_map/workspace/config.py`, `Settings.validate`, lines 113–145
- Evidence: production sets `docs_url=None` and `openapi_url=None`, installs
  `TrustedHostMiddleware` from an exact allowlist, and emits CSP, clickjacking,
  MIME-sniffing, referrer, permissions, and no-store controls.
- Impact: without these controls an attacker could amplify API discovery, poison
  host-derived links, frame the UI, or weaken browser isolation.
- Fix: implemented and regression-tested. HSTS is deliberately owned by the TLS
  edge rather than unconditionally asserted by the app.
- Mitigation: enforce the same Host allowlist and security headers at the edge.
- False positive notes: verify the deployed proxy does not replace these headers
  with weaker values.

## SEC-002 — Runner output and internal-path disclosure

- Rule ID: `FASTAPI-RESP-001`, `FASTAPI-FILES-001`
- Severity: Medium
- Status: Remediated
- Location: `lingbot_map/workspace/engines.py`, `_validate_glb`,
  `_public_report`, and `LingbotResearchEngine.run`, lines 113–158 and 318–372
- Evidence: the stored manifest contains checkpoint digest/size but no tenant or
  filesystem path; runner reports pass a bounded field allowlist; GLB magic,
  version, declared length, and byte limit are checked before storage.
- Impact: the previous boundary could have persisted local source/checkpoint
  paths and arbitrary runner report fields into downloadable or shareable
  metadata.
- Fix: split private execution input from public provenance and validate the
  output format before tenant-scoped storage.
- Mitigation: keep runner logs private and apply a separate artifact scanner for
  any future active-content formats.
- False positive notes: an operator can still place sensitive content inside a
  valid GLB; the current adapter only accepts trusted, configured runners.

## SEC-003 — Unsafe model/data deserialization and moving assets

- Rule ID: `FASTAPI-SUPPLY-001` and unsafe-deserialization review control
- Severity: Medium
- Status: Remediated
- Location: `lingbot_map/checkpoints.py`; `demo.py`; `demo_render/demo.py`;
  `benchmark/methods/lingbot_map.py`; `lingbot_map/aggregator/base.py`
- Evidence: PyTorch loads use `weights_only=True`; NumPy loads use
  `allow_pickle=False`; checkpoints and optional sky weights require exact
  digests, bounded regular files, group/world-write rejection, descriptor-bound
  hashing, and private content-addressed copies. Every direct PyTorch or ONNX
  model load consumes only a copied verified path; moving-revision acquisition
  fails closed, and generated sky-mask caches are bound to the model digest.
- Impact: a malicious pickle-capable checkpoint/NPZ or silently changed remote
  model could execute code or alter research output.
- Fix: implemented. The guarded downloader pins revision, size, and SHA-256.
- Mitigation: store verified weights read-only and record their digest in every
  job/release manifest.
- False positive notes: integrity is not licensing or model-safety clearance.

## SEC-004 — Multipart and chunked body denial of service

- Rule ID: `FASTAPI-LIMITS-001`, `FASTAPI-UPLOAD-001`
- Severity: Low
- Status: Partially mitigated; public-launch gate
- Location: `lingbot_map/workspace/app.py`, `security_headers`, lines 315–333;
  `lingbot_map/workspace/service.py`, `upload_video`, lines 151–215;
  `docs/deployment.md`, lines 17–22
- Evidence: declared request lengths are rejected before parsing, stored bytes
  are streamed with a hard ceiling, and media signature plus decoded duration,
  frames, and dimensions are validated. Chunked multipart traffic reaches the
  ASGI stack before the service stream limit.
- Impact: without an edge cap, a client could consume parser spool, disk, CPU, or
  connection resources before the application rejects the file.
- Fix: configure reverse-proxy limits for total body, multipart fields/parts,
  timeouts, and chunked transfers; move public scale to direct signed multipart
  object uploads.
- Mitigation: patched Starlette/python-multipart versions and per-tenant job
  reservations reduce—but do not remove—the edge DoS surface.
- False positive notes: mark complete only with deployed proxy configuration and
  an oversized/chunked integration test.

## SEC-005 — Distributed edge/login throttling and proxy trust

- Rule ID: `FASTAPI-PROXY-001`, `FASTAPI-LIMITS-001`
- Severity: Medium
- Status: Open before public or multi-instance deployment
- Location: `lingbot_map/workspace/app.py`, `LoginLimiter`, lines 202–218;
  `docs/deployment.md`, lines 24–26 and 49–54
- Evidence: upload, job, and share creation use durable transactional per-tenant
  rate buckets in SQLite. Login throttling remains intentionally process-local;
  proxy header trust and distributed IP/byte/concurrency limits are deployment
  responsibilities.
- Impact: multiple replicas reset the local counter, and incorrectly trusted
  forwarded headers can undermine IP-based throttles or audit trails.
- Fix: enforce distributed limits at the edge and restrict forwarded headers to
  exact proxy IPs.
- Mitigation: keep the app listener private and the single-instance demo bound
  to loopback.
- False positive notes: an existing gateway may supply this control; verify its
  live configuration and tests.

## SEC-006 — Research runner is a process boundary, not a sandbox

- Rule ID: `FASTAPI-INJECT-002` plus least-privilege execution control
- Severity: High if the research adapter is enabled on a public host
- Status: Conditional blocker; adapter remains research-only
- Location: `lingbot_map/workspace/engines.py`, `LingbotResearchEngine.run`,
  lines 352–395
- Evidence: the command is parsed into an argument vector with no shell, receives
  an environment allowlist and private HOME/TMP directories, and is terminated
  as a process group. It still executes with the web host's OS identity and
  filesystem visibility.
- Impact: a vulnerable or malicious configured runner processing attacker video
  could affect the host beyond its per-job directory.
- Fix: run reconstruction in a dedicated container/job identity with read-only
  code/weights, scoped object access, resource limits, seccomp/AppArmor (or
  platform equivalent), and restricted egress.
- Mitigation: the exact acknowledgement/checkpoint/command gate is closed by
  default, outputs remain `NOASSERTION`, and no billing path exists.
- False positive notes: an external worker implementation may provide the
  sandbox; the local command adapter alone does not.

## SEC-007 — Late/stale workers could mutate or clean a newer attempt

- Rule ID: application business-logic and durable-state race review
- Severity: High
- Status: Remediated
- Location: `lingbot_map/workspace/database.py`, `Database.finish_job` and
  `Database.fail_job`; `lingbot_map/workspace/service.py`,
  `WorkspaceService._process_job`
- Evidence: claims set a cryptographic attempt token and worker ID. Progress,
  artifact creation, completion, and failure require both; recovery selects
  only expired leases and clears ownership. Artifact keys and cleanup are
  attempt-scoped. Cancellation still wins atomically over completion/failure.
- Impact: without fences an old worker could publish after recovery or delete a
  newer worker's valid artifact, producing a ready job with missing bytes.
- Fix: implemented with regression tests for live-lease non-recovery, stale
  mutation rejection, current-attempt survival, cancellation races, and
  cooperative shutdown/requeue.
- Mitigation: the production Postgres repository must preserve this atomic
  ordering and include the same race tests; provider cancellation remains an
  efficiency control, not the source of truth for state.
- False positive notes: if completion commits first, the terminal ready state
  correctly wins and a later cancellation request is rejected.

## SEC-008 — Pre-existing runtime directories could retain permissive modes

- Rule ID: `FASTAPI-FILES-001` plus least-privilege storage review
- Severity: Medium
- Status: Remediated
- Location: `lingbot_map/workspace/database.py`, `Database.__init__` and
  `Database.connect`; `lingbot_map/workspace/storage.py`, `LocalObjectStore`;
  `lingbot_map/workspace/service.py`, initialization and runtime-manifest write
- Evidence: every startup corrects data/object/work directories to `0700`,
  SQLite plus existing WAL/SHM sidecars to `0600`, and the runtime manifest to
  `0600`; stored objects and research-runner manifests already use `0600`.
  A regression test starts from a deliberately permissive data directory and
  checks each resulting mode.
- Impact: `mkdir(mode=...)` does not tighten an existing directory. A
  misprovisioned volume could therefore have made hashed credentials, source
  names, job metadata, or artifact bytes visible to another local account.
- Fix: explicitly apply private modes rather than relying on the process umask
  or first-creation behavior.
- Mitigation: retain a dedicated unprivileged service identity and restrictive
  parent volume/IAM controls; POSIX mode bits are not a substitute for an
  encrypted volume.
- False positive notes: a newly created `0700` directory already prevented
  traversal, but the fix closes the pre-existing-volume case too.

## SEC-009 — Readiness could report healthy with failed dependencies

- Rule ID: deployment health and fail-closed availability review
- Severity: Medium
- Status: Remediated
- Location: `lingbot_map/workspace/service.py`, `WorkspaceService.ready`;
  `lingbot_map/workspace/app.py`, `health`
- Evidence: `/healthz` now returns success only when the database schema matches
  the running code, the object store passes an atomic write/delete probe, and a
  required worker thread is alive. Failures return a generic `503` without
  disclosing paths or exception details.
- Impact: the previous constant response could keep a broken instance in load
  balancer rotation even when it could not persist or process customer work.
- Fix: implemented with regression coverage for worker-required and dependency-
  failure states.
- Mitigation: keep a separate liveness probe for process supervision and avoid
  routing customer traffic until readiness succeeds.
- False positive notes: the single-instance local demo starts without a worker
  by design, so its in-process test client checks storage and schema only.

## SEC-010 — Database-first deletion could orphan customer bytes

- Severity: Medium
- Status: Remediated
- Location: deletion-outbox methods in `database.py`; delete/reconcile/drain
  methods in `service.py`
- Evidence: logical revocation, object-key capture, and row deletion commit with
  a durable outbox entry. Physical deletion retries with bounded exponential
  backoff; pending bytes remain charged. Startup reconciliation queues unknown
  objects and fails readiness on missing active objects. Durable, expiring
  provisional claims protect in-flight uploads/artifact writes from concurrent
  orphan reconciliation, and partial attempt artifacts are not published until
  the fenced ready transition commits.
- Impact: an object-store outage during deletion previously removed the only
  database pointer and left untracked customer bytes indefinitely.

## SEC-011 — Unbounded tenant storage and record growth

- Severity: High
- Status: Remediated
- Location: `config.py` and transactional create methods in `database.py`
- Evidence: byte, asset, unattached-upload, job, artifact, active-share, and
  compute limits are checked inside `BEGIN IMMEDIATE` transactions. Durable
  upload/job/share rates, terminal/unattached retention, cursor pagination, and
  bounded bulk deletion have regression coverage.
- Impact: zero-unit samples and retained uploads/artifacts could previously grow
  storage and SQLite without bound.

## SEC-012 — Cross-account browser state and GPU resource retention

- Severity: Medium
- Status: Remediated; external browser/accessibility matrix still required
- Location: `static/app.js` and `static/viewer.js`
- Evidence: logout, `401`, and principal change increment a session epoch,
  abort every in-flight request, clear tenant/job/share DOM state, and destroy
  fetches, event listeners, observers, WebGL buffers/program/shaders/context.
  A one-way marker on every authenticated response detects cookie/account
  changes made by another tab before the response is rendered.
- Impact: delayed responses or retained WebGL buffers could expose a previous
  tenant's metadata/scene after an account change on the same browser.

## SEC-013 — Capability share tokens in access logs

- Severity: Medium
- Status: Repository control remediated; edge verification remains a gate
- Location: CLI `uvicorn.run` in `app.py`; deployment runbook
- Evidence: built-in Uvicorn access logging is disabled and regression-tested.
  The runbook requires path redaction/disablement at CDN, proxy, WAF, APM, and
  trace layers.
- Impact: bearer share URLs copied into logs grant artifact read/download until
  expiry or revocation.

## Browser review result

The supported workspace frontend uses `textContent`, explicit DOM construction,
same-origin fetches, HttpOnly session cookies, CSRF headers, no browser storage,
no third-party scripts, and no eval/HTML insertion sinks. CSP includes Trusted
Types enforcement. A prior baseline in-app-browser pass verified the desktop
workflow at 1280 x 720. The final session-abort/WebGL-destruction changes have
static regression tests; mobile viewport, screen reader, contrast,
account-switch, and cross-browser execution remain explicit external gates.
