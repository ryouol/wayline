# Workspace architecture

## Components

`lingbot_map.workspace.app` owns HTTP routing, sessions, CSRF, response security
headers, exact Host validation, declared-body prechecks, input/output models, and
sanitized API responses. It never exposes a filesystem path or object key.

`Database` owns tenant scoping, job transitions, expiring leases, attempt/worker
fences, transactional compute and storage/count quotas, durable rate buckets,
request idempotency, deletion outbox entries, usage ledger entries, share
hashes, provisional object claims, retention, cursor pagination, and recovery.
Mutation responses and their idempotency completion records commit in the same
SQLite transaction, so a process interruption cannot leave a changed resource
behind an `in_progress` replay record.
Every customer-owned lookup includes `tenant_id`.

`ObjectStore` owns opaque byte storage and is injected into the service.
`LocalObjectStore` uses normalized POSIX keys, root confinement, atomic
replacement, byte limits, hashes, restrictive permissions, and stable listing
for reconciliation. Contract tests exercise a non-default adapter wrapper.

`WorkspaceService` owns upload inspection and the worker. The worker claims one
durable job, renews its lease on stage changes, calls an engine, stores artifacts,
and settles or releases reservations. Every progress, artifact, failure, and
completion mutation must match both the claim's worker ID and cryptographic
attempt token. Startup and periodic maintenance recover only expired leases,
queue only the expired attempt's artifacts for deletion, enforce retention,
reconcile storage, and retry the deletion outbox. Before any upload or artifact
bytes touch disk, a durable claim reserves the maximum permitted bytes and an
in-flight slot against tenant, global, and physical minimum-free-space budgets.
After writing, the claim reconciles to the measured size. Startup and expiry
recovery measure interrupted objects before moving their exact bytes into the
deletion outbox.

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

Only queued jobs are claimed. A non-expired running lease is never recovered.
After expiry, the attempt token is fenced and the job is requeued until the
configured final attempt, when it fails and releases its reservation. A stale
worker cannot renew progress, publish an artifact, finish, fail, or clean a
newer attempt. A running cancellation sets a durable flag that the engine
observes. Final settlement rechecks the flag and attempt fence in the same
transaction as the `ready` transition. Cooperative process shutdown enters the
same cancellation callback, terminates and waits for a research child process,
cleans the attempt, and requeues without charging a retry. Terminal jobs are
immutable except deletion.

Logical deletion revokes access and enqueues every object key in one SQLite
transaction. The API returns `202` with `state: deleting`; physical deletion is
idempotent and retried with bounded exponential backoff. Pending-delete bytes
continue to count against tenant storage until object deletion succeeds.
Attempt artifacts are not returned, downloaded, or shareable until their job's
fenced `ready` settlement commits.

## Production migration boundary

SQLite and a local worker are appropriate for the single-instance demo, not for
horizontal scaling. Preserve the current service and API contracts while
replacing:

| Current | Production | Required behavior |
|---|---|---|
| SQLite repository | Postgres | preserve attempt fences, quota/idempotency/outbox transactions; RLS/tenant tests; `FOR UPDATE SKIP LOCKED`; migrations |
| Local object store | S3/R2/GCS | implement the full injected protocol; direct signed multipart upload; checksums; scoped IAM; lifecycle/delete reconciliation |
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
- Authenticated responses carry a one-way principal marker. A browser that sees
  the marker change aborts its epoch, destroys the viewer, and reloads before
  rendering data from the replacement account. CSRF values remain stable for a
  session, logout does not depend on a fresh CSRF header, and peer tabs broadcast
  logout/account changes and revalidate on focus.
- Public shares store only token hashes, expire, and cascade-delete with
  artifacts. Idempotent share responses derive the capability from a private
  installation secret; raw tokens are not stored in idempotency records.
- Checkpoints are regular non-symlink files, not group/world-writable, bounded,
  descriptor-hashed, copied into a private content-addressed path, and verified
  again before restricted deserialization.
- External runners use argument arrays, private per-job directories, capped
  output/logs, process-group termination, and no shell evaluation. Their GLB
  header is validated, report output is allowlisted, and stored provenance omits
  tenant IDs and local paths. The child environment is allowlisted, but this is
  not an OS sandbox; public deployments must place runners in dedicated
  containers/jobs with restricted filesystem, identity, and egress.
- Application body checks reject oversized declared lengths and count actual
  ASGI stream bytes before the next chunk reaches the parser, including chunked
  transfers. Partial multipart files close on rejection. Edge concurrency,
  upload timeouts and aggregate resource limits remain deployment requirements.
