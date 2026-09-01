# Launch readiness

## Verified in this repository

- Authenticated sample-to-view/download/share/delete API path
- Tenant isolation on jobs and artifacts
- Stable per-session CSRF enforcement for cookie-authenticated mutations,
  stale-header logout revocation, authenticated error principal markers, and
  peer-tab logout/account-change revalidation
- Exact production Host allowlisting, disabled OpenAPI/docs, security headers,
  strict CSP/Trusted Types, and application declared-body ceilings
- Byte, media, container, duration, frame, and dimension upload gates
- Durable compute reservations plus pre-I/O byte/slot reservations, tenant and
  global logical storage budgets, a physical free-space floor, tenant/global
  in-flight limits, durable rates, retention, and exact-size claim recovery
- Expiry-only lease recovery with attempt/worker fencing on progress, artifact,
  completion, and failure mutations; attempt-scoped paths/cleanup and
  cooperative shutdown/child wait
- Transactional logical deletion plus durable physical-delete outbox, retry,
  and truthful `deleting` API responses
- Provisional durable object claims prevent reconciliation from deleting an
  in-flight upload/artifact; attempt artifacts stay private until `ready`
- Route-scoped request-hash idempotency whose completion commits atomically with
  each database mutation; browser ambiguous retries reuse the same key, and raw
  share capabilities are not persisted in replay records
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
  stale-response epoch fencing, complete private-DOM erasure, cross-tab/focus
  revalidation, immediate peer clearing on `signed-out`/`account-changed`
  broadcasts, and explicit WebGL resource/context teardown
- Cursor load-more controls for all job/asset/share pages, direct deletion and
  revocation, and bounded multi-inventory cleanup
- Worker iteration exception supervision with bounded backoff and a regression
  proving the sole worker survives a transient dependency failure
- Modal reference runner compile-time disabled; CI installs the pinned client,
  imports without credentials, and asserts the gate is closed
- The hardened UI passed an isolated in-app-browser run through authentication,
  peer-tab session reuse, synthetic generation, point-cloud review, and rendering
  of download and management controls at the desktop default and a 390 x 844 mobile
  viewport. The mobile page had no horizontal overflow and both tabs reported
  zero console warnings or errors. An API regression proves one tab's `/api/me`
  refresh does not invalidate a peer tab's stable CSRF token and that logout
  revokes the shared server session even when the initiating tab presents a stale
  CSRF header. A JavaScript behavior regression separately proves peer state is
  cleared synchronously on `signed-out` and `account-changed` broadcasts, while
  `session-changed` performs revalidation. External cross-browser, screen-reader,
  contrast, and real account-switch testing remain owner gates below.
- 69 passing Python unit/integration tests plus the executable JavaScript
  session-event regression in the remediation gate, with lint, type check,
  JavaScript/shell checks, wheel build, and CI definition validation

## Owner gates before a public production launch

- [ ] Legal clearance or a replacement commercial engine
- [ ] Complete screen-reader, contrast, cross-browser, and real account-switch
      QA; the desktop/mobile in-app browser workflow and keyboard viewer pass
      recorded above do not close this broader accessibility gate
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
