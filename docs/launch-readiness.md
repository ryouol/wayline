# Launch readiness

## Verified in this repository

- Authenticated sample-to-view/download/share/delete API path
- Tenant isolation on jobs and artifacts
- CSRF enforcement for cookie-authenticated mutations
- Exact production Host allowlisting, disabled OpenAPI/docs, security headers,
  strict CSP/Trusted Types, and application declared-body ceilings
- Byte, media, container, duration, frame, and dimension upload gates
- Durable quota reservation, success settlement, cancellation refund, and
  restart recovery
- Atomic local object writes and path traversal rejection
- Exact checkpoint digest verification and restricted PyTorch loading
- Separate auxiliary-model digest gate and no automatic moving-weight downloads
- Synthetic GLB provenance and CC0 license
- Static UI with system fonts, visible focus, semantic progress, responsive
  reflow, reduced-motion handling, and keyboard viewer controls
- Unit/integration tests, lint, type check, JavaScript syntax check, wheel build,
  and CI definition

## Owner gates before a public production launch

- [ ] Legal clearance or a replacement commercial engine
- [ ] Full browser visual and keyboard/assistive-technology QA; the current
      implementation environment could not provide the in-app browser
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
