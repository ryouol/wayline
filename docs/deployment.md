# Wayline deployment runbook — Render + Modal

## Single-instance beta deployment

- Linux, Python 3.11, one application instance
- TLS reverse proxy on the public edge
- Private application listener
- Persistent, encrypted volume for `LINGBOT_DATA_DIR`
- Nightly database and object backup with restore testing

Install from the built wheel or a pinned commit, never a moving branch. Set a
32+ character `LINGBOT_BOOTSTRAP_TOKEN`, production environment, secure cookie,
public base URL, data directory, and explicit upload/job limits. Run as a
dedicated unprivileged user with a read-only application filesystem and writable
data mount only.

Set tenant/global byte limits, the filesystem minimum-free floor, tenant/global
in-flight object limits, retention periods, durable upload/job/share rates, job
timeout, and shutdown deadline from the environment rather than accepting
defaults blindly. The local SQLite limits are safe for one instance; the
Postgres migration must preserve their transaction boundaries.

Set `LINGBOT_ALLOWED_HOSTS` to exact public DNS names. If omitted,
`LINGBOT_PUBLIC_BASE_URL` supplies its hostname; production refuses to start if
neither produces an allowlist. The app disables docs/OpenAPI in production and
rejects oversized declared bodies before parsing. Its ASGI receive wrapper also
counts streamed bytes, including chunked bodies and understated lengths, before
passing each chunk to the parser. Ordinary requests are capped at 64 KiB; the
upload route allows the configured file ceiling plus 1 MiB multipart overhead.
Authentication, guest rejection, tenant request rates, a single-parser admission
lock and temporary free-space checks precede multipart parsing. Only one file
and no text fields are accepted. A 15-minute server parser deadline closes
partial files and releases admission on timeout or disconnect. OpenAPI retains
the required binary file schema without an eager body dependency.
The reverse proxy must still
bound concurrent requests, slow uploads, multipart complexity and buffering:
per-request byte limits do not bound aggregate edge/parser resource use.

Terminate TLS at the edge and add HSTS there only after confirming the final
domain, preload, and subdomain policy. Configure forwarded-header trust to the
known proxy IPs; never trust forwarded headers from the public network.

## Render setup

The committed Dockerfile builds a pinned Python 3.11 image, installs the hashed
workspace dependency lock and runs as an unprivileged user. `render.yaml` selects
one Starter/0.5 CPU/512 MB service, a 5 GB persistent `/data` disk, `/healthz`, secure
cookies, 64 MiB uploads, 40 MiB artifacts and private environment settings.
The private workspace is `/data/wayline`: Render owns the mount root, so the
unprivileged application creates and secures its own child directory. Existing
installations must keep their configured data path; changing it without moving
the stopped workspace's database, objects and share secret creates an empty workspace.
Automatic deploys are off; use a reviewed commit for each manual deployment. See
[Render compute plans](https://render.com/docs/compute-plans).

The Render CLI is authenticated to `My Workspace`; a dedicated **Wayline** project
and **Production** environment were created on 2026-09-10. The `wayline` Starter
service (`srv-dahhn0u7bikc73e82h9g`) and 5 GB disk now exist there, with public URL
`https://wayline-9ten.onrender.com`. Keep all Wayline resources there; do not alter
the user's other projects. Hosting is $8.25/month before tax and overages. The
user accepted $20 as a monthly target with some flexibility; it is not an
enforced invoice cap. See [operating costs](operating-costs.md).

1. Connect `ryouol/lingbot-map` and
   `codex/production-ready-lingbot-map` within Wayline / Production. Review the
   Blueprint's Starter service and 5 GB disk and deploy the exact reviewed commit.
2. Supply `LINGBOT_PUBLIC_BASE_URL` and its exact `LINGBOT_ALLOWED_HOSTS` hostname.
   Keep the generated bootstrap token private as an operator credential.
3. Supply a Google Web OAuth client and secret through Render's secret environment
   settings. Register exactly `https://YOUR_HOST/auth/google/callback`. Google
   Cloud is used for OAuth configuration, not application hosting.
4. Authenticate Modal separately, deploy `modal_app.py`, and run its explicit
   checkpoint preparation entrypoint. Put a suitably scoped Modal token in the
   Render secret environment. Never put credentials in Git or frontend scripts.
5. Enable `WAYLINE_SIGNUP_ENABLED` and `WAYLINE_MODAL_ENABLED` for a controlled
   acceptance environment after setup. They are deliberately false in the
   initial Blueprint. This flag change is not acceptance evidence.
6. Run an owned short video through signup → upload → ready → camera replay →
   whole scene → download → expiring share in another session. Measure GPU time,
   VRAM, output size and failure behavior, then set trial and provider spend limits.

The private Modal worker is deployed and the pinned original checkpoint was
prepared and verified on 2026-09-10. A synthetic-input GPU diagnostic passed;
see [Modal QA](MODAL_QA.md) for measurements and the exact verification boundary.
Render deployment, a generated-input GPU round trip, download/share expiry and
revocation, visitor isolation and redeploy persistence passed; see [live QA](RENDER_QA.md).
The app runs commit `8e13910`. Google signup/returning login/logout passed in
`wayline-roy-20260910`; the initial signup ceiling is one account. An owned
capture, second-account switching, public Google branding, operator legal/contact
identity, provider budgets and upstream logging/edge-limit checks remain pending. Render holds a private personal-workspace Modal credential; it
is not scoped to one app. No credentials appear in Git or browser assets.

The production image passes `scripts/smoke_container.py` with a read-only root,
non-root user, 512 MiB memory and 0.5 CPU. Both `/data` and `/tmp` use disposable
disk-backed volumes for this test; a 512 MiB tmpfs would be below the upload
storage floor. The disk-root regression check makes `/data` root-owned and writable,
then verifies that the non-root app owns `/data/wayline` with mode `0700`.
Sample creation, multipart video upload, download, sharing and revocation
passed. A generated clip padded to the deployed 64 MiB ceiling uploaded and shared scene requests passed; peak cgroup memory was 210.4 MiB.
Actual server request overlap was not synchronized or established. Decoded dimensions
remain small, so this does not establish worst-case decoder or real-capture load.

## Modal execution

The web app uses private authenticated SDK calls. No public inference route is
registered in Modal. Each attempt uploads into a distinct volume prefix, records
its call identifier durably, and returns a GLB plus an allowlisted report. The
operator must provision both named volumes and keep access restricted. Failed
cancellation/volume deletion is retried from the durable cleanup table.

Resolve `requirements/modal.lock` for Linux x86-64/Python 3.11 using its recorded
compile command. CI verifies its complete hashed dependency closure. The image
explicitly copies `modal_app.py` because automatic source inclusion is disabled,
and imports the entrypoint, demo and original model during image build.

The initial runner uses A100 80 GB, one container, zero provider retries and a
600-second function timeout. It samples up to 120 frames and validates a pinned
checkpoint hash. Invocation expiry prevents stale queued work from beginning
inference indefinitely. Timeouts/admission limits are not exact invoice caps;
see [operating costs](operating-costs.md). Test crash recovery and remote deletion
against the deployed provider before treating cleanup as proven.

## Health and shutdown

`GET /healthz` exposes only `{"status":"ok"}` after the schema is current, the
object store passes an atomic write/delete probe, and both required worker threads
are alive; otherwise it returns `503` without revealing internal paths. The
successful dependency probe is cached briefly (two seconds by default) to avoid
turning health traffic into unbounded disk writes. The process stops accepting
work through the reverse proxy first, signals the active attempt through its
cancellation callback, terminates/waits for a research child process, and joins
its worker for up to `LINGBOT_SHUTDOWN_TIMEOUT_SECONDS`. Only expired leases are
recovered on boot or maintenance; stale workers are fenced by attempt/worker
identity.

Uploads and file-backed artifact writes reserve their maximum bytes and an in-flight slot
before touching storage. In-memory artifacts reserve their known bounded payload size. Claims enforce tenant/global logical budgets and the
configured physical free-space floor, then shrink to the measured object size.
Startup measures every leftover claim from a stopped process before exact-size
orphan cleanup; periodic maintenance does the same for expired claims. Alert on
claim recovery because it indicates an interrupted write or database/storage
availability gap.

The in-process worker has an iteration-level exception boundary with bounded
backoff, so a transient queue or maintenance error cannot silently kill it.
Readiness still fails if either required worker thread is not alive. Samples and
local maintenance use a separate worker from reconstruction and remote cleanup,
so a GPU wait does not block the playground. Disabling new Modal submissions does
not disable cleanup of remote attempts already recorded in the database.

The built-in CLI disables Uvicorn access logs. New share links use `/s#token`;
fragments do not enter HTTP request URLs. The share page sends the token in an
Authorization header to fixed `/api/public/share` and `/api/public/share/content`
paths. Expiry/revocation is checked for each request. Old token-in-path routes
were removed; issue new links for any local pre-rebuild shares.

Never collect Authorization/Cookie headers or request bodies in proxy/APM logs.
Google's `/auth/google/callback` contains a short-lived authorization code and
state in its query; verify Render/proxy log behavior and redact that query.
Application-level logging cannot certify upstream logging configuration.

## Backups

The snapshot tool coordinates the database, all private object files, runtime
manifest and `share-token.secret`. The supported `wayline` launcher takes an
exclusive workspace lock; snapshot creation refuses while that process is live.
Stop the application and take a verified snapshot into a **new directory outside
its data directory**:

```bash
python -m lingbot_map.workspace.backup create --data-dir /data/wayline --output /backup/wayline-YYYYMMDD
python -m lingbot_map.workspace.backup restore --snapshot /backup/wayline-YYYYMMDD --output /restore/wayline-YYYYMMDD
```

Creation uses SQLite's backup API and hashes every included file. Restore verifies
file hashes, database integrity and references, refuses an existing destination,
and removes incomplete output on failure. Tests recover scene bytes and an
idempotently generated share, proving the secret and database travel together.

Snapshots contain private captures and capability material. Encrypt and copy them
off the application disk with restricted access; verify a restore before switching
the live data path. On 2026-09-10 a pre-start Render maintenance snapshot and
separate server-environment export were encrypted to the operator's Mac. An
isolated Linux restore served the original artifact with its exact hash; see
[recovery procedure and evidence](RECOVERY_QA.md). Automation, retention, alerting,
separate key escrow and an isolated Render recovery drill remain open. Render's
automatic disk snapshots alone do not close this gate.

## Observability required before public launch

Send structured logs to a restricted sink and alert on authentication failures,
upload rejections, rate-limit hits, job failure rate, expired/stuck leases,
queue age, storage reconciliation mismatches, deletion-outbox age/retries,
provisional-claim recovery, quota exhaustion, and retention throughput. Never
log tokens, cookies, source paths, signed URLs, video bytes, or raw customer
filenames.

## Scale migration

The local architecture is intentionally explicit about its Postgres and
S3-compatible boundaries. Complete that migration, preserve transactional
quotas/idempotency/attempt fences/deletion outbox semantics, add distributed
login and edge byte/concurrency limits, use direct signed uploads, and run
engine workers outside the web process before adding a second replica.
