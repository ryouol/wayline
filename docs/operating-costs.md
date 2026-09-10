# Wayline operating costs and future credits

Planning estimate, 2026-09-10. Prices are USD before tax. Runtime, success rate,
output size and traffic have not been measured on a real owned capture yet.
The examples below are assumptions, not a LingBot performance claim.

## Small invited beta

| Resource | Assumption | Monthly cost |
|---|---|---:|
| Render web service | Starter, 0.5 CPU / 512 MB, one instance | $7 |
| Render persistent disk | 5 GB at $0.25/GB | $1.25 |
| Render workspace | Hobby | $0 |
| Modal A100 80 GB | $0.000694 per GPU-second | Usage based |

Sources: [Render pricing](https://render.com/pricing),
[Modal pricing](https://modal.com/pricing).
Fixed Render hosting is **$8.25/month before tax and usage overages**. Keep the
workspace on Hobby; no paid workspace upgrade is needed. Modal Starter advertises
$30/month of free compute credit; plan before credits.

The user accepted **$20/month as a target**, with some flexibility, on 2026-09-10.
The Starter service and 5 GB disk were created in Wayline / Production. Render bills outbound overages
when a payment method is attached and does not document a per-project hard total
spend cap. Its 5 GB allowance and pipeline allowance are shared with the account's
other projects. A build spend limit does not cap bandwidth or GPU charges.
Keep one instance, automatic deploys and previews off, and the limits below.
The target is not an enforced invoice cap.

Modal supports workspace usage budgets before credits and spend limits after
credits on its Usage & Billing page. The shared `royluo05` workspace showed a
$200 usage limit and no custom spend limit on 2026-09-10; these were not changed
because UNRENDER also uses the workspace. Wayline therefore relies on the
application allowances below, not a verified project-specific provider cap. Environment budgets require Team/Enterprise and cover
compute rather than the full invoice. Do not upgrade merely to obtain them or
silently impose workspace restrictions on unrelated apps. See
[Modal budgets](https://modal.com/docs/guide/budgets).

| Illustrative GPU allocation per attempt | GPU cost per attempt | 100 attempts |
|---|---:|---:|
| 5 minutes | $0.2082 | $20.82 |
| 10 minutes | $0.4164 | $41.64 |

CPU, memory, cold starts, model loading, idle scale-down windows, failed attempts,
storage, transfers and backups are additional. A ten-minute function timeout
is not an exact ten-minute invoice ceiling. The current first-run configuration
admits six maximum-duration submissions per rolling 30 days, not 100; raise it
only after measuring the first captures and approving the operating allowance.

Six 600-second allocations represent $2.4984 of A100 GPU time at the listed
rate, plus CPU, memory, model loading, scale-down windows, storage and transfers.
This is a calculation for one billing component, not a total cost ceiling.
Development labor, legal work, backups and domain registration are excluded.
Actual capture performance may require a different GPU, timeout or allowance.

Render Hobby includes 5 GB outbound bandwidth. Sending videos to Modal and
serving scene downloads both consume it; inbound uploads do not. Monitor it
alongside compute: [Render bandwidth](https://render.com/docs/outbound-bandwidth).
The 5 GB disk cannot retain unlimited originals/results; respect logical storage
limits and verify retention. Backups need separate encrypted storage.

## Limits implemented now

- Visitors receive an isolated one-hour synthetic playground with a 5 MiB
  allowance, three retained jobs, no uploads, no GPU access and no shares.
- Google preview accounts receive one successful reconstruction. A second active
  reconstruction is rejected; up to three submitted attempts per rolling day
  allow recovery from failures. Deleting scenes does not reset usage.
- The Render Blueprint initially caps signup at 20 Google accounts and concurrent
  retained playgrounds at 100. Playground retirement releases capacity.
- Captures: 60 seconds on the Render configuration, 64 MiB upload ceiling,
  at most 120 sampled frames and 750,000 exported points.
- Storage: 3.5 GB global logical limit, 256 MiB for the operator workspace,
  512 MiB per Google workspace, 5 MiB per playground, 40 MiB maximum artifact,
  two in-flight object writes globally and one per tenant. The physical free-space
  floor remains 1 GiB. One upload parser runs at a time with a 15-minute deadline;
  pre-parser admission allows two requests per tenant per minute.
- Scene delivery: reserve each entire file against a durable global 2 GB allowance
  before private view/download or public share delivery. Aborted/range transfers
  still charge the whole file; multi-range requests are rejected. Daily buckets
  remain for at least 31 days, across restarts, scene deletion and account changes.
  This omits HTML/JS/API/error responses, protocol overhead and Modal transfers:
  **it is not an invoice cap**. Manual deployment avoids automatic build charges.
- Modal: one GPU container, no automatic Modal retries, 600-second function
  timeout and a per-attempt submission expiry. The app has its own deadline and
  durable cancellation/cleanup records.
- `WAYLINE_GPU_SECONDS_BUDGET=3600` admits six submissions at 600 reserved
  invocation seconds each over a rolling 30-day window. Failed/cancelled runs
  retain this allowance reservation. It limits admissions, not every category
  on the provider invoice. Provider budgets/alerts remain to be configured.

## First diagnostic measurement

The original model completed one generated-video diagnostic on Modal: six sampled
64x48 source frames, 114.65 seconds queued-to-ready, 78.32 seconds inside the
runner, 5.65 seconds in model inference, and 5,994,845,696 bytes peak allocated
VRAM. These are different timing scopes, not billable-time measurements. The
11,728,872-byte output rendered in the browser. This tiny artificial input cannot
set pricing or GPU sizing for real captures; see [Modal QA](MODAL_QA.md).

A later live Render-to-Modal diagnostic reached READY in 41.28 seconds with four
frames and a 7.82 MB scene, then scaled to zero workers. This used the same tiny
generated source, not a room capture. See [live QA](RENDER_QA.md).

## Measure before pricing

Use several owned captures and retain source metadata, sampled frames,
checkpoint revision/hash, inference and total seconds, peak VRAM, output bytes,
success/failure reason and browser frame rate. Include cold and warm starts.
Calculate cost per *successful* scene across all attempts, including failures;
record median and slow-tail latency instead of quoting one best-case run.

## Proposed paid-credit design — not implemented

Call them **reconstruction credits**, not language-model tokens. A customer buys
an understandable bounded capture, such as one clip up to a stated duration and
quality setting. Quote the credit amount before submission. Viewing, replay and
downloading an existing scene should not consume reconstruction credits.

Keep financial credits separate from the existing sampled-frame capacity ledger:

1. Payment provider webhooks create immutable credit grants, verified and
   idempotent by provider event ID.
2. Job submission atomically reserves the quoted credits alongside its durable
   job/idempotency record. Concurrent submissions cannot spend the same balance.
3. Successful scene publication consumes the reservation exactly once. Failure
   or cancellation releases customer credits; provider costs still count toward
   operator spend controls.
4. Administrative adjustments and refunds are append-only compensating entries.
   Deleting an artifact never deletes a financial transaction or replenishes a
   spent credit.
5. Test duplicate/out-of-order webhooks, chargebacks, ambiguous retries, price
   changes after quoting and cancellation races before enabling checkout.

Set a selling price only after measured cost, support/storage overhead, failure
rate and target margin are known. No price or commercial entitlement is promised
by the current UI. Model-use clearance and approved billing/refund terms remain
prerequisites for selling inference.
