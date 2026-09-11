# Model provenance and hosted-use clearance

Status: **research-only release policy; hosted-use clearance remains unresolved,
including free third-party testing and commercial use**.

The repository source and the pinned Hugging Face model card both state
Apache-2.0. The model card has no machine-readable `license` field, and its
relative `LICENSE.txt` link has no matching file in that model repository.
Missing metadata must not be described as an absence of all published licensing
language. The remaining review concerns are the scope of the project-level
statement for checkpoint hosting/redistribution and the independent obligations
for derived implementation, training sources, example imagery and names.

The research-only designation here is Wayline's current release policy, not a
claim that the upstream project universally prohibits commercial use or a grant
of permission for a free hosted beta. A training dataset's terms require separate
analysis: restrictions are not automatically inherited by every trained model,
but some agreements expressly address downstream models and hosted services.
The Waymo evidence below requires resolution for this exact checkpoint.

Consequently:

- the default workspace ships with the deterministic `synthetic-studio-v1`
  sample; private research enablement is an explicit operator action;
- the LingBot adapter reports `commerciallyCleared: false` and cannot run until
  an operator supplies the exact research acknowledgement and configures an
  isolated runner with the pinned checkpoint and SHA-256 digest; the new private
  Modal deployment is an explicit operator action; its generated-input diagnostic
  and live Render integration are verified in `docs/MODAL_QA.md` and
  `docs/RENDER_QA.md`, without establishing real-capture quality or hosted-use rights;
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

## Unresolved hosted-use clearance

Obtain written confirmation from the checkpoint rightsholder covering hosted
testing, whether free or paid, checkpoint redistribution/cache rights,
training-data and output rights, and name/trademark use. Have counsel review the
applicable training agreements and VGGT-derived code. If the necessary rights
cannot be established, use an engine cleared for the intended hosted service.
An operator acknowledgement or a successful diagnostic run does not resolve
these rights questions.

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
every training dataset grant, or clear the product for hosted launch. No
research enablement, billing or deployment gate was changed by this source
recheck. Subsequent operator research enablement and diagnostics are recorded
in the deployment evidence; hosted-use clearance remains unresolved.

## Pinned source and hosted-testing recheck — 2026-09-11

The local `LICENSE.txt` exactly matches the Apache-2.0 file in upstream
[commit `ed0aee8b71b049cc857582c829ac31ab48660121`](https://github.com/Robbyant/lingbot-map/commit/ed0aee8b71b049cc857582c829ac31ab48660121),
which replaced the initial CC BY-NC license on April 17, 2026. The
[immutable license file](https://github.com/Robbyant/lingbot-map/blob/ed0aee8b71b049cc857582c829ac31ab48660121/LICENSE.txt)
permits use of covered source under Apache-2.0; it does not settle the scope of
checkpoint licensing or override third-party terms. Its SHA-256 is
`c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.

Meta's [VGGT relicensing commit](https://github.com/facebookresearch/vggt/commit/a1179fe98aea9bca4fa1cb618f49ab2fa9dd8f88)
and [license at that revision](https://github.com/facebookresearch/vggt/blob/a1179fe98aea9bca4fa1cb618f49ab2fa9dd8f88/LICENSE.txt)
establish the July 29, 2025 terms. They permit use subject to the agreement,
including redistribution and acceptable-use conditions. The local derived-file
inventory and applicable terms still need complete mapping.

The [LingBot paper, section 4.3 and Table 1](https://arxiv.org/html/2604.14141v1#S4.SS3),
identifies Waymo in stage-two training. The published
[Waymo Dataset License Agreement, March 2025](https://waymo.com/open/terms/),
expressly includes trained model weights in its definition of derivative IP.
Section 2.3 requires downstream model recipients to receive its terms and
attribution. Section 4.1 prohibits deploying covered models in production systems;
its definition includes services supplied to third parties without payment.
These provisions are more specific than a generic non-commercial dataset label.

This evidence does not establish which Waymo version or agreement governed the
pinned LingBot checkpoint, or whether Robbyant obtained a separate grant. No such
exception was established in this review. If those published terms apply, a free
third-party hosted beta would need permission beyond the research-only label.
The rightsholder and counsel must resolve applicability; the Apache model-card
statement alone does not answer that question.

The Modal image recipe now includes `LICENSE.txt`, `THIRD_PARTY_NOTICES.md` and
this provenance record beside the copied code. This carries the existing notices
into future image builds; it is not a complete third-party license bundle or
proof of derived-code coverage, and does not change model selection or enablement.

### Unsent rightsholder clarification

For `lingbot-map.pt` at Hugging Face revision
`204754b72bb24f561f8d7e7e1e4e4cd9e809adf9`, SHA-256
`ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72`,
which license grants checkpoint caching on Modal and inference for third-party
users in a free hosted beta, with users downloading and sharing their outputs?
Please identify the Waymo dataset version and agreement used for this checkpoint
and any separate permission that allows downstream hosted services despite the
published trained-model restrictions. Please also identify required notices,
output conditions and whether paid hosted use requires a different grant.
This question is prepared for the operator; it has not been sent.
