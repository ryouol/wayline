# Deployment runbook

## Supported demo deployment

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
rejects oversized declared bodies before parsing. The reverse proxy must also
cap total and multipart request sizes, including chunked bodies, because the
edge receives bytes before application validation.

Terminate TLS at the edge and add HSTS there only after confirming the final
domain, preload, and subdomain policy. Configure forwarded-header trust to the
known proxy IPs; never trust forwarded headers from the public network.

## Health and shutdown

`GET /healthz` exposes only `{"status":"ok"}` after the schema is current, the
object store passes an atomic write/delete probe, and the required worker thread
is alive; otherwise it returns `503` without revealing internal paths. The
successful dependency probe is cached briefly (two seconds by default) to avoid
turning health traffic into unbounded disk writes. The process stops accepting
work through the reverse proxy first, signals the active attempt through its
cancellation callback, terminates/waits for a research child process, and joins
its worker for up to `LINGBOT_SHUTDOWN_TIMEOUT_SECONDS`. Only expired leases are
recovered on boot or maintenance; stale workers are fenced by attempt/worker
identity.

Uploads and artifact writes reserve their maximum bytes and an in-flight slot
before touching storage. Claims enforce tenant/global logical budgets and the
configured physical free-space floor, then shrink to the measured object size.
Startup measures every leftover claim from a stopped process before exact-size
orphan cleanup; periodic maintenance does the same for expired claims. Alert on
claim recovery because it indicates an interrupted write or database/storage
availability gap.

The in-process worker has an iteration-level exception boundary with bounded
backoff, so a transient queue or maintenance error cannot silently kill it.
Readiness still fails if the worker thread itself is not alive.

The built-in CLI disables Uvicorn access logs because public share capability
tokens appear in URL paths. Configure every reverse proxy, CDN, APM agent, WAF,
and trace collector to disable or redact `/s/{token}` and
`/api/public/shares/{token}[/content]` paths before public traffic. Do not rely
on the application setting to sanitize upstream logs.

## Backups

Back up `workspace.sqlite3` through SQLite's online backup mechanism or a stopped
process, plus the entire `objects/` prefix, `runtime-manifest.json`, and the
private `share-token.secret`. The secret is required to replay an idempotent
share response; losing it does not reveal existing shares but makes such replay
unavailable. Test a restore into an isolated data directory. Database rows,
object bytes, and the secret must be restored to the same point in time.

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
