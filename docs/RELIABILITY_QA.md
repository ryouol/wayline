# Live reliability checks — 2026-09-10

These checks use the deployed application at
`351f339f9847530fae5955d2e9ce2ce68753624e` and generated test inputs. They
exercise cancellation and upload handling, not real-room reconstruction quality
or physical mobile behavior. No user capture or Google free-video allowance was
used.

## API cancellation during actual model inference

- Input: generated H.264 MP4, 640×480, 120 frames at 10 fps, 12 seconds,
  493,860 bytes. SHA-256:
  `63637860153244f131f936fad9eb7657f287cfbf8f228611633db3686fd968b7`.
- The operator upload/research APIs submitted one attempt to the existing private
  original-model A100 worker. No direct SDK inference was submitted.
- Job: `job_cd389c85e89e4c71b1694722e021230f`.
  Modal call: `fc-01M26Y9EZQCV2K55D1BVMMNRNF`.
- The observer saw the call's own streaming-inference log at frame 47/120 and
  provider statistics showing one running input and one container. It then
  called the application's cancel endpoint.
- Cancellation returned HTTP 202. The server recorded CANCELLED 0.138 seconds
  after the client's request timestamp. This is application-state timing, not
  provider termination latency or billable duration.
- The provider's final inference progress was 71/120. Logs recorded receipt of
  cancellation and successful input cancellation. Subsequent statistics showed
  zero backlog, zero running inputs and zero containers.
- No artifact was published; job usage was zero. The historical job record
  retains its original 120-unit reservation value. The Google workspace stayed
  at 120 quota units, zero reserved and zero consumed.
- The rolling provider-admission count increased from one to two of six.
  Cancellation does not refund that operator compute allowance.

The initial diagnostic driver incorrectly expected HTTP 200 for cancellation;
the API correctly returned 202 on both the first and its defensive repeated
request. The driver's response assertion was corrected, and observation
continued on the same job/call. No second GPU attempt, manual SDK cancellation,
application setting change or cleanup timestamp edit was used to obtain the
result.

The normal 1,620-second remote-cleanup grace period was observed without edits.
The running worker marked the record cleaned; observation recorded this
44.735 seconds after its original due time. A separate Modal directory listing
confirmed the attempt's source/output prefix was absent. Provider statistics
remained at zero backlog, running inputs and containers. The Render process's
start marker stayed unchanged and the Google allowance stayed unused.

The test job was then deleted. This also deleted its now-unreferenced source,
as designed; an extra source DELETE returned 404, and complete-inventory
inspection verified absence. The diagnostic did not recreate or resubmit it.

## Public-edge streamed requests

The following HTTP/1.1 requests used chunked transfer encoding without a
Content-Length header:

| Case | Result |
|---|---|
| 65,537-byte JSON body | HTTP 413, application byte-limit error |
| Complete generated-video multipart body | HTTP 201, correct byte size and video metadata |
| Multipart body without its closing boundary | HTTP 422, no asset created |

All three returned `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`
and `X-Frame-Options: DENY`. The valid upload was deleted and its absence checked
in the complete asset inventory. These cases did not submit a GPU job.

## Partial-upload disconnect

A separate slow chunked upload reached the running Render process: its open
temporary file was 2 MiB, a concurrent upload returned the specific upload-slot
HTTP 429 response, and health remained HTTP 200. The connection then reset before
an HTTP timeout response was recorded. This does not establish which network
layer caused the reset or verify the 900-second deadline through the public edge.

After disconnection, the temporary file descriptor was gone, the process had
not restarted, and the next empty upload reached normal HTTP 422 validation.
Health remained 200. The test therefore verifies the exercised disconnect and
admission-release path; the public-edge deadline remains open.

## Application deadline and concurrent sample work

A separate loopback observation against the same running Render application
verified its unchanged parser deadline while bypassing the public proxy. The
incomplete chunked upload held a 2 MiB temporary file and periodically sent more
bytes. The application returned HTTP 408 after 900.008 seconds with its expected
upload-timeout message. The temporary file descriptor was gone afterward,
the next empty upload reached HTTP 422 validation, and no asset was published.
The process did not restart. This proves the live application deadline; it does
not substitute for verification of every upstream timeout/buffering layer.

While that upload held the admission slot, an operator synthetic scene reached
READY in 0.403 seconds as observed from this Mac. It contained 5,908 points in a
95,388-byte GLB and used zero compute units. Upload admission was confirmed held
both before and after scene creation. The test scene was deleted. This shows
that sample work remained usable during this stalled upload; it is not a
multi-user throughput benchmark.

The final storage check retained all four original READY jobs and found zero
pending local deletions, object claims, remote-cleanup records or partial upload
file descriptors. The Render process start marker was unchanged throughout.

## Remaining acceptance

The later [recovery crash QA](RECOVERY_CRASH_QA.md) adds a real local SIGKILL
after an artifact transaction commits, followed by normal restart and natural
lease expiry. Partial artifacts stay private; the retry completes once, cleanup
finishes, idempotency holds and another saved scene is preserved. Its local
synthetic engine and three-second test lease do not establish remote provider
crash behavior. The new encrypted-backup publication regressions are separate.

Still open: full crash/failure recovery at every transport boundary, broader
codec/concurrency/load cases, public-edge timeout behavior, upstream OAuth/log
redaction, owned-capture quality and physical mobile QA. See
[launch readiness](launch-readiness.md) for the complete release boundary.
