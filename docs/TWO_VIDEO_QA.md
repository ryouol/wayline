# Unlimited signup and two-video allowance — 2026-09-12

This report records source/local verification. The ignored deployment receipt and live-verification JSON separately establish the exact production commit.

Google signup has no total account cap when `WAYLINE_SIGNUP_MAX_ACCOUNTS=0`. Each Google workspace receives two successful lifetime research reconstructions. Failed or cancelled jobs do not consume a success; three submitted attempts per rolling day and one active reconstruction per account remain enforced. Existing shared GPU, storage, delivery and backup budgets are unchanged. Unlimited signup does not promise unlimited concurrent processing or protection against a person creating multiple Google accounts.

Schema 6 stores a durable success counter on each tenant. The previous one-success Google policy lets migration infer zero or one prior success from persistent consumed units even after scene and usage-ledger deletion. Existing Google frame quotas rise to at least 240, enough for two 120-frame jobs. Consumed/reserved units and sessions remain intact. Successful completion increments once in the same guarded transaction as job settlement. New Google accounts use `WAYLINE_SIGNUP_QUOTA_UNITS=240`.

## Verification

- 258 Python tests passed in 25.88 seconds after the index change. Coverage includes repeat login, uncapped signup, two successes, refusal of a third, failed/cancelled work, duplicate completion, deletion, retention, existing sessions and schema-5 migration with zero or one prior success.
- All eleven Node suites pass. The capture suite covers remaining counts 2, 1 and 0 and disables exhausted uploads.
- Ruff and the CI-scoped type check (`workspace` and `checkpoints`, 21 files) pass. An exploratory type check of the entire model tree reports 69 existing errors in unrelated research-model modules; that broader tree is outside the configured CI type-check scope.
- An isolated loopback browser fixture displayed “2 of 2 videos remaining,” “1 of 2 videos remaining,” and “Both videos used”; the last state disables video selection. A screenshot confirmed the two-video allowance fits the existing create dialog. Fixture identities and an available-engine descriptor were local only; no worker, GPU call, production test account or real Google acceptance test was used.
- Three simplify passes and four code-review subskills completed. Findings 149–150 were fixed; existing aggregate PR-size finding 139 remains open. No other actionable finding was reported.

## Rollout and rollback

Capture an encrypted online SQLite snapshot before the schema upgrade and verify its encryption roundtrip. Deploy the reviewed exact commit only after CI passes, updating only the two signup environment values to 0 and 240. Verify schema 6, existing Google counter/quota/consumption, source hashes, health, signup availability, stored artifacts and unchanged spending limits.

The predecessor rejects schema 6. Rolling back code alone is insufficient: a rollback needs either a reviewed forward correction or a coordinated schema-5 snapshot restoration with application/object/secret state and any post-snapshot writes accounted for. Never reset account usage or the provider admission/backup ledger to regain capacity.
