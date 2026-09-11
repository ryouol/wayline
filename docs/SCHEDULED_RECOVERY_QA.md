# Scheduled recovery QA — 2026-09-11 UTC

This follow-up covers encrypted scheduled copies and three viewer accessibility
fixes, not owned-video reconstruction quality or public launch approval.

## Local verification

- 196 Python tests passed, including real age encryption/reassembly/restore,
  conservative reservation persistence, restored-source protection, seven verified
  retained sets, partial upload/readback failure, early allowance rejection,
  failed-provider ledger compaction and service shutdown with concurrent samples.
- Strict lint, formatting, mypy and provider-free app import passed. CI now
  installs age before tests so the encryption round trip is mandatory there.
- Standard non-root/read-only Docker smoke passed under 512 MiB / 0.5 CPU,
  including repeated samples, 64 MiB upload, share/download/revocation and host/auth
  checks. Its lifetime memory peak was 205.6 MiB. Recovery is disabled in that smoke.
- A separate real-SDK recovery drill ran alongside WorkspaceService workers
  inside a read-only, non-root 512 MiB / 0.5 CPU container. One generated fixture
  padded to 64 MiB produced a 67,477,784-byte encrypted archive in nine parts,
  each at most 8,388,608 bytes. Upload plus full readback verification completed
  in 37.478 seconds. Lifetime cgroup peak was 358,813,696 bytes; sampled anonymous
  memory peak during recovery was 126,631,936 bytes. No cgroup max, OOM or OOM-kill
  events occurred. All temporary remote prefixes were removed; no GPU was invoked.
- The constrained image was `0b6ab6e0a7840c2b79fc0b9a99f8f922b9d6b56f327b47cb9498b212de0498c3`.
  Later changes refine retention/compaction and add bounded read retries and
  explicit operator retry admission. This measurement predates those follow-ups.

The earlier 256 MiB diagnostics are not a full-capacity pass: one transfer reached
completion but a harness assertion rejected its cache-inclusive cgroup peak;
other attempts returned a provider ExecutionError during readback. Failure preserved
reservations and cleanup removed the temporary prefixes. Their precise upstream
cause was not established. A later read of the existing 8,399,048-byte encrypted
manual backup succeeded. Do not hide these results or claim the full 3.5 GB
workspace ceiling has been validated. Provider failure rate, full-capacity memory,
latency during backup and recovery time remain acceptance work.

Private receipts and diagnostic logs are under
`.lingbot-workspace/scheduled-recovery-qa/`; no credentials are included here.
Viewer focus, named progress and 44-pixel share controls are documented in
[ACCESSIBILITY_QA.md](ACCESSIBILITY_QA.md).

## Live activation

The worker was enabled with runtime `415956a` and the first automatic attempt
failed after its first 8,388,608-byte part appeared remotely. There was no
completion marker. Its exact failing operation was not captured; a later read
succeeded, which alone does not prove an immediate readback failure caused it.

The reviewed retry fix `1e78b473fd9806701435b3f560a42ea659ce663a` then deployed as
`dep-dahmc83m8hqs73cee4fg` after [CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34554260281).
One explicit bounded operator retry ran for 19.427 seconds and also failed with
`backup_failed`, leaving one encrypted part and no completion marker. Its actual
admission time and operator-retry tag are retained. The old partial prefix was
pruned, but all charges remain: 18,141,370 reserved bytes across both attempts.
No timestamps or reservations were reset and no further full backup was admitted.

Read-only checks of the retained part passed with and without a leading slash.
Three bounded diagnostic probes then passed: an 8 MiB existing-content transfer,
a fresh random 8 MiB transfer, and the app's two-part archive transfer with an
8 MiB existing part plus 1 KiB fresh tail. All diagnostic prefixes were removed;
no GPU was invoked. These probes do not turn either failed attempt into a backup,
and the root cause remains unknown. The next diagnostic-only change distinguishes
terminal upload/readback errors and logs exception class names without provider
messages or URLs; it does not change admission or claim to repair this failure.

HTTP /healthz and the root page returned 200. The live database retained four
READY jobs and one Google identity. The browser rendered the saved 5,908-point
scene and verified its keyboard focus outline at -4 pixels. No hosting plan,
environment value or GPU budget changed for this retry deployment.

**No complete automatic recovery set or scheduled-set restore is verified.** The
previous separately encrypted manual set remains preserved and readable. Full
workspace capacity, live seven-set retention, external alerts, independent key
escrow and a replacement Render restore remain open. Failed-attempt reservations
remain charged while the worker waits for its normal daily admission.
