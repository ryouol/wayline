# GPU efficiency and admission evidence

Wayline remains a research preview powered by upstream **LingBot-Map**. This work
adds observability; it does not establish commercial hosted-use clearance,
change sharing, or change repository visibility. Confirm intended recruiter
access before placing source links in recruiting material.

## Measurement contract

All durations use a monotonic clock within their process except persisted job
lifecycle timestamps. Do not subtract clocks on different machines.

| Measurement | Boundary |
|---|---|
| Application queue | Job `startedAt - createdAt`; first claim, including earlier waiting on recovered jobs |
| Source upload | Local Modal volume upload, before spawn |
| Provider round trip | Spawn through returned report; includes provider queue/startup, execution and RPC overhead |
| Worker imports | Entry into Python function through imports; **not container startup** |
| Volume reload | Worker input volume synchronization |
| Frame extraction | Decode and sample source frames |
| Frame preprocessing | Load images and resize to model tensor |
| Model loading | Checkpoint verification/load, device placement, dtype conversion, CUDA synchronization |
| Host-to-device transfer | Tensor copy through CUDA synchronization |
| GPU reconstruction | Model streaming call through CUDA synchronization; includes CPU output transfer within that call |
| Export | Postprocess, visualization preparation and GLB export |
| Artifact upload | Worker volume commit of scene/report |
| Artifact download | Web worker retrieval and GLB validation |
| Artifact storage | Web object writes through successful fenced finish |
| Server completion | Job `finishedAt - createdAt`; independent of whether anyone opens a viewer |
| Browser readiness | Scene load to first draw plus two animation frames; excludes job processing and is not proof of physical screen presentation |

The manifest and scene metadata carry allowlisted worker/transport fields. The
restricted `reconstruction_completed` structured log adds application queue,
storage and current-attempt processing durations. The browser exposes the last
measurement as `viewer.readiness` and emits `wayline-viewer-ready` on its canvas.
Stale or destroyed viewers cannot emit readiness. These timings are local only;
no new analytics requests or capability tokens are collected.

Provider queue and container startup are **unresolved separately**: the installed
Modal public call-graph contract supplies state/identity, not reliable lifecycle
timestamps. Preserve null fields until a provider trace/export supplies both
boundaries. Do not relabel the provider round-trip residual as container startup.
The remote volume's report is written before commit; the returned report and
application manifest include the completed commit duration.

Peak allocated and reserved CUDA memory are reset before model loading and sampled
after export. Record GPU model, processed tensor width/height, source dimensions,
source frame count and sampled frame count. CUDA allocator peaks exclude driver
and non-PyTorch allocations. `totalSeconds` retains its earlier boundary;
`workerTotalSeconds` includes function imports and volume commit.

## Fixed comparison protocol

`scripts/benchmark_wayline.py` validates a private manifest containing 1–3 scenes:

```json
{"scenes":[{"id":"scene-01","path":"capture.mp4","sha256":"REPLACE_WITH_SHA256",
 "license":"owned capture; permission recorded by operator",
 "providerProcessingAllowed":true}]}
```

Pass `--base-url`, `--output` and the manifest path to validate without submitting.
Set `WAYLINE_BENCHMARK_TOKEN` privately and add `--run` to submit through normal
API admission. Maximum six attempts; no automatic resubmission or budget increase.
The output directory must be new. A submission interrupted before receiving a
job ID remains uncertain: reconcile its saved idempotency key before proceeding.
A polling deadline requests cancellation but does not claim provider termination.

Compare 3 fps with 2 fps, keeping the checkpoint, 518 image-size setting, 120-frame
ceiling, export settings, source hashes and A100 80 GB GPU constant. Use captures
shorter than 40 seconds so neither arm truncates its trajectory. Record whether
runs are cold or warm; repeat with reversed order before generalizing timings.
Both arms remain private for review; this script creates no shares.

Freeze the baseline GLB hash as the visual reference. In the same browser,
1280×800 viewport, device pixel ratio and point size, compare whole-scene orbit
at identical yaw/pitch/distance plus replay positions at 0%, 25%, 50%, 75%, 100%
of capture time. Save paired screenshots. Score missing surfaces, floaters,
trajectory discontinuity and recognizable structure on an explicitly recorded
0–3 severity scale. Use identical camera transforms, not independent auto-fit.
This is a qualitative reference comparison, not ground-truth geometric accuracy.
Record verdicts per scene before accepting a speed improvement.

Profile the largest measured stage first. For loading/extraction/export, use
CPU timing/profiling and I/O evidence. Use PyTorch/Nsight only if reconstruction
is the relevant bottleneck. Change one factor per comparison; CPU/GPU overlap
and resolution changes are subsequent experiments, not part of the sampling arm.

## Cost accounting

The configured GPU-seconds budget is conservative admission accounting. It is
neither measured runtime nor invoice cost. A failed or cancelled remote attempt
retains its admission charge even when the user's frame reservation is released.

Benchmark receipts keep estimated and billed USD fields separate and initially
null. Populate estimates only with dated rates and explicit GPU/CPU/memory,
startup, idle and transfer assumptions. Populate billed values from attributable
provider billing exports; allocate shared idle charges with a documented rule.
For each fixed scene/arm, sum **all** attributable attempts (including failures)
and divide by successful completions. No success or incomplete cost evidence
means null, never zero. Report GPU-only component estimates with that label.

## Cancellation and recovery evidence

- Automated queue cancellation checks release reservations without provider work.
- The atomic-finish race test verifies committed cancellation wins and no partial
  artifact is published. Existing lease/attempt tests reject stale publication.
- Modal transport tests cover cancellation during upload, spawn, inference and
  download stalls, provider failure, retained remote charges and restart cleanup.
  These use a mocked provider and do not measure GPU termination.
- [Existing live reliability evidence](RELIABILITY_QA.md) observed inference at
  frame 47/120 before cancellation and final progress at 71/120: **24 additional
  logged frames after the observer's pre-cancel sample**. This is an observation
  window, not an exact count of frames executed after request receipt. The app
  reached CANCELLED in 0.138 seconds, then provider input/container counts reached
  zero. The 27-minute cleanup grace elapsed normally and remote files disappeared.
- New `provider_cancel_ack` logs measure cancellation RPC acknowledgement only and
  explicitly mark provider termination unverified. An acknowledged cancel is not
  proof that execution has stopped.

For a fresh running-cancel drill, capture request time, last running observation,
first terminal provider observation, sampling interval, call ID, post-cancel
progress and billing interval. Report residual-work bounds and observation lag;
never infer zero residual work from database state. Do not inject faults into
other users' jobs or terminate a shared container without isolating the drill.

## Completion boundary

Instrumentation and regression evidence are implemented. A licensed real-scene
comparison, separately attributed provider queue/startup, full per-success cost,
and a fresh residual-GPU-time/provider-failure drill remain required before this
optional portfolio story can be marked complete. Generated test patterns verify
execution only. Keep those gaps explicit in recruiting claims.
