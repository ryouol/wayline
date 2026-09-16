# Wayline efficiency evidence — 2026-09-16

**Finding:** model loading dominates the measured worker stages. Reducing the
sample rate retained recognizable office structure in this one exploratory
comparison, but cold/warm differences prevent attributing the observed latency
reduction to sampling alone. The production sampling default is unchanged.
Wayline remains a research preview powered by upstream LingBot-Map.

## Fixed input and execution

[Machine-readable measurements](gpu-efficiency-2026-09-16.json) retain the raw stage values.

One fixed scene, two successful runs, zero failed reconstructions. This is a
small exploratory set, not a general performance benchmark. The separate
cancellation drills are not successful-scene measurements.

- TUM RGB-D Benchmark, `freiburg3_long_office_household`, first 300 frames,
  640×480, 30 fps, 10 seconds; source MP4 SHA-256:
  `50ca39e22796f8e741983f9830cb7fffbbcf03579fa1f648eaa80a1c2fcccdbd`.
- CC BY 4.0, attributed to J. Sturm, N. Engelhard, F. Endres, W. Burgard and
  D. Cremers, *A Benchmark for the Evaluation of RGB-D SLAM Systems*, IROS 2012.
  Frames 0–299 were selected and transcoded to H.264; no resolution change.
  [Dataset and license](https://cvg.cit.tum.de/data/datasets/rgbd-dataset#license),
  [original preparation evidence](REAL_CAPTURE_QA.md).
- NVIDIA A100-SXM4-80GB, original pinned checkpoint
  `ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72`,
  processed tensors 518×392. Sampling alone changed: 3 fps versus 2 fps;
  both requested a 120-frame maximum. Both exported 750,000 points.
- Normal application upload/admission/worker/publication paths ran in an isolated
  local application using the deployed private Modal worker. This is not a
  Render network-latency benchmark. The isolated comparison had two 600-second
  admission slots; production admission settings and user allowances were unchanged.
- Baseline call `fc-01M2NFHA0ZC92CH8SE48VJ9CAH`; variant
  `fc-01M2NFMK2VN7RSGAE9ABER9W5A`. Both remote cleanup rows became cleaned.

## Stage breakdown

Seconds unless otherwise stated. Nested totals overlap; do not sum all rows.

| Measurement | 3 fps baseline | 2 fps variant |
|---|---:|---:|
| Sampled frames | 30 | 20 |
| Application queue | 0.0013 | 0.0015 |
| Source upload | 1.597 | 0.838 |
| Provider round trip | 103.415 | 31.691 |
| Worker imports | 4.691 | 0.00002 |
| Input volume reload | 0.126 | 0.391 |
| Frame extraction | 2.271 | 0.818 |
| Frame preprocessing | 0.134 | 0.068 |
| Model loading | **41.135** | **25.542** |
| Host-to-device copy | 0.016 | 0.010 |
| Reconstruction, including CPU output transfer | 5.798 | 1.533 |
| Postprocess and export | 0.606 | 0.445 |
| Artifact volume upload | 2.678 | 2.628 |
| Worker total | 57.522 | 31.437 |
| Artifact download/validation | 1.803 | 1.689 |
| Server completion from submission | **107.062** | **34.313** |
| Peak allocated CUDA memory, GiB | 8.627 | 8.635 |
| Peak reserved CUDA memory, bytes | 9,288,286,208 | 9,286,189,056 |
| GLB bytes | 12,210,576 | 12,140,192 |
| Local browser first-load readiness | 0.189 | 0.184 |

Browser measurements are independent loads from a loopback fixture in the Codex
browser; they are not submission-to-visible latency or production network tests.
The first baseline load preceded the explicit viewport override; fixed-view
screenshots and the later baseline reload used 1280×800. That reload measured
0.167 seconds. Do not claim a browser-speed comparison from these observations.

The 45.893-second baseline difference between provider round trip and worker
runtime combines queue, container startup and RPC overhead. Neither provider
queue nor container startup is separately established. Keep both fields null.

## Profile of the slowest worker stage

A coarse CPU/I/O profile from timestamped provider logs localizes the loading
cost. Baseline model construction began at 16:07:51 UTC, checkpoint verification
at 16:07:59, the private verified copy became available at 16:08:25, and checkpoint
load completed at 16:08:30. Approximate intervals: **8 seconds construction,
26 seconds integrity/copy, 5 seconds deserialization/state loading**, followed
by final device/dtype work. Logs have one-second resolution and buffering;
these intervals are diagnostic localization, not an exclusive CPU profile.

The warm variant logged construction at 16:08:46, verification at 16:08:54,
verified-copy availability at 16:09:06 and load completion at 16:09:10: roughly
8, 12 and 4 seconds. The loader constructs a new model each call and verifies
its private checkpoint copy. It does not retain a loaded GPU model between calls.
No integrity checks were removed. PyTorch/Nsight kernel profiling is not justified
by this evidence; checkpoint loading and host I/O deserve the next investigation.

The near-zero second import duration and shorter verification interval establish
a warm-order confound. Neither the 68% end-to-end decrease nor the 74% inference
decrease is a controlled sampling speedup. Reverse-order warm repetitions and
additional scenes are required before changing defaults.

## Fixed-reference quality review

Reference GLB SHA-256:
`3556540de61cb0a99f8d1d54b128715739ecd3cc06593fb22fa515aae0e992b3`.
Both outputs were inspected at 1280×800, identical viewer point size/theme,
whole-scene orbit yaw 0.35, pitch 0.15, distance 3 in each normalized scene,
and the nearest sampled replay frames to 0%, 25%, 50%, 75%, 100% of the clip.
This normalization does not establish world-coordinate alignment.

Paired replay frame indices were 0/0, 7/5, 15/10, 22/14 and 29/19. Their timestamps
were 0/0, 2.400/2.600, 5.133/5.233, 7.533/7.333 and 9.967/9.967 seconds.
Five paired replay views and a paired orbit view are saved in the local QA
workspace as `efficiency-{baseline,variant}-{0,25,50,75,100,orbit}.png`.
These screenshots derive from the attributed TUM input; no private capture is used.

Qualitative severity: 0 absent, 1 minor, 2 clearly visible, 3 prevents recognition.

| Criterion | Baseline | Variant | Observation |
|---|---:|---:|---|
| Missing visible surfaces | 2 | 2 | Both have incomplete wall/background and gaps around furniture |
| Floaters / noisy boundaries | 2 | 2 | Both show boundary noise, holes and thin outlying surfaces |
| Loss of recognizable structure | 0 | 0 | Globe, table, divider and chairs remain recognizable |
| Gross trajectory discontinuity at reviewed positions | 0 | 0 | Ordered viewpoints follow the same scene; not a continuous-motion or pose-accuracy test |

The variant did not show an obvious structural regression in these views. It
provides 20 replay frames instead of 30, so temporal granularity is coarser.
The point cap also allocates more points per sampled frame, which can make an
early variant replay look denser despite fewer input frames. This is not proof
of equal geometric accuracy or improved reconstruction quality. Retain 3 fps as
the default until a controlled, broader comparison supports a change.

## Cost breakdown and limits

[Modal pricing](https://modal.com/pricing), checked September 16, 2026, lists
A100 80 GB at **$0.000694/GPU-second** before credits. Multiplying measured worker
function time by that rate gives these **GPU-only function-window components**:

| Cost component, USD | Baseline | Variant |
|---|---:|---:|
| Model loading window | $0.02855 | $0.01773 |
| Reconstruction window | $0.00402 | $0.00106 |
| Complete measured worker window, includes rows above | **$0.03992** | **$0.02182** |
| Full estimated cost per successful scene | Unknown | Unknown |
| Attributable billed cost per successful scene | Unknown | Unknown |

These are not invoices, full resource estimates or price promises. Container
startup/idle, CPU, host memory, storage, transfer, build cost and the cancellation
drills are outside the component calculation. Provider billing exports were not
obtained. Full-cost and billed-cost fields remain null; do not divide partial
components by two successes and advertise that as actual cost per success.
Configured 600-second reservations remain admission accounting, not billed time.

## Verification and deployment

Commit `aff758c0f3cb09fe8635665c945fa50005107ef2` passed 278 Python tests,
all 11 browser-script suites, lint/type checks and GitHub CI including the
production container smoke check. Render deploy `dep-dalbtqbl550s73anmigg`
reached live at 16:08:50 UTC. Health returned `ok`; deployed viewer bytes matched
this commit, and a browser reload showed the research-preview page without
console errors. The private Modal worker was deployed with the timing changes.

Queue cancellation, running cancellation, provider-failure tests, attempt fencing
and reservation behavior are described in [the measurement contract](GPU_EFFICIENCY.md).
Fresh cancellation observations are recorded below when available. No sharing,
repository visibility or recruiter access settings were changed.

## Fresh cancellation observations

**Provider-queued cancellation:** generated 64×48 test pattern; call
`fc-01M2NF9N8YBH0GMMCXWNZP7BKV`. Before cancellation, the provider showed a
pending call, one queued input and no allocated GPU runner. The isolated app
was observed CANCELLED 1.295 seconds after the local service cancellation
request, with zero reserved/consumed units and no artifacts. The provider call
graph remained PENDING throughout the first 32.17-second observation window,
then later reported TERMINATED. This demonstrates why database state is not
provider-execution evidence. No worker execution was observed for this call;
that is not a measured zero-cost claim. After terminal status was confirmed,
the exact test prefix was manually deleted and absence verified. This manual
cleanup is not evidence of natural grace-period recovery.

**Running cancellation through production API:** generated 640×480, 120-frame,
12-second fixture; call `fc-01M2NFXMCX73TM1DQ4R2QNPX7E`.
The current deployed application admitted one attempt under its unchanged
9,600-second rolling allowance. Before cancellation, that call's logs showed
23/120 inference frames and provider statistics showed one running input and
one container. The application cancel endpoint returned 202.

| Observation | Time / result |
|---|---|
| Cancellation requested | 16:14:45.688 UTC |
| App observed CANCELLED | 1.173 seconds after request |
| Provider cancellation log | 16:14:48 UTC, one-second log resolution |
| Provider observed zero backlog, running inputs and containers | 6.444 seconds after request |
| Last logged inference progress | 72/120 |
| Published artifacts / consumed job units | None / zero |
| Remote admission usage | Increased by one, retained after cancellation |

The 6.444-second interval is an **observed upper bound on residual execution**
under this drill's provider-stat observation, including polling/RPC delay. It is
not exact GPU-kernel duration or invoice cost. The 49 additional logged frames
span the pre-request log sample through final progress; log buffering and request
latency prevent treating all 49 as frames executed after server receipt. The
provider log explicitly recorded receipt and successful input cancellation.
No stale output was published, and other accounts' quota state was unchanged.
The operator ledger recorded `reserve +120` then `cancelled -120`; the operator
ended with zero reserved units. Historical consumed units were unaffected.

The new running attempt's normal remote-file cleanup remains scheduled for
16:40:40.612 UTC; its grace timestamp was not advanced. At the cancellation
receipt it was still pending. Existing [live recovery evidence](RELIABILITY_QA.md)
verifies a previous unmodified 27-minute cleanup cycle. Automated tests exercise
provider errors, retained remote charges, reservation release, stale attempts,
restart cleanup and the cancel-versus-publish race. Provider-error injection is
mocked; no provider outage or crash was induced in production.

Remaining gaps: separate provider queue/startup attribution, controlled warm
repetitions, broader scene coverage, full/billed per-success cost, and actual
provider failure at every transport boundary. These results support a bounded
research-preview engineering story, not a completed production-readiness claim.
