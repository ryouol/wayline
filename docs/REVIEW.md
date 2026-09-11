# Wayline review and verification

Updated 2026-09-10. All findings from the three simplify agents and four code-review skill agents are retained below, including fixed and deferred items. Links identify the current code location; earlier review line numbers moved as fixes were applied.

## Findings and dispositions

1. **Sampling estimates disagreed with low-FPS source counts — Fixed.** Simplify / reuse. [lingbot_map/workspace/runner_contract.py:15](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/runner_contract.py:15). Capture extraction and reservation now use the same bounded helper; settlement uses the actual reported frame count.

2. **Shared replay controls missed ID-specific styles — Fixed.** Simplify / reuse. [lingbot_map/workspace/static/styles.css:349](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:349). Shared and private timelines use common class selectors.

3. **Modal names/checkpoint/timeout constants were duplicated — Fixed.** Simplify / reuse. [lingbot_map/workspace/runner_contract.py:5](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/runner_contract.py:5). The transport and GPU deployment share a dependency-free contract.

4. **Neutral GLB serialization overlaps the synthetic encoder — Deferred.** Simplify / reuse. [lingbot_map/workspace/scene_export.py:24](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/scene_export.py:24). Keep the small encoders separate in this change to preserve the authored CC0 sample contract while the new reconstruction format is validated. Consolidation is a maintenance follow-up, not required behavior.

5. **Cleanup could race a late remote start whose call ID was not persisted — Fixed.** Simplify / quality. [lingbot_map/workspace/modal_engine.py:89](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:89). Failure cleanup waits beyond the latest permitted start plus the full remote runtime and buffer. Success can clean up immediately.

6. **Camera replay lost horizontal calibration and image aspect — Fixed.** Simplify / quality. [lingbot_map/workspace/static/viewer.js:443](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/viewer.js:443). Export carries fx/fy/cx/cy and image size; replay uses them with a fitted viewport. Node tests cover unequal focal lengths and portrait display.

7. **A selected filename remained after sign-out — Fixed.** Simplify / quality. [lingbot_map/workspace/static/app.js:175](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:175). Private filename, upload message and frame thumbnails clear with the session.

8. **An old timeline could continue during a scene replacement — Fixed.** Simplify / quality. [lingbot_map/workspace/static/app.js:169](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:169). Detach playback before load; enforce scene/epoch/viewer identity before attaching the result.

9. **Config/login response ordering could hide Google upgrade controls — Fixed.** Simplify / quality. [lingbot_map/workspace/static/app.js:247](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:247). Render account actions both when account state arrives and when feature configuration resolves.

10. **A snapshot could be called verified while missing a referenced object — Fixed.** Simplify / quality. [lingbot_map/workspace/backup.py:45](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/backup.py:45). Create/restore compare every database object reference to manifest size/hash; regression removes an object and expects rejection.

11. **Shared mobile views lacked zoom controls — Fixed.** Simplify / quality. [lingbot_map/workspace/static/share.html:29](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/share.html:29). Shared views have zoom and reset buttons; the common timeline now also exposes touch walking controls.

12. **Synchronous Modal transfers could hang past the job deadline — Fixed.** Simplify / efficiency. [lingbot_map/workspace/modal_engine.py:160](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:160). Async SDK upload/spawn/get/download are covered by a total deadline and cancellation watcher. Stalled-I/O regressions cover every stage.

13. **Default confidence allocation eagerly created a full large tensor — Fixed.** Simplify / efficiency. [lingbot_map/workspace/scene_export.py:118](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/scene_export.py:118). Only allocate a per-frame float32 fallback when confidence is absent.

14. **Expired call IDs and repeatedly failing rows could starve remote cleanup — Fixed.** Simplify / efficiency. [lingbot_map/workspace/modal_engine.py:113](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:113). Missing calls do not prevent volume deletion; per-row timeout and retry deferral allow other due attempts to progress. Old cleaned budget records expire after 31 days.

15. **GPU setup hashed the 4.63 GB checkpoint twice — Fixed.** Simplify / efficiency. [modal_app.py:136](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/modal_app.py:136). Removed the redundant preliminary GPU hash; the mandatory private verified model loader remains in place.

16. **Unsupported Modal options returned HTTP 500 — Fixed.** Code review / compatibility / P2. [lingbot_map/workspace/app.py:725](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:725). Engine validation now returns 422. TestClient regressions cover maxFrames=121, maskSky=true and windowed mode.

17. **Disabling submissions also stopped deletion of old remote captures — Fixed.** Code review / compatibility / P2. [lingbot_map/workspace/service.py:126](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/service.py:126). Cleanup is independent of selected inference engine; a restart with Modal disabled still drains persisted remote records.

18. **Configured job deadlines could exceed the GPU submission contract — Fixed.** Code review / compatibility / P2. [lingbot_map/workspace/config.py:188](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/config.py:188). Modal-enabled configuration rejects job timeouts over 3600 seconds before startup.

19. **The full rebuild exceeds the 800-line review guidance — Open before merge.** Code review / size. [lingbot_map/workspace/static/app.js:11](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:11). The reviewer measured 7,329 changed text lines at 20:44 UTC on 2026-09-10, before the final test/evidence additions. The smallest independent stage is the 15-line synthetic RGBA correction; the 55-line preserved canvas lifecycle fix/test/CI invocation is another separable stage. Further stages are listed below. The branch is for review and is not being merged or treated as release-approved.

20. **Exported RGB byte colors violated glTF vertex alignment — Fixed.** Code review / testing / P2. [lingbot_map/workspace/scene_export.py:33](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/scene_export.py:33). Use RGBA/VEC4 with a four-byte stride. Khronos gltf-validator@2.0.0-dev.3.10 reports zero errors and warnings for the corrected export.

21. **Nominal FPS changed variable-frame-rate replay timing — Fixed.** Code review / testing / P2. [lingbot_map/workspace/capture.py:45](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/capture.py:45). Use actual decoded presentation timestamps; a committed synthetic VFR fixture preserves 0,.1,.2,.3,.4,.5,1,1.5,2,2.5 seconds.

22. **A 60-second request deadline aborted ordinary mobile uploads — Fixed.** Code review / testing / P2. [lingbot_map/workspace/static/app.js:678](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:678). Uploads receive a bounded 15-minute client deadline. Real mobile/network and deployed edge tests remain required.

The context-review skill found no conversational-history/model-context injection path. LingBot consumes bounded image tensors; OAuth/share tokens are credentials, and Rust `core/context` fragment rules are N/A. The testing skill’s Rust/Codex harness paths are likewise N/A; this repository uses FastAPI/TestClient and Node behavior tests.

## Review staging before merge

Preserved original hardening and canvas replacement remain in 027d338; history has not been rewritten. The reviewer recommends these coherent units: canvas lifecycle; HTTP/session hardening; offline snapshots; identity foundations; onboarding; capture/export contract; replay/walking viewer; atomic share-protocol change; queue separation; Modal transport and deployment; presentation/branding; Render delivery.

The disk-fix follow-up is 106 changed lines across seven files and fits one commit. The aggregate three-dot diff `origin/main...HEAD` at a2c3cb5 is 24,840 text lines across 124 files (18,201 excluding lockfiles); its merge base is 90d05ae. The earlier approximately 7,329-line estimate used a direct tree comparison and is not the three-dot PR size. Finding 19 remains open. The smallest independent first stage is the two-line `allow_pickle=False` correction in `benchmark/viewer.py:160`; the eight-line keyframe DOM rendering hardening is another independent stage. No history rewrite or merge was performed.

Keep auth routes with identity schema/dependencies; keep timeline construction with matching markup/script order; keep share-fragment URLs with header-authenticated routes/viewer downloads; keep the CLI lock with runtime_lock.py. The aggregate PR should remain draft until remaining acceptance gates and review-size concerns are resolved.

## Request-limit follow-up review

Reviewed the cohesive delta after `bcc8ffe`: [request_limits.py:9](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/request_limits.py:9), its middleware registration and streaming integration tests. All three simplify reviewers and the compatibility, change-size, testing and model-context reviewers completed their passes with no additional findings. The context skill was N/A because no model-visible content changed. The follow-up fits the size guidance; the previously recorded aggregate PR-size concern remains open.

## Modal deployment follow-up

23. **CI omitted the Modal lock from its pip cache key — Fixed.** Simplify / efficiency / P3. `.github/workflows/ci.yml:30` now includes both dev and Modal locks, allowing downloads from the new hashed dependency check to be cached.

24. **The Modal lock omitted a Linux-only dependency — Fixed.** Live deployment QA. `requirements/modal.lock:478` now pins and hashes `embreex`, requested by the visualization dependency graph on Linux. Regeneration targets the deployed Linux x86-64/Python 3.11 platform and preserves existing pins. An isolated Linux dry-run and the actual Modal installation passed; CI runs the same dependency/hash check.

25. **The remote image omitted its function-defining module — Fixed.** Live deployment QA. `modal_app.py:40` explicitly includes `modal_app.py` while automatic source inclusion remains disabled. A build-time import check loads the entrypoint, demo and original model. The corrected image built, deployed and prepared the verified checkpoint; actual inference completed. The failed preparation app was stopped.

All three final simplify reviewers and the four final code-review skill reviewers completed this Modal delta. The cache-key finding above was fixed; no further findings remained. The context pass was N/A. The 171-line deployment/evidence delta fits size guidance; aggregate PR size remains open.

## Budget and production hardening review

26. **Synthetic RGB colors violated vertex stride alignment — Fixed.** Simplify reuse/efficiency, P2. [lingbot_map/workspace/sample.py:125](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/sample.py:125). The authored sample now uses RGBA/VEC4. Determinism, 5,908 points and CC0 provenance are preserved; sample and reconstruction exports both pass Khronos validation with zero errors/warnings.

27. **Job creation queried the same tenant twice — Fixed.** Simplify reuse, P3. [lingbot_map/workspace/database.py:935](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:935). Reuse the existing _tenant helper and its job-limit field.

28. **Capture and export duplicated the frame ceiling — Fixed.** Simplify reuse, P3. [lingbot_map/workspace/capture.py:11](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/capture.py:11). Both modules import runner_contract.MAX_FRAMES.

29. **Guest detection duplicated the identity query — Fixed.** Simplify reuse, P3. [lingbot_map/workspace/identity.py:88](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/identity.py:88). is_guest delegates to account_type.

30. **Inventory selection retained removed or inactive rows — Fixed.** Simplify quality, P3. [lingbot_map/workspace/static/app.js:435](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:435). Merge pages by ID and reconcile selections against fresh deletable/active records. Node tests cover refresh, pagination, expiry and revocation.

31. **Multipart bodies allocated files before authentication — Fixed.** Simplify efficiency, P1. [lingbot_map/workspace/app.py:667](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:667). Authentication, guest rejection, rate admission, one-parser locking and free-space checks precede one-file/no-field parsing. Tests verify rejected principals allocate no spool files and concurrent uploads are bounded.

32. **No enforceable total project billing ceiling — Budget target accepted; provider settings remain open.** Simplify efficiency, P1 under the former hard-cap requirement. [docs/operating-costs.md:22](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/operating-costs.md:22). A durable 2 GB artifact-delivery allowance and six GPU admissions reduce usage. They do not cover every response or provider charge. Render has no documented per-project hard total cap. On 2026-09-10 the user accepted $20/month as a target with some flexibility, and the Starter service/5 GB disk were created. Modal workspace budget/spend settings remain unverified and must not silently restrict unrelated projects.

33. **SQLite handles remained open until garbage collection — Fixed.** Simplify efficiency, P2. [lingbot_map/workspace/database.py:88](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:88). Managed connections close explicitly after transaction completion; read-only schema inspection also closes. Tests disable GC, repeat authentication and verify rollback plus closure of every recorded connection.

34. **Latest complex delta exceeds review-size guidance — Split into focused commits; aggregate remains open.** Code review size, P2. [lingbot_map/workspace/app.py:667](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:667). The reviewer measured 937 changed lines before final tests/docs. Stage sample, inventory, database/delivery, uploads, sampling, viewer, OAuth tests and deployment evidence separately. Each commit stays below 500 changed lines. Separate commits do not resolve the full PR size concern in finding 19.

35. **Rounded duration underreserved fractional-FPS captures and old queued jobs — Fixed.** Code review compatibility, P2. [lingbot_map/workspace/modal_engine.py:84](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:84). New uploads retain precise sampling timing; legacy millisecond metadata gets a conservative rounding allowance. The service forwards persisted reserved_units, and remote sampling/result validation cannot exceed it. A 1,019-frame fractional-FPS fixture needs 52 samples; an older job reserved at 51 completes within 51 instead of failing after paid work.

36. **Manual upload parsing removed the OpenAPI file contract — Fixed.** Code review compatibility, P2. [lingbot_map/workspace/app.py:647](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:647). An explicit required multipart binary-file schema restores client/docs compatibility while preserving authentication before parsing.

37. **Untraced research GLBs were rotated as synthetic scenes — Fixed.** Code review compatibility, P2. [lingbot_map/workspace/static/viewer.js:142](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/viewer.js:142). Only the existing synthetic-studio-v1 provenance triggers Z-up conversion. Untraced glTF keeps Y-up; regression covers both.

38. **Deployment/cost docs described the old larger resources — Fixed.** Code review compatibility, P2. [docs/deployment.md:48](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/deployment.md:48). Runbook and cost guide now match Starter, a 5 GB disk, 64 MiB uploads and 3,600 GPU reservation seconds. Hard-cap limitations are explicit.

39. **Direct research install used pip absent from the uv environment — Fixed.** Code review compatibility, P2. [README.md:102](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/README.md:102). Use uv pip with the explicit environment interpreter for direct CUDA/research installation.

40. **Smoke-test tmpfs was smaller than the upload admission floor — Fixed.** Code review compatibility/testing, P2. [scripts/smoke_container.py:47](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:47). Disposable disk-backed /tmp replaces the 512 MiB tmpfs. The unchanged physical free-space floor and real multipart smoke now pass.

41. **A stalled upload held the only admission slot indefinitely — Fixed.** Code review testing, P2. [lingbot_map/workspace/app.py:693](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:693). A bounded server parser timeout returns 408; disconnects return 400. Both paths close rolled spool files and release the lock. Tests also cover 507 before allocation, exact free-space boundary and admission recovery.

42. **Google exchange branches were only tested through a replaced route helper — Fixed with provider mocks; live acceptance open.** Code review testing. [tests/test_identity.py:13](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_identity.py:13). Tests call the actual exchange helper for nonce, verified-email, subject, missing token, provider status, POST timeout, signature rejection and certificate-fetch timeout. Actual Google signup/account switching remains required.

43. **Reduced service sizing lacked maximum-payload/concurrent-delivery evidence — Partially verified; real media/load acceptance open.** Code review testing. [scripts/smoke_container.py:146](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:146). The constrained container smoke includes a synthetic MP4 padded to the deployed 64 MiB upload ceiling alongside client scene requests; server overlap is not established. A later generated 4096×4096 H.264 pass succeeded locally and through Render, including the 64 MiB upload. See `CAPACITY_QA.md`. This adds supported-resolution evidence but does not establish every codec's worst-case memory, real capture quality or physical mobile performance.

44. **Persisted reservation forwarding was not covered through the service — Fixed.** Code review testing, P3. [tests/test_modal_engine.py:147](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_modal_engine.py:147). A legacy queued row now runs through WorkspaceService with mocked Modal: 51 reported frames settle successfully, while a 52-frame response fails without charging customer units.

45. **Google certificate-fetch timeout callback was not exercised — Fixed.** Code review testing, P3. [tests/test_identity.py:58](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_identity.py:58). The verification stub invokes the real bounded callback; a mocked GoogleRequest checks the 15-second deadline and timeout propagation, independently of the token POST.

46. **Cost guide incorrectly applied the operator storage limit to Google accounts — Fixed.** Code review compatibility, P3. [docs/operating-costs.md:70](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/operating-costs.md:70). Document actual limits separately: 256 MiB operator, 512 MiB Google, 5 MiB playground, all under the global 3.5 GB limit.

47. **Smoke evidence did not establish overlapping server requests — Claim corrected; live load acceptance open.** Code review testing, P3. [scripts/smoke_container.py:151](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:151). Requests can prepare the 64 MiB multipart body before sending it, so the client thread and GETs do not prove server overlap. Documentation reports maximum-payload upload and successful scene requests only. The enforced 512 MiB limit and measured 210.4 MiB peak remain valid for the exercised workload.

48. **Render disk root could not be secured by the non-root process — Fixed.** Deployment verification, P1. [Dockerfile:15](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/Dockerfile:15). The initial deploy failed while applying private permissions to `/data`. Docker and Render now use `/data/wayline`; the smoke preserves a root-owned mount and verifies the child owner and mode `0700`. Existing installations retain their explicit data path until a coordinated move.

49. **Smoke startup failures leaked the named disk volume — Fixed.** Simplify quality and efficiency, P2. [scripts/smoke_container.py:211](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:211). One cleanup scope covers startup and verification; container removal and named-volume removal are independently attempted. An invalid-port startup test verified removal of the volume and temporary environment file.

50. **Visitor UI incorrectly claimed a disconnected GPU — Fixed.** Live browser QA. [lingbot_map/workspace/static/app.js:606](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:606). Trial accounts now see synthetic-playground messaging and no upload form; Google availability updates the signup guidance independently of GPU availability.

51. **Upload completion duplicated button eligibility — Fixed.** Simplify reuse. [lingbot_map/workspace/static/app.js:720](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:720). Completion uses the same reconstruction-state renderer as engine loading.

52. **The first UI fix could re-enable an in-flight upload on focus — Fixed before deployment.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:251](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:251). Account/config refresh updates reconstruction controls only for trial accounts. Operator/Google uploads retain the disabled button until their existing completion path runs. Follow-up review and direct function execution covered these transitions; the five existing Node suites passed. Local browser entry confirmed the corrected visitor UI. Compatibility/testing found no new issues; context was N/A; size retained finding 19.

The disk-fix simplify pass reported finding 49 from both quality and efficiency; reuse found no issue. After the fix, compatibility and testing found no new issues, model-context rules were N/A, and size review retained finding 19. Earlier final simplify reviewers found no additional issues. Compatibility and testing follow-ups are retained above. The model-context pass is N/A and found no additional issue. No review comments were posted on GitHub. The owned draft PR retains the `code-reviewed` label; that label is not production approval.

## Verification

- Live Render evidence, including the 41.28-second generated-input model run and zero remaining Modal capture files/workers, is in [RENDER_QA.md](RENDER_QA.md). Application commit `d3a6989` passed [CI](https://github.com/ryouol/lingbot-map/actions/runs/34534857893).

- Disk-layout follow-up: image `b4ed28700c4391e329e57e3d9fe46e29dd3762af2a0d9dada2e4b4bfff5828f7` passed the full constrained smoke with a root-owned mount and private app-owned child; peak memory 206.4 MiB. Docker copy-up initially reset the empty volume owner, so the regression setup now uses `volume-nocopy`.

- Python: 165 tests passed, including queue separation, disabled-submission cleanup, bounded remote I/O, unsupported options, VFR sampling and streamed request limits with multipart spool cleanup.
- Ruff strict lint and formatting passed. Mypy passed across 19 source files after the request-limit addition.
- All packaged JavaScript syntax checks passed; session-event, inventory-selection, viewer-lifecycle, viewer-trace/walking and timeline Node behavior checks passed.
- `uv lock --check` passed. Wheel built with `uv build`; required UI and license files verified. The local uv-created venv does not contain pip, so the equivalent local pip-wheel command was unavailable; Docker independently built and installed the wheel using pip.
- Docker image `9772c37f95d5055a9c52bc3bd7643e34ca62ad181d8e5ec2bd00fc554c5b53ff` built successfully. The final smoke ran with 512 MiB / 0.5 CPU, a 64 MiB padded synthetic upload and shared downloads; peak memory was 210.4 MiB. `scripts/smoke_container.py` passed with a non-root/read-only app, private persistent data, readiness and host/auth rejection, two sequential synthetic jobs, GLB download, capability-header sharing and revocation. The disposable container was removed afterward. An initial ad-hoc smoke assertion expected 204 for revocation; the documented API correctly returns 202, and the reproducible script now checks that contract.
- Corrected reconstruction fixture: Khronos glTF Validator zero errors/warnings. This validates serialization, not model output quality.
- High-confidence working-tree private-key/provider-token signature scan: no matches. Not a full Git-history or provider audit.
- Post-review browser QA: repeat sample creation, 750,000-point/120-frame synthetic fixture, replay completion, walking/reset, logout cleanup, anonymous share, verified GLB download and automatic expiry passed. Private/shared pages fit at 390px; see `BROWSER_QA.md`. No application code changed during this pass.
- Request-limit follow-up: real HTTP chunked requests against a separate local Uvicorn process returned 413 for oversized JSON, 200 for a normal login and 201 with exact stored bytes for a small synthetic video upload. No provider upload or model inference occurred; the temporary workspace/server were removed.

## Remaining acceptance

Live Render hosting, a generated-input original-model run, owner Google signup/returning login/logout, visitor isolation and sharing are verified in `RENDER_QA.md`. An encrypted export of the live workspace and server environment passed an isolated Linux restore (`RECOVERY_QA.md`). The latest runtime is `cd24f7f`, with green CI and verified private SSH permissions. Google-account capacity is one and the owner's free video is unused.

The later live reliability pass verified API cancellation during model inference, normal remote cleanup after the complete grace period, streamed request handling, disconnect cleanup, a 900-second loopback parser deadline and responsive sample creation during a stalled upload. No application code changed; see `RELIABILITY_QA.md`. Historical pattern and exact-live-credential scans found no matches within their stated scope (`SECURITY_QA.md`).

Owned-capture quality, second-Google-account switching, physical mobile QA, remaining crash/failure cleanup boundaries, upstream logging/edge limits, automated backup retention and a separate Render restore drill remain open. Public hosted-use rights and approved operator legal/contact details are unresolved. Shared Modal credentials/budgets still need project isolation. See `launch-readiness.md` and `PRODUCTION_UX_AUDIT.md` for every release gate and TODO.

## Recovery access review — 2026-09-10

53. **Render SSH directory permissions were not reproducible — Fixed.** Parent integration finding, P2. [Dockerfile:7](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/Dockerfile:7). Render created the non-root user's SSH directory at `0755`; the image now creates it with owner `wayline` and mode `0700`. The rebuilt image passed a non-root, read-only, network-disabled ownership/mode check.

The three simplify passes found no further reuse, quality or efficiency issues. All four final code-review skill passes completed for the one-line image change and the temporary offline-snapshot startup script. No new findings were reported; model-visible context was N/A. Existing aggregate PR-size finding 19 remains open. Recovery export/restore and owner Google OAuth acceptance passed; evidence is in `RECOVERY_QA.md` and `RENDER_QA.md`. Current [CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34537748484).

## Online snapshot review — 2026-09-10

54. **Uploaded-source restoration was absent from snapshot tests — Fixed.** Code review testing, P3. [tests/test_backup.py:16](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_backup.py:16). Earlier cases generated artifacts without uploaded assets, so sharing a metadata-query helper between online copying and verification could hide an omitted assets query. The round-trip test now uploads the existing generated MP4 fixture through the service and independently compares restored capture bytes, in both online and offline modes.

All three simplify passes found no actionable issues. Final compatibility and
change-size reviews found no new issues; model-context review was N/A. The
testing finding above is retained and fixed. This follow-up fits the complex
change-size guidance; aggregate PR-size finding 19 remains open. No GitHub
comments or merge were performed.

The final [CI passed](https://github.com/ryouol/lingbot-map/actions/runs/34543233887),
including 170 Python tests, strict lint, formatting, type checking, the Node
checks and production container smoke. Tests cover later publication exclusion, live-runtime
lock bypass only when explicitly requested, concurrent deletion/corruption,
database-copy timeout cleanup, and recovered source/artifact/share identity.
The CLI is an online snapshot capability, not an automated backup service.

## Accessibility and scheduled recovery review — 2026-09-11

55. **Private viewer keyboard focus was clipped — Fixed.** Read-only accessibility review, P2. [lingbot_map/workspace/static/styles.css:331](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:331). The canvas focus outline extended outside its overflow-hidden wrapper. The shared canvas rule now places the ring inside the edge; local browser QA verified a visible ring while arrow-key orbiting.

56. **Scene processing progress had no accessible name — Fixed.** Read-only accessibility review, P2. [lingbot_map/workspace/static/index.html:145](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:145). The progress element now has a stable accessible name. A real local sample job exposed “Scene processing progress” at 92% in the accessibility tree.

57. **Shared zoom controls were below the required touch width — Fixed.** Read-only accessibility review, P2. [lingbot_map/workspace/static/styles.css:353](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:353). The live controls measured 37.234375 by 44 pixels. The shared control group now enforces 44-pixel minimum width; local QA measured 44 by 44 pixels at 390-pixel viewport width without document overflow.

58. **Restoring a scheduled set could delete its sole recovery source — Fixed.** Simplify quality, P2. [lingbot_map/workspace/recovery.py:341](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:341). The encrypted ledger preserves its current source as retained. The live ledger marks completion only after all parts and the final marker are verified. A failed replacement cannot remove the restored source.

59. **Whole-archive SDK transfers could exceed container memory — Fixed.** Simplify efficiency, P1. [lingbot_map/workspace/recovery.py:218](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:218). Transfers are sequential parts of at most 8 MiB, preventing Modal SDK host-CPU-based block prefetch and hashing from scaling with the full archive. Real constrained SDK verification is recorded separately.

60. **Exhausted allowance still caused complete workspace copying — Fixed.** Simplify efficiency, P2. [lingbot_map/workspace/recovery.py:313](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:313). An allowance preflight now occurs before snapshot copying. The final conservative reservation remains durable before encryption and provider upload.

61. **Failed attempts could prevent ledger compaction — Fixed.** Simplify efficiency, P2. [lingbot_map/workspace/recovery.py:299](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:299). Expired already-pruned entries are compacted before provider construction or deletion. Current reservations and every unpruned prefix remain. A regression covers failed remote cleanup.

62. **An ordinary online snapshot could later delete a completed remote set — Fixed.** Breaking-change review, P2. [lingbot_map/workspace/backup.py:120](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/backup.py:120). Snapshots protect running entries as retained because an upload may finish after their cutoff. The source ledger remains unchanged. A restore followed by a failed replacement preserves the remote prefix.

63. **Actual encryption test could skip in CI — Fixed.** Testing review, P2. [tests/test_recovery.py:208](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_recovery.py:208). CI explicitly installs age before Python tests. The local skip message now states the actual dependency limitation, without claiming coverage from the ordinary image smoke.

64. **Enabled recovery service lifecycle was not covered — Fixed.** Testing review, P2. [tests/test_recovery.py:425](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_recovery.py:425). The integration test starts WorkspaceService with recovery enabled, verifies sample completion while its child is blocked, then checks shutdown reaps that child and retains its allowance charge.

65. **Full part manifests could make the recovery ledger permanently too large — Fixed.** Testing review, P2. [lingbot_map/workspace/recovery.py:376](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:376). The local ledger stores only total size and checksum. Ordered part metadata remains in the remote completion marker. Eight runs with 448-part manifests exercise retention without reaching the embedded-state ceiling.

66. **Incremental recovery change exceeds the change-size guidance — Open.** Change-size review, P2. [lingbot_map/workspace/recovery.py:263](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:263). Reviewable stages are accessibility, bounded snapshot copying, encryption/transfer primitives, durable transaction, and scheduled activation. The incremental feature exceeds 800 changed lines including tests and the under-500 complex-change guidance. The broader draft PR also retains finding 19; separate commits alone do not resolve aggregate PR size.

67. **Ordinary 512 MiB image smoke did not exercise recovery — Scoped verification complete.** Testing review, P2. [scripts/smoke_container.py:18](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:18). The standard image smoke keeps recovery disabled. A separate real-SDK 64 MiB generated-input workload passed under 512 MiB / 0.5 CPU; results and failed larger diagnostics are recorded in SCHEDULED_RECOVERY_QA.md. Full-capacity validation remains open; CI requires offline age tests but does not invoke provider storage.

68. **Uncertain restored entries displaced verified retention slots — Fixed.** Breaking-change follow-up, P2. [lingbot_map/workspace/recovery.py:244](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:244). Retention selects seven completed sets independently of uncertain retained entries. Uncertain sources remain protected until seven completed sets exist, so they cannot displace a verified backup. Regression preserves seven actual completion markers.

All three simplify passes and four final code-review skill passes completed. Reuse found no issue; model-visible context was N/A. Every actionable finding is retained above, including follow-ups. No review comments or merge were performed.

## Recovery readback follow-up — 2026-09-11

69. **Backup verification lacked bounded read retries — Implemented; live backup still failing.** Live verification, P2. [lingbot_map/workspace/recovery.py:207](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:207). The first live attempt failed after its first part appeared remotely; a later read succeeded. Its exact failing operation was not captured. The deployed retry also failed, so these changes do not establish a repaired live backup. Read exceptions now receive at most three attempts within the existing child deadline, resetting byte count and digest each time. Uploads are never repeated by this loop, checksum mismatches fail immediately, and failed reservations remain charged.

70. **Operator retries could bypass their rolling-day limit — Fixed.** Simplify quality, P2. [lingbot_map/workspace/recovery.py:297](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:297). Counting recent attempts alone allowed a second operator retry when the original scheduled failure aged out. Admission now persists and checks the operator retry type. Regression tests cover that boundary, concurrent locking, retained charges and rejection after success.

71. **Operator retry supervisor and CLI path were not exercised — Fixed.** Testing review, P3. [tests/test_recovery.py:424](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_recovery.py:424). The bounded-child test now asserts forwarding of --retry-failed. A real CLI subprocess parses that flag and proves it cannot bypass a recent successful admission, without accessing a provider.

The local suite passes 196 tests, strict lint/format checks and mypy. Reuse,
quality and efficiency passes found no remaining actionable issues. Final
compatibility and change-size passes found no new issues; existing size findings
19 and 66 remain open. Testing found only the fixed coverage gap above;
model-context review was N/A. No comments or merge were performed.

72. **Generic backup errors did not identify the failed transfer stage — Fixed in code.** Operator diagnosis, P2. [lingbot_map/workspace/recovery.py:208](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:208). Terminal upload and readback errors now record distinct safe categories and log exception class names only. Tests assert raw provider messages are absent. This is an observability fix; the original live failure remains unresolved and no additional full backup admission was granted.

All three simplify passes and four final code-review skill passes also completed
for the diagnostic follow-up. No additional findings remain; context review is
N/A. All 196 Python tests, strict lint/format checks and mypy passed locally.
The failed live backups remain an acceptance limitation, not a passing test.

## Capture onboarding and real-geometry review — 2026-09-11

73. **Google upload eligibility was discovered after uploading — Fixed.** Product-flow audit, P2. [lingbot_map/workspace/database.py:920](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:920). One policy now drives job admission, `/api/me`, upload preflight and the transaction that creates new assets. Used, processing and daily-attempt states reject fresh uploads before multipart parsing; operator uploads retain their existing behavior.

74. **Full signup capacity ended at a JSON error page — Fixed.** Product-flow audit, P2. [lingbot_map/workspace/auth_routes.py:170](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/auth_routes.py:170). Config distinguishes returning login from new-account capacity. The callback redirects to a visible capacity notice and clears its OAuth cookie; existing sessions and returning Google accounts remain usable.

75. **Capture limits appeared too late — Fixed.** Product-flow audit, P2. [lingbot_map/workspace/static/app.js:686](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:686). The picker displays configured limits, rejects excess bytes immediately, and checks local media duration before upload. Timeout/unsupported decoding falls back to server validation; object URLs, timers and callbacks are released.

76. **Allowance preflight broke completed upload replays — Fixed.** Breaking-change review, P2. [lingbot_map/workspace/app.py:684](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:684). Only completed, unexpired keys for the same tenant and upload route may bypass the early allowance rejection. The existing parser/hash path still detects changed payloads. New asset creation rechecks allowance transactionally, including expiry/deletion/state races after preflight.

77. **Logout could restart a stale job poll — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:395](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:395). The job loader checks its session epoch after account/detail awaits, so an aborted terminal refresh cannot rearm polling after reset.

78. **A transition could reuse an older account snapshot — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:121](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:121). Post-queue and terminal refreshes request a snapshot after any already pending account request. Ordinary focus checks still coalesce, and regression tests verify the later state replaces the pre-transition response.

79. **Capacity feedback depended on config fetch success — Fixed.** Simplify quality, P3. [lingbot_map/workspace/static/app.js:969](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:969). Fixed callback notices render before config loading and outside either account view, including an existing trial session while config is unavailable.

80. **An initially missed terminal transition left upload disabled — Fixed.** Breaking-change review, P2. [lingbot_map/workspace/static/app.js:389](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:389). A processing allowance is reconciled when the jobs snapshot contains no active research job, including completion between initial account and job requests. Unchanged, reconciled terminal polls do not keep refreshing the account.

81. **Content policy blocked local metadata decoding — Fixed.** Testing review, P2. [lingbot_map/workspace/app.py:456](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:456). Real Chromium reproduced a blob media CSP violation under the previous default-src policy. A narrow media-src permits local blob media while script-src remains self-only. Actual file-selection QA confirms decoding under the fixed policy.

82. **Successful clip validation looked like an error — Fixed.** Testing/browser review, P3. [lingbot_map/workspace/static/styles.css:294](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:294). Checking, valid and unsupported-metadata fallback messages use neutral text; only invalid captures use the error color.

83. **Onboarding exceeds the suggested complex-change size — Open.** Change-size review, P2. [lingbot_map/workspace/static/app.js:121](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:121). Backend policy, browser onboarding and geometry are separated into commits. The coupled browser flow and its behavioral suite still exceed the under-500 guidance; the reviewer recommended separating allowance/session work from media validation. Aggregate draft-PR size findings 19 and 66 also remain open. Commits do not resolve aggregate PR size.

84. **Exported camera convention duplicated real scene geometry — Fixed and verified live.** Real-capture QA, P1. [lingbot_map/workspace/scene_export.py:128](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/scene_export.py:128). The exporter now inverts the world-to-camera matrices consumed by the original LingBot viewer before depth unprojection and trace generation. Existing comments in the upstream demo disagree with its actual visualization contract. An independent rotated/translated shared-landmark regression covers both depth and global-point branches. An offline diagnostic reduced blue-object centroid spread about 13.5 times. A separate fresh deployed inference then reproduced that correction within floating-point precision; desktop replay, walking, whole view and matching browser download passed. See REAL_CAPTURE_QA.md.

85. **New camera regression failed strict lint — Fixed.** Simplify quality, P2. [tests/test_scene_export.py:89](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_scene_export.py:89). The frame/camera zip now declares strict equality. Strict Ruff passes; the expected frame cardinality is explicit.

All three simplify passes and four code-review skill passes completed for onboarding and the geometry follow-up. Model-visible context was N/A. Geometry reuse, efficiency, compatibility and testing found no further issues; its strict-lint finding is fixed. Every finding is retained above, including the open change-size concern. No GitHub comments or merge were performed.

The deployed capture release is `cd24f7fda60586840c2a6c425e44363f3eac3965`, Render deploy `dep-dahn4rnqj5pc739n7f30`, with [passing CI](https://github.com/ryouol/lingbot-map/actions/runs/34557607186). Local verification passed 212 Python tests, six Node suites, strict lint/format checks and mypy. The new real-camera benchmark passed the corrected original-model path, desktop replay/walking/reset and exact browser download; its QA share was revoked. The one-account signup ceiling and all cost allowances are unchanged.

## Shared reconstruction capacity — 2026-09-11

86. **Full shared GPU allowance still accepted uploads and jobs — Fixed in code.** Product-flow audit, P2. [lingbot_map/workspace/modal_engine.py:99](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:99). Admission now counts pending research jobs alongside conservative remote charges. Serialized engine availability, upload preflight, asset creation and job submission use the same policy. Job admission and remote charging check inside write transactions. The frontend refreshes personal allowance and engine availability together before uploading and after transitions. Completed idempotent requests still replay with payload validation; samples and local engines retain their behavior. Availability is advisory and can conservatively understate capacity while another charged job is running.

87. **Worker capacity denial consumed personal retry allowance — Fixed in code.** Budget-accounting review, P2. [lingbot_map/workspace/database.py:1343](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:1343). A dedicated pre-dispatch capacity error now receives safe user-facing feedback. Within the existing fenced failure transaction, its reserve ledger entry is classified as capacity-denied only if the job has no prior remote attempt. Units, timestamps, settlement and remote charges are preserved. The exemption survives job deletion; prior charged or uncertain attempts and unrelated failures remain counted.

88. **Capacity regression exceeded the strict lint line limit — Fixed.** Validation, P3. [tests/test_modal_capacity.py:263](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_modal_capacity.py:263). The historical remote-run fixture's SQL literal is split across adjacent strings. The strict E/F/I/B/UP/SIM check now passes without weakening the lint configuration.

89. **An older login response could overwrite newer capacity — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:765](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:765). Operator login and trial entry now use the same combined account/engine refresh coordinator as pre-upload and focus. The separate engine-state writer is removed. Behavioral regressions delay each entry response while a newer refresh waits, then verify that newer capacity wins. Server and pre-upload checks already prevented additional GPU work; this fixes controls incorrectly becoming enabled.

90. **Capacity follow-up exceeded the suggested complex-change size — Split into reviewable stages.** Change-size review, P2. [lingbot_map/workspace/modal_engine.py:99](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/modal_engine.py:99). The reviewed delta was 683 changed lines, below 800 but above the under-500 complex-change guidance. Backend enforcement and its tests are a 424-line commit; browser coordination and its regressions are a separate 185-line commit, followed by documentation. The reviewer confirmed this ordering addresses the incremental staging issue. Aggregate draft-PR size findings 19, 66 and 83 remain open.

All three simplify passes and four final code-review skill passes completed.
Reuse and efficiency found no additional issues; the quality race above is fixed.
Final compatibility and testing reviews found no issues; model-context review
was N/A. The full local suite passed 226 Python tests and six Node suites, strict
Ruff/format checks and mypy. The testing reviewer independently reran the 14
capacity Python cases and onboarding suite. Backend commit `1fc30a2` and frontend
commit `bafb1c0` preserve the separate review stages. No provider GPU jobs,
shared-account limit changes, GitHub comments or merge were performed for this
capacity pass. See `GPU_CAPACITY_QA.md` for deployment evidence and limitations.

The reviewed capacity release `1fbfe9a` is live on Render deploy
`dep-dahnr4fqj5pc739q5i50`, with passing CI including the production container.
HTTPS health, deployed source hashes, dynamic engine availability and the saved
Google browser session/scene were verified. Six READY jobs, four GPU admissions
and the owner's unused video remain unchanged. No GPU inference was repeated.
