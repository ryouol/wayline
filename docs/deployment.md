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
process stops accepting work through the reverse proxy first, then joins its
worker for up to five seconds. On the next boot, durable running jobs are
requeued once or failed/refunded after their final attempt.

## Backups

Back up `workspace.sqlite3` through SQLite's online backup mechanism or a stopped
process, plus the entire `objects/` prefix and `runtime-manifest.json`. Test a
restore into an isolated data directory. Database rows and object bytes must be
restored to the same point in time.

## Observability required before public launch

Send structured logs to a restricted sink and alert on authentication failures,
upload rejections, job failure rate, stuck leases, queue age, storage errors,
quota exhaustion, and delete failures. Never log tokens, cookies, source paths,
signed URLs, video bytes, or raw customer filenames.

## Scale migration

The local architecture is intentionally explicit about its Postgres and
S3-compatible boundaries. Complete that migration, add distributed request
limits, use direct signed uploads, and run engine workers outside the web process
before adding a second application replica.
