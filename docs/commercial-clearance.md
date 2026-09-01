# Commercial clearance plan

Current decision: **do not sell or enable paid LingBot inference**.

## Required evidence

1. Written rightsholder grant for hosted commercial inference, checkpoint
   storage/caching, redistribution if applicable, and generated-output use.
2. Training-data inventory with the exact dataset version, source agreement,
   permitted purpose, attribution, downstream-output terms, and deletion duties.
3. Counsel review of datasets identified with non-commercial or research-only
   restrictions in the paper, including CO3D, Waymo, Matterport3D/HM3D, and
   ScanNet++.
4. Counsel/rightsholder review of VGGT-derived files and their redistribution
   terms.
5. Written permission or replacement branding for the LingBot/Robbyant name.
6. Rights manifest for every demo image/video and every published output.

## Go/no-go rule

The product may sell the generic workspace with a commercially cleared engine.
The LingBot adapter may become billable only when every item above is attached to
an approved release record. Code license, a public download, or a checkpoint hash
alone is not clearance.

If clearance cannot be obtained, retain the engine boundary and replace LingBot
with a checkpoint trained only on documented commercial-use data. Do not weaken
the UI disclosure or relabel `NOASSERTION` output.
