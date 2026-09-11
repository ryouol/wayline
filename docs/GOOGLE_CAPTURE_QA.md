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
physical device and browser behavior remain awaiting confirmation. Actual visual
coherence, replay/walk, browser download and expiring-share acceptance for this
new scene remain separate checks; READY, finite points and a verified hash alone
do not close them. No new GPU job, share or deletion was initiated for this read.
