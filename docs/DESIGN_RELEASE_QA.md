# Gallery + Instrument release — 2026-09-11

The approved redesign is live at [Wayline](https://wayline-9ten.onrender.com/).
Runtime commit: `9516dbfe7e3b672ad13a9b5288c26bf589484fb8`.
[Hosted CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34623265006).
Render deployment `dep-dai2v86743jc73dqucdg` finished with status `live` at
2026-09-11 16:43:56 UTC. A later documentation-only commit records this receipt;
it does not change the verified runtime. Local design and package evidence is in
[design-qa.md](../design-qa.md).

Target: https://wayline-9ten.onrender.com, existing Wayline Production service
`srv-dahhn0u7bikc73e82h9g`, project `prj-dahh0r2fngtc739mh2hg`. No additional
provider service, autoscaling, GPU inference or account-capacity change is needed
for this frontend release. The existing footprint remains one Starter instance
with a 5 GB disk at `/data`, no autoscaling and automatic deploys disabled.
Other Render projects were untouched. Application allowances reduce exposure;
they do not guarantee a provider invoice cap.

## Verified live release

- HTTPS `/healthz` returned 200 with `status: ok`; public configuration reported
  Google sign-in enabled and a signup slot available.
- Public HTML has the new signup-first landing, responsive imagery and no
  Explore sample CTA. Ten critical assets matched over HTTP; all 64 deployed
  static files matched the reviewed source by SHA-256 over SSH.
- The live 390 × 844 landing and Get started → signup flow were inspected.
  Google returning login completed through the existing account chooser and
  returned to the saved workspace. The existing 5,908-point synthetic scene
  rendered; library navigation and reopening it also passed.
- The creation dialog showed the configured 60-second / 64 MiB capture limits
  and one available video. No video was submitted and no GPU job was invoked.
- The read-only deployment comparison retained six READY jobs, one Google
  identity, four remote runs and zero remote runs awaiting cleanup.
- The final browser was signed out and left on the public light landing.
  Public screenshots: [desktop](ux-evidence/2026-09-11/live-landing-desktop.jpg),
  [mobile landing](ux-evidence/2026-09-11/live-landing-mobile.jpg),
  [mobile signup](ux-evidence/2026-09-11/live-signup-mobile.jpg).

The browser checks use the desktop in-app browser, including viewport resizing;
they do not establish physical-phone or second-account acceptance. This release
did not repeat original-model inference: the previous licensed benchmark and
the local precomputed UI fixture retain their separately documented scopes.

The pre-deployment read-only recovery check still showed two failed automatic
attempts and no completed automatic set. The next normal daily admission is
2026-09-12 02:24:37 UTC (September 11, 22:24:37 Toronto). The gate was preserved;
no additional retry was requested during this release. Existing verified manual
encrypted recovery evidence remains valid for its stated snapshot.

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
