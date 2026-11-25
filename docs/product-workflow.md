# Wayline product and delivery

The [project Space](https://chatgpt.com/space/page_6ac1875536bc8191af022b6db30a8ef8)
holds the current product backlog, acceptance criteria, and verified release records.
The [Notion project page](https://app.notion.com/p/3ee69b28e04f8144ae51d44e83a595a3)
links to that Space rather than maintaining a second backlog.

The Wayline PM and shipping Codex heartbeat reviews the project daily at 09:00
America/Toronto. It checks current source and production evidence, chooses one
bounded improvement, implements and verifies it, and deploys through the existing
Wayline Render service. It reports releases, meaningful findings, failed checks,
and required decisions. This local workflow requires the connected computer to
be available. Dot activation is separate and has not been completed.

Before editing, check for user changes, other active work, and remote updates.
Run the checks defined in `.github/workflows/ci.yml`; publish and deploy an exact
verified commit, preserving the existing production branch and rollback path.
Record the deployment and live verification in the Space. Do not expand billing,
permissions, model usage rights, or account allowances as part of routine polish.

## Delivery accounting

Artifact content, attachment downloads, and public share content use one durable,
atomic global delivery budget. File responses validate Range and If-Range before
reserving capacity and sending response headers. Successful full responses reserve
their content length; single-range responses reserve only their response length.
Malformed and unsatisfiable ranges consume no delivery allowance. Multiple ranges
remain unsupported. An If-Range mismatch requires capacity for the full response.

Reservations remain charged after interruption because the server cannot reliably
know how many bytes the peer received. Concurrent admission and restart durability
remain database responsibilities. This accounting correction does not introduce
per-tenant fairness or new per-share/IP abuse limits; those are separate product
and capacity decisions.
