# Third-party notices and review flags

This file is not a substitute for legal review. It prevents the repository's
top-level Apache-2.0 file from being mistaken for a complete statement about
every model, dataset, asset, dependency, or derived source file.

## VGGT-derived implementation

Several geometry, pose, head, layer, and vision-transformer files are derived
from or closely track Meta's VGGT implementation. VGGT is distributed under its
own license terms at <https://github.com/facebookresearch/vggt/blob/main/LICENSE.txt>.
Those terms and attribution requirements continue to apply to covered material;
the top-level Apache-2.0 file does not override them. Review the applicable
version and covered files for redistribution and acceptable-use obligations;
the label “Research Materials” alone does not establish a commercial-use ban.

## DINOv2-derived layers

Files carrying Meta copyright headers and DINO/DINOv2 references retain those
notices. Review the corresponding upstream license and attribution requirements
when redistributing a model runtime.

## Model checkpoints and data

The pinned `robbyant/lingbot-map` model card states that the project is
Apache-2.0, although its machine-readable license metadata is absent and its
relative LICENSE link has no matching repository file. Metadata absence is not
proof of absent licensing language. Checkpoint-hosting scope, derived code,
training-source and output questions remain separate review items. This product
keeps its research-only policy and `NOASSERTION` output metadata pending that
review; see `MODEL_PROVENANCE.md` for the dated source recheck.

## Sky segmentation

The optional `JianyuanWang/skyseg` project identifies its code/model repository
as MIT-licensed. Its model is not bundled in the workspace wheel. The guarded
research downloader records and verifies the exact downloaded object.

## Python and browser dependencies

The workspace viewer is original code and downloads no browser runtime package.
Python package licenses and notices remain available in their installed package
metadata. A production image must generate and ship a software bill of materials
and third-party notice bundle from the exact lock before release.
