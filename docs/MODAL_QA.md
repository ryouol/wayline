# Modal diagnostic evidence — 2026-09-10

## Scope

The original LingBot model executed on a private Modal A100 80 GB worker. The
input was `tests/fixtures/vfr-test-pattern.mp4`, a generated 64x48 test pattern
with no uploaded or third-party footage. This proves execution and the exported
artifact contract; it is not evidence of useful reconstruction quality on an
owned room capture, mobile performance, or public-product readiness.

## Deployment and checkpoint

- Workspace: `royluo05`; app: `wayline-reconstruction`.
- [Private deployment](https://modal.com/apps/royluo05/main/deployed/wayline-reconstruction).
- Model revision: `204754b72bb24f561f8d7e7e1e4e4cd9e809adf9`.
- Checkpoint: 4,632,303,465 bytes; SHA-256 `ee665103348e07e6b826d529b8e61de8f413d5432a4f2e84970d6c8fd2e1cd72`.
- [Successful CPU checkpoint preparation](https://modal.com/apps/royluo05/main/ap-8iL9yBN5xlbotKypxvz5gN).
- Final image `im-vshtx2ZDGSj80dn3BbPjTG` passed its entrypoint/demo/model import build check and deployed. The preceding image `im-55kzvq50bNBVY6kUB3yXuV` produced the diagnostic; the final delta only adds the build check.
- No public HTTP inference endpoint was registered. New public signup remains disabled in the Render Blueprint.

## One successful GPU invocation

| Measurement | Observed |
|---|---:|
| Sampled frames | 6 |
| Point count | 731,004 |
| Queue submission to READY, including transport | 114.65 seconds |
| Time inside runner, including loading/export | 78.32 seconds |
| Model inference only | 5.65 seconds |
| Peak allocated VRAM reported by PyTorch | 5,994,845,696 bytes |
| GLB bytes | 11,728,872 |

Function call: `fc-01M2666B60BSMF51ZA1RMRH10G`.
GLB SHA-256: `64313f42d889f0287373593913408667f95467843a17c4ed5956df75ad8d47d5`.
These timings are one diagnostic observation, not billed GPU duration or a
real-capture performance forecast. OpenCV reported nominal metadata duration
1.8 seconds; exported presentation timestamps still reached the actual last
frame at 2.5 seconds. Nominal FPS is not the replay timebase.

## Checks performed

- The real FastAPI application and worker accepted the video via its upload API,
  queued research, invoked the private Modal function, downloaded its result and
  published READY. The driver used TestClient with an isolated operator account,
  not Google OAuth or Render.
- GLB structure used the viewer's POINTS primitive. API content and download were
  byte-identical. The manifest reported the expected original checkpoint hash.
- After logout, a capability-authorized anonymous session read identical scene
  bytes. Revocation rejected later reads with 404.
- The durable remote record was marked cleaned. A separate Modal volume listing
  returned `[]`, confirming the capture prefix and outputs were physically gone.
- The real result loaded in the in-app browser through a separate localhost
  instance: 731,004 points, all six thumbnails and timestamps, path playback to
  frame 6 at 2.5 seconds, walking step controls and whole-scene reset.
- The Mac had about 533 MiB free. The normal storage floor rejected the first
  upload before any GPU submission. The isolated diagnostic used a 50 MiB logical
  storage budget, 20 MiB artifact ceiling and 256 MiB free-space floor; application
  defaults and the user's main local workspace were unchanged.

## Remaining acceptance

Run a short owned capture, then realistic upper-bound captures, including cold
and warm timings, visual quality and physical mobile QA. Test cancellation and
failure/crash cleanup with the deployed provider. Configure Render, Google OAuth,
provider spend controls, offsite restore, logging/edge limits and operator
legal/contact details. Commercial hosted-use clearance remains unresolved.
