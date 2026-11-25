# Third-party notices and review flags

This file is not a substitute for legal review. It prevents the repository's
top-level Apache-2.0 file from being mistaken for a complete statement about
every model, dataset, asset, dependency, or derived source file.

`LicenseRef-Wayline-Bundled-Source` in the wheel metadata refers to this
inventory: project code under `LICENSE.txt`, separately covered inherited
source, and the unresolved source fragments below. It is not a new license
grant or a claim that this inventory is complete. The source distribution,
wheel, Docker image and Modal image include the four identified upstream
texts in `third_party_licenses/` alongside the project notices.

## VGGT-derived implementation

Several geometry, pose, head, layer, and vision-transformer files are derived
from or closely track Meta's VGGT implementation. VGGT is distributed under its
own [license at revision `a1179fe`](https://github.com/facebookresearch/vggt/blob/a1179fe98aea9bca4fa1cb618f49ab2fa9dd8f88/LICENSE.txt),
dated July 29, 2025.
Those terms and attribution requirements continue to apply to covered material;
the top-level Apache-2.0 file does not override them. Review the applicable
version and covered files for redistribution and acceptable-use obligations;
the label “Research Materials” alone does not establish a commercial-use ban.
The full agreement and its included acceptable-use policy are preserved in
`third_party_licenses/VGGT.txt`.

Comparison against that pinned revision found byte-identical
`lingbot_map/heads/head_act.py`, `heads/utils.py` and `utils/rotation.py`.
`heads/camera_head.py`, `heads/dpt_head.py`, `utils/geometry.py`,
`utils/load_fn.py` and `utils/pose_enc.py` modify their VGGT counterparts.
`vis/viser_wrapper.py` and `vis/glb_export.py` modify VGGT's `demo_viser.py`
and `visual_util.py`. These are verified comparison revisions, not evidence
of the exact commits originally imported into LingBot-Map.

## DINOv2-derived layers

Files carrying Meta copyright headers and DINO/DINOv2 references retain those
notices. Review the corresponding upstream license and attribution requirements
when redistributing a model runtime.

At VGGT revision `a1179fe98aea9bca4fa1cb618f49ab2fa9dd8f88`,
`layers/{drop_path,layer_scale,mlp,patch_embed,swiglu_ffn}.py` match exactly;
`layers/{attention,block,vision_transformer}.py` and the first portion of
`layers/rope.py` are modified. Their explicit Apache headers remain in place.
The corresponding [DINOv2 comparison tree](https://github.com/facebookresearch/dinov2/tree/592541c8d842042bb5ab29a49433f73b544522d5/dinov2)
also establishes matching layer implementations; DINO/DINOv2/timm references
are retained. The project `LICENSE.txt` provides the Apache-2.0 text.

## Other identified source portions

The paths below are relative to `lingbot_map/`. Existing copyright headers
remain. The copied license files are unmodified upstream texts.

| Source portion | Comparison source, attribution and modifications | Included text |
| --- | --- | --- |
| `utils/geometry.py`, DROID-SLAM section | `induced_flow`, `coords_grid`, `iproj`, `proj` and `actp` match [Princeton's projective operations](https://github.com/princeton-vl/DROID-SLAM/blob/2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99/droid_slam/geom/projective_ops.py); `projective_transform` is modified. Copyright (c) 2021, Princeton Vision & Learning Lab. | `third_party_licenses/DROID-SLAM.txt` (BSD-3-Clause) |
| `utils/rotation.py` and quaternion helpers in `utils/geometry.py` | Matching or modified [PyTorch3D rotation conversions](https://github.com/facebookresearch/pytorch3d/blob/5043d15361d16a7093b4b60572c5f730c6c83308/pytorch3d/transforms/rotation_conversions.py). Copyright (c) Meta Platforms, Inc. and affiliates. | `third_party_licenses/PyTorch3D.txt` (BSD) |
| `heads/utils.py`, `create_uv_grid` | Its source comment attributes a rewrite of [MoGe's `normalized_view_plane_uv`](https://github.com/microsoft/MoGe/blob/72fdee98935d93b69f7ce0a1369cfd6e2573fc2f/moge/utils/geometry_torch.py). Copyright (c) Microsoft Corporation. | `third_party_licenses/MoGe.txt` (upstream file containing Microsoft's MIT notice and Apache text) |
| `heads/dpt_head.py`, fusion/residual blocks | Matching or modified [Depth Anything V2 blocks](https://github.com/DepthAnything/Depth-Anything-V2/blob/e5a2732d3ea2cddc081d7bfd708fc0bf09f812f1/depth_anything_v2/util/blocks.py). Existing attribution is retained. | `LICENSE.txt` (Apache-2.0, byte-identical to that revision's license) |
| `layers/rope.py`, `get_1d_rotary_pos_embed` | Derived from the [Diffusers rotary helper](https://github.com/huggingface/diffusers/blob/a2ed6b452631d30ed23f45ea5fb7f5995c6dc613/src/diffusers/models/embeddings.py#L1107), with comments/docstrings changed and the NPU conversion branch omitted. Copyright 2025 The HuggingFace Team. | `LICENSE.txt` (Apache-2.0) |
| `layers/rope.py`, `WanRotaryPosEmbed` | Modified [Diffusers Wan rotary class](https://github.com/huggingface/diffusers/blob/a2ed6b452631d30ed23f45ea5fb7f5995c6dc613/src/diffusers/models/transformers/transformer_wan.py#L167), including cache and frame-offset handling. Copyright 2025 The Wan Team and The HuggingFace Team. | `LICENSE.txt` (Apache-2.0) |

### Remaining source-fragment questions

- The two `modulate` expressions in `heads/camera_head.py` explicitly cite
  [DiT revision `796c29e`](https://github.com/facebookresearch/DiT/blob/796c29e532f47bba17c5b9c5eb39b9354b8b7c64/models.py),
  whose source carried CC BY-NC terms. Applicability to these small expressions
  remains unresolved; this does not label the entire file noncommercial.
- `layers/rope.py` cites NAVER and CodeLlama inspirations.
  [NAVER's pinned NOTICE](https://github.com/naver-ai/rope-vit/blob/ce85c2e56c5ff3aadc10e1a849872081f7b86293/NOTICE)
  identifies CodeLlama exceptions to Apache. The local functions do not establish
  which exceptions apply. Neither blanket Apache nor blanket Llama coverage is
  asserted for those portions.
- `vis/{point_cloud_viewer,utils,__init__}.py`, sky-segmentation additions and
  remaining helpers in `geometry.py`/`pose_enc.py` have not all been traced to
  their older secondary sources. These four supplied texts close identified
  omissions; they do not complete the inherited-source or checkpoint review.

## Model checkpoints and data

The pinned `robbyant/lingbot-map` model card states that the project is
Apache-2.0, although its machine-readable license metadata is absent and its
relative LICENSE link has no matching repository file. Metadata absence is not
proof of absent licensing language. Checkpoint-hosting scope, derived code,
training-source and output questions remain separate review items. This product
keeps its research-only policy and `NOASSERTION` output metadata pending that
review; see `MODEL_PROVENANCE.md` for the dated source recheck. That policy is not
permission for free third-party hosted testing. The paper identifies Waymo in
training, and its [published agreement](https://waymo.com/open/terms/) expressly
restricts downstream trained models and third-party services, including unpaid
services. The exact checkpoint's applicable training agreement and any separate
grant remain unresolved; this notice does not assume that every dataset license
automatically governs every trained model or output.

## Sky segmentation

The optional `JianyuanWang/skyseg` project identifies its code/model repository
as MIT-licensed. Its model is not bundled in the workspace wheel. The guarded
research downloader records and verifies the exact downloaded object.

## Python and browser dependencies

The workspace viewer is original code and downloads no browser runtime package.
Python package licenses and notices remain available in their installed package
metadata. A production image must generate and ship a software bill of materials
and third-party notice bundle from the exact lock before release.

The Modal image recipe includes the existing project `LICENSE.txt`, this notice
and `MODEL_PROVENANCE.md` beside the code. The project license matches upstream
[Apache-2.0 commit `ed0aee8`](https://github.com/Robbyant/lingbot-map/blob/ed0aee8b71b049cc857582c829ac31ab48660121/LICENSE.txt).
The four identified source-license texts are also copied into that image.
Remaining fragment-level questions are listed above; checkpoint and training-data
scope remain separate. A packaged notice does not resolve those questions.

## Public presentation and interface assets

The landing office example, thumbnail frames, and studio screenshots derive
from the first 10 seconds of the TUM RGB-D Benchmark
`freiburg3_long_office_household`, attributed to J. Sturm, N. Engelhard,
F. Endres, W. Burgard and D. Cremers (IROS 2012). TUM identifies its benchmark
data as CC BY 4.0 at <https://cvg.cit.tum.de/data/datasets/rgbd-dataset#license>.
The scene was reconstructed with LingBot-Map and reduced to 75,000 points for
public presentation. Its model/output clearance remains `NOASSERTION`.
Full attribution, modifications, and license links are shipped in
`static/ASSET-NOTICES.txt` and linked through the public Credits link.

Interface SVGs are unmodified Phosphor Icons regular from
`@phosphor-icons/core` 2.1.1, Copyright (c) 2023 Phosphor Icons, MIT License.
The package integrity, source, and full license are shipped in `static/icons`.
