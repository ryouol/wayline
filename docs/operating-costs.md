# Wayline operating costs and future credits

Planning estimate, 2026-09-10. Prices are USD before tax. Runtime, success rate,
output size and traffic have not been measured on a real owned capture yet.
The examples below are assumptions, not a LingBot performance claim.

## Small invited beta

| Resource | Assumption | Monthly cost |
|---|---|---:|
| Render web service | 1 CPU / 2 GB, one instance | $25 |
| Render persistent disk | 20 GB at $0.25/GB | $5 |
| Render workspace | Hobby | $0 |
| Modal A100 80 GB | $0.000694 per GPU-second | Usage based |

Sources: [Render pricing](https://render.com/pricing),
[Modal pricing](https://modal.com/pricing).
The optional Render Pro workspace adds $25/month, separately from compute.
Modal Starter advertises $30/month of free compute credit; plan before credits.

| Illustrative GPU allocation per attempt | GPU cost per attempt | 100 attempts |
|---|---:|---:|
| 5 minutes | $0.2082 | $20.82 |
| 10 minutes | $0.4164 | $41.64 |

CPU, memory, cold starts, model loading, idle scale-down windows, failed attempts,
storage, transfers and backups are additional. A ten-minute function timeout
is not an exact ten-minute invoice ceiling. The current first-run configuration
admits 24 maximum-duration submissions per rolling 30 days, not 100; raise it
only after measuring the first captures and approving the operating allowance.

For a later 100-attempt/month beta, provisionally reserve $100–150/month under
the ten-minute allocation assumption. This is not a quote. Development labor,
legal work and domain registration are excluded. Actual runtime may require a
different GPU, timeout or allowance.

Render Hobby includes 5 GB outbound bandwidth. Sending videos to Modal and
serving scene downloads both consume it; inbound uploads do not. Monitor it
alongside compute: [Render bandwidth](https://render.com/docs/outbound-bandwidth).
The 20 GB disk cannot retain unlimited originals/results; respect logical storage
limits and verify retention. Backups need separate encrypted storage.

## Limits implemented now

- Visitors receive an isolated one-hour synthetic playground with a 5 MiB
  allowance, three retained jobs, no uploads, no GPU access and no shares.
- Google preview accounts receive one successful reconstruction. A second active
  reconstruction is rejected; up to three submitted attempts per rolling day
  allow recovery from failures. Deleting scenes does not reset usage.
- The Render Blueprint initially caps signup at 20 Google accounts and concurrent
  retained playgrounds at 100. Playground retirement releases capacity.
- Captures: 60 seconds on the Render configuration, 250 MiB upload ceiling,
  at most 120 sampled frames and 750,000 exported points.
- Modal: one GPU container, no automatic Modal retries, 600-second function
  timeout and a per-attempt submission expiry. The app has its own deadline and
  durable cancellation/cleanup records.
- `WAYLINE_GPU_SECONDS_BUDGET=14400` admits 24 submissions at 600 reserved
  invocation seconds each over a rolling 30-day window. Failed/cancelled runs
  retain this allowance reservation. It limits admissions, not every category
  on the provider invoice. Provider budgets/alerts remain to be configured.

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
