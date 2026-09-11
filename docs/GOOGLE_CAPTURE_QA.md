# Observed Google-account reconstruction — 2026-09-11

A new video reconstruction was submitted through the existing Google account
while an operator slow-upload diagnostic was running. The diagnostic did not
submit this reconstruction. Read-only database observations establish account
ownership, successful publication and settlement; they do not establish who
filmed the input, the device/browser used or visual reconstruction quality.

The upload was a 9,558,547-byte QuickTime video, 720×1280, approximately 14.133
seconds at 30fps. The original pinned LingBot checkpoint produced 43 sampled
frames and 749,963 points. Queue creation to READY took 77.388 seconds; reported
inference was 8.743 seconds and runner total was 61.421 seconds. These are observed
timings, not invoiced compute duration or a cost forecast.

The scene contains 12,189,048 bytes. A read-only inspection of its actual stored
bytes verified its recorded SHA-256, valid GLB header/length, POINTS primitive,
749,963 finite positions and a nonzero extent on all axes. Its hash is
`140b74abfc14b260d62dca8d8b98dfeba2194fd0cd36e4557dc5655bf01e6c45`.
The manifest is a separate 370-byte artifact. No private imagery or filenames are
included here, and nothing from this scene was promoted to a public sample.

The Google tenant settled 43 consumed units and zero reserved units against its
120-unit ceiling. Remote cleanup was complete. Five of the six conservative GPU
admissions have now been used. Previous receipts showing four admissions and an
unused Google video describe earlier state, not this observation.

## Interleaved operator diagnostic

The operator attempted one generated 1,780,059-byte video upload with a declared
Content-Length and an intended 180-second send. Its initial empty-request control
returned 422 with no observed application spool. After the actual Google job
started, the generated upload received the application's capacity-full 409 after
52.382 seconds. No diagnostic asset was published; health stayed 200 and partial
spool/object claims were absent afterward. No retry or allowance reset followed.

The harness's final invariant assertion failed because it expected no concurrent
user activity and a 422 control response; actual state correctly contained the
new account job and a 409 capacity response. This is not proof of a timeout or a
passing 180-second upload. It also does not locate all buffering between client
and application. The earlier public-edge deadline requirement remains open.

Private receipts are under `.lingbot-workspace/slow-upload-qa/`. Source ownership,
physical device and browser behavior remain awaiting confirmation. No new GPU
job, share or deletion was initiated for that production read.

## Saved-output visual and interaction check

The existing scene was retrieved through authenticated read-only operator
transport and verified against the recorded size/hash. Current production UI
code then served those saved bytes in an isolated loopback fixture. The fixture
had no worker or inference path. Source thumbnails came from the GLB itself;
the original video was not downloaded. Private evidence and the seven-step
illustrated report remain under `.lingbot-workspace/account-scene-qa/`, excluded
from Git, public assets and built distributions.

1. **Load/whole scene: viewer works; visual acceptance fails.** All 749,963
   points load, but the assembled scene shows separated layers rather than a
   convincing continuous space.
2. **Frame selection: functional; quality mixed.** First, middle and last
   selections use the expected camera/timestamp. First/middle views resemble
   their source thumbnails; the last view has substantial depth artifacts.
3. **Replay: completes.** Play from the end restarts at frame one and eventually
   reaches frame 43 at 14.1 seconds, restoring the stopped control state. Exact
   playback wall time was not measured. The strip can remain scrolled away from
   the active thumbnail when playback restarts.
4. **Walk/reset: functional.** A forward step visibly changes the view; Whole
   scene restores orbit/all points. This is not collision-aware or metrically
   validated navigation, and the geometry quality limits its usefulness.
5. **Narrow layout: functional with a usability limitation.** The saved scene
   renders at 390×844 in light and dark mode without horizontal document
   overflow. Walk buttons measure 44px high but sit below the viewer; inspecting
   the full view and stepping requires scrolling. Physical-phone performance,
   touch gestures and assistive technology remain unverified.
6. **Download: HTTP bytes verified, browser save unverified.** The local browser
   link was clicked; a saved browser file was not located. A separate local
   authenticated request delivered the exact 12,189,048-byte attachment/hash.
7. **Local sharing: signed-out access and revocation work.** After sign-out and
   zero local session rows, a fresh tab rendered the scene via a local link.
   The expiry explanation/label was present. API revocation returned 202 and a
   fresh tab showed the unavailable state. No 24-hour wait or production share
   was performed. The shared header's raw `NOASSERTION` wording needs clearer
   user-facing explanation.

The independent numerical check accepts all 43 increasing timestamps and camera
bases. Every frame contributes 17,441 finite, unique points, which project into
their own source image with maximum grid residual 0.000314 pixels. Estimated
motion is rotation-heavy, and several adjacent frames have large depth
disagreement. This is internal consistency evidence, not ground truth: all
poses/depths come from the same model, and occlusion/sampling effects are not
excluded. It does not prove physical camera motion, metric scale or pose drift.

The fixture's three tabs, local database/credentials and server were removed;
the temporary viewport was reset. Its local share was revoked. Production
artifacts, allowances and GPU admissions were unchanged. This closes saved-file
viewer checks, but not owned-capture quality, physical-device acceptance, the
Google account's actual browser save/share flow or a second-account isolation
test. A READY result is not sufficient for the product's reconstruction promise.

### Viewer follow-up

The two direct UI issues found in this audit are corrected in source by
`c8fd218` and were verified in the isolated local fixture. The production
deployment receipt is recorded separately below.
Replay reveals the current source thumbnail by moving only the filmstrip's
horizontal scroll position. Shared headers display “Usage rights unconfirmed”
for `NOASSERTION`; the API/output identifier and other license displays remain
unchanged. The existing tests cover restart, advancing/end frames, no scroll
change for a visible thumbnail, known licenses and label cleanup on expiry or
revocation. All eleven Node suites pass.

The same private saved artifact verified restart/final thumbnail visibility at
desktop and 390×844. Document scroll remained 193px for the desktop observations
and 441.5px for the narrow observations. A 390×844 signed-out local share showed
the readable label without horizontal overflow. Private screenshots/receipts
are under `.lingbot-workspace/replay-followup-qa/`. Its local share, credentials,
database, server and tabs were removed afterward. This follow-up does not alter
the scene's visual-quality conclusion or close physical-phone acceptance.

### UI deployment receipt

Exact-source [CI 34640794995](https://github.com/ryouol/lingbot-map/actions/runs/34640794995)
passed for `c8fd218`: 255 Python tests in 31.08 seconds, all eleven Node suites,
strict lint/type/format and wheel/container verification. The 512 MiB / 0.5 CPU
container smoke peaked at 214.2 MiB. All simplify and code-review subskill passes
completed; aggregate PR size remains open.

Render deployment `dep-dai5nk6k1f9s73cv8kog` became live at
`2026-09-11T19:52:32.766858Z`. Read-only verification matched all 64 static files,
eight backend modules, eight source/installed-wheel notice files and all 14
stored artifact hashes. Health was 200; seven READY jobs, one Google identity,
five GPU admissions, zero active/uncleaned runs, configured limits and recovery
reservations were preserved. Analytics remains disabled. This is production
source/state verification, separate from the local browser evidence above.
Modal remains at the verified `5e1d370` model/notice build; the frontend-only
follow-up required no new Modal deployment or GPU job.
