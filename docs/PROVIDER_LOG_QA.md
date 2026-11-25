# Render logging verification — 2026-09-11

Read-only inspection confirmed Wayline uses one Starter compute instance in a
Hobby workspace. These are separate plan dimensions. The authenticated Billing
UI matched the service's existing owner workspace. No plan or setting changed.

The app already disables Uvicorn access logging in its runtime entrypoint.
This controls application logs, not Render or Cloudflare ingress logging.
Render documents customer-visible HTTP request logs for Pro workspaces and
above; Starter compute alone does not enable them. Log-forwarding destinations
and filters do not establish redaction before upstream storage. See
[logging](https://render.com/docs/logging),
[log streams](https://render.com/docs/log-streams) and
[Cloudflare ingress](https://render.com/docs/uptime-best-practices).

## Observed configuration and probes

- The owning workspace lookup succeeded. Its default log-stream lookup returned
  404 and supplied no destination; this is not a redaction guarantee. The UI
  stream-settings check was not completed after the user changed pages.
- Two public GET requests used non-secret dummy query/header markers. Health
  returned 200; an invalid OAuth callback returned 400. Both supplied Render and
  Cloudflare request-ID headers. No real OAuth code/state, session, cookie,
  capability, login or signup was used.
- Queries were restricted to this service and the 14.32-second window from
  18:20:38 to 18:20:53 UTC. Both app and request API queries returned 200 with
  zero records and no pagination remaining. All five marker-presence checks
  were false; only app/build log types were advertised.

An empty accessible log window is weak negative evidence. It does not establish
whether markers were excluded from provider-internal logs, whether ingestion
was delayed, or what an unavailable request-log feature would expose. No raw
logs, markers, credentials, request IDs or forwarding destinations were retained.
Safe configuration and observation receipts are in the ignored local directory
`.lingbot-workspace/provider-log-qa/`.

## Remaining external verification

No documented setting was found for per-field OAuth query/header redaction at
Render/Cloudflare ingress. An authorized workspace operator needs provider
confirmation of whether code/state query parameters and Authorization/Cookie
headers are captured, where they are retained, and which controls apply before
storage or forwarding on Hobby. No workspace upgrade is justified by this probe.

Prepared support question (not sent):

> For our Hobby workspace's Wayline web service, do Render or its Cloudflare
> ingress logs retain OAuth callback code/state query parameters or
> Authorization/Cookie headers? What redaction occurs before storage and
> forwarding, what retention/access applies, and which controls are available
> on Hobby?

Upstream redaction remains an open launch requirement. This report narrows the
unknown; it does not replace provider confirmation with the app's log setting.
