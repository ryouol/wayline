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

## Signup contrast and WebKit — 2026-09-11

91. **Returning Google login became unreadable when signup filled — Fixed.** Contrast review, P2. [lingbot_map/workspace/static/styles.css:256](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:256). The secondary state inherited light text while the unconditional Google background stayed the same light color, giving 1.00:1 contrast. Restricting the light background to `.google-button.primary` restores the secondary palette. Rendered WebKit and Chromium checks measured 16.47:1 for returning login while open signup remains 13.44:1.

92. **Empty text fields had an indistinct input boundary — Fixed.** Contrast review, P2. [lingbot_map/workspace/static/styles.css:61](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:61). Text/password/number fields used the faint decorative line color; the empty token field's boundary was about 1.52:1 against its surroundings. Reusing `--quiet` gives measured 6.19:1 against the fill and 6.72:1 against the landing background. File, range and checkbox controls and decorative dividers are unchanged.

All three simplify passes and all four xhigh code-review passes completed for the
two-line CSS follow-up. Reuse, quality, efficiency, compatibility and testing
found no additional issues; model-visible context was N/A. The incremental size
review passed; existing aggregate findings 19, 66 and 83 remain open. No new
implementation-mirroring tests were added for this presentation change: actual
computed styles and screenshots cover both signup states in WebKit and Chromium.
The verified real scene also passed WebKit replay, frame selection, walking and
reset. A screenshot-tool CSP injection was isolated without changing app CSP.
See ACCESSIBILITY_QA.md and REAL_CAPTURE_QA.md for scope and retained evidence.

## Gallery + Instrument redesign — 2026-09-11

93. **Offline presentation writer repeats GLB serialization — Deferred.** Simplify reuse, P3. [scripts/prepare_landing_scene.py:18](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/scripts/prepare_landing_scene.py:18). The reviewer suggested extending `scene_export.encode_point_glb` to preserve presentation metadata. This pinned one-source asset preparation command deliberately retains the original trace and attribution. Changing the production exporter API solely for this offline presentation asset is not worthwhile in this release. The duplication and follow-up remain explicit.

94. **Feedback was behind the native modal layer — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:351](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:351). The existing feedback element is moved into the active dialog, or back to the document when no dialog is open. It remains visible for validation, copy and in-progress close errors; the behavioral regression checks the actual parent.

95. **Cached-page restoration left a retained capture invalid — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:1163](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:1163). Page-hide cleanup still releases media URLs and callbacks. A persisted pageshow now revalidates the retained file unless a submission is active, restoring its preview and eligibility. Regression covers the browser lifecycle.

96. **Sample creation could overlap video submission — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:893](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:893). Both actions share the submission lock and epoch-safe cleanup. The dialog cannot close during submission; the UI explains why. Both overlap directions are tested.

97. **Deleting an unrelated scene changed the open scene — Fixed.** Simplify quality, P2. [lingbot_map/workspace/static/app.js:1004](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:1004). Single-scene deletion preserves the currently selected scene unless that is the deleted item. This prevents an inventory cleanup action from unexpectedly replacing the viewport.

98. **Landing repeatedly drew unchanged scroll positions — Fixed.** Simplify efficiency, P2. [lingbot_map/workspace/static/landing.js:39](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/landing.js:39). The renderer remembers its last progress and skips identical camera updates. Resize explicitly invalidates that value. The regression proves both the no-op boundary and resize redraw.

99. **A large raster replaced the required favicon set — Fixed.** Simplify efficiency and full-brief audit, P2. [lingbot_map/workspace/pages.py:48](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/pages.py:48). The original efficiency review found a 650 KB favicon, temporarily reduced to 157 KB. The requirement audit correctly identified the missing explicit format set. Offline exports now provide 16/32 PNG, a two-resolution ICO, 180px Apple and 192/512 manifest icons from the approved mark. The visible brand uses a 1,194-byte WebP; favicon PNGs are 348/634 bytes. Metadata, packaged files and actual icon appearance were checked.

100. **An acknowledged deletion could leave a ghost inventory row — Fixed.** Breaking-change and model-context reviewers independently reported the same P2. [lingbot_map/workspace/static/app.js:1004](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:1004). The deleted row and selection are removed locally before the preserve-loaded refresh, preventing merge logic from retaining it. Regression covers deletion with previously loaded inventory.

101. **Share could target a previously viewed artifact — Fixed.** Breaking-change review, P2. [lingbot_map/workspace/static/app.js:689](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:689). Empty/non-ready detail and full detail reset remove the old artifact identifier and download URL. A later focus/allowance refresh cannot re-enable sharing for another scene. The delayed-refresh regression covers the trigger.

102. **Account skip link replaced the signup route — Fixed.** Breaking-change review, P2. [lingbot_map/workspace/static/app.js:1154](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:1154). The handler focuses the visible main heading without changing the fragment. Browser keyboard QA confirms focus on `accountTitle` while the URL stays `#signup`; both public account routes have regression coverage.

103. **The redesign exceeds review-size guidance — Staged review recorded; aggregate concern open.** Change-size review, P2. [lingbot_map/workspace/static/styles.css:1](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:1). The reviewed redesign was approximately 3,038 changed text lines before this report, plus binary assets. The user explicitly approved a broad redesign. The additive three-file scene-name API is committed first; the coupled UI is reviewed in the stages below. Neither stages nor commits shrink the existing draft PR, whose previous size findings 19, 66 and 83 remain open. No merge is performed.

104. **Delete looked like a close-window X — Fixed.** Design review, P2. [lingbot_map/workspace/static/index.html:111](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:111). The action now visibly says Delete, retains its accessible name and opens the existing explicit confirmation flow.

105. **Portrait initial view clipped the real scene — Fixed.** Browser/design follow-up, P2. [lingbot_map/workspace/static/viewer.js:394](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/viewer.js:394). Initial/reset orbit fits rotated bounds against the actual canvas aspect and projection. Resize adjusts untouched views but preserves manual orbit, zoom, camera and walk state. A projection-based test and a fresh 390 × 844 browser view of the 750,000-point reference verify the result.

106. **Shared service failure could look like expiry, and WebGL failure removed download — Fixed.** Shared-view review, P2. [lingbot_map/workspace/static/share.js:50](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/share.js:50). Authentication/expiry statuses close the share, server failure gets a retry message, and valid metadata allows download even if preview creation/parsing fails. Expiry aborts in-flight downloads and releases object URLs. Status/fallback/cancellation regressions pass.

107. **Shared skip link replaced its capability fragment — Fixed.** Accessibility follow-up, P2. [lingbot_map/workspace/static/share.js:32](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/share.js:32). The handler focuses the shared title without hash navigation. Both the behavioral suite and actual keyboard/download flow preserve the active share.

108. **Small differences from the illustrative mockup remain — Accepted P3 design differences.** Final design review. [lingbot_map/workspace/static/index.html:35](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:35). The real hero is sparse and omits the decorative source-frame fan. The studio has two functional header rows, looser scene framing and secondary details below the main experience. The final reviewer found no P0/P1/P2 visual issue. We retain truthful actual imagery and functional controls rather than invent product capabilities.

### Recorded review stages

1. **Scene naming API:** `app.py`, `database.py`, `test_job_display_names.py`.
   Tenant-scoped source-name join, additive display field and ownership/pagination
   cases; approximately 140 changed lines. Reviewed separately before UI adoption.
2. **Presentation and conversion:** `index.html`, `styles.css`, `pages.py`,
   `theme.js`, `site.js`, brand/icons and light/dark assets. Compared against the
   approved source and actual desktop/mobile captures; theme/capacity cases pass.
3. **Authenticated interactions:** `app.js` and onboarding/inventory regressions.
   Signup routing, capture preview, dialogs, selection, safe teardown and sharing
   reviewed with real HTTP local fixture progression plus delayed-response tests.
4. **Viewer, landing and sharing:** `viewer.js`, `timeline.js`, `landing.js`,
   `share.js` and their suites. Includes portrait projection, cancellation,
   lost-canvas replacement, accessibility, prefetched share response and motion.
5. **Packaging and evidence:** asset preparation, notices, wheel/CI manifest and
   this report. Clean wheel and constrained production container verified.

All three simplify passes and four xhigh code-review skill passes completed.
Testing found no additional issues; the model-context skill itself was N/A, and
its useful duplicate compatibility finding is retained as 100. The final follow-up
review found no actionable regression and reran all ten Node suites. The full
local suite passed 229 Python tests, strict Ruff/format and mypy. Docker smoke
passed under 512 MiB / 0.5 CPU with a 204.6 MiB peak. See `design-qa.md` for exact
browser evidence and limitations. The PR owner's existing `code-reviewed` label
is retained; no GitHub review comments or dependency merges were made.

### Full-brief completion audit and final follow-up

109. **Sticky mobile conversion and creation were missing — Fixed.** Full-brief audit, P2. [lingbot_map/workspace/static/styles.css:356](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:356). The existing public navigation now stays visible on mobile with Get started. The existing workspace scene bar keeps New scene available while scrolling. CUA measured both bars at top=0 after actual page scroll; no floating overlay was added. The public wordmark becomes the approved compact mark below 560px so all actions fit.

110. **Several controls fell below the requested 44px target — Fixed.** Full-brief audit, P2. [lingbot_map/workspace/static/styles.css:81](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:81). Theme, refresh, mode, playback, slider, selection, storage and artifact controls now meet 44px minimum hitboxes. Actual in-app-browser measurements at 390px found no undersized visible workspace buttons, action links or range inputs. Public Sign in, appearance and both signup actions measured 44px high.

111. **New large imagery lacked responsive delivery variants — Fixed.** Full-brief audit, P2. [lingbot_map/workspace/static/index.html:35](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:35). The actual light/dark captures now have 640px, 960px and full-width WebP exports with sizes/srcset. Native lazy loading avoids loading hidden account/theme imagery eagerly. Actual 390px browser currentSrc selected the 640px hero and studio variants. Both srcset and ordinary URLs receive content fingerprints; CI compares every packaged static file with source bytes.

112. **The production checklist overstated the redesigned implementation — Corrected.** Full-brief audit, P2. [docs/PRODUCTION_UX_AUDIT.md:1](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/PRODUCTION_UX_AUDIT.md:1). The earlier playground, lime palette, absent-hero rationale and temporarily deleted favicon/sticky/touch-target claims are replaced with current implementation and scoped evidence. All six phases retain explicit unresolved operator/provider/device requirements instead of a blanket completion claim.

113. **Selecting a scene could hide its actions behind the new sticky bar — Fixed.** Final breaking-change review, P2. [lingbot_map/workspace/static/app.js:639](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:639). Small-screen selection now scrolls the containing workspace to its start, keeping the scene bar in normal layout above title and actions. It no longer aligns the details underneath the sticky layer.

114. **Account artwork advertised a full-width image slot — Fixed.** Final efficiency review, P3. [lingbot_map/workspace/static/index.html:85](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:85). Account imagery now declares its actual responsive column, padding and maximum 618px desktop/420px mobile width. A 1440px 1× display can select the 31 KB 640px light variant instead of the 115 KB full-width variant. The export and fingerprinting follow-up found no other issues.

### Deployed release verification

Runtime `9516dbfe7e3b672ad13a9b5288c26bf589484fb8` passed hosted CI and became
live on the existing Render service at 2026-09-11 16:43:56 UTC. All 64 deployed
static files match the reviewed source. Live public/signup layouts, Google
returning login, the saved 5,908-point scene and library reopening passed. The
database comparison retained six READY jobs, one Google identity, four remote
runs and zero pending remote cleanups. No new GPU job or provider service was
created. [The release receipt](DESIGN_RELEASE_QA.md) records deployment IDs,
public screenshots and the remaining acceptance/recovery boundaries. The draft
PR remains unmerged, with the aggregate-size finding and other recorded open
launch requirements preserved.

## Recovery crash follow-up — 2026-09-11

115. **A lost completion acknowledgement could delete the only restorable backup — Fixed.** Recovery review, P2. [lingbot_map/workspace/recovery.py:409](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:409). Durable publication intent now precedes marker upload. Uncertain candidates survive preflight cleanup and follow the existing seven-verified-set retention rule; marker-publication failures do not refund charges or advance success. Real age/subprocess regressions reproduce the previously unsafe crash boundary and verify restoration.

116. **The first regression did not prove pre-upload durability — Fixed.** Testing review, P2. [tests/test_recovery.py:438](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_recovery.py:438). The subprocess test now also exits immediately after the destination copies the marker, before upload returns. This catches moving the durable intent write after the upload; both exit points reuse actual decrypt/restore and blocked-next-attempt assertions.

117. **Aggregate PR size remains above guidance — Open.** Change-size review, P2. [docs/REVIEW.md:43](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/REVIEW.md:43). The first recovery code/test commit contained 437 changed lines; the final cap commit `d88da15` contains 151 (15 runtime and 136 test lines). Both increments are below the 500-line complex-change limit. The earlier documentation-inclusive cap review snapshot contained 284 changed lines, and the aggregate snapshot was 15,414 changed text lines plus 48 binary files. Those two snapshots precede final test/evidence additions; findings 19, 66, 83 and 103 remain open. The independently testable sample RGBA/VEC4 stride correction remains the smallest coherent aggregate stage; no main-branch merge is performed.

118. **Uncertain completions could accumulate storage across upload-allowance windows — Fixed.** Recovery follow-up review, P1. [lingbot_map/workspace/recovery.py:344](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:344). Protected `completion_pending` candidates outlived their rolling 30-day upload reservations, allowing fresh allowance windows to add remote sets indefinitely. `MAX_REMOTE_SETS = 8` now rejects fresh work before snapshot copying, reservation, encryption or upload when eight known unpruned prefixes remain. Restart, explicit retry and expired reservations cannot bypass the ceiling; uncertain sources are preserved for operator reconciliation. The multi-window upload/readback regressions assert eight actual scheduled prefixes and unchanged remote bytes when admission stops. This bounds known scheduled sets, not manual or ledger-unknown objects or the provider invoice.

119. **Failed deletion of superseded completed sets could accumulate backups — Fixed.** Recovery follow-up review, P2; pre-existing behavior. [lingbot_map/workspace/recovery.py:277](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/recovery.py:277). Preflight previously protected every completed set, so failed post-success deletion was retried only after another upload succeeded. It now retries deletion of completed sets outside the latest seven verified copies before admitting another snapshot, including after upload reservations expire. Deletion failure stops fresh work, preserves verified copies and leaves charges unchanged. The cleanup-failure regression checks one removal retry per blocked attempt, no new snapshot/upload, and recovery to seven sets once deletion succeeds. Uncertain-candidate protection remains unchanged.

120. **The restored-candidate test still expected a ninth prefix — Fixed.** Duplicate finding retained from both testing and breaking-change reviewers, P2. [tests/test_recovery.py:871](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/test_recovery.py:871). The old expectation admitted another backup with seven verified sets plus one retained candidate already present. The revised regression asserts `recovery_storage_limit`, unchanged prior state and upload count, empty new reservations, and preservation of all seven verified copies. It now verifies the intended eight-prefix policy instead of requiring the superseded behavior.

All three simplify passes (reuse, quality and efficiency) and all four code-review
subskill passes completed for this follow-up; the model-context pass was N/A.
The actionable recovery, testing and breaking-change findings are recorded above,
including the duplicate test-expectation finding. No additional simplify findings
remain; the aggregate-size finding stays open. The actual process-kill test adds
partial-artifact privacy, normal startup, exactly-once settlement and preserved-scene
coverage. [Recovery crash QA](RECOVERY_CRASH_QA.md) records verification evidence
and the separately scoped near-capacity offline drill. The follow-up is now deployed; the release receipt does not claim successful
provider recovery.

Final local verification passed 237 Python tests, including 31 recovery tests,
strict Ruff, formatting for 38 files and mypy for 20 source files. Container
`3cf2b42c4b229a29e0a11e51d6c358ed775103de3e7818bf896d179ae9a8c541`
passed the 512 MiB / 0.5 CPU smoke with a 205.9 MiB peak. Exact-commit hosted CI passed, and runtime `d88da15` became live at
2026-09-11 17:37:23 UTC. All 64 static assets, the recovery source, all 12
stored artifacts and preserved live state passed the read-only deployment check.

121. **The crash summary overstated public artifact visibility — Fixed.** P2. [docs/launch-readiness.md:64](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/launch-readiness.md:64). Documentation review. The kill occurs after a private artifact transaction commits and before job completion. The acceptance record now names that boundary and preserves the HTTP rejection evidence; it does not claim a post-publication crash test.

122. **The recovery summary generalized failure semantics — Fixed.** P3. [docs/RECOVERY_CRASH_QA.md:12](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/RECOVERY_CRASH_QA.md:12). Documentation review. The unchanged-success and failed-attempt retry statements now apply to failures before durable verified completion. A subsequent retention-deletion failure preserves the completed set and newer success and does not qualify that completed attempt for an operator retry.

## Optional analytics and current-theme follow-up — 2026-09-11

123. **The consent sender had no collector — Fixed.** P2. [lingbot_map/workspace/analytics.py:26](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/analytics.py:26). Completion audit identified an explicit unfinished brief item. The optional first-party collector now validates a fixed public schema, stores bounded daily aggregates and supplies an operator-readable report. Production activation and approved policy remain separate inputs.

124. **A failed storage write could undo analytics withdrawal — Fixed.** P2. [lingbot_map/workspace/static/site.js:6](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/site.js:6). Breaking/privacy review. Readable old acceptance previously remained effective if writing rejection failed, allowing a later public-surface change to send an event. In-memory rejection now wins, with best-effort removal of stale acceptance. Regressions cover failed writes with both successful and failed removal, delayed config, account-to-landing transitions and failed re-acceptance.

125. **Code and documentation together exceeded the small-change guidance — Addressed for this increment.** P2. [lingbot_map/workspace/app.py:433](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/app.py:433). Change-size review initially counted 557 lines, then 581 after the consent fix, when code and documentation were combined. The complete source/schema/client/tests/CI increment is 480 changed lines across ea61446 (476) and b4dd896 (four recovery-export assertions). The runbook, theme evidence and release documentation are reviewed and committed separately.

126. **Aggregate PR size still exceeds guidance — Open.** P2. [docs/REVIEW.md:43](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/REVIEW.md:43). Duplicate aggregate finding retained from the change-size reviewer. Its snapshot was 16,005 changed text lines plus 48 binary files; subsequent evidence additions change that total. Prior size findings remain open. The independent sample RGBA correction remains the smallest coherent aggregate first stage. No main or dependency PR merge is performed.

127. **The checklist described the completed collector as missing — Fixed.** P3. [docs/PRODUCTION_UX_AUDIT.md:83](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/PRODUCTION_UX_AUDIT.md:83). Documentation review. The implementation row and operator TODO now reference the local property label and explicit enable flag. The collector/reporting requirement is implemented; policy approval and production activation remain open. No external measurement-ID or endpoint placeholder is presented as unfinished code.

All simplify passes (reuse, quality, efficiency) and four code-review subskill
passes completed. The model-context pass was N/A. The withdrawal finding and
regressions were independently rechecked; no remaining actionable code finding
was reported. The source increment passed 255 Python tests, eleven Node suites,
strict lint/format/type checks and a 512 MiB / 0.5 CPU container smoke (208.1 MiB
peak). The isolated browser exercised opt-in, withdrawal, public navigation and
account-surface exclusion against real SQLite totals. See `ANALYTICS_QA.md`.
Current live public-theme contrast evidence is separately scoped in
`CURRENT_THEME_QA.md`; no visual source edit was needed.

Exact-commit [CI](https://github.com/ryouol/lingbot-map/actions/runs/34631234915) passed. Runtime `b4dd896`
became live at `2026-09-11T18:10:32.618362Z`. The live disabled-state check
verified eight backend modules, 64 static files, all 12 stored artifacts,
preserved jobs/identities/usage/recovery state, zero analytics rows and health
200. No provider plan, GPU use or extra backup admission changed. Final independent
documentation review returned no findings. [Analytics QA](ANALYTICS_QA.md) retains
the complete receipt; the full product goal and aggregate PR-size finding remain open.

## Private studio footer and provider-log follow-up — 2026-09-11

128. **The management action was clipped on mobile — Fixed.** P2. [styles.css:296](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:296). Actual 390×844 browser geometry placed the button bottom at 825 while the dialog ended at 820. The sticky footer now uses bottom zero; final checks retain the whole 44px button at 320px single-selection top/intermediate/end, 390px mixed-selection top/end, and short-desktop top/intermediate/end positions.

129. **The first offset change left a mobile override active — Fixed.** P2. [styles.css:434](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:434). Both quality/testing and efficiency/change-size reviewers independently reported the same remaining bottom:-24px override. Removing it makes mobile inherit the corrected base rule. Both findings are retained here; subsequent source and actual-browser checks verified the correction.

130. **A narrow footer shrank its button beneath the label — Fixed.** P2. [styles.css:297](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:297). The 320px interim screenshot showed a 90px button with overflowing label text. The scoped non-shrinking action now remains about 151×44px inside the dialog, including mixed selections.

131. **Selection copy included empty categories and incorrect singular nouns — Fixed.** P3. [app.js:475](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:475). The footer now reports only selected categories with singular/plural forms. Real browser states verified Nothing selected, 1 scene selected and 1 scene · 1 share selected, including correct action enablement. Selection sets and removal handlers are unchanged.

All three simplify passes and all four code-review subskill passes completed
for the final 10-line source increment. No additional actionable issue remained;
model-context was N/A. The aggregate PR-size finding remains open. The testing
review explicitly noted that the inventory suite stubs the summary function;
browser observations, not that stubbed suite, establish the wording evidence.
All eleven existing Node suites passed, and exact-commit hosted CI passed for
b8ac0fc, including Python, packaging and container verification. The local QA
fixture was stopped and removed. [Studio QA](STUDIO_THEME_QA.md) records the
seven-step visual audit and its limits.

[Provider log QA](PROVIDER_LOG_QA.md) confirms Hobby workspace/Starter compute and
records non-secret marker probes. The accessible log window was empty, so it
does not prove upstream redaction. No provider setting, plan, GPU admission or
backup retry was changed by that investigation. Authorized-operator confirmation
from Render remains an external requirement; no support message was sent.

Runtime b8ac0fc became live at `2026-09-11T18:40:07.818394Z`. The final read-only
check verified all 64 static files, eight backend modules, all 12 saved artifacts,
health 200 and unchanged saved state/allowances/recovery reservations. Analytics
remains disabled. [The release receipt](STUDIO_THEME_QA.md) records scope; this
release does not close the full product goal.

132. **The summary overstated final scroll-position coverage — Fixed.** P3. [STUDIO_THEME_QA.md:31](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/STUDIO_THEME_QA.md:31). Final documentation review distinguished the final 320px single-selection top/intermediate/end checks, 320px mixed near-bottom sample and 390px mixed top/end checks. The earlier 390px intermediate observation predates the last button-width change. The QA report, review summary and illustrated report now preserve that matrix instead of implying every combination passed.


## Dialog feedback and provenance follow-up — 2026-09-11

133. **Pending feedback was behind native management dialogs — Fixed.** P2. [lingbot_map/workspace/static/app.js:126](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:126) and [styles.css:303](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:303). The existing request indicator follows the open dialog and remains sticky while scrolling. Deferred requests and real local narrow-window observations cover visibility, completion and closing.

134. **Modal code copy omitted existing license/notice files — Fixed in recipe.** P2. [modal_app.py:41](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/modal_app.py:41). The recipe now copies the existing project license, third-party notices and provenance beside the model code. This is not a complete derived-code license bundle or hosted-use clearance. MODEL_PROVENANCE.md records conditional Waymo applicability and an unsent exact-checkpoint clarification question.

135. **DOM order did not match asynchronous modal opening order — Fixed.** P2. [lingbot_map/workspace/static/app.js:113](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:113), [tests/capture-onboarding.test.js:227](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/tests/capture-onboarding.test.js:227). Both the reuse/breaking reviewer and quality/testing reviewer independently reported the same reachable late-Share/confirmation race. A bounded opening-order set now supplies the status and toast host; all four opening paths share one helper. The real handler regression verifies Share appearing above confirmation, rejection feedback and Keep it without a DELETE request. The native-browser reproduction separately verifies visible pending feedback in the front Share dialog, close restoration and scene preservation after Keep it. Both reviewers re-reviewed the fix with no remaining issue.

All three simplify focuses and all four code-review subskills passed for the final 267-line source increment (166 UI/CSS/test lines and 101 provenance/packaging lines, committed separately as fe07999 and abd3f43). Model-context changes are N/A. The change-size reviewer retained existing finding 19: the aggregate PR is still oversized (33,172 text lines across 171 files plus 48 binaries before the final 62-line race delta). These incremental commits do not resolve that concern. No main/dependency PR was merged.

Local validation: 255 Python tests passed in 27.05 seconds before the final JavaScript-only race correction; all 11 Node suites passed afterward. The local browser confirmed the reverse opening order and 320/390px pending layouts. See [dialog loading QA](DIALOG_LOADING_QA.md), which preserves the distinction between layout captures before the host-order correction and the later race capture.

A separate live Google-account reconstruction was submitted during the bounded operator upload test and completed afterward. [Google capture QA](GOOGLE_CAPTURE_QA.md) records real publication/settlement and why the interleaved diagnostic cannot establish the intended 180-second upload. No production job was cancelled, deleted or resubmitted by that test.

136. **The review summary placed job completion inside the upload-test window — Fixed.** P3. [docs/REVIEW.md:508](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/REVIEW.md:508). Evidence review compared the diagnostic end timestamp with the actual job finish timestamp. The job was submitted during the diagnostic and completed approximately 53.345 seconds afterward; the summary now states that chronology.

Exact-source CI 34637277544 passed for abd3f43, including 255 Python tests (32.20 seconds), all 11 Node suites and a 200.8 MiB production-container smoke peak. Render became live at 19:14:07 UTC; Modal deployed the notice files without inference. All 14 saved artifact files, seven READY jobs, five GPU admissions, configured limits and recovery ledger were preserved across this deployment. See [release verification](DIALOG_LOADING_QA.md#release-verification).

137. **The summary blurred rejection-test and browser evidence — Fixed.** P3. [docs/REVIEW.md:502](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/REVIEW.md:502). Rejection/error-host behavior was verified by deferred Node tests. The browser separately verified visible ordering, focus, closing and scene preservation; the report now assigns each claim to its actual evidence.

138. **The fixture description could imply cleared scene-output rights — Fixed.** P3. [docs/DIALOG_LOADING_QA.md:10](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/DIALOG_LOADING_QA.md:10). The source data is CC BY 4.0, while the reconstructed output retains NOASSERTION. The description now says the precomputed scene is derived from CC BY 4.0 TUM data.


## Source notices and actual-scene follow-up — 2026-09-11

139. **Aggregate PR size remains above guidance — Open.** P2. [docs/REVIEW.md:43](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/REVIEW.md:43). Both new change-size passes retain the existing finding. The source-notice increment is 485 changed lines across 11 files, including 398 verbatim license lines; the subsequent UI increment is 29 lines across four files. Each is coherent and below 800 lines. The aggregate at 5e1d370 is still 33,838 changed text lines across 179 text files plus 48 binaries, before the UI/docs follow-up. Separate commits do not close the aggregate concern, and main/dependency PRs remain unmerged.

140. **Identified inherited-code license texts were absent from distributions — Fixed for the mapped portions.** P2. [Dockerfile:11](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/Dockerfile:11), [pyproject.toml:8](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/pyproject.toml:8), [modal_app.py:45](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/modal_app.py:45). The four exact upstream license files, source attributions, covered-file mapping and unresolved-fragment inventory now ship with source/wheel/Docker/Modal builds. Docker/wheel also carry MODEL_PROVENANCE. Verified comparison pins are not presented as actual historical import commits. [Source notice QA](SOURCE_NOTICE_QA.md) records hashes, builds and deployment; complete inherited-source and hosted-model rights remain unresolved.

141. **Replay could leave the current source thumbnail off-screen — Fixed.** P2. [timeline.js:104](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/timeline.js:104). Actual-scene QA reproduced restarting from the last frame while the strip remained at late thumbnails. The shared seek path now changes only horizontal strip scroll when a selected thumbnail lies outside its visible bounds. Existing timeline regressions cover restart, right-edge advancement, final frame and unchanged visible selections; desktop and 390px browser observations keep the active thumbnail visible without changing document scroll.

142. **The shared header exposed an unexplained technical license value — Fixed.** P3. [share.js:60](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/share.js:60). NOASSERTION now displays as Usage rights unconfirmed. The underlying identifier, other license labels, research warning and access controls remain intact. Existing share tests verify the wording, unchanged CC0 and cleanup on expiry/revocation; the 390px local browser shows the label without overflow.

All three simplify focuses and all four code-review subskills completed for both source increments. No further actionable code finding remained; model-context was N/A. The testing reviewers distinguish real browser layout evidence from DOM stubs. All eleven Node suites pass after the UI changes. Documentation review found no issue in the initial saved-scene report; final follow-up evidence remains separately scoped.

[Google capture QA](GOOGLE_CAPTURE_QA.md) records the first actual account artifact's saved-output checks: load, frame selection, replay, walk/reset and local signed-out sharing work, but the assembled geometry fails visual acceptance as a convincing continuous space. Download bytes/hash pass a separate loopback HTTP check; browser-save completion is unverified. The optional mobile walk-control placement remains a usability limitation, not a broken movement action. No private images, source filename or share capability enter this repository, and no new GPU run was used.

143. **The viewer summary did not distinguish local evidence from deployment state — Fixed.** P3. [docs/launch-readiness.md:60](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/launch-readiness.md:60), [docs/GOOGLE_CAPTURE_QA.md:101](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/GOOGLE_CAPTURE_QA.md:101). Documentation review identified present-tense wording while the supplied production receipt still covered 5e1d370. The report now explicitly names source/local verification and keeps the subsequent exact-commit deployment receipt separate.

The UI deployment now has its own exact-source receipt: CI 34640794995 passed 255 Python tests in 31.08 seconds, all eleven Node suites and a 214.2 MiB container smoke peak. Render c8fd218 became live at 19:52:32 UTC; all 64 static files, eight backend modules, eight source/installed-wheel notice files and 14 stored artifacts matched, with preserved jobs, admissions, limits and recovery ledger. Modal remains at 5e1d370. Final documentation re-review confirmed finding 143 resolved with no further finding.


## Capture framing guidance — 2026-09-11

144. **Portrait framing loss was not explained before submission — Fixed in source.** P2. [index.html:133](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/index.html:133). The existing Create scene instruction now explains possible top/bottom cropping and centered framing. The model's crop and full local preview remain unchanged. Browser inspection at 390×844 and 320×568 verifies readable guidance without horizontal overflow; this is an isolated no-worker fixture, not a physical-device or Google acceptance test.

All three simplify focuses and four separate code-review subskills completed for the two-line markup delta, with no further actionable finding; model-context was N/A. Existing aggregate PR-size finding 139 stays open. No new logic or text-mirroring tests were added. Eleven existing Node suites and 35 existing Python static/production-UX tests pass (1.51 seconds). The bounded source/saved-output investigation in [Google capture QA](GOOGLE_CAPTURE_QA.md) records portrait cropping and regular point sampling without claiming either explains or fixes the fragmented reconstruction.


## Mobile walk workflow — 2026-09-11

145. **Reaching walking controls obscured the mobile scene — Fixed in source.** P2. [timeline.js:51](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/timeline.js:51), [styles.css:234](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:234). Existing movement controls now sit inside the viewport, begin hidden and follow existing detach/mode lifecycle. Narrow loaded scenes let the source column scroll away. Private 390/320px and shared 390px checks keep the full canvas and 44px controls together; reset/logout/revoked-share checks hide controls correctly. Fullscreen geometry and button entry/exit passed, while fullscreen screenshot fidelity and physical-device behavior remain unverified.

The 24-line, three-file source increment passed all three simplify focuses and all four code-review subskills without further actionable findings. Context was N/A; existing aggregate size finding 139 remains open. All eleven Node suites and 35 Python UI tests pass. [Mobile walk QA](MOBILE_WALK_QA.md) separates accepted screenshots, computed geometry and unverified physical-device/model-quality claims. No inference, new GPU admission or provider setting change was used for local QA.


146. **The mobile-walk report implied a deployment receipt already existed — Fixed.** P3. [MOBILE_WALK_QA.md:3](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/docs/MOBILE_WALK_QA.md:3). Final evidence review distinguished the new local source checks from the predecessor's live receipt. The introduction now explicitly says these checks do not establish production deployment.


## Sign-out visibility — 2026-09-11

147. **Sign out scrolled out of reach in the scene workspace — Fixed in source.** P2. [styles.css:151](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:151). The account header stays visible while the page scrolls, and Sign out uses the existing outlined secondary style. The mobile source-column offset and scroll padding keep account controls accessible.

148. **Global pending feedback covered the signing-out label — Fixed in source.** P3. [styles.css:153](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/styles.css:153). The redundant global status hides during logout while the disabled button displays Signing out…. Error/retry and successful session cleanup remain visible and tested.

The focused source/test increment completed three simplify passes and four code-review subskills; no new actionable review finding remained. Existing aggregate size finding 139 remains open. All eleven Node suites and 56 Python API/static/production-UX tests pass. [Sign-out QA](SIGNOUT_QA.md) records local scrolling, narrow pending layout and actual cross-tab logout, separately from deployment verification.

## Unlimited signup and two lifetime videos — 2026-09-12

149. **The allowance title duplicated the API's limit — Fixed.** P3. [app.js:768](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:768). The title now reads both remaining and limit from the allowance response, retaining the existing safe display defaults.

150. **Google allowance lookup lacked a tenant-user index — Fixed.** P2. [database.py:190](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:190). Unlimited signup would grow the identity scan on each account/admission lookup. Initialization now creates `idx_users_tenant` for existing and new databases; the reviewed query plan resolves the tenant's users before the unique identity lookup.

All three simplify focuses and four code-review subskills completed for this coherent increment, with no further actionable finding; context was N/A. Existing P2 aggregate size finding 139 remains open at line 521: the PR spans 34,464 changed text lines and 48 binaries at review time, despite this increment staying below 500 lines. [Two-video QA](TWO_VIDEO_QA.md) records 258 passing Python tests, eleven Node suites, scoped lint/type checks, browser allowance states and schema migration/rollback requirements separately from deployment evidence.

## Capture timestamp origin — 2026-09-12

151. **Valid MOV capture failed on a negative starting timestamp — Fixed in source.** P1. [capture.py:49](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/capture.py:49). A real submitted capture decoded successfully but began at −1.6667 milliseconds, triggering the nonnegative timestamp guard before inference. Extraction now subtracts the first presentation timestamp before validation, retaining variable frame intervals, strict ordering and duration bounds. The exact private upload now extracts 47 frames from 0 to 15.541667 seconds locally; this is decoder verification, not a claim of completed GPU reconstruction.

Twelve scene/export tests pass, including positive/negative origin offsets, variable timing and rejection of nonfinite, duplicate or backward timestamps. Three simplify passes and four code-review subskills found no new actionable issue; existing aggregate PR-size finding 139 remains open. Deployment and any controlled repair attempt are recorded separately from these source/local checks. Private video and frames are excluded from version control.

## Owner quota exemption — 2026-09-12

152. **Owner admissions calculated unused personal usage aggregates — Fixed.** P3. [database.py:1065](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/database.py:1065). Owner admission paths now skip the nine-subquery personal usage calculation where personal ceilings do not apply. Usage reporting and global capacity/reservation checks remain in place.

153. **Changing the owner setting left old sessions exempt — Fixed.** P2. [identity.py:27](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/identity.py:27). Startup now compares a persisted hash of normalized owner configuration and atomically revokes old grants when it changes or is removed. Existing-session regressions cover removal/reassignment and case-insensitive unchanged configuration. The strengthened owner GPU test exercises actual upload and job admission, in addition to the reservation guard.

All three simplify focuses and four code-review subskills completed; no new actionable issue remains. Existing aggregate PR-size finding 139 remains open. [Owner access QA](OWNER_ACCESS_QA.md) records policy, schema migration, source/local verification, private activation and budget requirements separately from provider release evidence.

## Processing presentation — 2026-09-12

154. **Late progress could hide pending cancellation — Fixed.** P2. [app.js:671](../lingbot_map/workspace/static/app.js#L671). The presentation uses the authoritative cancellation flag for nonterminal jobs, so a late worker stage cannot replace “Stopping safely.” Terminal states take precedence. The actual detail-rendering regression covers this race's response shape.

155. **Unchanged polling rewrote progress accessibility attributes — Fixed.** P3. [app.js:695](../lingbot_map/workspace/static/app.js#L695). Progress values, status/job attributes, current-step attributes and transform updates now check for changes. New scenes still suppress the previous scene's transition. The regression asserts no repeated attribute mutations on unchanged responses.

156. **Current-step typography had a duplicate CSS rule — Fixed.** P3. [styles.css:214](../lingbot_map/workspace/static/styles.css#L214). Removed the leftover duplicate after replacing the original stage styling.

Three simplify focuses and four code-review subskills completed. No further actionable finding; model-context is N/A. Existing P2 aggregate PR-size finding 139 at line 521 remains open; this presentation increment is a coherent stage below 500 changed lines. [Processing QA](PROCESSING_UI_QA.md) separates local browser/state evidence from provider deployment receipts.
