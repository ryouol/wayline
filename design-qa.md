# Gallery + Instrument implementation QA — 2026-09-11

**Design result: passed.** The accepted combination of Gallery (01) and Instrument
(03), refined in mockup 04, is implemented in the existing Wayline application.
There are no remaining P0/P1/P2 visual findings in the inspected states. This is
design and release-package acceptance, not commercial-launch or new-model acceptance.

## Reference and comparison

Approved source: private operator design artifact `04-gallery-instrument-signup.png` (not included in Git).
Studio reference: `03-instrument.png` in the same directory. The handoff and
revision brief remain alongside those artifacts.

The approved image and final desktop landing/studio screenshots were opened
together in the same comparison input. A second reviewer independently compared
those same files. Desktop screenshots use a 992 × 1100 viewport for the landing
and 1440 × 700 for the compact studio. The tall source is compared section by
section at its intended desktop width; these are viewport captures, not a claim
of pixel-identical full-page stitching. CUA full-page/clip capture produced
incorrect stitching, so only its verified viewport captures are used as evidence.

| Surface | Result |
|---|---|
| Typography | System sans, centered two-line hero, restrained weight and larger display headings match the chosen direction. No remote font dependency. |
| Layout | Brand/navigation → hero → real scene → studio story → final signup CTA. Hero heading around y=90, CTA around y=240, scene caption around y=735 and story around y=810 closely match 04. |
| Color | Porcelain light default, cobalt primary action, neutral studio; complete dark and system choices. Manual theme also selects the appropriate real imagery. |
| Imagery | Actual precomputed TUM office reconstruction and actual rendered studio screenshots. No invented mesh quality, people, scene versions, or collaboration. The original two-plane W mark replaces the old identity. |
| Copy and conversion | All Get started actions open signup; returning Sign in remains separate. No public Explore sample CTA. Research-preview context remains visible. Google is the public identity flow; local operator access stays secondary. |

## Browser evidence

Evidence directory: [docs/ux-evidence/2026-09-11](docs/ux-evidence/2026-09-11).

| State | Evidence and outcome |
|---|---|
| Desktop landing | `landing-desktop-top-final.jpg`, `landing-desktop-story-final.jpg`, `landing-desktop-footer-final.jpg`: correct section order, spacing, real imagery, clear signup actions. |
| Compact studio, both themes | `studio-light-final.jpg`, `studio-dark-final.jpg`: scene title, Share/Download/Delete, orbit/camera/walk, viewport controls and source strip remain available at 1440 × 700. |
| Mobile landing | `landing-mobile-light.jpg`: 390 × 844, responsive hero and clear Get started. |
| Mobile signup and keyboard access | `signup-mobile-light.jpg`, `signup-mobile-dark.jpg`: 390 × 844; Google action, returning login and research disclosures are readable. Light screenshot deliberately shows keyboard focus on the heading after Skip to main content; URL remains `#signup`. |
| Mobile shared scene | `shared-mobile-dark-final.jpg`: 750,000 real points and 30 source frames at 390 × 844. New aspect-aware fit keeps the whole scene inside the portrait canvas. Camera/Walk/Orbit controls were exercised. |
| Unavailable share | `shared-unavailable.jpg`: fresh invalid-capability navigation displays a recovery action, with no scene or Download button. |

Additional inspected interactions: Get started and Sign in routing; How it works
scroll; pause/play of landing motion; persistent appearance choices; local token
login; video picker, decoded preview and 10-second metadata; upload/progress to a
second READY scene; native creation/share dialogs; source replay and walking;
shared keyboard skip preserving the capability fragment; and browser download.
The downloaded `Office walkthrough.glb` was 12,210,576 bytes and matched the
precomputed reference SHA-256 exactly. The browser event waiter timed out, but
the actual newly downloaded file was independently checked on disk.

Local upload/progress used an isolated, ignored preview runner returning an
already verified TUM reference. It exercised the real application upload and job
flow without new model inference. It is not shipped in the package. Local Google
credentials were layout-only; no OAuth success or new-user acceptance is claimed
from the local preview. No Modal GPU work was submitted for this redesign.

## Motion, accessibility and resource use

- Landing scene: 75,000 points, 30 source frames, 1,411,016-byte public GLB. Source
  hash is pinned by `scripts/prepare_landing_scene.py`; attribution and modifications
  are in `static/ASSET-NOTICES.txt` and the artifact metadata.
- Motion is a bounded scroll-driven orbit. Pause, reduced motion, data saving,
  hidden tab and hidden landing stop or avoid it. Poster imagery remains useful
  without WebGL. No-op scroll positions do not redraw; resize still refits.
- Shared download remains available when WebGL fails. Expiry/revocation cancels
  pending work and hides download. Server failure has a distinct retry message.
- Native dialogs retain keyboard behavior; their feedback is moved into the
  active dialog so it is visible above the modal layer. Skip links focus the
  appropriate heading without changing account or share fragments.
- Final completion audit restored the complete favicon/manifest exports, 44px
  control hitboxes, sticky mobile signup/create navigation and responsive WebP
  imagery. Actual browser measurements confirmed the public controls at 44px,
  zero undersized visible workspace controls, both sticky bars at top=0 after
  scrolling, and 640px currentSrc choices on a 390px viewport. Account artwork
  has separate sizes for its narrower column. `landing-mobile-sticky.jpg` records
  the persistent signup action.

## Review and release checks

All three simplify passes and all four code-review skill passes completed.
Every finding and disposition is recorded in [docs/REVIEW.md](docs/REVIEW.md),
including the unresolved aggregate draft-PR size concern. An independent final
follow-up found no actionable regressions and reran all 10 Node suites.

- 229 Python tests; 10 Node suites; base and strict Ruff; formatting for 37 files;
  mypy for 20 modules; lock and shell checks: passed.
- Clean wheel verified all 64 current static files byte for byte, required
  notices, restored favicon formats and responsive delivery variants.
- Production Docker smoke passed under 512 MiB / 0.5 CPU, peaking at 204.6 MiB.
  It checked non-root storage, health/authentication, multipart inspection and
  deletion, two sequential sample jobs, 64 MiB upload during artifact delivery,
  download, sharing and revocation. This is CPU sample/container evidence.

Nonblocking P3 differences: the real hero is sparser than the illustrative mockup
and omits its decorative source-frame fan; the studio keeps two functional header
rows and looser framing; secondary details use progressive disclosure. The full favicon set is exported from the approved mark; the visible brand is a
1,194-byte WebP.

Physical mobile hardware, second-Google-account/owned-capture acceptance, model
and checkpoint hosted-use rights, approved operator policies/contact details,
dedicated provider billing isolation and successful automated backup readback
remain the existing launch gates. See [docs/launch-readiness.md](docs/launch-readiness.md).
Production deployment and live observations are recorded separately in
[docs/DESIGN_RELEASE_QA.md](docs/DESIGN_RELEASE_QA.md).
