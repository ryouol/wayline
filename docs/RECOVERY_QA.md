# Deployed recovery verification — 2026-09-10

A coordinated snapshot of the live Render workspace was encrypted, exported to
the operator's Mac, restored into a fresh Linux volume, and served by the
production application. This verifies the manual recovery path. It does not
establish a nightly schedule or a completed restore onto a replacement Render service.

## Evidence

- Source: Wayline service `srv-dahhn0u7bikc73e82h9g`, `/data/wayline`, application
  commit `d3a6989899bd5e369df62db4e1fb83e73d1bbf74`.
- Successful snapshot deployment: `dep-dahitv15efls73c50sfg`.
- Snapshot: 18 files, 8,629,163 bytes, including SQLite, private objects,
  runtime manifest and the 32-byte share secret. Database integrity, foreign
  keys, object references, byte sizes and SHA-256 hashes passed verification.
- Encrypted archive: `workspace-20260910.tar.age`, 8,706,312 bytes.
  SHA-256: `9748da2bf9d04f27b2583995e9058eff14a080acb6de9498c5b1cea5df3f2330`.
- Server environment, including the operator token, Google OAuth credentials and
  Modal credentials, was exported separately as `render-env-20260910.json.age`.
  No plaintext environment archive was written. Decryption and the bootstrap
  credential match were verified without printing secret values.
- Both encrypted files are in `/Users/royluo/Documents/Wayline Backups`, with
  private directory/file permissions. The age identity is stored separately at
  `/Users/royluo/.config/wayline/recovery-age.key` with mode `0600`.
  Both locations are on the same Mac; independent key escrow is still required.
- A fresh Docker volume was restored with the existing snapshot verifier. The
  app then ran as UID 10001 with a read-only root, 512 MiB, 0.5 CPU, no external
  network and no published port. Checks ran against its internal loopback.
- The restored app returned health 200, accepted the original operator credential,
  rejected anonymous workspace access, and opened original READY reconstruction
  `job_545c7816731848e59a720aa046ffe42c`.
- Its GLB was exactly 7,819,504 bytes with SHA-256
  `b55041c0b31f7978dbb780a1be62bfa2d0410c2e7050d52265274ac54707110f`.
  The restored share secret matched; a newly issued share returned the same GLB.
- Google signup and Modal execution were disabled in the isolated restore.
  Temporary plaintext directories, restore containers and volumes were removed.
- Normal Docker startup was restored. Deployment `dep-dahj0sek1f9s73fgcvu0`
  runs reviewed commit `8e1391012766d6eacb518cd51c6ba3a40fbe10f6` with health 200.
  The temporary script on the persistent disk was removed after comparing its hash.

The snapshot predates the owner's first Google signup. It is a consistent
point-in-time backup, not a claim that later account or scene changes are included.

## Tested maintenance procedure

Render's disk is available only to the live service at runtime, so neither a
pre-deploy command nor a one-off job can snapshot it. A disk-backed deployment
stops the old instance before the replacement mounts the disk. See
[Render disk constraints](https://render.com/docs/disks).

1. Register the operator Mac's existing public key in Render account settings.
   The key named **Wayline recovery · Roy Mac** was added without changing other
   keys or services. SSH keys are account-level. Verify the Ohio host fingerprint
   against [Render's published key](https://render.com/docs/ssh) before connecting.
   The Dockerfile creates the app user's SSH directory with mode `0700`.
2. Confirm there are no queued/running jobs and preserve the exact current service
   settings, reviewed commit, and Docker command in a private operation record.
3. Upload this temporary script privately to `/data/wayline-recovery-YYYYMMDD.py`
   and compare its SHA-256 before using it:

```python
import os
import tempfile
from pathlib import Path
from lingbot_map.workspace.backup import create_snapshot

os.umask(0o077)
snapshot = Path(tempfile.mkdtemp(prefix="wayline-recovery-")) / "snapshot"
create_snapshot(Path("/data/wayline"), snapshot)
Path("/tmp/wayline-recovery-location").write_text(str(snapshot))
print("Verified recovery snapshot ready", flush=True)
os.execv("/usr/local/bin/wayline", ["wayline", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "10000")])
```

4. Temporarily set Docker Command to
   `/usr/local/bin/python /data/wayline-recovery-YYYYMMDD.py` and deploy the reviewed
   commit. This performs the verified offline copy before starting Wayline. Check
   free space in `/tmp`; copying into the 5 GB app disk can exhaust it at higher
   utilization. Each start uses a fresh private temporary directory.
5. After the deployment is live, read the private snapshot-location marker over
   SSH, validate that it names the expected temporary directory, and stream its
   tar content through age encryption to a new local output file. Require both
   SSH and age to exit successfully. Export the service environment to a separate
   encrypted file through an in-memory pipe. Preserve the source commit and
   service ID with the encrypted recovery set.
6. Decrypt into a private temporary location, restore into a fresh destination
   using `python -m lingbot_map.workspace.backup restore`, and verify the app can
   authenticate, open a known job, download its exact artifact, and use the share
   secret. Disable external integrations and networking in the test instance.
7. Compare the service's current temporary command before restoring the saved
   command, avoiding overwriting another operator's concurrent change. Redeploy,
   verify health/persistence, then remove only the known temporary script and
   dispose of temporary test data. Never restore over the running production data.

The first attempt used nested shell quotes in Render's Docker Command; it exited
127 and Render restored the previous healthy deployment. The tested procedure
uses a script path instead. An initial local restore harness could not use a
published port on an internal Docker network; the successful drill ran all HTTP
checks inside a fully network-disabled container.

## Still required

- An unattended offsite destination, schedule, retention policy and failure alerts.
- Recovery-key escrow independent of both Render and this Mac.
- A measured recovery objective and an isolated replacement-Render-service drill.
- A fresh recovery set after material account, data or secret changes.

No additional paid service was provisioned for this manual export. Render disk
snapshots remain a supplementary mechanism, not proof of a consistent application
backup or an independently recoverable secret set.
