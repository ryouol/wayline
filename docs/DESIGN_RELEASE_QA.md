# Gallery + Instrument release — 2026-09-11

The local release candidate passes design and package verification in
[design-qa.md](../design-qa.md). Deployment confirmation will be recorded here
after CI and the existing Render service report the new release live.

Target: https://wayline-9ten.onrender.com, existing Wayline Production service
`srv-dahhn0u7bikc73e82h9g`, project `prj-dahh0r2fngtc739mh2hg`. No additional
provider service, autoscaling, GPU inference or account-capacity change is needed
for this frontend release. Other Render projects remain outside its scope.

## Verified local package

- 229 Python tests and ten Node suites, strict lint, formatting and mypy pass.
- Clean wheel SHA-256: `0e3dd6645868d335db2da4715bccd56f2bd164350ccd78b2cdba23380a35bea9`.
  It contains all 64 current static files, matching source bytes, plus notices;
  restored favicon sizes and responsive WebP variants are present.
- Local Docker image: `sha256:424a516abcb6f6e032ac1abbca941d3f24feb5981f983df600f9997c14d8d9ee`.
  Production smoke passed with a 204.6 MiB peak under 512 MiB / 0.5 CPU.
- Browser shared download matched the 12,210,576-byte precomputed TUM reference.
  Local upload/progress used an isolated fixture and made no Modal GPU call.

## Release boundaries

Original model/checkpoint, inference budget, account ceiling and durable storage
behavior are preserved. The landing reconstruction is public, attributed,
precomputed media; opening it does not start inference. The application remains a
restricted research preview. Unresolved launch requirements are listed in
[launch-readiness.md](launch-readiness.md) and [REVIEW.md](REVIEW.md).
