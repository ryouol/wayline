# Optional first-party page counts

Analytics is disabled by default. The production service remains disabled until
the operator supplies an approved policy and explicitly configures it. This
feature uses the existing SQLite database; it needs no external provider,
subscription or tracking script.

## Configuration and consent

- `WAYLINE_ANALYTICS_ENABLED=false` is the default.
- `WAYLINE_ANALYTICS_PROPERTY_ID` is an operator-chosen label of 1–64 ASCII letters,
  digits, underscores or hyphens. It is public configuration, not a secret or a
  Google Analytics ID. An enabled installation requires this label.
- Before activation, approve the privacy disclosure and consent wording. Keep
  the explicit operator TODOs until those inputs are provided.

The public configuration response supplies a fixed same-origin collector path.
The client contacts it only after an accepted analytics choice and only on the
public landing, Privacy, Terms or Contact page. Account, workspace, share and
other paths are excluded. DNT/GPC suppress collection. Withdrawal, navigation
away from the public surface and page exit abort pending work; consent is checked
again after asynchronous configuration arrives. A rejected choice remains effective
for the current document even if browser storage writes/removal fail; old stored
acceptance is removed where possible. If both persistence operations fail, a later
page load cannot be guaranteed to retain that changed preference. Requests omit credentials and
referrers. Each page document attempts at most one count, with no retry loop.

## Collection and storage

`POST /analytics/page-view` is intentionally public ingestion, not a private-data
API. It requires a matching Origin, same-origin fetch metadata when supplied,
an explicit consent header and no opt-out signal. A strict schema permits only
the configured property, `page_view` event and four public page buckets. Extra
fields, arbitrary URLs, query strings, fragments and private paths are rejected.
Declared and streamed bodies are capped at 512 bytes.

A single global rate bucket permits at most 120 accepted requests per minute.
A transactional daily ceiling stops at 10,000 counts, including after restart.
Only UTC day, fixed page bucket and aggregate count are stored. The collector
stores no visitor IDs, IP addresses, cookies, session/account identifiers,
referrers, filenames or scene content. Its global rate limiter needs no visitor
key. Existing infrastructure request logs have separate verification requirements.

There are at most four page rows per UTC day in normal operation. Accepted events
and the existing periodic retention maintenance remove days older than the
current 30-day window; maintenance also runs when collection is disabled. Backup
copies follow their own retention policy. The approved environment configuration
is included in encrypted recovery exports.

## Read the report

An operator with access to the workspace directory can run:

```sh
python -m lingbot_map.workspace.analytics --data-dir /data/wayline
```

The command opens the existing database read-only and prints JSON containing the
last 30 UTC days of page totals. It does not create an HTTP reporting endpoint,
change the database or activate collection. These are best-effort client-reported
page counts, not unique visitors, trustworthy financial usage or a signup funnel.
