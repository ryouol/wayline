# Wayline

A private video-to-3D workspace built around the original LingBot-Map model.
Upload a short walkthrough, follow its processing stages, explore the resulting
point cloud, replay the captured camera path frame by frame, and download or
share the scene.

**Current verification boundary:** the synthetic playground works locally.
The private Modal runner is deployed and its original checkpoint is verified.
An actual GPU diagnostic reconstructed a generated test-pattern video and passed
API/download/share checks plus browser replay/walking. This does not establish
quality on a real capture; see [the measured evidence](docs/MODAL_QA.md).
Google OAuth remains unverified against a configured client, and the Render
Blueprint is not a deployed website. Public signup and video testing are not live.

Original LingBot model code, checkpoint attribution, package identifiers and
upstream license notices remain intact. Wayline is the product name; it is not
a claim of endorsement or commercial model rights. Read
[MODEL_PROVENANCE.md](MODEL_PROVENANCE.md) before enabling hosted inference.

## Run locally

Use Python 3.11 and the committed dependency lock:

```bash
uv sync --frozen --extra dev
uv run wayline --dev
```

Open http://127.0.0.1:7860 and choose **Explore the playground**. Each visitor
receives a separate temporary workspace with the CC0 synthetic sample, no GPU
access and no upload permission. Playground data expires after one hour.
The development token printed on first startup is an operator login, available
under **Operator access**, and is not public onboarding.

## Architecture

```text
Browser: website, WebGL point-cloud viewer and camera timeline
  │ one origin; HttpOnly session and CSRF protection
  ▼
Render: FastAPI + durable job worker + SQLite + private persistent disk
  │ authenticated Modal SDK; unique staging path per attempt
  ▼
Modal: original LingBot model on a bounded A100 80 GB job
  └── GLB with colored points, camera poses, timestamps and source thumbnails
```

Render serves both frontend and API. Modal is a private GPU worker with no
public inference endpoint. The viewer uses client-side WebGL; reopening a
completed scene does not invoke inference. A persistent Render disk means one
application instance and brief deploy downtime. Postgres/object storage are a
later scaling migration, not dependencies of this controlled beta.

## Preview behavior

- Google identities use the verified immutable Google subject, a server-side
  authorization-code exchange, PKCE, nonce and one-use browser-bound state.
- A Google account receives one successful reconstruction, with at most one
  queued/running reconstruction and three attempts in a rolling day. Deleting
  scenes does not reset these limits. There is no checkout or paid credit sale.
- The Render configuration limits captures to 60 seconds; the Modal engine
  samples at most 120 frames and exports at most 750,000 points. These are
  configured limits, not measured quality/performance guarantees.
- Stored jobs survive web restarts; reservations, request idempotency, attempt
  fencing and durable deletion protect the database/object boundary.
- Shared links use `/s#capability`; the browser sends the capability in an
  authorization header, never a request path or query. Every metadata/content
  fetch rechecks expiry and revocation. Shares include camera replay.
- The viewer accepts one untransformed POINTS primitive with vertex colors.
  Reconstruction export bakes coordinates into glTF Y-up and stores its camera
  trace alongside the points. It is not a general-purpose mesh/GLB renderer.

## Deploy Render + Modal

Start with [docs/deployment.md](docs/deployment.md), the committed
[Dockerfile](Dockerfile) and [render.yaml](render.yaml). Both Google signup and
Modal submission default off in the Blueprint until their external setup and
acceptance tests are complete.

The explicit Modal deployment module is now `modal_app.py`; the previous inert
manifest and separate disabled module were replaced as part of this rebuild.
Importing the web application does not import the Modal deployment or start
remote work. Deploy and prepare weights explicitly:

```bash
uv run modal token new
uv run modal deploy modal_app.py
uv run modal run modal_app.py
```

Preparing the original pinned checkpoint is a research-only operator action.
It downloads and verifies the checkpoint on a CPU task; it is not a GPU
reconstruction test. Hosted usage rights remain unresolved. CUDA PyTorch is
version/index-pinned; the other runner dependencies use the hashed Modal lock.

## Direct model research

Install the CUDA runtime separately and exactly as required by your host:

```bash
uv pip install --python .venv/bin/python torch==2.8.0 torchvision==0.23.0 \
  --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -e '.[research,vis]'
LINGBOT_RESEARCH_ACK='I understand LingBot is research-only' ./download_weights.sh
.venv/bin/python demo.py \
  --model_path ./lingbot-map.pt \
  --model_sha256 "$(cut -d' ' -f1 lingbot-map.pt.sha256)" \
  --image_folder /path/to/owned-or-licensed-images \
  --use_sdpa
```

The downloader pins a model-repository revision, checks exact sizes and hashes,
and writes the sidecar digest required by every direct loader. Every PyTorch and
ONNX model loader copies the exact digest into a private content-addressed file
before use; PyTorch also loads with `weights_only=True`. Sky-mask caches are
bound to that model digest, and there is no unverified escape hatch.

No throughput, scale, accuracy, or state-of-the-art claim is made by this fork;
none is covered by a reproducible CI artifact on the supported runtime.

## Verify

```bash
uv run pytest
uv run ruff check .
uv run ruff check lingbot_map/workspace lingbot_map/checkpoints.py tests modal_app.py webui/server.py --select E,F,I,B,UP,SIM
uv run mypy lingbot_map/workspace lingbot_map/checkpoints.py
node tests/session-events.test.js
node tests/viewer-lifecycle.test.js
node tests/viewer-trace.test.js
node tests/timeline.test.js
docker build -t wayline:local .
uv run python scripts/smoke_container.py
```

The tests cover storage/auth isolation, sample creation, quotas, OAuth protocol
handling with mocked provider responses, Modal transport with a mocked client,
scene export geometry, camera timeline behavior, share capabilities, and offline
backup/restore. Mocks are not evidence that Google or Modal works remotely.

## Delivery and operating plan

- [Launch readiness](docs/launch-readiness.md): evidence and remaining gates.
- [Delivery plan](docs/WAYLINE_PLAN.md): full requested scope.
- [Operating costs and future credits](docs/operating-costs.md): assumptions,
  beta limits and billing design.
- [Production UX audit](docs/PRODUCTION_UX_AUDIT.md): attached six-phase checklist.
- [Model provenance](MODEL_PROVENANCE.md): research-use and commercialization questions.

## License

Repository source is presented under [`LICENSE.txt`](LICENSE.txt). That source
license must not be assumed to cover model weights, training data, example
assets, output rights, or trademarks. The generated synthetic sample has the
separate provenance and CC0 dedication in [`SAMPLE_LICENSE.md`](SAMPLE_LICENSE.md).
See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for retained upstream
notices and review flags.
