# Source-notice packaging — 2026-09-11

The source inventory identified four absent upstream texts: the VGGT agreement
and included acceptable-use policy, DROID-SLAM's BSD-3-Clause license,
PyTorch3D's BSD license, and MoGe's complete license file (Microsoft MIT notice
plus its included Apache text). The files are copied verbatim from pinned
comparison revisions; those revisions do not establish the exact historical
commits originally imported into LingBot-Map.

`THIRD_PARTY_NOTICES.md` maps the identified source portions, their modification
scope and remaining fragment-level questions. DROID-SLAM and Diffusers/Wan
attributions are added beside the affected source. Existing headers remain.
The top-level Apache license is unchanged. The wheel metadata now points to
`LicenseRef-Wayline-Bundled-Source`, explained by the notice inventory, rather
than representing the whole bundled source as Apache alone.

Docker, Modal and wheel packaging include the four texts; Docker/wheel also
include `MODEL_PROVENANCE.md`. The existing wheel check now verifies exact
notice bytes at the installed license paths, rather than accepting any file
with a matching basename.

## Verification

- All four files match the SHA-256 of their pinned upstream originals.
- The local wheel and source archive contain all eight current project and
  third-party notice files with exact bytes. Wheel metadata contains the custom
  license expression. Private QA folders and the account artifact are absent.
- Global/strict scoped Ruff and format checks pass. The two existing checks for
  a Modal-free web import and private/bounded Modal deployment pass.
- Executable model ASTs and non-license project metadata are unchanged. There
  is no new request/startup work, dependency, checkpoint, admission or API change.
- All three simplify passes and all four code-review subskill passes completed.
  Reuse, quality, efficiency, breaking and testing reviews reported no new
  actionable finding; the model-context skill is not applicable.

The coherent source increment is 485 changed lines across 11 files, including
398 lines of verbatim license text. Aggregate PR-size concerns remain open:
the change-size reviewer measured 33,838 changed text lines across 179 text
files plus 48 binary files with this increment. This small commit does not make
the aggregate draft PR small. Main and dependency PRs remain unmerged.

Private build/hash receipts are under `.lingbot-workspace/source-notice-qa/`.
The first local sdist inspection matched both root and icon `LICENSE.txt` by
basename; the corrected check uses exact paths relative to the archive root.
The resulting wheel/sdist byte verification passes.

This closes identified packaging omissions. It does not certify a complete
inherited-source inventory, resolve the DiT/NAVER/CodeLlama fragment questions,
establish checkpoint/training-data hosted-use rights or authorize a public
launch. See `THIRD_PARTY_NOTICES.md` and `MODEL_PROVENANCE.md` for the remaining
questions.

## Deployment receipt

Exact-source [CI 34639918566](https://github.com/ryouol/lingbot-map/actions/runs/34639918566)
passed for `5e1d370`: 255 Python tests in 35.73 seconds, all eleven Node suites,
strict lint/type/format, wheel verification and production-container smoke.
The 512 MiB / 0.5 CPU smoke peaked at 202.3 MiB.

Render deployment `dep-dai5iv142hec73db6o9g` became live at
`2026-09-11T19:42:38.572760Z`. Read-only checks verified all eight notice files
both beside the source and inside the installed wheel, the composite metadata,
all 64 static assets, eight backend modules, all 14 stored artifacts and health
200. Seven READY jobs, one Google identity, five GPU admissions, zero active
jobs/uncleaned remote runs, configured limits and the recovery ledger were
preserved. Analytics remains disabled.

Modal deployed the same source commit and its seven model/project notice files
without inference or checkpoint preparation. The image build/import checks
passed; backlog, running inputs and runners were zero before and after. No
provider plan, secret, limit, extra backup admission or unrelated project changed.
