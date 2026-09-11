# Upload capacity verification — 2026-09-10

This exercises upload acceptance and resource use with generated media. It does
not establish real-capture reconstruction quality, GPU sizing, every codec's
worst-case behavior, or physical-mobile performance.

## Generated input

- H.264 MP4, 4096×4096 pixels, 10 frames at 10 fps, one second.
- 1,780,059 bytes; SHA-256 `7df7eea379010d331cfa500842bf11aa99517769e230ed492702534fb0d038f0`.
- Generated with FFmpeg's `testsrc2` filter, not recorded from a real room.
- A second copy was padded to 67,108,864 bytes (64 MiB); decoded content is unchanged.

```sh
ffmpeg -nostdin -hide_banner -loglevel error -f lavfi -i testsrc2=size=4096x4096:rate=10 -t 1 -an -c:v libx264 -preset fast -crf 28 -threads 2 -movflags +faststart -n generated-4096.mp4
```

## Local container

The cached `wayline:recovery-access` Linux/arm64 image has
byte-identical upload service, configuration and request-body-limit source to
the current checkout. The existing container smoke was run with the larger input
in place of its tiny fixture, retaining the same assertions and limits:
512 MiB RAM, 512 MiB memory-plus-swap ceiling, 0.5 CPU, non-root user,
read-only application filesystem and disposable private storage.

Both ordinary and 64 MiB padded uploads passed inspection and deletion. Health,
private authentication, two sample jobs, shared scene delivery, download and
revocation also passed. Peak container memory was approximately
285.2 MiB. This is one generated H.264 workload, not a
worst-case guarantee. The disposable container and test volume were removed.

## Live Render

The same two generated files were uploaded to the operator workspace on
`351f339f9847530fae5955d2e9ce2ce68753624e`. Both returned HTTP 201 and correct 4096×4096 / 10-frame
metadata. The 64 MiB upload completed in 1.371 seconds
from this Mac. Both assets were deleted by their recorded IDs; the complete
asset inventory confirmed their absence.
The final database cleanup check found no pending deletions and no unsettled
object claims.

A subsequent read from Render's Linux/x86_64 container
reported a cgroup memory peak of 261,459,968 bytes
(249.3 MiB). This is the high-water
mark since the container started, not an isolated per-upload measurement.
All four existing jobs remained READY. No reconstruction was submitted, no GPU
was invoked, and the Google account's free video was not consumed.

This verifies the exercised full-payload path through Render. It does not prove
worst-case concurrency, slow-client deadlines, truncated/chunked edge behavior,
or upstream OAuth/proxy log redaction. The earlier local fixture verification
had been small dimensions; this adds a supported-resolution boundary case.

## Physical-mobile and provider setup

The Mac's iPhone Mirroring app showed its initial onboarding screen. Setup was
not enabled, so no physical-device browser QA is claimed. That requires operator
setup or a direct phone test.

Modal's dedicated `wayline-roy` workspace was rechecked: Starter, $1 total usage
limit, $0 charges and payment activation required. The live runner remains in
`royluo05`; its shared limit was $200 with no custom spend cap, $0.41 of credits
used and $0 charges. Shared account limits were changed by neither this test nor
the prior backup copy. Scoped service users require Team/Enterprise; no paid
upgrade was selected. See [Modal service users](https://modal.com/docs/guide/service-users)
and [Modal pricing](https://modal.com/pricing).

The dedicated workspace's activation flow reached a Stripe-hosted US$0.50
account-verification checkout. It requires the account holder's verification
to use the saved payment details. No payment was completed and no independent
production spend limit was enabled during this pass.
