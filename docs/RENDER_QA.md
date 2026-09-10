# Live Render verification — 2026-09-10

Wayline is deployed at <https://wayline-9ten.onrender.com>. Public visitors can
create isolated synthetic playgrounds. Operator-authenticated reconstruction
uses the private original-model Modal worker. Google signup remains disabled.
This is a deployed research preview, not completed public-launch acceptance.

## Deployment

- Project **Wayline**, environment **Production**, service `srv-dahhn0u7bikc73e82h9g`.
- Starter, one instance, Ohio, 5 GB persistent disk; automatic deployments,
  previews and autoscaling are off. Fixed hosting is $8.25/month before tax/usage.
- Application commit `d3a6989899bd5e369df62db4e1fb83e73d1bbf74`;
  deploy `dep-dahifeqfngtc739s0pog` reached live at 21:58 UTC.
- [CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34534857893).
  The preceding disk-fix commit also passed
  [CI](https://github.com/ryouol/lingbot-map/actions/runs/34533934729).
- Private data is `/data/wayline`, below Render's root-owned `/data` mount.
  The initial `/data` configuration failed before database initialization.
- Modal app `wayline-reconstruction`, workspace `royluo05`, image
  `im-xGuD7TTyLnOQbqQwNYIuT5`; project/environment tags identify Wayline production.
  No public inference HTTP endpoint exists.

## Verified on the deployed service

- HTTPS and canonical `/healthz` return 200; anonymous `/api/me` returns 401;
  production OpenAPI is unavailable. Public configuration advertises the 64 MiB
  upload and 60-second video limits and disabled Google signup.
- Two sequential operator samples and two sequential browser visitor samples
  reached READY. The browser rendered 5,908 points after canvas teardown/recreation.
- A generated MP4 uploaded through the live API and reconstructed through Modal.
  Private download and an independent capability-authorized share returned
  byte-identical GLB content.
- Reconstruction state and the exact GLB hash survived the subsequent deployment.
- A five-minute share expired naturally: the API rejected content with 404, and
  the already-open browser cleared its viewer and displayed expiry. A separate
  share was explicitly revoked and later reads returned 404.
- Independent visitor sessions could not read each other's jobs. Session cookies
  were Secure, HttpOnly and SameSite=Strict. Missing CSRF was rejected, as were
  cross-origin trial creation/logout and visitor uploads. Normal logout passed.
  An initial QA assertion incorrectly expected rejection of an ordinary mutation
  carrying a valid CSRF token solely for its Origin header; the corrected check
  follows the application's CSRF and explicit entry/logout origin contracts.
- Browser camera replay reached frame 4 at 2.5 seconds. Walking controls and
  whole-scene reset worked. The generated source thumbnails were visible.
- The visitor copy fix hides the unavailable upload form and accurately labels
  the synthetic playground. Local phone-width verification measured a 390px
  document in a 390px viewport. Live reconstruction QA used a desktop viewport;
  this is not physical mobile evidence.
- Live environment settings confirmed the 3,600-second GPU admission allowance,
  2 GB scene-delivery allowance, 3.5 GB storage limit, one attempt per job,
  secure cookies and upload/artifact ceilings. Known production credentials
  were absent from sampled application logs, public scripts, HTML and config.
  This does not certify all upstream proxy logging or abuse limits.

## Original-model diagnostic

Input: `tests/fixtures/vfr-test-pattern.mp4`, an owned generated 64×48 diagnostic.
It contains no user footage. The request selected 2 FPS and a 30-frame ceiling.

| Measurement | Observed |
|---|---:|
| Queue submission to READY | 41.28 seconds |
| Time inside runner, loading/export included | 27.54 seconds |
| Inference only | 2.48 seconds |
| Source frames exported | 4 |
| Last presentation timestamp | 2.5 seconds |
| Points | 487,336 |
| Peak allocated VRAM | 4,937,646,592 bytes |
| GLB bytes | 7,819,504 |

GLB SHA-256: `b55041c0b31f7978dbb780a1be62bfa2d0410c2e7050d52265274ac54707110f`.
The manifest retained checkpoint SHA-256
`ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72`.
After completion, Modal reported zero backlog, running inputs and containers;
the Wayline capture volume listing contained zero entries. Timings are not billed
duration and do not establish quality or performance on an owned room capture.

## Remaining gates

Google OAuth provisioning was attempted in the personal console, but no accessible
Wayline project was verified; the console reported missing project/OAuth access.
No client credentials were created, and signup remains disabled. The corporate
Google CLI account and unrelated projects were not modified.

Modal's shared Starter workspace showed a $200 usage limit, no custom spend
limit, and $29.77 credits at inspection. Those are account-wide observations,
not Wayline's cost. They were not changed because another project also uses the
workspace. The Render integration uses a private personal-workspace API token;
it is not scoped to one app. Service-user/RBAC options require a paid plan.
Separate project credentials/budgets remain a hardening item before public signup.

An owned real capture, Google signup/account switching, physical mobile QA,
running-inference cancellation/failure cleanup, deployed offsite backup/restore,
upstream logging/edge limits, hosted-use rights and approved operator legal/contact
details remain open. See [launch readiness](launch-readiness.md),
[operating costs](operating-costs.md) and the [UX checklist](PRODUCTION_UX_AUDIT.md).
