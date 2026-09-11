# Live Render verification — 2026-09-10

Wayline is deployed at <https://wayline-9ten.onrender.com>. Public visitors can
create isolated synthetic playgrounds. Operator-authenticated reconstruction
uses the private original-model Modal worker. Google signup, returning login and
logout are verified for the owner; the initial account ceiling is one.
This is a deployed research preview, not completed public-launch acceptance.

A later [capacity pass](CAPACITY_QA.md) also verified live upload and deletion
of generated 4096×4096 media, including a 64 MiB padded file. No GPU was invoked.

## Deployment

- Project **Wayline**, environment **Production**, service `srv-dahhn0u7bikc73e82h9g`.
- Starter, one instance, Ohio, 5 GB persistent disk; automatic deployments,
  previews and autoscaling are off. Fixed hosting is $8.25/month before tax/usage.
- Current application commit `351f339f9847530fae5955d2e9ce2ce68753624e`;
  deploy `dep-dahk166k1f9s73fk7bq0` is live with normal Docker startup.
  The SSH directory is owned by UID 10001 with mode `0700`.
- [Current CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34543233887),
  including 170 Python tests and the production container smoke.
  The initial application deployment also
  [passed CI](https://github.com/ryouol/lingbot-map/actions/runs/34534857893).
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
  upload and 60-second video limits. Google sign-in is now enabled.
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

## Google identity verification

The dedicated personal Google project `wayline-roy-20260910` (Wayline Auth) and
Web OAuth client are configured with exactly
`https://wayline-9ten.onrender.com/auth/google/callback`. The earlier generic
project attempt was not verified; the unique project was created successfully.
The corporate Google CLI account and unrelated projects were not modified.
Only `openid email profile` scopes are requested. Client credentials are private
Render environment settings and are included in the encrypted recovery export.
Google's brand remains in Testing; public brand/policy verification is unfinished.

The owner completed real Google consent, entered a new private workspace,
generated a 5,908-point sample, logged out with viewer cleanup, and returned via
Google to the same saved scene. The database contains one Google identity with
120 available units and zero reserved/consumed units; the free video remains
unused. `WAYLINE_SIGNUP_MAX_ACCOUNTS=1` limits this first acceptance stage.
This is a total-account ceiling, not an email allowlist. Google's basic-identity
[scope exception](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
means Testing alone is not a reliable application access gate.
Second-Google-account switching and the owner's actual video are still untested.

## Recovery verification

An offline snapshot of the live Render workspace was exported encrypted and
restored into an isolated Linux container. All 18 files verified; the original
READY job, exact 7,819,504-byte GLB, share secret, authentication and new share
access passed. Normal service startup was restored and the temporary server
script removed. See [the procedure and limits](RECOVERY_QA.md).

## Remaining gates

Modal's shared Starter workspace showed a $200 usage limit, no custom spend
limit, and $29.77 credits at inspection. Those are account-wide observations,
not Wayline's cost. They were not changed because another project also uses the
workspace. The Render integration uses a private personal-workspace API token;
it is not scoped to one app. Service-user/RBAC options require a paid plan.
Separate project credentials/budgets remain a hardening item before public signup.

An owned real capture, second-Google-account switching, physical mobile QA,
running-inference cancellation/failure cleanup, automated backup/retention and
an isolated Render recovery drill,
upstream logging/edge limits, hosted-use rights and approved operator legal/contact
details remain open. See [launch readiness](launch-readiness.md),
[operating costs](operating-costs.md) and the [UX checklist](PRODUCTION_UX_AUDIT.md).
