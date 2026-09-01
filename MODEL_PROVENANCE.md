# Model provenance and commercialization gate

Status: **research-only; commercial use is not cleared**.

The repository source is presented under Apache-2.0, but that does not establish
commercial rights for the released checkpoint, its training data, example
imagery, or the LingBot name. The public checkpoint repository does not publish
an explicit checkpoint license. The paper lists training sources with
non-commercial or research-only terms, and portions of the implementation are
derived from VGGT under separate terms.

Consequently:

- the hosted workspace ships with only the deterministic `synthetic-studio-v1`
  sample enabled;
- the LingBot adapter reports `commerciallyCleared: false` and cannot run until
  an operator supplies the exact research acknowledgement, an isolated runner,
  a checkpoint path, and a pinned SHA-256 digest;
- there is no payment or billing path for LingBot inference;
- research outputs carry `NOASSERTION` rather than an invented commercial
  license; and
- product copy must not claim metric accuracy, survey use, production scale,
  state-of-the-art quality, or verified throughput without reproducible evidence.

## Pinned research assets

The guarded `download_weights.sh` pins Hugging Face revision
`204754b72bb24f561f8d7e7e1e4e4cd9e809adf9` and verifies:

| File | Bytes | SHA-256 |
|---|---:|---|
| `lingbot-map.pt` | 4,632,303,465 | `ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72` |
| `skyseg_batch.onnx` | 175,997,119 | `b09c0f6cf79e1caa2591b946b659487bd7c8208caddd3f80680cbb169617e378` |

The CLI uses PyTorch's restricted `weights_only=True` loader and requires an
exact digest or downloader-generated sidecar by default. Integrity verification
reduces supply-chain risk; it does not grant usage rights.

The workspace keeps sky masking off by default. Enabling it requires both
`LINGBOT_SKYSEG_PATH` and `LINGBOT_SKYSEG_SHA256`; the same regular-file,
permission, size, and digest checks run before the path reaches an isolated
runner. Legacy moving-revision automatic downloads now fail closed.

## Clearance required before commercial inference

Obtain written confirmation from the checkpoint rightsholder covering hosted
commercial inference, checkpoint redistribution/cache rights, training-data and
output rights, and name/trademark use. Have counsel review the VGGT-derived code
and every training source identified by the paper. Replace or retrain the engine
on commercially cleared data if those grants cannot be obtained.
