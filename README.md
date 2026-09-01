# 3D Scene Workspace

An authenticated workspace for turning a video-to-3D engine result into a
durable, reviewable artifact: queued job, stage-based progress, browser-native
point-cloud viewer, download, deletion, and expiring sharing.

The repository also contains the LingBot-Map research model. Its checkpoint and
training-data commercial rights are unresolved, so that adapter is disabled by
default, marked `commerciallyCleared: false`, and has no billing path. The
working zero-cost demo uses an explicitly CC0 synthetic point cloud and makes no
claim about LingBot quality or performance.

## Run the complete local workflow

Use Python 3.11:

```bash
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
.venv/bin/lingbot-workspace --dev
```

The server prints a high-entropy development token once and listens on
`http://127.0.0.1:7860`. Sign in with that token, choose **Create synthetic
scene**, and the worker will persist a real GLB plus provenance manifest. The
result can be orbited in the bundled WebGL viewer, downloaded, shared through a
24-hour permissioned link, or deleted with all associated stored objects.

`python webui/server.py --dev` remains as a compatibility launcher.

## What is implemented

- High-entropy bearer-token login exchanged for an HTTP-only, SameSite session
  and rotating CSRF token.
- Tenant checks on every asset, job, artifact, download, and share operation.
- SQLite state with WAL mode, explicit job transitions, worker leases, one
  retry after restart, terminal recovery failure, and partial-artifact cleanup.
- Atomic filesystem object storage behind a small `ObjectStore` protocol.
- Streamed uploads with byte limits, container signatures, media-type checks,
  decode probing, duration/frame/dimension limits, and opaque storage keys.
- Deletion of unsubmitted uploads, including browser cleanup when job submission
  fails; referenced uploads remain protected by a database invariant.
- Capacity reservations released on cancellation/failure and settled on
  success. These are operational compute units, not money or paid credits.
- A pluggable `ReconstructionEngine` interface with a production-safe synthetic
  engine and a gated LingBot command adapter.
- Stored GLB and manifest artifacts with SHA-256, media type, license, and
  provenance metadata.
- A dependency-free WebGL point-cloud viewer with pointer, wheel, and keyboard
  controls; no remote fonts, analytics, or third-party runtime scripts.
- Expiring, hashed share tokens and tenant-scoped deletion of source uploads,
  artifacts, and related shares.

## Architecture

```text
browser
  │ authenticated session + CSRF
  ▼
FastAPI routes
  ├── Database repository ── SQLite now / Postgres production boundary
  ├── ObjectStore ────────── local disk now / S3-compatible production boundary
  └── durable worker
        ├── SyntheticSampleEngine (enabled, CC0 output)
        └── LingbotResearchEngine (disabled until every gate is present)
```

The local worker is deliberately small and reliable for a single-instance demo.
Before horizontal scaling, replace the repository and storage implementations
at their existing boundaries, claim jobs with Postgres `SKIP LOCKED`, and pass
signed object references to workers instead of local paths. See
[`docs/architecture.md`](docs/architecture.md).

## Production configuration

Production refuses to boot without a secure token and secure cookies:

```bash
export LINGBOT_ENV=production
export LINGBOT_BOOTSTRAP_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export LINGBOT_DATA_DIR=/var/lib/scene-workspace
export LINGBOT_PUBLIC_BASE_URL=https://scenes.example.com
export LINGBOT_ALLOWED_HOSTS=scenes.example.com
lingbot-workspace --host 127.0.0.1 --port 7860
```

Terminate TLS at a trusted reverse proxy, keep the app on a private interface,
back up the data directory, and set upload/worker limits explicitly. The
single-process login limiter is defense in depth; a production edge must apply
distributed request and upload limits. Production disables interactive docs and
OpenAPI, validates `Host`, and applies an application-level declared-body
ceiling. Configure HSTS at the TLS edge only after the final domain and
subdomain policy has been reviewed.

Important environment variables:

| Variable | Purpose | Default |
|---|---|---:|
| `LINGBOT_ALLOWED_HOSTS` | Comma-separated exact Host allowlist; inferred from the public URL when present | required in production |
| `LINGBOT_MAX_UPLOAD_BYTES` | Per-video byte limit | 250 MiB |
| `LINGBOT_MAX_VIDEO_SECONDS` | Decoded duration limit | 300 seconds |
| `LINGBOT_MAX_VIDEO_FRAMES` | Source frame limit | 9,000 |
| `LINGBOT_MAX_VIDEO_DIMENSION` | Largest width/height | 4,096 px |
| `LINGBOT_TENANT_QUOTA_UNITS` | Operational capacity ceiling | 10,000 |
| `LINGBOT_JOB_TIMEOUT_SECONDS` | Worker/lease timeout | 3,600 seconds |
| `LINGBOT_MAX_JOB_ATTEMPTS` | Recovery attempts | 2 |

## Research-only LingBot adapter

Read [`MODEL_PROVENANCE.md`](MODEL_PROVENANCE.md) before enabling anything. All
four gates are required:

```bash
export LINGBOT_RESEARCH_ACK='I understand LingBot is research-only'
export LINGBOT_CHECKPOINT_PATH=/absolute/path/lingbot-map.pt
export LINGBOT_CHECKPOINT_SHA256=ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72
export LINGBOT_RESEARCH_COMMAND='/absolute/path/to/isolated-runner'
```

The command is split without a shell. It receives these environment variables:

- `LINGBOT_JOB_MANIFEST`: private per-job JSON input and rights record
- `LINGBOT_OUTPUT_DIR`: private per-job output directory
- `LINGBOT_CHECKPOINT_PATH`: already verified regular checkpoint file
- `LINGBOT_SKYSEG_PATH`: present only when sky masking was requested and its
  separate digest gate passed

Sky masking defaults off. To permit it, provision the pinned auxiliary model and
set both `LINGBOT_SKYSEG_PATH` and `LINGBOT_SKYSEG_SHA256`; moving-revision,
automatic model downloads are rejected.

It must write a structurally valid GLB 2.0 `scene.glb` (maximum 100 MiB) and may
write `report.json` (maximum 1 MiB). Only an allowlist of bounded report metrics
is exposed. The stored provenance manifest omits tenant IDs and filesystem
paths. Cancellation terminates the entire child process group, a timeout kills
it, logs are capped, and work directories are removed after artifact storage or
failure. The child receives an environment allowlist rather than application
secrets. This process boundary is not an OS sandbox; production research must
run in a separately isolated worker/container. Research output license remains
`NOASSERTION`.

The separate [`modal_app.py`](modal_app.py) follows the same research-only gate,
uploads this checkout rather than cloning a moving branch, uses pinned packages
and model revision, validates archives, isolates every job, and writes artifact
keys to a Volume instead of returning large GLB bytes over RPC. It is a reference
runner, not an enabled hosted product path; no paid GPU run is required for the
workspace demo.

## Direct model research

Install the CUDA runtime separately and exactly as required by your host:

```bash
.venv/bin/pip install torch==2.8.0 torchvision==0.23.0 \
  --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -e '.[research,vis]'
LINGBOT_RESEARCH_ACK='I understand LingBot is research-only' ./download_weights.sh
.venv/bin/python demo.py \
  --model_path ./lingbot-map.pt \
  --image_folder /path/to/owned-or-licensed-images \
  --use_sdpa
```

The downloader pins a model-repository revision, checks exact sizes and hashes,
and writes the sidecar digest required by `demo.py`. PyTorch loads with
`weights_only=True`. `--allow_unverified_checkpoint` exists only as a clearly
named research escape hatch and does not relax restricted deserialization.

No throughput, scale, accuracy, or state-of-the-art claim is made by this fork;
none is covered by a reproducible CI artifact on the supported runtime.

## Verify

```bash
.venv/bin/pip install -r requirements/dev.lock
.venv/bin/pip install --no-deps -e .
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy lingbot_map/workspace lingbot_map/checkpoints.py
node --check lingbot_map/workspace/static/app.js
node --check lingbot_map/workspace/static/viewer.js
```

CI also builds the wheel and verifies that the packaged static UI is present.
The automated suite covers authentication, CSRF, host/body gates, tenant
isolation, upload rejection and orphan cleanup, job reservations/refunds,
cancellation, recovery, sample artifact generation, viewing bytes, sharing,
expiry, deletion, path traversal, sanitized runner provenance, and checkpoint
integrity.

## Product and launch documents

- [`docs/product-decision.md`](docs/product-decision.md): user, positioning,
  scope, and non-goals
- [`docs/architecture.md`](docs/architecture.md): components, invariants, and
  Postgres/S3 migration boundary
- [`docs/deployment.md`](docs/deployment.md): production runbook
- [`docs/launch-readiness.md`](docs/launch-readiness.md): evidence and owner gates
- [`docs/commercial-clearance.md`](docs/commercial-clearance.md): legal plan
- [`docs/security-review.md`](docs/security-review.md): remediated findings and
  remaining deployment controls

## License

Repository source is presented under [`LICENSE.txt`](LICENSE.txt). That source
license must not be assumed to cover model weights, training data, example
assets, output rights, or trademarks. The generated synthetic sample has the
separate provenance and CC0 dedication in [`SAMPLE_LICENSE.md`](SAMPLE_LICENSE.md).
See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for retained upstream
notices and review flags.
