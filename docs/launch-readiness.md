# Wayline launch readiness

Snapshot: **2026-09-13 UTC**, web runtime `785bc7e`, Modal runtime `5ff66bb`.
This is a live research preview with unresolved launch gates, not a general-availability approval.
[Production URL](https://wayline-9ten.onrender.com/) · [Review guide](REVIEWER_GUIDE.md)

## Current deployed behavior

| Area | Verified state |
|---|---|
| Signup | Google sign-in enabled; no application-wide account-count ceiling; two identities observed |
| Public allowance | Two successful lifetime reconstructions; failures/cancellations do not consume a success |
| Owner | One verified owner exempt from personal processing/storage/inventory quotas; no cross-tenant privileges |
| Shared compute | 9,600 reserved GPU seconds / rolling 30 days, at most sixteen 600-second admissions; prior charges preserved |
| Captures | 60 seconds, 64 MiB, at most 120 sampled frames and 750,000 exported points |
| Hosting | One Render Starter instance, 5 GB disk; private Modal A100 runner with one container |
| UX | Light/dark/system appearance; stage progress; orbit/replay/walk; download and expiring shares; sign-out |
| Recovery | Scheduled ledger reports a completed archive; independent provider restore/retention acceptance remains open |
| Analytics / billing | Optional analytics disabled; no payment or paid-credit flow |
| Verification | 273 Python tests, eleven Node suites, exact-source CI and constrained production-container smoke passed |

The owner exemption does not bypass shared compute, storage, rate, media or
execution safeguards. Unlimited signup does not promise unlimited or immediate
processing. The application admission ledger is not a provider invoice cap.

## Evidence and limits

A licensed TUM real-camera benchmark passed reconstruction, desktop replay,
download and sharing. A later Google-account capture reached READY but failed
visual-quality acceptance as a convincing continuous space. A valid MOV starting
with a negative timestamp was subsequently fixed and retried successfully; file
integrity and completion do not establish visual quality.

Live release checks verified saved artifact hashes, schema 7, account usage and
configured limits across redeployment. A manual encrypted database/object/secret
export passed an isolated Linux restore. Scheduled backup completion is a ledger
observation; it does not close the independent provider restore requirement.
Desktop browser emulation at phone widths is not physical-mobile acceptance.

See [benchmark](REAL_CAPTURE_QA.md), [capture](GOOGLE_CAPTURE_QA.md),
[recovery](RECOVERY_QA.md), [processing](PROCESSING_UI_QA.md), and
[owner](OWNER_ACCESS_QA.md) evidence. Earlier snapshots are in [history](https://github.com/ryouol/wayline/blob/785bc7e10ccb1e3ff1974b0af26ddfb2a45426b1/docs/launch-readiness.md).

## Outstanding before broader launch

- Confirm source/checkpoint/training-data terms permit the intended hosted use;
  [MODEL_PROVENANCE.md](../MODEL_PROVENANCE.md) remains authoritative.
- Pass a short owned capture end-to-end with acceptable geometry and document
  cold/warm latency, costs, output sizes and failure rates.
- Verify the second real Google account's full isolated upload/returning-login flow.
- Test a physical mobile browser, touch controls, long uploads and large scenes;
  complete accessibility, edge/load and shutdown acceptance.
- Verify provider credential/budget isolation, external alerts and upstream log
  redaction, including OAuth callback queries and share capabilities.
- Independently restore a completed scheduled provider backup, verify retention,
  escrow the recovery key and run a replacement-Render/full-capacity drill.
- Supply approved operator identity, privacy/terms and contact information.
- Break the oversized draft PR into reviewable landing stages before approval.

Anchored comments, versions, collaboration, checkout, arbitrary meshes and
horizontal scaling are future work. Do not advertise them as current features.
