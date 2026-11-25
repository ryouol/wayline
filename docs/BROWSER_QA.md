# Browser verification — 2026-09-10

Application commit: `d88fe47ba6e774bd263215a030c2d7f187d1844f`. These checks changed no application code. The Codex in-app browser exercised the actual local FastAPI app and packaged JavaScript; screenshots were inspected during the run. This record does not assert a real LingBot reconstruction, measured frame rate, or physical mobile compatibility.

## Environments and fixture

- Normal local app: `http://127.0.0.1:7860`, existing private data, new isolated visitor playground. Its stopped process was restarted without changing configuration or exposing the operator token.
- Separate renderer fixture: loopback-only `http://localhost:7861`, fresh temporary database/objects and a disposable test identity. The existing synthetic-engine extension point supplied the fixture; production source and the user's workspace were unchanged.
- Synthetic planar checker/gradient images: 120 frames, 100×80 pixels, 10 frames/second, uniform depth 4, identity rotations and horizontal camera translation from −0.75 to +0.75. Intrinsics `[70,70,50,40]`. The production exporter generated 750,000 points and calibrated trace/thumbnails. No model, user video, provider upload or GPU was involved.
- GLB: 12,866,924 bytes; SHA-256 `287dbd9c63d0422be0b14a7cae884259ee95ab626a778ea2c98258efd3045a06`.
- Desktop viewport and a 390×844 override. Viewport overrides were reset after inspection. Emulation does not reproduce mobile GPU/memory limits or native touch behavior.

## Observations

| Flow | Result |
|---|---|
| Visitor onboarding | Created an isolated playground and automatically queued its synthetic sample. |
| Repeat scene creation | A second sample reached READY and rendered 5,908 points; no shader/context errors. |
| Maximum configured fixture size | Loaded 750,000 points and all 120 thumbnail controls. Browser error/warning logs were empty during normal scene operations. |
| Calibrated frame view | Frame selection showed the expected checker/gradient point pattern in a source-aspect viewport. This was a visual check, not pixel-level projection validation. |
| Timed replay | Play changed to Pause, then returned to Play path after reaching `Frame 120 / 120 · 11.9s`; the range input's live value was 119. |
| Walking | Walk from here exposed directional controls. Forward/side steps changed the view; keyboard W and ArrowRight were exercised in the shared viewer. |
| Reset | Whole space restored the complete scene and hid directional walking controls. Shared Reset view used the same reset flow. |
| Narrow layout | Private and shared pages each measured `scrollWidth = innerWidth = 390`. Directional buttons measured 44px high. Timeline thumbnails scrolled inside their own strip. |
| Logout cleanup | Fixture filename disappeared from the page and thumbnail image count became zero. |
| Share without login | After owner logout, a separate tab loaded the scene through its capability link and exposed replay/walk/reset/download. No account session was required. |
| Download | The browser saved the GLB into Downloads; bytes and SHA-256 matched the original fixture. The automation download-event wait timed out, so filesystem equality was used as the result evidence. |
| Live expiry | Only the disposable fixture's share expiry was shortened in its temporary database, then reloaded. At expiry, the page showed “This share link has expired.”, removed all thumbnails, hid the timeline/download and disposed the viewer. Reload rejected the link. This tests expiry behavior without waiting the UI's default 24 hours. |

## Remaining acceptance

Real model inference, original-video/geometry alignment, quality, timing, failure rate and provider cost remain unmeasured. Google OAuth and deployed Render/Modal behavior need credentials and configuration. Test a physical mobile browser, native touch gestures, slower/long uploads, accessibility/contrast and actual captures before inviting video testers. Existing automated tests cover share revocation; this browser pass exercised expiry. No synthetic result should appear in marketing as reconstructed footage.
