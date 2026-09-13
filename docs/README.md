# Wayline documentation

Start with the [product README](../README.md) and [engineer review guide](REVIEWER_GUIDE.md).
Current guides below supersede dated rollout snapshots when account limits or
operational state conflict. Every live claim is a dated observation, not a monitor.

## Current guides

| Need | Read |
|---|---|
| Review the code | [Engineer review guide](REVIEWER_GUIDE.md), [findings](REVIEW.md) |
| Understand the design | [Architecture](architecture.md) |
| Assess launch blockers | [Launch readiness](launch-readiness.md) |
| Deploy and recover | [Deployment](deployment.md), [scheduled recovery](SCHEDULED_RECOVERY.md) |
| Understand cost controls | [Operating costs](operating-costs.md) |
| Understand model rights | [Provenance](../MODEL_PROVENANCE.md), [third-party notices](../THIRD_PARTY_NOTICES.md) |
| Inspect the product visually | [Screenshots and sources](screenshots/README.md) |

## Focused evidence

- Accounts and limits: [two-video policy](TWO_VIDEO_QA.md), [owner exception](OWNER_ACCESS_QA.md), [sign-out](SIGNOUT_QA.md).
- Product UI: [processing](PROCESSING_UI_QA.md), [theme](CURRENT_THEME_QA.md), [studio](STUDIO_THEME_QA.md), [mobile viewport](MOBILE_WALK_QA.md).
- Reconstruction: [real benchmark](REAL_CAPTURE_QA.md), [user capture quality](GOOGLE_CAPTURE_QA.md), [capacity](CAPACITY_QA.md), [GPU admission](GPU_CAPACITY_QA.md).
- Reliability: [request/cancellation checks](RELIABILITY_QA.md), [manual recovery](RECOVERY_QA.md), [scheduled recovery](SCHEDULED_RECOVERY_QA.md), [crash recovery](RECOVERY_CRASH_QA.md).
- Security and policy: [security review](security-review.md), [provider logs](PROVIDER_LOG_QA.md), [analytics](ANALYTICS_QA.md).

The remaining `*_QA.md` files and `ux-evidence/` are dated implementation evidence.
They intentionally retain the limits, failures and results seen at that time.
Do not use an old test count, account ceiling or deployment hash as the latest state.

## History and planning

- [Earlier launch record](https://github.com/ryouol/wayline/blob/785bc7e10ccb1e3ff1974b0af26ddfb2a45426b1/docs/launch-readiness.md)
- [Earlier cost/credits plan](https://github.com/ryouol/wayline/blob/785bc7e10ccb1e3ff1974b0af26ddfb2a45426b1/docs/operating-costs.md)
- [Product plan](WAYLINE_PLAN.md), [product decision](product-decision.md), [commercial clearance checklist](commercial-clearance.md)

Plans describe intended work; they are not evidence of implemented functionality.
