# Product decision: reviewable 3D scene workspace

## Decision

Build the product around the durable review workflow, not around an unlicensed
model claim: **turn an owned handheld walkthrough into a reviewable 3D scene
package for spatial-computing, robotics-prototyping, and technical-content
teams**.

The customer outcome is a stored artifact with an inspectable provenance
record, browser review, download, controlled sharing, and deletion. A
reconstruction engine is replaceable infrastructure.

## First user and job

The first user is a technical practitioner who already has a short walkthrough
video and needs colleagues to inspect a rough scene without installing a model
stack. They value a clear failure state and an exportable GLB more than a
marketing claim about benchmark rank.

## Safe first slice

1. Sign into a private workspace.
2. Create the explicitly synthetic sample without compute or third-party data.
3. Watch truthful stages backed by the durable job state.
4. Orbit the stored GLB in the browser.
5. Download, create an expiring share, and delete the job and objects.
6. Optionally configure a research-only engine adapter outside the web process.

## Non-goals until clearance and evidence exist

- Paid LingBot inference or credits with monetary value
- Surveying, measurement, safety, navigation, or digital-twin accuracy claims
- “Production scale,” “20 FPS,” “10,000 frames,” or state-of-the-art claims
- Anonymous uploads or permanent public links
- Treating example repository imagery as a commercially reusable demo

## Success evidence

- A first-time user can complete the sample-to-share flow without weights.
- Restarts preserve jobs and recover interrupted work deterministically.
- Tenant A cannot enumerate or retrieve Tenant B objects.
- Every artifact records its engine, content hash, source category, and license.
- Cancellation/failure releases its capacity reservation.
