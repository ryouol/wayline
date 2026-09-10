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

19. **The full rebuild exceeds the 800-line review guidance — Open before merge.** Code review / size. [lingbot_map/workspace/static/app.js:11](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:11). The reviewer measured 5,478 changed text lines before later fixes. The smallest first stage is the 55-line preserved canvas lifecycle fix/test/CI invocation. Further stages are listed below. The branch is for review and is not being merged or treated as release-approved.

20. **Exported RGB byte colors violated glTF vertex alignment — Fixed.** Code review / testing / P2. [lingbot_map/workspace/scene_export.py:33](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/scene_export.py:33). Use RGBA/VEC4 with a four-byte stride. Khronos gltf-validator@2.0.0-dev.3.10 reports zero errors and warnings for the corrected export.

21. **Nominal FPS changed variable-frame-rate replay timing — Fixed.** Code review / testing / P2. [lingbot_map/workspace/capture.py:45](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/capture.py:45). Use actual decoded presentation timestamps; a committed synthetic VFR fixture preserves 0,.1,.2,.3,.4,.5,1,1.5,2,2.5 seconds.

22. **A 60-second request deadline aborted ordinary mobile uploads — Fixed.** Code review / testing / P2. [lingbot_map/workspace/static/app.js:678](/Users/royluo/Documents/Codex/2026-08-31/turn-this-into-a-workable-prompt-2/work/lingbot-map/lingbot_map/workspace/static/app.js:678). Uploads receive a bounded 15-minute client deadline. Real mobile/network and deployed edge tests remain required.

The context-review skill found no conversational-history/model-context injection path. LingBot consumes bounded image tensors; OAuth/share tokens are credentials, and Rust `core/context` fragment rules are N/A. The testing skill’s Rust/Codex harness paths are likewise N/A; this repository uses FastAPI/TestClient and Node behavior tests.

## Review staging before merge

Preserved original hardening and canvas replacement remain in 027d338; history has not been rewritten. The reviewer recommends these coherent units: canvas lifecycle; HTTP/session hardening; offline snapshots; identity foundations; onboarding; capture/export contract; replay/walking viewer; atomic share-protocol change; queue separation; Modal transport and deployment; presentation/branding; Render delivery.

Keep auth routes with identity schema/dependencies; keep timeline construction with matching markup/script order; keep share-fragment URLs with header-authenticated routes/viewer downloads; keep the CLI lock with runtime_lock.py. The aggregate PR should remain draft until remaining acceptance gates and review-size concerns are resolved.

## Verification

- Python: 133 tests passed, including queue separation, disabled-submission cleanup, bounded remote I/O, unsupported options and the VFR fixture.
- Ruff strict lint and formatting passed. Mypy passed across 18 source files.
- All packaged JavaScript syntax checks passed; session-event, viewer-lifecycle, viewer-trace/walking and timeline Node behavior checks passed.
- `uv lock --check` passed. Wheel built with `uv build`; required UI and license files verified. The local uv-created venv does not contain pip, so the equivalent local pip-wheel command was unavailable; Docker independently built and installed the wheel using pip.
- Docker image built successfully. `scripts/smoke_container.py` passed with a non-root/read-only app, private persistent data, readiness and host/auth rejection, two sequential synthetic jobs, GLB download, capability-header sharing and revocation. The disposable container was removed afterward. An initial ad-hoc smoke assertion expected 204 for revocation; the documented API correctly returns 202, and the reproducible script now checks that contract.
- Corrected reconstruction fixture: Khronos glTF Validator zero errors/warnings. This validates serialization, not model output quality.
- High-confidence working-tree private-key/provider-token signature scan: no matches. Not a full Git-history or provider audit.
- Post-review browser QA: repeat sample creation, 750,000-point/120-frame synthetic fixture, replay completion, walking/reset, logout cleanup, anonymous share, verified GLB download and automatic expiry passed. Private/shared pages fit at 390px; see `BROWSER_QA.md`. No application code changed during this pass.

## Remaining acceptance

Actual Modal inference and remote cancellation/deletion, Google signup/account switching, deployed Render/TLS/edge/log/backup behavior and physical mobile testing are not verified. Modal/Render/Google credentials and an owned capture are unavailable. Browser access has resumed, and the synthetic desktop/mobile-viewport checks are recorded above. Public model-use rights and operator legal/contact details remain unresolved. See launch-readiness.md and PRODUCTION_UX_AUDIT.md for every release gate and TODO.
