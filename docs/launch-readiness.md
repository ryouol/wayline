# Launch readiness

## Verified in this repository

- Authenticated sample-to-view/download/share/delete API path
- Tenant isolation on jobs and artifacts
- CSRF enforcement for cookie-authenticated mutations
- Exact production Host allowlisting, disabled OpenAPI/docs, security headers,
  strict CSP/Trusted Types, and application declared-body ceilings
- Byte, media, container, duration, frame, and dimension upload gates
- Durable compute reservations plus tenant byte/record quotas, durable
  upload/job/share rates, retention, reconciliation, and bounded inventories
- Expiry-only lease recovery with attempt/worker fencing on progress, artifact,
  completion, and failure mutations; attempt-scoped paths/cleanup and
  cooperative shutdown/child wait
- Transactional logical deletion plus durable physical-delete outbox, retry,
  and truthful `deleting` API responses
- Provisional durable object claims prevent reconciliation from deleting an
  in-flight upload/artifact; attempt artifacts stay private until `ready`
- Route-scoped request-hash idempotency with replay and conflict coverage for
  costly/mutation endpoints; raw share capabilities are not persisted in replay
  records
- Readiness fails closed on schema, object-store write/delete, or required-worker
  failure without exposing internal paths
- Atomic local object writes and path traversal rejection
- Runtime data/object/work directories are forced to `0700`; SQLite, WAL/SHM,
  stored objects, runner manifests, and the runtime manifest are forced to `0600`
- Descriptor-bound checkpoint digest verification, private content-addressed
  copies, group/world-write rejection, and restricted PyTorch/ONNX loading
  across every direct model loader
- Separate auxiliary-model digest gate and no automatic moving-weight downloads
- Synthetic GLB provenance and CC0 license
- Static UI with system fonts, visible focus, semantic progress, responsive
  reflow, reduced-motion handling, and keyboard viewer controls
- Browser tenant-state reset on logout/`401`/account change, request abortion,
  stale-response epoch fencing, and explicit WebGL resource/context teardown
- A prior baseline in-app-browser pass covered the desktop workflow at
  1280 x 720; the hardened final UI still requires the external cross-browser,
  mobile, accessibility, and account-switch run listed below
- 57 passing unit/integration tests before final release verification, plus
  lint, type check, JavaScript syntax checks, wheel build, and CI definition

## Owner gates before a public production launch

- [ ] Legal clearance or a replacement commercial engine
- [ ] Complete mobile-viewport, screen-reader, contrast, and cross-browser QA;
      the desktop in-app browser workflow and keyboard viewer pass are recorded
      above, but they do not close this broader accessibility gate
- [ ] Postgres and S3-compatible implementations plus migration/contract tests
- [ ] TLS host, DNS, private networking, secret manager, and restrictive IAM
- [ ] Distributed login/edge concurrency and byte limits, malware scanning,
      direct multipart uploads, and deployed lifecycle-policy validation
- [ ] Structured logs, metrics, alerting, error reporting, and incident runbook
- [ ] Backup restoration drill and disaster recovery objective
- [ ] Privacy notice, acceptable-use terms, data-processing terms, support path,
      security contact, and company identity
- [ ] Licensed customer-like fixture and reproducible quality/performance report
- [ ] Independent security review and tenant-isolation abuse test
- [ ] Verify CDN/proxy/WAF/APM access logs redact capability-token URL paths
- [ ] If using Modal: configured budget ceiling, object-store integration,
      cancellation test, and paid GPU validation explicitly authorized by owner

## Billing gate

There is intentionally no Stripe, checkout, or monetary credit path. Add billing
only after an engine is commercially cleared and the non-billing launch gates
pass. Usage reservations in the current schema are operational capacity, not a
promise of price or payment.
