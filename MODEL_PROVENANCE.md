# Model provenance and commercialization gate

Status: **research-only; commercial use is not cleared**.

The repository source and the pinned Hugging Face model card both state
Apache-2.0. The model card has no machine-readable `license` field, and its
relative `LICENSE.txt` link has no matching file in that model repository.
Missing metadata must not be described as an absence of all published licensing
language. The remaining review concerns are the scope of the project-level
statement for checkpoint hosting/redistribution and the independent obligations
for derived implementation, training sources, example imagery and names.

The research-only designation here is Wayline's current release policy, not a
claim that the upstream project universally prohibits commercial use. A
training dataset's terms also require separate analysis; this file does not
infer the license of a trained checkpoint or its outputs solely from those terms.

Consequently:

- the hosted workspace ships with only the deterministic `synthetic-studio-v1`
  sample enabled;
- the LingBot adapter reports `commerciallyCleared: false` and cannot run until
  an operator supplies the exact research acknowledgement and configures an
  isolated runner with the pinned checkpoint and SHA-256 digest; the new private
  Modal deployment is an explicit operator action and remains unverified;
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

## Source recheck — 2026-09-10

- [Pinned model card](https://huggingface.co/robbyant/lingbot-map/blob/204754b72bb24f561f8d7e7e1e4e4cd9e809adf9/README.md):
  Apache-2.0 badge and project-level license statement are present.
- [Pinned repository metadata](https://huggingface.co/api/models/robbyant/lingbot-map/revision/204754b72bb24f561f8d7e7e1e4e4cd9e809adf9):
  no card license field and no standalone LICENSE file were returned. This is
  incomplete metadata, not proof that the checkpoint is unlicensed.
- [Upstream source license](https://github.com/Robbyant/lingbot-map/blob/main/LICENSE.txt):
  Apache-2.0.
- [VGGT license](https://github.com/facebookresearch/vggt/blob/main/LICENSE.txt):
  the published version dated July 29, 2025 grants use/modification/distribution
  subject to its terms, including redistribution and acceptable-use obligations.
  Its use of the label “Research Materials” is not itself a non-commercial-only
  condition. Identify the version and covered files before drawing conclusions
  about this fork.

This recheck did not provide checkpoint-specific written confirmation, review
every training dataset grant, or clear the product for commercial launch. No
research enablement, billing or deployment gate was changed.
