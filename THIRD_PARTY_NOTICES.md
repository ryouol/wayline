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
