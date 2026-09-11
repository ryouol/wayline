# Wayline production and UX checklist

Updated 2026-09-10 against the attached six-phase brief. Stack: Python/FastAPI, plain JavaScript and CSS, SQLite/private files, Render for the app and Modal for original LingBot GPU jobs. No React, Svelte, Supabase or Firebase.

✅ implemented with local evidence; ⚠️ needs input or verification; ➖ N/A with rationale. A phase containing ⚠️ is not release-complete. Paths below are relative to the repository root. Final executable check counts are recorded in `REVIEW.md`.

## Phase 1 — Security

| Item | Status / evidence |
|---|---|
| Exposed keys | ✅ Working-tree high-confidence credential scan found no embedded live key; no key needed moving. Bootstrap, Google client secret and Modal credentials are server environment values. Runtime bearer/session/share secrets are private; tests use fake credentials. ⚠️ Provider secrets and complete Git history have not been independently audited. |
| Every endpoint authenticated/validated | ✅ Inventory below; intentionally public shells/config/auth entrypoints expose no private tenant data. Private operations use server-derived ownership and cookie CSRF. Tests cover anonymous access, cross-tenant isolation and malformed input. |
| RLS | ➖ SQLite is accessible only to the server; no network/browser DB access or RLS switch exists. Tenant checks and transactions are tested. A future Postgres migration needs its own roles/RLS tests. |
| Broken/bypassed auth | ✅ No unconditional auth bypass introduced. Trial and Google sessions are isolated identities. Research acknowledgement and provider enablement remain deliberate gates. |
| Public storage | ✅ Local objects are private, with normalized keys and 0600 files under 0700 directories. Shares are scoped/expiring/revocable. ⚠️ Modal private resources are provisioned and remote deletion is verified; account-role/token-scope review and Render edge/storage settings remain pending. |

Credentials: `LINGBOT_BOOTSTRAP_TOKEN`, `WAYLINE_GOOGLE_CLIENT_ID`, `WAYLINE_GOOGLE_CLIENT_SECRET`, `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` are loaded server-side, supplied through Render secrets/environment. OAuth state, nonce, PKCE verifier and server sessions are temporary server records. Client ID is not a secret. Share capabilities travel in URL fragments and request authorization headers, not request paths/query strings. No credential value is committed or printed in this report.

Endpoint inventory (`P` = authenticated principal plus tenant ownership; `C` = CSRF for cookie-authenticated writes):

| Method and route | Protection |
|---|---|
| GET `/healthz` | Public minimal readiness; database/storage/workers probed without disclosing paths. |
| GET `/api/config` | Public allowlisted feature availability only. |
| POST `/api/trial` | Public session creation; origin/fetch-metadata checks, rate/capacity bounds, isolated one-hour identity, no uploads/GPU/shares. |
| GET `/auth/google/start` | OAuth initiation, feature gate, bounded attempts, browser-bound state, nonce and PKCE. |
| GET `/auth/google/callback` | One-use browser state, bounded code exchange, signed issuer/audience/nonce verification, bounded signup. |
| POST `/api/session` | Valid operator API token, strict normalized input, rate limiting; HttpOnly session. |
| GET `/api/me` | P; current account and quota only. |
| DELETE `/api/session` | P; same-origin browser logout, current session only. Intentional stale-CSRF recovery retained. |
| GET `/api/engines` | P; safe capability descriptors, guest GPU disabled. |
| GET `/api/assets` | P; bounded pagination. |
| POST `/api/assets` | P+C; guest rejection, upload/container/duration/dimension/byte validation, quota/idempotency. |
| DELETE `/api/assets/{asset_id}` | P+C; typed ID, ownership, attachment/retention rules and durable deletion. |
| POST `/api/jobs/sample` | P+C; controlled synthetic engine, quota/rate/idempotency. |
| POST `/api/jobs/research` | P+C; owned asset, strict parameters plus engine validation, rights/availability gates, one-video account limits. |
| GET `/api/jobs` | P; bounded tenant pagination. |
| GET `/api/jobs/{job_id}` | P; typed owned job. |
| POST `/api/jobs/{job_id}/cancel` | P+C; owned state transition/idempotency. |
| DELETE `/api/jobs/{job_id}` | P+C; owned terminal-job deletion/outbox. |
| GET `/api/artifacts/{artifact_id}/content` | P; owned published artifact only. |
| GET `/api/artifacts/{artifact_id}/download` | P; same ownership, generated attachment filename. |
| POST `/api/artifacts/{artifact_id}/shares` | P+C; owned artifact, bounded TTL/quota/rate/idempotency. |
| GET `/api/shares` | P; bounded tenant pagination. |
| DELETE `/api/shares/{share_id}` | P+C; owned revocation/idempotency. |
| POST `/api/bulk-delete` | P+C; bounded typed IDs, per-resource ownership and transition checks. |
| GET `/api/public/share` | Capability in Authorization header; shape/hash/expiry/revocation validation, no account required. |
| GET `/api/public/share/content` | Same capability validation, only its selected artifact. |
| GET `/s` | Generic public share shell; private content loaded with capability. |
| GET `/`, `/privacy`, `/terms`, `/contact` | Public shells/disclosure scaffolds, no private records. |
| GET `/robots.txt`, `/sitemap.xml` | Disallow-all and empty sitemap, no private enumeration. |
| GET/HEAD `/static/{path}` | Packaged static directory only. |
| GET `/docs`, `/docs/oauth2-redirect`, `/openapi.json` | Development/test only; disabled in production. |

Changed: `lingbot_map/workspace/{app,config,database,identity,auth_routes,service,modal_engine,request_limits}.py`, tests, Docker/Render configuration. Declared and observed request bytes are bounded before parser consumption; tests cover chunked rejection and partial multipart spool cleanup. Retained: source licensing notices and established auth/storage transaction boundaries. Skipped: cloud permission changes without credentials, invented commercial rights, shared-owner public signup. Deployed concurrency/timeout controls, OAuth callback/query and authorization-header redaction still require verification.

## Phase 2 — Make it real

| Requested item | Status / implementation |
|---|---|
| Custom 404 and 500 | ✅ HTML recovery pages and safe JSON API errors, including induced-error tests. |
| Above-fold CTA | ✅ Playground entry and upload-first studio; operator login is secondary. Desktop/narrow viewport inspected; owner Google signup and returning login verified on Render. |
| Per-page title and description | ✅ Home/share/support/error metadata. |
| OG/Twitter tags and fallback | ✅ Generic 1200×630 Wayline image and privacy-safe tags. ⚠️ Final public origin required. |
| Full favicon set | ✅ Original W mark, ICO, 16/32 PNG, Apple, 192/512 icons and manifest; raster assets generated/inspected earlier. |
| robots.txt and generated sitemap | ✅ Deliberate non-indexable workspace; no private URLs enumerated. |
| Alt text | ✅ Source thumbnails have frame labels; canvas has accessible instructions; social alt supplied. |
| Analytics | ⚠️ Consent-aware adapter exists but measurement ID and audited collector are missing; collection disabled. |
| Privacy policy | ⚠️ Real route with explicit draft/TODO; approved operator policy missing. |
| Terms | ⚠️ Real route with explicit draft/TODO; approved terms missing. |
| Cookie banner | ✅ Essential-only/opt-in/withdraw controls, analytics fails closed. ⚠️ Legal adequacy requires operator review. |
| Thank-you page | ➖ OAuth/signup enters the studio; upload enters job progress. No lead/contact form warrants a separate page. Success/next-step states are present. |
| Real contact information | ⚠️ Support email, phone policy and legal address unknown; no fake links or business details. |

Changed: `pages.py`, `app.py`, `static/{index.html,share.html,site.js,site.webmanifest,icon.svg}`, raster assets, `ICON-LICENSE.txt`, `scripts/build_brand_assets.py`, page tests. Skipped: fabricated legal/contact/analytics data and tracking requests without consent/configuration.

## Phase 3 — Forms, states and dead ends

| Item | Status / implementation |
|---|---|
| Loading states | ✅ Busy state, upload/queue/progress/viewer feedback. API calls bounded; video upload receives a 15-minute total client window. GPU transfer/inference cancellation bounded. |
| Inline validation and errors | ✅ Native forms plus server validation; engine-specific unsupported options return 422. |
| Submission success/errors | ✅ Signup/login, uploads, jobs, cancellation/deletion, share/copy failures all communicate outcome. |
| Working buttons | ✅ API/Node tests cover key actions. Fresh browser QA covered repeat creation, replay, walking/reset, share/download/expiry and logout cleanup; see `BROWSER_QA.md`. Actual Modal diagnostic download/share/replay and due cleanup after restart passed (`MODAL_QA.md`). ✅ Live Render diagnostic and owner Google signup/returning-login/logout passed (`RENDER_QA.md`). ⚠️ Second-Google-account and owned-capture flows remain pending. |
| Internal/external/footer links | ✅ Local routes/static links checked; deliberate expired/revoked links show recovery. Google callback verified on the Render hostname. ⚠️ A custom domain, if selected, needs its own callback and metadata verification. |
| Clickable logo | ✅ Home link across product/support/shared pages. |
| Placeholder text/unused navigation | ✅ Fake product copy removed; explicit operator TODO disclosures retained. Research settings remain secondary. |
| Dynamic copyright | ✅ Current year rendered by shared site script. |

Changed: `static/{app.js,share.js,timeline.js,viewer.js,index.html,share.html,site.js}`, API validation and tests. Skipped: invented checkout/contact submission and claims of owned-capture or public-deployment acceptance. Private filenames/thumbnails are cleared on logout; stale requests and old timelines cannot repopulate a new account/scene.

## Phase 4 — Mobile and performance

| Item | Status / implementation |
|---|---|
| No horizontal overflow | ✅ Fresh private/shared 390px fixture views measured no document overflow, including walking controls and 120-frame timelines. |
| Mobile breakpoints | ✅ Responsive studio, fluid support pages, wrapped controls. ⚠️ Physical mobile verification pending. |
| Mobile hamburger/focus trap | ➖ No drawer/navigation menu is needed; footer links stay visible. Existing share dialog uses native dialog semantics. |
| Sticky mobile CTA | ✅ Jump to upload/create action for authenticated users. |
| Optimize images/srcset/lazy | ✅ Small local brand assets; embedded bounded JPEG source thumbnails lazily displayed. ➖ No responsive photo hero/gallery requires srcset. |
| Tap targets/readable fonts | ✅ CSS minimum 44px controls and readable mobile text; directional walking buttons measured 44px high in the browser. ⚠️ Full contrast/device checks pending. |

Changed: CSS, viewer/timeline/app scripts, markup and icon generation. Performance fixes remove an eager full confidence tensor and redundant checkpoint hash pass while retaining mandatory verified model loading. Sample work and local maintenance continue during a GPU wait. Skipped: new frontend frameworks, decorative media, unsupported physical-device claims.

## Phase 5 — UX laws applied

| Principle | Concrete change |
|---|---|
| ✅ Hick / Occam / Tesler | One primary upload path; operator access and advanced options secondary; server owns quotas and model configuration. |
| ✅ Fitts | Large primary action, nearby viewport controls, mobile create shortcut and touch walking controls. |
| ✅ Jakob / Similarity / Connectedness | Conventional Google entry, labeled file input, grouped playback/actions and native share dialog. |
| ✅ Proximity / Prägnanz | Source frame controls stay next to the scene; records keep their own actions. |
| ✅ Miller | Short public navigation, grouped processing states, paginated inventories. |
| ✅ Doherty | Immediate busy/progress feedback and unchanged-list caching; GPU latency is not advertised as sub-400ms. |
| ✅ Von Restorff | Lime primary action against quiet dark/neutral surroundings. |
| ✅ Serial Position | Upload first, latest scenes prominent, review/download/share at completion. |
| ✅ Peak-End / Zeigarnik | Visible processing stages, frame replay and explicit ready/download/share result. |
| ✅ Postel | Trim operator token whitespace; strict stored identities, bounds and canonical object keys. |
| ✅ Pareto | Focus on signup → upload → status → view/replay/walk → download/share. Collaboration/versioning deferred. |

Changed: Phase 3/4 UI files. These are design decisions, not usability-study results. ⚠️ Full real-user/provider flow remains an acceptance gate.

## Phase 6 — Visual polish

✅ Authorized direction: a dark olive/neutral studio with a lime accent, original W mark, spacious scene viewport and restrained controls. Rebrand is Wayline; upstream model/package/license identifiers remain LingBot for attribution.

➖ Magic UI: React-specific, this app is plain JavaScript. ➖ Threlte/R3F: neither Svelte nor React is present; extending the existing WebGL renderer avoids a framework migration. ➖ Vectary/Jitter: no exported asset supplied or needed; these are not code dependencies. ✅ Fresh synthetic desktop/narrow-view screenshots inspected; see `BROWSER_QA.md`. ⚠️ Real-capture and physical-device visual acceptance remain pending.

Changed: public copy, CSS, markup, brand assets, metadata/manifest, CLI product name/alias and documentation. Skipped: dependency/framework replacements without product benefit.

## TODOs requiring operator input

1. `lingbot_map/workspace/pages.py`: approved privacy policy, controller/subprocessors, actual retention, rights-request process and privacy contact.
2. Same file: approved terms, entity, jurisdiction, billing/refund/acceptable-use/liability rules.
3. Same file: support email/mailto, phone/tel or explicit no-phone-support policy, legal entity/address.
4. Same file and `static/site.js`: approved analytics measurement ID and an implemented/audited same-origin collector; update policy/consent before enabling.
5. Final custom domain, if desired. `LINGBOT_PUBLIC_BASE_URL` currently supplies the working Render HTTPS hostname for absolute metadata.
6. Remaining provider setup: scoped Modal credentials/budgets, owned acceptance capture, spend alerts, automatic offsite backups/retention and separate key escrow. Render hosting, the Google client/callback, and a manual encrypted export plus isolated Linux restore are verified (`RENDER_QA.md`, `RECOVERY_QA.md`).

See `launch-readiness.md` for remaining deployment, mobile, model-quality and rights gates. These unresolved items prevent claiming the full requested product is finished.
