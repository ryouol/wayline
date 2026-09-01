# Security review

Review date: 2026-09-01. Scope: the supported `lingbot_map.workspace` web
application, its browser client, the research-engine boundary, dependency locks,
and adjacent model-loading utilities. This is an application-code review, not a
penetration test or infrastructure attestation.

No known Critical or High application-code finding remains open in the
synthetic demo path. The conditional research runner and two edge controls below
remain explicit launch gates.

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
- Location: `lingbot_map/checkpoints.py`, `verify_checkpoint`, lines 33–50;
  `demo.py`, `demo_render/demo.py`, `benchmark/viewer.py`, and NPZ loaders;
  `lingbot_map/vis/sky_segmentation.py`, lines 434–440
- Evidence: PyTorch loads use `weights_only=True`; NumPy loads use
  `allow_pickle=False`; checkpoints and optional sky weights require exact
  digests, bounded regular files, safe permissions, and non-symlink paths;
  legacy automatic moving-revision sky-model acquisition fails closed.
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

## SEC-005 — Distributed throttling and proxy trust

- Rule ID: `FASTAPI-PROXY-001`, `FASTAPI-LIMITS-001`
- Severity: Medium
- Status: Open before public or multi-instance deployment
- Location: `lingbot_map/workspace/app.py`, `LoginLimiter`, lines 202–218;
  `docs/deployment.md`, lines 24–26 and 49–54
- Evidence: login throttling is intentionally process-local. Proxy header trust
  and distributed request/token/tenant limits are deployment responsibilities.
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

## SEC-007 — Cancellation could lose to late worker completion

- Rule ID: application business-logic and durable-state race review
- Severity: High
- Status: Remediated
- Location: `lingbot_map/workspace/database.py`, `Database.finish_job` and
  `Database.fail_job`; `lingbot_map/workspace/service.py`,
  `WorkspaceService._process_job`
- Evidence: result settlement now reads `cancellation_requested` and performs
  the `ready` or `cancelled` transition in the same SQLite transaction. A
  committed cancellation releases the reservation and causes the service to
  delete both database artifact rows and stored objects. Failure settlement also
  gives a committed cancellation precedence over a provider error.
- Impact: before the fix, cancellation could commit while a worker was storing
  output and the subsequent completion transaction could still mark the job
  ready, exposing an artifact the user had cancelled.
- Fix: implemented with regression tests for cancellation immediately before
  completion and cancellation immediately before worker failure.
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

## Browser review result

The supported workspace frontend uses `textContent`, explicit DOM construction,
same-origin fetches, HttpOnly session cookies, CSRF headers, no browser storage,
no third-party scripts, and no eval/HTML insertion sinks. CSP includes Trusted
Types enforcement. The offline benchmark report retains audited escaped HTML
templates; generated artifact URLs now pass a same-origin/protocol gate. The
in-app browser verified token sign-in, job creation/review, WebGL loading,
keyboard viewer controls, share creation, the unauthenticated share view, and no
browser errors at 1280 x 720. Mobile-viewport, screen-reader, contrast, and
cross-browser coverage remains an owner gate.
