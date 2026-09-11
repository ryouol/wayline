# Scheduled encrypted recovery sets

This describes the implementation and operator procedure. It is not a deployment
receipt or evidence that a maximum-size workspace has passed recovery QA.
See [manual recovery evidence](RECOVERY_QA.md) for the earlier tested sets.

## Enable

Set both destination values on the existing single Render service:

| Environment setting | Value |
| --- | --- |
| WAYLINE_RECOVERY_RECIPIENT | The operator's public age recipient, starting with age1 |
| WAYLINE_RECOVERY_VOLUME_ID | The existing Modal recovery volume's vo-… ID |
| WAYLINE_RECOVERY_UPLOAD_BUDGET_BYTES | 10737418240 by default: 10 GiB |

Both destination settings must be supplied together; leaving both unset disables
the worker. The image includes a pinned age executable. Modal authentication uses
the service's existing SDK credentials, which must access the selected volume.
No new service, public backup endpoint or GPU invocation is needed.
Only the public encryption recipient belongs in Render. Keep the private age
identity outside Render and Modal. Independent key escrow is still required:
losing the only Mac copy would make the encrypted sets unrecoverable.

## Schedule and limits

- The worker checks approximately every minute and admits at most one attempt
  per 24 hours, persisting admission before work. Restarting does not reset the
  interval or retry a failed attempt immediately.
- A child process performs the copy, encryption and transfer. The supervisor
  stops its process group after 15 minutes or during application shutdown.
  Startup cleanup removes recorded abandoned staging directories under the
  recovery lock, without disturbing a concurrent manual invocation.
- The online SQLite snapshot includes referenced objects, the share secret,
  runtime manifest and recovery ledger. Concurrent object deletion can fail
  the copy. Keep deployment configuration and secrets stable during capture.
- Staging uses a new private directory in disk-backed /tmp, outside the live
  workspace. Preflight requires roughly twice the estimated snapshot size plus
  512 MiB free. The snapshot payload ceiling is 4 GiB; this rejection limit is
  not proof of full-capacity performance.
- Remaining allowance is checked before copying. Before encryption, durable
  reservations cover the measured archive estimate with tar/age/metadata
  headroom and a separate 128 KiB completion manifest allowance. Reservations
  count for 30 rolling days and remain charged on failure or uncertain upload.
  They are deliberately conservative and are not refunded to actual byte counts.
- An explicit allowlist of application configuration, Google/Modal credentials
  and deployment identifiers is included as encrypted environment.json.
  Unrelated process environment, SSH credentials and Render API keys are excluded.
  There is no plaintext environment file or intermediate plaintext tar.

## Transfer format and retention

The encrypted archive is uploaded under /scheduled/TIMESTAMP-UUID/ as ordered
part-0000.age, part-0001.age, etc. Every part is at most 8 MiB. Uploads and full
readback/hash checks run sequentially; only one local part file exists at a time.
This avoids the SDK's large-file parallel buffering path. The parts are pieces
of one age archive and cannot be decrypted separately.

Only after every part verifies does the worker upload and verify complete.json:

    {
      "format": 1,
      "created_at": 1800000000,
      "archive": {
        "bytes": 12345,
        "sha256": "<whole encrypted archive SHA-256>",
        "parts": [
          {"name": "part-0000.age", "bytes": 12345, "sha256": "<part SHA-256>"}
        ]
      }
    }

These numbers illustrate the schema only. Parts without a verified completion
manifest describe an incomplete attempt, not a completed recovery set.

Retention keeps the latest seven locally verified completed sets. A restored
ledger also protects uncertain retained candidates until seven verified completed
sets exist. This can temporarily preserve more than seven prefixes; uncertain
candidates do not displace verified sets. Completed sets are pruned only after a
newer set verifies. Failed-prefix cleanup continues on later attempts even when
the upload allowance is exhausted. Existing manual prefixes are outside this
worker's deletion scope. Expired, already-pruned ledger entries are compacted
while recent reservations and unpruned prefixes remain recorded.

## Reassemble and restore

1. Select a completed prefix in the intended Modal workspace. Download its
   complete.json using the authenticated SDK/CLI and check format 1. Reject
   an empty parts list, duplicate names, unexpected paths or parts above 8 MiB.
   Names must be the sequential part-NNNN.age names in the manifest.
2. In a new operator-only directory, download each listed part sequentially.
   Verify its exact byte count and SHA-256 before appending it to a new
   workspace.tar.age file. Delete each downloaded part after appending.
   Use manifest order, not filesystem listing order. Reject the entire set
   on a missing, truncated, oversized or mismatched part.
3. Verify the assembled file's byte count and SHA-256 against archive.
   Successful transfer verification alone is not a completed restore test.
4. On the operator machine with its private identity, decrypt the assembled file:

       umask 077
       age --decrypt -i /path/to/private-recovery-age.key -o workspace.tar workspace.tar.age

5. Extract the tar into a new private directory with a safe tar extractor,
   rejecting unsafe paths and links. It contains workspace/ and environment.json.
   Treat both as private data. Restore into another new path:

       python -m lingbot_map.workspace.backup restore --snapshot /path/to/extracted/workspace --output /path/to/new-restored-workspace

6. In an isolated instance, disable Google signup, Modal execution and scheduled
   recovery; restore required environment values privately. Verify database/object
   integrity, operator access, identities, a known artifact hash and sharing.
   Preserve the restored recovery ledger: it carries admission and reservations
   and protects the recovery source against premature deletion.
7. Switch production only through a separate planned restore, preserving the old
   workspace until acceptance. Remove temporary plaintext tar, extraction and
   test data after verification. Do not restore over the running workspace.

## Status, cost and remaining acceptance

LINGBOT_DATA_DIR/recovery-state.json is private operator state, written atomically
with mode 0600. It records attempts, reservations, last success and safe failure
categories. The supervisor logs a stale warning when no verified success exists
within 36 hours. These logs are not an independently delivered alert; an external
notification channel and monitored recovery objective remain to be configured.

Ten GiB is 10.7374 decimal GB. At Render's $0.15/GB public egress rate, that
reservation volume corresponds to **about $1.61**, before shared allowances.
This is not a wire-byte or invoice cap: SDK retries, protocol traffic and other
application traffic are outside that calculation. Modal storage is additional.
See [Render bandwidth pricing](https://render.com/docs/outbound-bandwidth) and
[operating costs](operating-costs.md).

At 3.5 GB of live data, full daily copies cannot continue throughout the month
within the 10 GiB allowance. Exhaustion preserves existing sets but makes new
backups fail until allowance becomes available. Daily admission is not a
guaranteed daily recovery point. Full-capacity memory/time/restore verification,
offsite key escrow, scoped or immutable recovery access, failure alerts and a
replacement Render recovery drill remain required.
