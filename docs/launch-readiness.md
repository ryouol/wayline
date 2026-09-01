# Launch readiness

## Verified in this repository

- Authenticated sample-to-view/download/share/delete API path
- Tenant isolation on jobs and artifacts
- CSRF enforcement for cookie-authenticated mutations
- Exact production Host allowlisting, disabled OpenAPI/docs, security headers,
  strict CSP/Trusted Types, and application declared-body ceilings
- Byte, media, container, duration, frame, and dimension upload gates
- Durable quota reservation, success settlement, cancellation refund, atomic
  cancellation/completion ordering, partial-artifact discard, and restart
  recovery
- Atomic local object writes and path traversal rejection
- Exact checkpoint digest verification and restricted PyTorch loading
- Separate auxiliary-model digest gate and no automatic moving-weight downloads
- Synthetic GLB provenance and CC0 license
- Static UI with system fonts, visible focus, semantic progress, responsive
  reflow, reduced-motion handling, and keyboard viewer controls
- In-app browser pass of token sign-in, synthetic job creation, completed-scene
  review, WebGL load, viewer keyboard controls, expiring-share creation, and the
  unauthenticated share view at a 1280 x 720 viewport; no browser errors observed
- 27 passing unit/integration tests, lint, type check, JavaScript syntax check,
  wheel build, and CI definition

## Owner gates before a public production launch

- [ ] Legal clearance or a replacement commercial engine
- [ ] Complete mobile-viewport, screen-reader, contrast, and cross-browser QA;
      the desktop in-app browser workflow and keyboard viewer pass are recorded
      above, but they do not close this broader accessibility gate
- [ ] Postgres and S3-compatible implementations plus migration tests
- [ ] TLS host, DNS, private networking, secret manager, and restrictive IAM
- [ ] Distributed rate limits, malware scanning, direct multipart uploads, and
      retention/deletion policy
- [ ] Structured logs, metrics, alerting, error reporting, and incident runbook
- [ ] Backup restoration drill and disaster recovery objective
- [ ] Privacy notice, acceptable-use terms, data-processing terms, support path,
      security contact, and company identity
- [ ] Licensed customer-like fixture and reproducible quality/performance report
- [ ] Independent security review and tenant-isolation abuse test
- [ ] If using Modal: configured budget ceiling, object-store integration,
      cancellation test, and paid GPU validation explicitly authorized by owner

## Billing gate

There is intentionally no Stripe, checkout, or monetary credit path. Add billing
only after an engine is commercially cleared and the non-billing launch gates
pass. Usage reservations in the current schema are operational capacity, not a
promise of price or payment.
