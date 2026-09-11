# Real capture reconstruction QA — 2026-09-11 UTC

The first real-camera benchmark clip reached READY through the deployed Render
and original LingBot Modal pipeline. Browser inspection then exposed repeated
globe/table structures instead of a coherent scene. The initial artifact is an
execution result, **not an accepted reconstruction**. A pose-convention defect
was identified, a local exporter fix was added, and an offline corrected artifact
was inspected in the browser. The corrected diagnostic shows a single coherent
globe/table/chairs arrangement with partial, noisy geometry. A fresh run through
the corrected deployed worker then reproduced that geometry numerically and
passed the desktop browser checks recorded below.

## Input and rights

Input: TUM RGB-D Benchmark `freiburg3_long_office_household`, recorded with an
Asus Xtion moving through an office/household scene. This is real camera footage,
not a generated pattern and not the user's owned phone capture.

- [Official sequence description](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download#freiburg3_long_office_household).
- [Official RGB AVI](https://webshare.cvg.cit.tum.de/g/rgbd/dataset/freiburg3/rgbd_dataset_freiburg3_long_office_household-rgb.avi):
  26,026,292 bytes; SHA-256
  `3200d7a76f5b3307e33863d4b38dbad414527ce14084f4c1f6303a0f69eb794c`.
- TUM's [dataset license declaration](https://cvg.cit.tum.de/data/datasets/rgbd-dataset#license)
  specifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) unless an
  exception is stated; none was found for this sequence. Retain attribution,
  the source/license links, and disclosure of modifications when sharing.
- Attribution: TUM RGB-D Benchmark; J. Sturm, N. Engelhard, F. Endres,
  W. Burgard and D. Cremers, *A Benchmark for the Evaluation of RGB-D SLAM
  Systems*, IROS 2012. Wayline QA selects AVI frames 0–299 and transcodes that
  RGB segment to H.264 MP4 without changing resolution or frame timing.

The prepared clip is 640×480, 30 FPS, 300 frames, 10.000 seconds, without audio.
It covers AVI-relative time `[0, 10)` seconds; its last frame is at 9.966667.
All 300 decoded presentation timestamps were checked against `frame_index / 30`.
The MP4 is 3,314,868 bytes; SHA-256
`50ca39e22796f8e741983f9830cb7fffbbcf03579fa1f648eaa80a1c2fcccdbd`.

Source frames at 0.5-second intervals and the encoded clip's first, middle and
last frames showed office furniture/objects with no people visible. This was
sampled visual inspection. The original AVI has 2,585 frames and duration
86.166667 seconds, whereas the dataset description gives 87.09 seconds. Exact
alignment with raw benchmark timestamps/ground truth has not been established.

Input licensing does not settle the separate original-model/checkpoint terms.
The output remains `NOASSERTION`, `researchOnly: true`, and
`commerciallyCleared: false`; this report does not relicense it as CC0 or assert
commercial hosted-use clearance.

## Deployed generation receipt

- Render runtime: `0ca62c35be8b77f8db1063b8c39fe560fb472907`.
- Job: `job_a0303ce458dc4160baa07fae57391948`; engine `lingbot-research-v1`.
- Submitted: 2026-09-11 02:53:10.836 UTC; server finished:
  2026-09-11 02:54:04.008 UTC. The observer saw READY after 53.833 seconds.
- Request: `extractFps=3`, `maxFrames=30`, streaming, memory guard enabled,
  rotation and sky masking disabled. One attempt was admitted.
- Original checkpoint revision:
  `204754b72bb24f561f8d7e7e1e4e4cd9e809adf9`; SHA-256
  `ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72`.
- Runner-reported inference: 5.691 seconds; total inside runner: 40.243 seconds;
  peak allocated VRAM: 8,018,625,024 bytes. These are one-run observations, not
  invoiced GPU duration, cold/warm guarantees, or general performance estimates.
- Initial GLB: 12,210,636 bytes; SHA-256
  `48f20a55dc1d69dc6e0db2274635e85923f132c312f55d3e2d5a9d5071567904`.
- The live receipt records the remote cleanup row as cleaned, zero pending
  remote cleanups and zero active jobs. GPU admissions increased from two to
  three of six. The Google account's free-video quota remained unused.

## Initial artifact structure and numerical checks

The downloaded bytes match the published size/hash. The GLB contains one scene,
one untransformed node, one mesh and one unindexed POINTS primitive with float32
positions and normalized uint8 RGBA vertex colors. It fits the current viewer's
point-cloud contract; it is not a mesh suitable for collision or a general GLB
renderer acceptance fixture.

| Check | Observed in the initial artifact |
|---|---|
| Points | 750,000 finite, unique coordinate rows; the configured export cap |
| Per-frame contribution | 25,000 points for each of 30 frames |
| Trace timing | Strictly increasing, 0.000000 through 9.966667 seconds |
| Trace spacing | 0.333333–0.366667 seconds; preserved sampled timestamps |
| Model image size | 518×392, with positive focal lengths and 30 JPEG thumbnails |
| Camera centers | 30 distinct positions; path length 1.215253 model units |
| Orientation | Maximum orthonormality error approximately 1.44×10⁻⁷ |
| Point bounds minimum | `[-0.691942, -0.480422, -1.405771]` |
| Point bounds maximum | `[0.854913, 0.583810, -0.083921]` |
| Covariance eigenvalues | `[0.038156, 0.059209, 0.095684]` |

The cloud is neither empty nor collapsed onto a single point, line or plane.
That check did not detect the scene-coherence defect. All exported points have
positive depth relative to their associated exported camera, and 99.9099%
project inside its image bounds. This is internal consistency between exported
points and poses, not independent geometric accuracy: both used the same wrong
pose convention. Coordinate distances above are model units, not verified meters.

## Pose-convention defect and local correction

The active `GCTStream` constructor disables the point head by default, and the
runner does not enable it. This run therefore takes the depth-unprojection branch.
The original visualizer passes the postprocessed extrinsics to
`unproject_depth_map_to_point_map` (`lingbot_map/vis/point_cloud_viewer.py:177`);
`depth_to_world_coords_points` inverts them before mapping camera points into
world space (`lingbot_map/utils/geometry.py:104–112`). The original visualizer
also inverts the extrinsics for camera placement.

Wayline's exporter instead treated the postprocessed matrices as camera-to-world
and applied them directly to depth points and the camera trace. Legacy comments
in `demo.postprocess` and the pose helper contradict the original visualization
contract. Following those comments produced a valid-looking GLB with duplicated
objects across frame groups.

The local `scene_export.py` correction treats the input as world-to-camera and
inverts its rigid transform once for both depth unprojection and traced camera
poses. Already-global world-point maps receive only the shared OpenCV-to-glTF
basis change. The original model and `demo.py` are unchanged. Regression fixtures
now start from independently defined physical camera-to-world poses and supply
their inverses. Rotated, translated cameras must reconstruct one shared landmark;
the same test also checks that global point maps are not transformed again.
All seven exporter tests pass. Both new landmark test cases fail against the
previous exporter, confirming that they detect the convention defect.

An offline diagnostic recovered camera-local points from each initial GLB frame
group and re-expressed both points and cameras with the inverse original pose.
It preserves colors, frame boundaries, timestamps, intrinsics and thumbnails.
This is **not new inference** and has not replaced the deployed job's artifact.

| Blue-object alignment heuristic | Initial artifact | Inverse-pose diagnostic |
|---|---:|---:|
| RMS of per-frame median positions | 0.427936 | 0.031807 |
| First/last median displacement | 1.003376 | 0.088730 |

The heuristic selects each frame's points with `B > 1.4R`, `B > 1.15G`, and
`B > 75`, approximately isolating the blue globe. These are color-based medians,
not independently tracked correspondences or ground truth. The approximately
13.5-fold RMS reduction supports the convention diagnosis; residual drift and
surface quality still require assessment.

Diagnostic GLB: 12,210,576 bytes; SHA-256
`f2e277567b372ac82fe90b3f449664fbf3d64181516be7f0f1b921fdbc05ce3d`.

## Fresh deployed correction verification

The same prepared TUM MP4 was submitted once after deploying the exporter fix.
This was a fresh original-model GPU inference through the service, not the
offline transformation above.

- Render runtime: `cd24f7fda60586840c2a6c425e44363f3eac3965`.
- Deployed Modal worker image: `im-d66mkdXA6lELtEIDxFhufN`.
- Job: `job_b650b0f2ff414ff3b8b9768d343e4c07`; engine `lingbot-research-v1`.
- Created: 2026-09-11 03:17:17.729 UTC; server finished:
  2026-09-11 03:18:38.075 UTC. The observer saw READY after 80.356 seconds.
- Parameters: `extractFps=3`, `maxFrames=30`, streaming, memory guard enabled,
  rotation and sky masking disabled. Attempt 1; 30 units reserved and used.
- Checkpoint revision and SHA-256 match the initial generation receipt above.
  The receipt reports `modelInference: true`, `researchOnly: true`,
  `commerciallyCleared: false` and artifact license `NOASSERTION`.
- Runner-reported inference: 7.887 seconds; total inside runner: 62.291 seconds;
  peak allocated VRAM: 8,018,625,024 bytes. These are observed execution times,
  not invoiced GPU duration or a cost forecast.
- Downloaded scene: 12,210,576 bytes; SHA-256
  `3556540de61cb0a99f8d1d54b128715739ecd3cc06593fb22fa515aae0e992b3`.
  Both match the fresh job's artifact metadata.
- Cleanup is recorded complete, with zero pending remote cleanups and zero
  active jobs. GPU admissions increased from three to four of six; the
  configured GPU seconds budget remained 3,600. The Google account's free-video
  quota remained 120 units with zero reserved or consumed.

The fresh GLB retains the POINTS contract with 750,000 finite, unique coordinate
rows, 30 traced cameras and 25,000 points per frame. Trace times run from 0.000000
through 9.966667 seconds. Its bounds are `[-0.782691, -0.424674, -1.558240]` to
`[0.659073, 0.448459, -0.535626]`; covariance eigenvalues are
`[0.011383, 0.043745, 0.078406]`. It is not numerically collapsed to a point, line
or plane. Its camera path length is 1.181662 model units. All points have positive
depth in their associated exported camera, with 99.9137% inside its image bounds;
these remain internal consistency checks, not ground-truth accuracy measures.

| Blue-object alignment heuristic | Initial artifact | Offline diagnostic | Fresh corrected run |
|---|---:|---:|---:|
| RMS of per-frame median positions | 0.427936 | 0.031807 | 0.031807 |
| First/last median displacement | 1.003376 | 0.088730 | 0.088730 |

Using the same color selection described above, the fresh run's RMS is
0.031807072 and its first/last displacement is 0.088730425 model units. Its
per-frame median axis spans are `[0.092092, 0.028024, 0.033340]`. The color arrays
match the offline diagnostic exactly; corresponding coordinates differ by at
most 2.3842×10⁻⁷ model units, with point-distance RMS 5.3927×10⁻⁸. The newly
deployed export path therefore reproduces the offline inverse-pose diagnostic
within floating-point precision. This verifies the pipeline correction for
this capture; it does not make the color heuristic an independent correspondence
test or establish the remaining reconstruction-quality gates.

## Browser verification and remaining launch acceptance

The offline corrected whole-space view shows one globe/table/chairs arrangement,
and the last-frame replay appears correctly aligned. Partial coverage and noisy
surfaces remain. This comparison supports the pose correction without asserting
metric accuracy. The fresh inference is separately verified above.

The fresh deployed artifact was then checked in the desktop browser:

- Whole space rendered the coherent 750,000-point scene. Evidence screenshot:
  `whole-scene-deployed-corrected.png` in the private external
  `real-capture-qa-2026-09-11` evidence directory.
- Replay naturally reached frame 30/30 at 10.0 seconds. Walk from here,
  Step forward, Step right, Whole space, Zoom in and Reset responded.
- All 30 source thumbnails were present. At the tested desktop viewport,
  document `scrollWidth` and browser `innerWidth` were both 1,280 pixels.
- Download GLB saved 12,210,576 bytes with SHA-256
  `3556540de61cb0a99f8d1d54b128715739ecd3cc06593fb22fa515aae0e992b3`,
  matching the fresh server artifact and local numerical-analysis input.
- Post-run Modal function statistics showed zero backlog, zero active inputs
  and zero runners.

These checks establish a successful real-camera benchmark upload, inference,
coherent point-cloud view, replay and matching browser download for the corrected
pipeline. Partial coverage and noisy surfaces remain visible.

The initial artifact's UI behavior was tested independently of its failed scene
geometry: replay naturally reached frame 30/30 at 10.0 seconds; Walk from here,
Step forward and Step right responded; Whole space restored the full scene.
Its 15-minute share expired naturally without changing the database, removed
the timeline, thumbnails and download control, disposed the viewer canvas, and
showed the expired state. The existing signed-in Google owner's synthetic
5,908-point scene and session also persisted across the new Render deployment.
These checks do not rehabilitate the initial artifact's geometry.

The fresh QA share was revoked after testing. Its public API returned 404, and
reloading the browser showed the invalid/expired state with no scene or download.
The app's GPU, delivery, signup and recovery allowances were rechecked unchanged.

An isolated desktop Chromium 153 browser then rendered the exact corrected GLB
with the current share/viewer/timeline scripts at 390×844. It loaded all 750,000
points and 30 frames, advanced playback, showed the expected 375,000-point prefix
at frame 15, entered walking mode, moved forward and reset to the whole scene.
Document width remained 390 pixels. No JavaScript, CSP or WebGL errors occurred;
SwiftShader emitted ReadPixels performance warnings. The screenshots show the
office and matching camera view. This is software-rendered desktop viewport
emulation, not a physical-phone performance or touch test. Private evidence:
`corrected-share-browser-review.json` and `corrected-share-390px-{whole,frame15}.png`.

Pending: broader source-to-scene alignment and physical mobile testing.
The initial whole-space browser view failed coherence; READY and a populated
WebGL canvas are insufficient acceptance criteria.

This single compressed benchmark segment does not establish ordinary phone-video
quality, physical mobile GPU/touch performance, a user's owned capture, accurate
metric geometry, scene completeness, upper-bound capacity, or failure-rate/cost
distribution. No independent comparison with TUM ground truth has been performed.
Original-model usage rights and the other launch gates remain open.

Private evidence is in `.lingbot-workspace/real-capture-qa/`: `source.json`,
`live-result.json`, source/clip FFprobe records, preview PNGs, original
`tum-office-scene.glb`, `inverse-pose-diagnostic.json`, and
`tum-office-scene-inverse-pose-diagnostic.glb`, plus the fresh
`corrected-live-result.json` and `corrected-tum-office-scene.glb`. Media and private
receipts are ignored by Git; this document contains no authentication or share
capability.
