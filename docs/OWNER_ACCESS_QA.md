# Owner quota exemption — 2026-09-12

This report records source/local verification. Deployment, account activation and current provider settings have separate private receipts.

`WAYLINE_OWNER_EMAIL` identifies the sole exempt Google email. Ownership is granted only after the existing verified Google OAuth flow returns that exact normalized email with `email_verified=true`; user-supplied form fields and display names cannot grant it. Accounts stay linked by Google's immutable subject, preserving workspaces, sessions, scenes and usage.

The owner has no personal lifetime reconstruction, sampled-frame, storage-byte or inventory-count quota. Public Google accounts retain two successful lifetime reconstructions. Owner requests still obey project GPU admission, physical/global storage, in-flight I/O, request-rate, media-size/duration and execution-time safeguards. Owner status grants no access to another tenant's scenes.

Schema 7 adds the owner flag, defaulting existing accounts to non-owner, and a singleton hash of the configured owner email. Startup atomically revokes old exemptions when that setting changes or is removed; unchanged normalized configuration preserves the grant. Existing sessions immediately see the revised flag. The email setting is included in encrypted recovery configuration. Actual owner email and private snapshots stay out of source control.

The API adds `accountType=owner`, a null reconstruction allowance, and null personal quota ceilings for owners; real usage remains numeric. Other account responses retain numeric ceilings. The create dialog shows “Owner account · No video limit” and keeps video selection enabled when shared capacity is available.

273 Python tests passed locally in 62.63 seconds; eleven Node suites and scoped lint/type checks passed. Local tests cover verified/nonmatching/unverified email claims, promotion and demotion without usage reset, existing-session revocation on configuration changes, schema-6 migration, four successful owner jobs despite zero personal quotas, tenant isolation, global storage and pre-I/O reservation limits, owner upload/submission under exhausted GPU capacity, and owner upload controls. A loopback browser fixture displayed the owner message with two prior successes and enabled video selection; no GPU invocation was used for these checks.

Three simplify passes and four code-review subskills completed. Findings 152–153 were corrected; the existing aggregate PR-size finding 139 remains open.

## Operating allowance

The deployment is intended to raise the shared allocation from 4,200 to 9,600 seconds per rolling 30 days: sixteen bounded 600-second submissions, including all prior attempts. At Modal's September 12 A100 80 GB rate of $0.000694/second, this GPU component is $6.6624; the existing Render service/disk baseline is $8.25/month. CPU, memory, idle windows, storage, transfers, backups and tax are additional. This provides room within the approximately $20 target, not a guaranteed total invoice cap. No instance count, workspace plan or automatic retry increase is intended.

Sources: [Modal pricing](https://modal.com/pricing), [Render pricing](https://render.com/pricing). Provider deployment receipts establish the applied setting. Normal sign-in after deployment activates the matching existing account; do not grant ownership by guessing which stored Google subject belongs to an email.

Before migration, capture and verify an encrypted online SQLite snapshot. Rolling back to schema-6 code requires coordinated restoration or a forward correction; code rollback alone is insufficient. Usage, prior GPU admissions and backup reservations must not be reset.
