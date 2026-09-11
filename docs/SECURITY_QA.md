# Credential-history verification — 2026-09-10

No credential matches were found by the two checks below at commit
`19f628a22ccc8f0928fa76d59e7e92031496f637`. This is scoped verification,
not a claim that the complete application or provider accounts are free of
security issues.

## Historical pattern scan

Gitleaks 8.30.1 scanned all locally available Git refs with full history and
inline suppression comments ignored. The checkout is not shallow and contains
156 reachable commits. Gitleaks processed 150 commit patches, approximately
4,505,802 bytes, and exited successfully with zero findings. No repository
Gitleaks configuration or ignore file was present.

```sh
gitleaks git --log-opts='--all --full-history' --ignore-gitleaks-allow \
  --redact=100 --no-banner --no-color --report-format=json \
  --report-path=.lingbot-workspace/cancellation-qa/gitleaks-history.json \
  --timeout=180 .
```

The report and terminal output were redacted. The scanner ran locally; source
files were not uploaded to a scanning service. See the
[Gitleaks documentation](https://github.com/gitleaks/gitleaks) for scan behavior.

## Exact comparison with current secrets

A separate local check compared the current Render environment's operator
bootstrap token, Google OAuth client secret, Modal token ID and Modal token
secret, plus the local Render CLI credential, against every reachable Git blob.
It inspected 2,518 unique file versions totaling 418,664,632 bytes, including
binary blobs. All five values were absent.

Credentials were read into process memory and never printed, written into the
report, or submitted to another service. The receipt records category names,
object counts and match counts only. This complements the pattern scan for
live credentials whose formats a detector might not recognize.

## Boundaries and remaining work

- This covers refs present in this checkout, not deleted/unreachable Git objects,
  external forks, other repositories, local ignored files or provider log stores.
- Exact comparison covers the five current values, not previously rotated
  credentials or every runtime session/share/recovery secret.
- A detector can miss unfamiliar formats; zero findings is not a proof of the
  absence of all historical secrets.
- Provider credential scope remains a separate open issue. The live Modal token
  can access the recovery workspace; a new workspace name has not established
  credential isolation. See [operating costs and provider controls](operating-costs.md).
- Upstream OAuth-query/header log redaction still needs provider verification.
  Render documents HTTP request logs for Pro workspaces and above; the absence
  of such logs in a Hobby dashboard does not certify all upstream handling.
  See [Render logging](https://render.com/docs/logging).

The complete endpoint inventory, implemented controls and remaining release
gates are in [the production checklist](PRODUCTION_UX_AUDIT.md) and
[launch readiness](launch-readiness.md). No production security setting was
weakened or credential rotated as part of these checks.
