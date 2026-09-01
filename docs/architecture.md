# Workspace architecture

## Components

`lingbot_map.workspace.app` owns HTTP routing, sessions, CSRF, response security
headers, exact Host validation, declared-body prechecks, input/output models, and
sanitized API responses. It never exposes a filesystem path or object key.

`Database` owns tenant scoping, job transitions, leases, quota reservations,
usage ledger entries, share hashes, and recovery. Every customer-owned lookup
includes `tenant_id`.

`ObjectStore` owns opaque byte storage. `LocalObjectStore` uses normalized POSIX
keys, root confinement, atomic replacement, byte limits, hashes, and restrictive
permissions.

`WorkspaceService` owns upload inspection and the worker. The worker claims one
durable job, renews its lease on stage changes, calls an engine, stores artifacts,
and settles or releases reservations. Startup recovery discards artifacts left
before a durable `ready` transition.

`ReconstructionEngine` owns only estimate, provenance, and execution. The
synthetic engine is enabled. The LingBot command engine is research-only and
requires rights acknowledgement, runner configuration, checkpoint path, and
exact checkpoint SHA-256. Optional sky masking requires its own path and digest;
automatic model downloads are disabled.

## Job invariant

```text
queued → running(validating → generating/reconstructing → exporting → storing)
       → ready
       → failed
       → cancelled
```

Only queued jobs are claimed. A startup moves an interrupted running job back to
queued once; the next interruption fails it and releases its reservation. A
running cancellation sets a durable flag that the engine observes. Terminal
jobs are immutable except deletion.

## Production migration boundary

SQLite and a local worker are appropriate for the single-instance demo, not for
horizontal scaling. Preserve the current service and API contracts while
replacing:

| Current | Production | Required behavior |
|---|---|---|
| SQLite repository | Postgres | transactional reservation; RLS/tenant tests; `FOR UPDATE SKIP LOCKED`; migrations |
| Local object store | S3/R2/GCS | direct signed multipart upload; checksums; scoped IAM; lifecycle/delete policy |
| Worker thread | Dedicated worker pool | leases/heartbeats; bounded tenant concurrency; timeout; cancellation; retry class |
| Local artifact response | Signed object response | short expiry; content disposition; audit log |
| Process login limiter | Edge limiter | distributed limits by IP, token, tenant, bytes, and job rate |

Do not pass GLB bytes through Modal RPC. Modal documents a
[100 MB payload limit](https://modal.com/docs/guide/troubleshooting); workers
should exchange object keys and small manifests, exactly as the reference runner
does.

## Threat boundaries

- Browser input is untrusted: content type, extension, magic bytes, decoded
  metadata, byte count, frame count, dimensions, and duration are bounded.
- API identifiers are opaque database IDs and always paired with tenant ID.
- Public shares store only token hashes, expire, and cascade-delete with artifacts.
- Checkpoints are regular non-symlink files, not world-writable, bounded, and
  SHA-256 verified before restricted deserialization.
- External runners use argument arrays, private per-job directories, capped
  output/logs, process-group termination, and no shell evaluation. Their GLB
  header is validated, report output is allowlisted, and stored provenance omits
  tenant IDs and local paths. The child environment is allowlisted, but this is
  not an OS sandbox; public deployments must place runners in dedicated
  containers/jobs with restricted filesystem, identity, and egress.
- Application body checks reject oversized declared lengths; the production
  edge remains responsible for total/multipart limits on chunked transfers.
