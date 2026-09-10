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

43. **Reduced service sizing lacked maximum-payload/concurrent-delivery evidence — Partially verified; real media/load acceptance open.** Code review testing. [scripts/smoke_container.py:146](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/smoke_container.py:146). The constrained container smoke includes a synthetic MP4 padded to the deployed 64 MiB upload ceiling alongside client scene requests; server overlap is not established. Decoded dimensions remain tiny; this does not establish worst-case decoder memory, real capture quality or physical mobile performance.

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

Actual Modal inference on a generated diagnostic, successful-run physical deletion, explicit SDK cancellation and cleanup of a deliberately due record after restart are verified in `MODAL_QA.md`. The cancellation driver encountered GPU capacity delay; API-triggered cancellation during inference and the full cleanup grace period remain unverified. Owned-capture quality, remote cancellation/failure cleanup, Google signup/account switching, full deployed edge/log/backup behavior and physical mobile testing remain unverified. Live Render HTTPS/health, generated-input original-model reconstruction, repeated samples, visitor isolation/CSRF, share expiry/revocation and redeploy persistence passed; see `RENDER_QA.md`. Modal and Render CLIs are authenticated. Wayline / Production now contains the Starter service and 5 GB disk after the user accepted a flexible $20/month target. The assigned host is `https://wayline-9ten.onrender.com`; first-deploy disk permissions are fixed and application commit `d3a6989` is live with successful CI. Google credentials and an owned capture remain unavailable. Browser access has resumed, and the synthetic desktop/mobile-viewport checks are recorded above. Public model-use rights and operator legal/contact details remain unresolved. See launch-readiness.md and PRODUCTION_UX_AUDIT.md for every release gate and TODO.

## Recovery access review — 2026-09-10

53. **Render SSH directory permissions were not reproducible — Fixed.** Parent integration finding, P2. [Dockerfile:7](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/Dockerfile:7). Render created the non-root user's SSH directory at `0755`; the image now creates it with owner `wayline` and mode `0700`. The rebuilt image passed a non-root, read-only, network-disabled ownership/mode check.

The three simplify passes found no further reuse, quality or efficiency issues. All four final code-review skill passes completed for the one-line image change and the temporary offline-snapshot startup script. No new findings were reported; model-visible context was N/A. Existing aggregate PR-size finding 19 remains open. Recovery export/restore and Google OAuth acceptance evidence will be recorded separately after verification.
