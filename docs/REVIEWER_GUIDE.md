# Wayline — engineer review guide

This is the entry point for reviewing the application, rather than the inherited
research repository. Read [current launch readiness](launch-readiness.md) before
interpreting historical QA reports as current production facts.

## Source and release boundary

- Repository: [ryouol/wayline](https://github.com/ryouol/wayline), private.
- Default/application branch: `codex/production-ready-lingbot-map`.
- Review: [PR #10 against main](https://github.com/ryouol/wayline/pull/10), draft.
- Production URL: [wayline-9ten.onrender.com](https://wayline-9ten.onrender.com/).
- Verified web runtime: `785bc7e`, live September 13, 2026 at 00:00:01 UTC.
- Modal runtime: `5ff66bb`; later owner/progress changes affect the web app only.
- This repository handoff changes documentation, links and repository metadata.
  It does not migrate Python imports, database schema, environment keys or model weights.

`main` does not yet contain the product branch. Do not infer deployed behavior
from `main`. The existing PR is too large for one approval; finding
139 in [REVIEW.md](REVIEW.md) remains open. Eight dependency PRs are also open;
none was merged during this handoff.

## Suggested review order

1. **Run the local sample.** Follow the root README. Verify sign-in, scene creation,
   orbit, download and logout before configuring a paid runner.
2. **Trace one request.** Follow `app.py` → `WorkspaceService` → `Database` and
   `ObjectStore`. Tenant scoping, CSRF and request idempotency belong at this boundary.
3. **Trace one job.** Inspect queue claims, leases, attempt tokens, cancellation,
   publication and settlement in `service.py`/`database.py`. A stale worker must
   never publish or settle a newer attempt's work.
4. **Inspect the GPU boundary.** Read `modal_engine.py`, `modal_app.py`, capture/export
   code and `MODEL_PROVENANCE.md`. Verify checkpoints, private staging, timeouts,
   conservative admission charges and cleanup after uncertain failures.
5. **Inspect viewer assumptions.** Read `viewer.js`, `timeline.js` and export tests.
   The viewer needs colored points, baked transforms and the supported camera trace.
6. **Review operating behavior.** Check secret handling, one-instance constraints,
   bounded uploads/downloads, backups, restore and provider isolation in the runbooks.
7. **Separate test coverage from acceptance.** Read CI and focused QA documents;
   real capture quality, physical mobile and provider restore remain separate gates.

## Invariants worth challenging

| Boundary | Required property |
|---|---|
| Identity | Verified immutable Google subject; owner exemption only for configured verified email |
| Isolation | Every tenant resource access scoped; owner quota exemption grants no cross-tenant access |
| Admission | Global capacity checked before costly upload/dispatch; no budget reset on deletion |
| Publication | Artifacts remain private until fenced READY settlement |
| Cancellation | Durable request wins over concurrent completion; remote cleanup remains owed |
| Sharing | Expiry/revocation on every fetch; capability in fragment/header, not URL query/path |
| Recovery | Coordinated database, objects and secrets; checked hashes and actual restore evidence |
| UI | Server-backed progress, safe session switching, disposed WebGL contexts never reused |

## Validation and review disposition

The deployed web commit passed 273 Python tests, eleven Node suites, strict lint,
format/type checks, packaging and a 512 MiB / 0.5 CPU container smoke (201.1 MiB
peak). See [exact CI run](https://github.com/ryouol/wayline/actions/runs/34726685228).
The processing release matched 64 static files, eleven backend modules, license
notices and saved artifact hashes while preserving accounts and all limits.

Simplify/code-review findings are recorded in [REVIEW.md](REVIEW.md). Fixed findings
are not outstanding blockers. Do not approve the aggregate solely because CI is green.
Split independent upstream fixes first; keep coupled identity/schema/API, job/recovery,
export/viewer and deployment contracts together when preparing smaller landing PRs.
No new feature work or dependency upgrades are included in this handoff.

## What is intentionally absent

No payments, scene versions, anchored comments, collaborative editing, mesh
renderer, metric reconstruction guarantee or multi-instance deployment. The
public policy/contact pages still need approved operator details. The original
research demos remain available for model work; they are not the product server.

Use [documentation index](README.md) to find current guides and dated evidence.
No private captures, production database, tokens or raw provider logs are included
in the new screenshots or this review package.
