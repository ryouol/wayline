# Wayline operating costs

Configuration snapshot: **2026-09-13 UTC**. Pricing inputs last checked September 12,
2026; USD before tax and overages. The operating target is approximately **$20/month**,
with modest flexibility. There is no verified hard project-level invoice cap.

| Component | Current setup / planning input |
|---|---|
| Render workspace | Hobby |
| Web service | One Starter instance: $7/month |
| Persistent disk | 5 GB at $0.25/GB: $1.25/month |
| Fixed hosting | **$8.25/month** before tax/overages |
| Modal GPU | A100 80 GB: $0.000694/GPU-second, before credits |
| Shared GPU admission | 9,600 seconds per rolling 30 days: sixteen 600-second allocations |

Sources: [Render pricing](https://render.com/pricing), [Modal pricing](https://modal.com/pricing).
At those inputs, 9,600 GPU-seconds represent **$6.6624 of GPU time**; adding fixed
hosting gives **$14.9124**. This excludes CPU, memory, startup/model loading,
scale-down idle time, storage, transfers, builds, backups and tax. It is a component
estimate, not a bill forecast or guarantee. Do not assume provider credits.

## Enforced application controls

- One GPU container, no automatic Modal retry, 600-second remote timeout.
- Fresh uploads/jobs check shared capacity, including pending holds and durable
  remote charges. Failed/cancelled remote attempts remain charged; deleting a scene
  does not restore compute capacity. Requeued remote work requires another slot.
- Public accounts: two successful lifetime reconstructions, one pending research
  job and three admitted attempts per rolling day. The verified owner has no
  personal processing/inventory quota; global safeguards remain in force.
- 60-second / 64 MiB captures, 120 sampled frames, 750,000 exported points,
  40 MiB maximum artifact; one upload parser and bounded in-flight object writes.
- 3.5 GB global logical storage on a 5 GB disk, with a 1 GiB physical free-space floor.
- 2 GB scene-delivery reservation allowance per rolling 30 days. Full files are
  charged even for aborted/range delivery; non-scene traffic is outside this ledger.
- Scheduled recovery: separate 10 GiB rolling upload reservation allowance,
  daily admission and seven retained verified sets.
- Manual Render deployments; no added instances or paid workspace upgrade.

These guards reduce exposure. They do not measure or cap every provider charge.
The repository Blueprint starts GPU admission at 3,600 seconds with signup and
Modal disabled; it is a conservative new-install template, not an export of the
live secrets/settings. The live 9,600-second budget is an explicit operator setting.

## Shared-account boundary

Other projects use the Render account and the `royluo05` Modal workspace. Do not
apply workspace-wide limits, disable billing or rotate shared credentials as a
Wayline-only change. Independent provider budget/credential isolation and alerting
remain open; see [launch readiness](launch-readiness.md).

Before raising admission, measure actual per-job GPU/CPU/memory runtime, model
loading, output bytes and egress. Plan storage retention and backup cost alongside
compute. A one-instance local-disk service does not support horizontal scaling or
zero-downtime deployment.

## Future billing

There is no checkout, paid credit balance or paid processing entitlement today.
The [historical credits plan](https://github.com/ryouol/wayline/blob/785bc7e10ccb1e3ff1974b0af26ddfb2a45426b1/docs/operating-costs.md) contains planning
assumptions only. Any monetization needs cleared hosted-use rights, verified costs,
payment webhooks/idempotency, refunds and revised product policies.
