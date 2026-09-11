# Recovery crash and capacity QA — 2026-09-11

## Crash fix

A local reproduction found that a process exit after a remote completion marker
was verified, but before local success was saved, left a restorable backup marked
running. Restart marked it failed; the next attempt deleted its remote prefix
before checking allowance, leaving no replacement when that check failed.

The fix durably records `completion_pending` before marker upload. Cleanup
protects that uncertain candidate using the existing retained-source rules.
Verified success clears the flag. Failures before durable verified completion
preserve charges, retry eligibility and the previous `last_success`. A later
retention-deletion failure leaves the verified set and newer success recorded;
that completed attempt is not eligible for a failed-attempt retry. The flag
itself does not claim a successful backup.

Two real subprocess-exit regressions cover death immediately after the fake
destination copies the marker and death after marker verification but before
local success persistence. Both verify multipart/whole hashes, real age
decryption, snapshot restore and the original scene hash, then restart cleanup
and prove that an exhausted next admission preserves the source and reservations.
Marker upload/readback uncertainty also remains retryable; candidate removal
requires the normal post-success retention condition with seven verified sets.

A separate test starts real Uvicorn processes and sends SIGKILL after an artifact
transaction commits but before job completion. Unfinished artifacts reject HTTP
content/download/share requests. Normal restart after natural lease expiry
completes attempt two, removes abandoned data, settles usage once, preserves
idempotent submission and retains the previous READY scene byte-for-byte.
These are local synthetic execution/transport fixtures, with no provider calls.

The final local suite passed **237 Python tests**, including 31 recovery tests
and the process-kill integration. Strict Ruff, formatting and mypy passed.
Container `3cf2b42c4b229a29e0a11e51d6c358ed775103de3e7818bf896d179ae9a8c541`
passed the non-root/read-only 512 MiB / 0.5 CPU smoke with a 205.9 MiB peak,
including health/authentication, two samples, 64 MiB upload and share/download/revoke.
Hosted CI and deployment evidence are recorded below.

## Bounded remote retention

A follow-up found two ways stored archives could grow over successive allowance
windows: uncertain completions survived indefinitely, and failed deletion of
superseded completed sets was not retried before another upload. The worker now
retries eligible cleanup first and permits at most eight known, unpruned scheduled
prefixes. Admission stops before copying, reserving or uploading a ninth set.
Normal rotation preserves seven verified sets plus room for one replacement.

Tests cover marker upload/readback uncertainty across expired 30-day allowances,
restart and explicit retry, as well as repeated deletion failures and resumed
rotation after cleanup recovers. A sole possibly usable marker remains preserved.
Seven verified sets plus one uncertain candidate intentionally pause new backups
until operator reconciliation. The code does not promote an uncertain set to
success or evict it merely to free capacity. This is a bounded-storage policy,
not automatic reconciliation or a provider invoice cap. The theoretical maximum
known scheduled payload is approximately 32.13 GiB; manual/unknown prefixes and
provider accounting are outside this limit.

## Near-capacity offline drill

The pinned pre-fix image `424a516abcb6f6e032ac1abbca941d3f24feb5981f983df600f9997c14d8d9ee`
ran with no network, a read-only root, 512 MiB memory/no swap and 0.5 CPU.
Seven disposable 512 MiB tenants held 52 inspected MP4 fixtures, each padded to
64 MiB with a valid free atom, plus a synthetic scene and manifest. There were
54 referenced objects totaling **3,489,756,895 bytes**, 99.71% of the configured
3.5 GB global ceiling. This is near capacity, not an exact-ceiling admission test.

- Real snapshot, age encryption and sequential disk-backed fake-volume transfer
  verified a 3,491,002,680-byte archive in 417 parts, each at most 8 MiB.
- Archive SHA-256: `a7ebd87d8b8afde881eb5f10c456edc02b3a64e148fa6b78307a5fc900303543`.
- Snapshot/encryption/upload/readback took 86.861 seconds; streaming decryption
  and extraction 52.540 seconds; verified restore 13.222 seconds. The complete
  fixture preparation and drill took 163.549 seconds on this local machine.
- Restore verified all 54 object hashes, seven tenants and their asset counts,
  the share secret, selected encrypted environment and bootstrap authentication.
- Sampled anonymous memory peaked at 92,426,240 bytes. Cgroup lifetime peak was
  536,875,008 bytes with 157,279 `max` reclaim events and zero OOM/OOM-kill events.
  This demonstrates completion under memory pressure, not spare service capacity.
- Peak logical disk use was 13,959,501,721 bytes. Host free space stayed above
  4,349,210,624 bytes, exceeding the enforced 2 GiB abort floor. The disposable
  container, volume, generated identity and plaintext were removed afterward.

No service workers or HTTP server ran concurrently with this capacity drill.
The inherited web healthcheck reported missing web configuration because the
container entrypoint was the offline harness; it is not a live-service health
result. The disk fake volume does not exercise Modal SDK buffers, latency,
durability or billing. Its seven local tenant limits differ from the live
two-account pilot and 256 MiB operator limit. The pinned image predates the
completion-acknowledgement fix, so this drill validates the existing bulk
snapshot/encryption/restore path separately from the new crash regressions.

The first harness attempt stopped on an incorrect result-field name before
filling the fixture. That assumption was corrected after its terminal exit;
the successful run and both diagnostic receipts remain in the ignored local
`.lingbot-workspace/full-capacity-recovery-qa/` directory.

## Live release verification

- Runtime: `d88da1579e57de8ba99d44e3ebdf8662f1679bc3`; Render deploy `dep-dai3o8m7bikc73bekfs0`
  became live at 2026-09-11T17:37:23.389238Z on the existing Wayline service.
- [Exact-commit CI](https://github.com/ryouol/lingbot-map/actions/runs/34628366203)
  passed 237 Python tests, ten Node suites, strict lint/type/format checks,
  packaging and production-container verification.
- Public HTTPS health returned 200. All 64 deployed static files and the recovery
  module match the reviewed source. All 12 stored artifact files match database
  sizes/hashes; their complete metadata digest is unchanged across deployment.
- SQLite integrity is `ok`; six READY jobs, one Google identity, four remote runs
  and zero active jobs/pending remote cleanups are unchanged. The two-account
  pilot, GPU allowance, storage/delivery budgets and recovery reservations remain
  intact. This deploy created no new service, GPU invocation or backup admission.
- The recovery ledger still has no successful automatic set. Its two prior
  attempts, 18,141,370 reserved bytes and next normal admission at September 12,
  02:24:37 UTC are unchanged. A source fix and healthy web process do not prove
  recovery at the provider.

The previous [design release](DESIGN_RELEASE_QA.md) records live Google returning
login and saved-scene browser rendering. This backend-only deployment did not
repeat that browser flow or run new model inference. Exact selected-state and
hash receipts are retained in the ignored local recovery QA directory. A later
documentation-only commit records this result without changing the runtime.

## Remaining operational gates

The live ledger still had two charged attempts, 18,141,370 reserved bytes and no
successful automatic set at the read-only post-release check. Its next normal
admission remains September 12 at 02:24:37 UTC. This fix does not establish the
cause of either earlier provider failure and admits no extra retry.

Still required: a complete scheduled provider copy and restore, live retention,
full-capacity provider/concurrent-service recovery, external alerts, independent
key escrow and a replacement Render drill. Owned-capture, second-account,
physical-mobile, rights and operator-policy gates also remain open.
