# Scheduled recovery QA — 2026-09-11 UTC

This follow-up covers encrypted scheduled copies and three viewer accessibility
fixes, not owned-video reconstruction quality or public launch approval.

## Local verification

- 189 Python tests passed, including real age encryption/reassembly/restore,
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
  Later changes only refine retained-set selection and move ledger compaction
  before provider cleanup; they do not change the measured transfer path.

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

Pending the reviewed commit, green CI and a first verified automatic live copy.
External alerts, independent private-key escrow and a replacement Render restore
remain open. The existing separately encrypted manual recovery set is preserved.
