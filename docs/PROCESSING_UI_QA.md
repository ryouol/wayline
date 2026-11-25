# Processing status — 2026-09-12

The processing panel now uses the existing light/dark design tokens, a prominent
reported percentage, five numbered steps and a bar that eases between server
updates over 800 ms. It never advances on a timer or invents an ETA. The existing
reduced-motion rule removes transitions.

Preparing includes video validation and transfer to the private runner. Build
covers synthetic generation or reconstruction; Finish covers export and storage.
Recovered work returns to Queued. Pending cancellation uses the authoritative
cancellation flag even if a worker publishes a later stage. Failed/cancelled jobs
show a stopped state with the last reported percentage; READY hands over to the
existing viewer. Selecting another scene snaps to its own progress.

Local browser checks use an isolated loopback fixture with no worker, provider
calls or private captures:

1. Before: the small bar exposed raw stage names and offered no explanation of
   long waits. Captured in `01-before.png`.
2. Building: light and dark layouts show readable stage copy, completed checks,
   current-step emphasis and a clear percentage. Captured in
   `02-building-light.png`, `03-building-dark.png`, `04-mobile-dark.png`.
3. Saving: changing the fixture from 48% to 92% updates through normal polling.
   The browser reports the expected 0.8-second transform transition and a final
   scale of 0.92. The 390px and 320px layouts have no horizontal overflow.
   `05-saving-320.png` captures the narrow layout.

4. Failed: the panel switches to a stopped heading and red bar, with no active
   step. The existing error detail remains visible (`06-failed.png`).

Screenshots are private local evidence in `.lingbot-workspace/progress-qa/`.
They demonstrate controlled UI states, not a new production reconstruction.
Physical mobile devices and screen-reader announcements were not tested.
The progressbar exposes its actual value and stage; stage text is a polite live
region and is only rewritten when it changes. The current step uses `aria-current`.

The existing Node integration harness exercises actual detail rendering with API
responses: all known stages, cancellation/terminal precedence, recovered jobs,
unknown stages, bounded progress, unchanged polling, scene switches, ready/reset.
All eleven Node suites and 56 Python static/API/UX tests pass locally.
Exact-commit CI and deployment evidence are recorded separately in the private
release receipt; this document does not assert deployment before it is verified.
