# Wayline production and UX checklist

Updated 2026-09-11 against the attached six-phase brief. Stack: Python/FastAPI, plain JavaScript and CSS, SQLite/private files, Render for the app and Modal for original LingBot GPU jobs. No React, Svelte, Supabase or Firebase.

The current public journey is visual landing → Get started → Google signup →
create scene. There is no public Explore sample CTA. The approved Gallery +
Instrument direction uses a light default, dark/system choices, cobalt actions,
an original two-plane W mark, a precomputed TUM reconstruction and actual studio
captures. Full favicon exports, responsive WebP images, sticky mobile navigation
and 44px controls preserve the production brief within this direction.

This checklist describes the current implementation. [Design QA](../design-qa.md)
records the redesign's local browser evidence; [the release receipt](DESIGN_RELEASE_QA.md)
separately records packaging, CI and deployment status. Earlier security, OAuth,
GPU and browser reports remain evidence only for their stated revisions and
inputs. The redesign does not close the pending account, device, recovery or
legal gates. [Studio QA](STUDIO_THEME_QA.md) records the management control fixes; [dialog loading QA](DIALOG_LOADING_QA.md) records latest runtime `abd3f43`, pending-feedback fixes, optional collection disabled, and saved state/allowances preserved across deployment.

✅ implemented with local evidence; ⚠️ needs input or verification; ➖ N/A with rationale. A phase containing ⚠️ is not release-complete. Paths below are relative to the repository root. Final executable check counts are recorded in `REVIEW.md`.

## Phase 1 — Security

| Item | Status / evidence |
|---|---|
| Exposed keys | ✅ The recorded 2026-09-10 working-tree/history scans found no credential matches; exact comparison of five live values against 2,518 reachable blobs also found none. The 2026-09-11 redesign scan copied all 1,200 Git-visible files and returned zero findings across approximately 5.96 MB of eligible content. [Security QA](SECURITY_QA.md) separates current-source and historical scan scopes. Bootstrap, Google client secret and Modal credentials are server environment values. Runtime bearer/session/share secrets are private; tests use fake credentials. No exposed key required relocation in these scans. ⚠️ Provider credential scope, external/unreachable history and upstream logs require their own verification. |
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
| POST `/analytics/page-view` | Intentionally public aggregate ingestion; disabled by default. Strict same-origin/consent/privacy-signal checks, fixed event/page schema, 512-byte bodies, global rate and durable daily ceiling. No private reads or stored visitor identifiers. |
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

Changed: `lingbot_map/workspace/{app,config,database,identity,auth_routes,service,modal_engine,request_limits}.py`, tests, Docker/Render configuration. Declared and observed request bytes are bounded before parser consumption; tests cover chunked rejection and partial multipart spool cleanup. The redesign's additive job `displayName` uses an asset join constrained to the job's tenant; detail, pagination and cross-tenant tests cover it. Existing auth, quota and storage boundaries are retained. Skipped: invented commercial rights and shared-owner public signup. [Provider log QA](PROVIDER_LOG_QA.md) confirms Hobby/Starter and records a bounded empty-log probe; it does not establish upstream redaction. Provider scope, remaining deployed load/shutdown behavior, OAuth callback/query and authorization-header log redaction remain unverified. Phase 1 is not declared release-complete while these checks are open.

## Phase 2 — Make it real

| Requested item | Status / implementation |
|---|---|
| Custom 404 and 500 | ✅ HTML recovery pages and safe JSON API errors, including induced-error tests. |
| Above-fold CTA | ✅ Landing Get started opens the Google account step; returning Sign in is separate. The studio exposes New scene and an empty-workspace Choose a video action. Desktop and mobile layouts were inspected in [design QA](../design-qa.md); local operator access and synthetic creation remain secondary. |
| Per-page title and description | ✅ Home/share/support/error metadata. |
| OG/Twitter tags and fallback | ✅ Per-page privacy-safe tags use the actual 1440×700 studio JPEG as the default social image. `LINGBOT_PUBLIC_BASE_URL` supplies the existing Render HTTPS origin. A custom domain is optional and would require updating and verifying that configuration. |
| Full favicon set | ✅ The approved W mark is exported as `favicon.ico` with 16/32 sizes, `favicon-16.png`, `favicon-32.png`, 180px `apple-touch-icon.png`, and 192/512 PNG manifest icons. Metadata and manifest reference those files; `scripts/export_web_assets.sh` regenerates delivery assets from retained sources. |
| robots.txt and generated sitemap | ✅ Deliberate non-indexable workspace; no private URLs enumerated. |
| Alt text | ✅ Hero/account/studio imagery has descriptive alt text; source thumbnails have frame labels. Decorative brand/control images use empty alt text with visible or accessible control names. Interactive canvases expose instructions; decorative landing motion stays out of keyboard/screen-reader navigation. Social image alt is supplied. |
| Analytics | ✅ Optional first-party collector, bounded daily aggregates, automatic retention and read-only operator report are implemented and tested. Client/server consent and privacy-signal checks remain enforced. ⚠️ Approved policy and operator property label are still needed for activation; production collection stays disabled. See [analytics](ANALYTICS.md). |
| Privacy policy | ⚠️ Real route with explicit draft/TODO; approved operator policy missing. |
| Terms | ⚠️ Real route with explicit draft/TODO; approved terms missing. |
| Cookie banner | ✅ Essential-only/opt-in/withdraw controls, analytics fails closed. ⚠️ Legal adequacy requires operator review. |
| Thank-you page | ➖ OAuth/signup enters the studio; upload enters job progress. No lead/contact form warrants a separate page. Success/next-step states are present. |
| Real contact information | ⚠️ Support email, phone policy and legal address unknown; no fake links or business details. |

Changed: `lingbot_map/workspace/{pages,app,analytics,auth_routes,config,database,recovery,request_limits}.py`, `static/{index.html,share.html,site.js,site.webmanifest}`, current favicon/brand/image exports and `ASSET-NOTICES.txt`, `scripts/export_web_assets.sh`, and page/asset tests. The old icon SVG, icon-license file and brand-generation script are superseded by the approved source artwork, current notices and export script. Skipped: fabricated legal/contact/analytics data and tracking requests without consent/configuration. Separate thank-you and indexable-content pages are N/A for the reasons above.

## Phase 3 — Forms, states and dead ends

| Item | Status / implementation |
|---|---|
| Loading states | ✅ Account configuration, capture metadata/upload, queue/progress, viewer and download actions communicate pending work. Local public-route changes focus their heading immediately. API calls are bounded; video upload receives a 15-minute total client window. [Dialog loading QA](DIALOG_LOADING_QA.md) verifies modal-visible pending feedback, overlapping requests and an asynchronous Share/confirmation race. GPU transfer/inference cancellation remains bounded. |
| Inline validation and errors | ✅ Native forms plus server validation; unsupported engine options return 422. Capture metadata/size checks, authoritative one-video allowance and global capacity appear before upload. OAuth failures keep visible feedback on the account route. [Earlier onboarding QA](ONBOARDING_QA.md) covers accepted/oversized/overlong files; [design QA](../design-qa.md) covers the new creation dialog and decoded preview. |
| Submission success/errors | ✅ Signup/login, uploads, jobs, cancellation/deletion and share/copy failures communicate outcomes. A queued video closes the creation dialog and selects progress; native confirmation protects deletion. Feedback is placed inside an open modal when needed. Valid shares retain download when WebGL fails; invalid/expired shares have a recovery state distinct from server failure. |
| Working buttons | ✅ Current Node regressions cover routing, skip links, dialogs, capture cleanup, concurrent submission prevention, deletion selection and stale share actions. [Design QA](../design-qa.md) exercises the actual interface with a precomputed real-scene fixture and no new inference. [Earlier browser QA](BROWSER_QA.md), [Modal QA](MODAL_QA.md), [Render OAuth QA](RENDER_QA.md) and [real-capture QA](REAL_CAPTURE_QA.md) retain their distinct acceptance scopes. The first live Google-account video now reached READY with settled usage; [its scoped receipt](GOOGLE_CAPTURE_QA.md) does not establish ownership, device or visual acceptance. ⚠️ Second-Google-account and owned-phone-capture flows remain pending. |
| Internal/external/footer links | ✅ Product/support/credit routes and packaged assets are linked; unavailable shares offer recovery. Google callback verification on the Render hostname is recorded in [Render QA](RENDER_QA.md). The landing links its public TUM source and the footer links current asset notices. ⚠️ A custom domain, if selected, needs its own callback and metadata verification. |
| Clickable logo | ✅ Landing/support/shared branding returns home; account branding returns to the landing and workspace branding returns to the scene library. |
| Placeholder text/unused navigation | ✅ Public copy describes the actual point-cloud product, with no public sample-entry CTA or invented collaboration/versioning. Operator TODO disclosures remain explicit; local access, capture settings and synthetic creation are secondary. |
| Dynamic copyright | ✅ Current year rendered by shared site script. |

Changed: `lingbot_map/workspace/static/{app.js,share.js,timeline.js,viewer.js,index.html,share.html,site.js}`, API validation and behavior tests. Skipped: invented checkout/contact submission and claims that fixture QA proves owned-capture or provider acceptance. Private filenames/thumbnails and open dialogs are cleared on logout; stale requests cannot restore an old account/scene. Capture previews release object URLs and revalidate a retained file after page-cache restoration. Skip links focus content without replacing account routes or share capabilities.

## Phase 4 — Mobile and performance

| Item | Status / implementation |
|---|---|
| No horizontal overflow | ✅ The redesigned landing/account/shared views were inspected at 390×844; the private/shared fixture evidence and limits are in [design QA](../design-qa.md). The earlier 120-frame stress case is recorded separately in [browser QA](BROWSER_QA.md). Scene libraries and timelines scroll within their own regions. |
| Mobile breakpoints | ✅ Landing/account/studio/shared/support layouts adapt to narrow viewports, with wrapped controls and an aspect-aware initial scene fit. Resize preserves deliberately chosen orbit/zoom and captured/walking viewpoints. ⚠️ Physical mobile verification remains pending. |
| Mobile hamburger/focus trap | ➖ The compact landing has directly available Sign in and Get started actions; footer destinations remain visible. There is no hidden drawer needing a hamburger or trap. Creation, management, confirmation and sharing use native dialogs for their modal focus behavior. |
| Sticky mobile CTA | ✅ The public mobile header keeps Get started visible while scrolling; the mobile workspace source column keeps New scene available. Browser inspection measured the public header at top 0 after scrolling. These existing navigation areas provide the sticky actions; the unused floating CTA is not the implementation. |
| Optimize images/srcset/lazy | ✅ Both themes have 640px, 960px and full-width WebP hero/account/studio exports with `srcset` and `sizes`; native lazy loading defers hidden/below-fold imagery. A browser selected the 640px hero and studio variants at the inspected mobile viewport. The compact brand WebP is separate from retained PNG artwork and favicon exports. Original JPEGs remain source/social assets; bounded source thumbnails load lazily. `scripts/export_web_assets.sh` regenerates the delivery formats. |
| Tap targets/readable fonts | ✅ Theme, refresh, scene, share/download, replay/mode, storage, selection and other styled controls now retain at least 44px hit dimensions, including mobile overrides. Current mobile browser measurements confirmed 44px buttons; responsive text and layouts were inspected in [design QA](../design-qa.md). [Accessibility QA](ACCESSIBILITY_QA.md) records earlier WebKit/Chromium contrast and focus checks for the prior palette; the [current-theme pass](CURRENT_THEME_QA.md) now measures landing/signup/consent text at desktop and 390px, with a lowest observed contrast of 5.134:1. It excludes the private studio and uninspected states. ⚠️ Physical-device and broader assistive-technology coverage remain pending. |

Changed: `lingbot_map/workspace/static/{styles.css,viewer.js,timeline.js,app.js,landing.js,index.html,share.html}`, responsive image/favicon exports, `pages.py` asset fingerprinting and `scripts/export_web_assets.sh`. Landing motion is visibility-, preference- and scroll-bounded; the poster remains useful without WebGL. Earlier model-memory and checkpoint-hash optimizations are retained without changing verified model loading. Sample work and local maintenance continue during a GPU wait. Skipped: a navigation drawer or framework migration without a product need, and unsupported physical-device/performance claims.

## Phase 5 — UX laws applied

| Principle | Concrete change |
|---|---|
| ✅ Hick / Occam / Tesler | Landing → account → create scene separates decisions; operator access, capture settings, synthetic creation and management stay secondary. The server owns quotas and model configuration. |
| ✅ Fitts | Large primary actions, 44px control targets, nearby viewport tools, sticky mobile Get started/New scene and touch walking controls. |
| ✅ Jakob / Similarity / Uniform Connectedness | Conventional Google entry, labeled file input with local preview, grouped playback/actions and native creation/management/confirmation/share dialogs. |
| ✅ Proximity / Prägnanz | Source frame controls stay next to the scene; records keep their own actions. |
| ✅ Miller | Short public navigation, grouped processing states, paginated inventories. |
| ✅ Doherty | Immediate route/focus and pending-work feedback, unchanged-list caching and scroll rendering only when the view changes. GPU latency is not advertised as sub-400ms. |
| ✅ Von Restorff | Cobalt primary action against porcelain/light or neutral/dark surfaces; secondary controls remain restrained. |
| ✅ Serial Position | Get started is prominent in the public header/hero and repeated at the landing's end; New scene and latest scenes lead the studio, followed by review/download/share at completion. |
| ✅ Peak-End / Zeigarnik | A selected-video preview precedes submission; visible processing stages lead to the ready scene, camera replay, download and sharing. |
| ✅ Postel | Trim operator token whitespace; strict stored identities, bounds and canonical object keys. |
| ✅ Pareto | Focus on signup → upload → status → view/replay/walk → download/share. Collaboration/versioning deferred. |

Changed: Phase 3/4 UI files. These are design decisions, not usability-study results. ⚠️ Full real-user/provider flow remains an acceptance gate.

## Phase 6 — Visual polish

✅ Authorized direction: Gallery + Instrument, combining a spacious visual landing with a focused scene studio. Porcelain light is the default; dark and system choices persist across pages. Cobalt actions, restrained system typography, the original two-plane W mark and actual TUM/studio imagery implement the approved references. This supersedes the earlier olive/lime design. Wayline is the product name; upstream model/package/license identifiers remain LingBot for attribution.

➖ Magic UI: React-specific, this app is plain JavaScript. ➖ Threlte/R3F: neither Svelte nor React is present; extending the existing WebGL renderer avoids a framework migration. ➖ Vectary/Jitter: no export is supplied or required; a future approved still/scene/motion export would enter the static-media workflow, not the dependency list. ✅ [Design QA](../design-qa.md) compares approved references with current desktop/mobile captures, theme changes, dialogs and the real precomputed scene. [Real-capture QA](REAL_CAPTURE_QA.md) separately records the licensed benchmark through the original model. ⚠️ Owned-phone capture, physical-device visual/performance and second-account acceptance remain pending; the redesign fixture invoked no new inference.

Changed: public copy, `static/{styles.css,theme.js,landing.js,viewer.js,timeline.js,index.html,share.html}`, brand/image assets, metadata/manifest, `scripts/{prepare_landing_scene.py,export_web_assets.sh}` and current asset notices. The earlier CLI product name/alias is retained. Skipped: dependency/framework replacements without product benefit and invented reconstruction quality or product capabilities.

The follow-up [private studio audit](STUDIO_THEME_QA.md) records current theme/dialog contrast samples, the corrected management footer at 320/390px and short desktop sizes, and selection/confirmation behavior. Physical-device and complete accessibility acceptance remain open.

## TODOs requiring operator input

1. `lingbot_map/workspace/pages.py`: approved privacy policy, controller/subprocessors, actual retention, rights-request process and privacy contact.
2. Same file: approved terms, entity, jurisdiction, billing/refund/acceptable-use/liability rules.
3. Same file: support email/mailto, phone/tel or explicit no-phone-support policy, legal entity/address.
4. `WAYLINE_ANALYTICS_PROPERTY_ID`: approved local property label, plus operator approval of privacy/consent wording before setting `WAYLINE_ANALYTICS_ENABLED=true`. The first-party collector and reporting path now exist; no external measurement account or endpoint is required. Update the policy TODO in `pages.py` together with activation.

These are the explicit `TODO: provide ...` source markers; the contact page has separate email, phone/no-phone-policy and legal-address markers. No fabricated business information replaces them.

## Remaining acceptance and operational work

- Obtain an owned acceptance capture, a second Google account and physical-mobile evidence. Owner signup/returning-login/logout and the licensed benchmark are already recorded; they do not establish these remaining cases.
- Complete dedicated Modal billing verification and credential/role/budget isolation; validate spend alerts and upstream storage/edge/logging behavior. Existing application allowances remain in force and are not a provider invoice cap.
- Verify a complete automatic recovery set, readback/restore and live retention. Scheduled encrypted offsite recovery and seven-set retention are implemented and enabled on Render, but both admitted live attempts failed without a completion marker. Successful diagnostic probes and the actual-data offline differential do not establish a completed provider backup or its root cause. Safe stage diagnostics await a normally admitted run; failed-attempt reservations and the daily gate remain intact. See [scheduled recovery QA](SCHEDULED_RECOVERY_QA.md).
- Complete full-capacity provider/concurrent-service recovery, external failure/staleness alerts, separate key escrow and a replacement-Render restore drill. A local offline 3.49 GB drill (99.71% of the global ceiling) restored every referenced object under 512 MiB with zero OOM events and substantial memory pressure. This disk-fake transport fixture does not close the provider/concurrency gates. The verified manual encrypted export and isolated Linux restore remain preserved; see [recovery crash and capacity QA](RECOVERY_CRASH_QA.md).
- Finish the remaining deployed load/shutdown/crash-cleanup checks. The redesign source scan and browser verification are recorded in [the design release receipt](DESIGN_RELEASE_QA.md). The subsequent recovery-only runtime `d88da15` passed 237 Python tests, ten Node suites, simplify/code review, packaging/container checks, hosted CI and live source/artifact/state verification; [the recovery receipt](RECOVERY_CRASH_QA.md) records scope. Local SIGKILL tests cover one real private-artifact commit boundary before job completion, and scheduled storage is bounded to eight known prefixes; broader failure cases remain open. Aggregate PR-size review concerns remain open; the draft PR is unmerged.
- Resolve model/checkpoint/data hosted-use rights and approved public operator disclosures before claiming public-launch readiness. A custom domain is optional: the existing Render HTTPS origin already supplies absolute metadata; a new domain would require callback/metadata verification.

Implementation and read-only diagnostics can continue autonomously within the existing authorizations and allowances. Owner/provider inputs, physical devices and normal admission timing are distinct from unfinished engineering work. None is closed by this documentation update.

See `launch-readiness.md` for remaining deployment, mobile, model-quality and rights gates. These unresolved items prevent claiming the full requested product is finished.
