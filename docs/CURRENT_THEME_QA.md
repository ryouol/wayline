# Current-theme public-screen QA — 2026-09-11

The live `d88da15` interface was inspected in the in-app Chromium browser.
This supplements the earlier palette checks; it does not certify the private
studio, all interaction states, assistive technology or physical mobile hardware.

| Step | Screen | Viewport | Rendered text elements | Lowest ratio | Result |
|---|---|---|---:|---:|---|
| 1 | Light landing | 1280×720 | 26 | 5.134:1 | Passed |
| 2 | Dark landing | 1280×720 | 26 | 7.498:1 | Passed |
| 3 | Dark signup | 1280×720 | 22 | 7.804:1 | Passed |
| 4 | Light signup | 1280×720 | 22 | 5.134:1 | Passed |
| 5 | Light signup and consent | 390×844 | 25 | 5.134:1 | Passed |
| 6 | Dark signup | 390×844 | 22 | 7.804:1 | Passed |

The measurements use computed foreground and composited solid ancestor background
colors. Each element is checked against its applicable threshold before rounding:
4.5:1 for ordinary text, 3:1 for large text. These are the
[W3C contrast thresholds](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
Text in images/canvases, placeholders, pseudo-elements, transient states and
closed-details descendants are outside this check. The accepted samples had no
background-image or opacity effects requiring a separate contrast assessment.

At 390px the document's scroll width matched the viewport. Keyboard Tab visibly
focused Allow analytics with a 3px solid cobalt outline, 4px offset and a
135.71×44px control. Essential only was selected afterward. Browser dimensions
were restored and the live page was left on the light landing screen.

Accepted screenshots, computed-style JSON, the capture helper and an illustrated
six-step report are retained under the ignored local directory
`.lingbot-workspace/current-theme-qa/`. The first full-page capture had stitching
artifacts and was rejected; accepted images are viewport captures. An initial
measurement included hidden details content during a color transition; it was
corrected to exclude that content and resampled. A suspected missing dark logo
was not reproduced: independent inspection of the saved screenshot and source
confirmed the logo and wordmark. No visual source change was required.

No account was created, private scene accessed or GPU invoked during this pass.
The consent appearance evidence predates the separately reviewed first-party
collector implementation. Activation and functional consent tests are distinct
from these contrast measurements.
