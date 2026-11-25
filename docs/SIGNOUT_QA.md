# Sign-out visibility and feedback — 2026-09-11

Local source checks after f2f367c; deployment is recorded separately.

The account header previously scrolled away from a loaded scene. At 390×844,
scrollY 441 placed Sign out at y=-431.5. The updated sticky header keeps the
44px button at y=9.5, with the header at y=0. Sign out uses the existing outlined
secondary style. Scroll padding and the mobile source-column offset account for
the fixed header area. No session endpoint or authentication policy changed.

Clicking Sign out disables duplicate submissions and displays Signing out… until
the existing session-revocation request completes. Failure retains the workspace,
shows its error and re-enables retry; success uses the existing session cleanup.
The redundant global Working pill hides only during logout, preserving readable
button feedback and avoiding a relocated overlay over New scene.

## Verification

- Isolated loopback fixture, disposable operator identity, saved private artifact;
  no production account mutation, inference or new GPU admission.
- 390px light scrolling and 320px dark layout keep Sign out visible without
  horizontal overflow. An eight-second loopback-only delay verifies the complete
  Signing out… label at 320px, a disabled button and no overlapping Working pill.
- Clicking Sign out returns both local tabs to the landing, hides the workspace,
  clears frame thumbnails/walking controls and revokes the local session.
- Existing Node harness now checks pending state, duplicate clicks, success,
  failed request, retry and private capture cleanup. All eleven Node suites pass.
- 56 existing Python API/static/production-UX tests pass, including cross-site
  logout rejection and revocation with stale CSRF. The initial test command used
  a nonexistent filename; the corrected command is the passing run.
- Three simplify passes and all four code-review subskills found no new source
  issue. Model-context is N/A; aggregate PR-size finding 139 remains open.

Private screenshots stay in ignored .lingbot-workspace/signout-qa. These local
checks do not establish the user's exact browser failure or physical-phone QA.
