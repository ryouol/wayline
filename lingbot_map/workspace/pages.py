"""Public, non-indexable support pages; never interpolate request or tenant data."""

import re
from functools import lru_cache
from hashlib import sha256
from html import escape
from pathlib import Path

from fastapi.responses import HTMLResponse

STATIC = Path(__file__).resolve().parent / "static"


@lru_cache(maxsize=128)
def asset_digest(path: Path, modified_ns: int, size: int) -> str:
    # File identity is part of the cache key, so local edits invalidate the digest.
    return sha256(path.read_bytes()).hexdigest()[:12]


def version_assets(document: str) -> str:
    """Content fingerprints prevent stale JS/CSS after an in-place release."""

    def replace(match: re.Match[str]) -> str:
        path = STATIC / match.group(1)
        try:
            info = path.stat()
            digest = asset_digest(path, info.st_mtime_ns, info.st_size)
        except OSError:
            return match.group(0)
        return f"/static/{match.group(1)}?v={digest}"

    return re.sub(r"/static/([\w.-]+(?:/[\w.-]+)*)(?=[\"']|\s+\d+(?:w|x))", replace, document)


def metadata(title: str, description: str, origin: str = "") -> str:
    title, description = escape(title, quote=True), escape(description, quote=True)
    image = escape(f"{origin}/static/studio-preview.jpg", quote=True)
    return f'''<meta name="description" content="{description}">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta property="og:type" content="website"><meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta property="og:image:alt" content="Wayline point-cloud scene studio">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">
<link rel="icon" href="/static/favicon.ico" sizes="16x16 32x32">
<link rel="icon" href="/static/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/static/favicon-16.png" sizes="16x16" type="image/png">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png" sizes="180x180">
<link rel="manifest" href="/static/site.webmanifest">'''


def app_page(name: str, title: str, description: str, origin: str = "") -> HTMLResponse:
    document = (STATIC / name).read_text(encoding="utf-8")
    return HTMLResponse(
        version_assets(
            document.replace("<!-- PAGE_METADATA -->", metadata(title, description, origin))
        )
    )


def support_page(
    title: str, description: str, body: str, *, status: int = 200, origin: str = ""
) -> HTMLResponse:
    # All body strings are source-controlled constants, not request input.
    return HTMLResponse(
        version_assets(f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · Wayline</title>{metadata(title, description, origin)}
<script src="/static/theme.js"></script>
<link rel="stylesheet" href="/static/styles.css"></head><body>
<main class="support-shell"><header class="support-header">
<a class="wordmark" href="/"><img class="brand-mark" src="/static/brand-mark.webp" alt=""
width="48" height="36">wayline</a>
<button class="icon-button" type="button" data-theme-toggle aria-label="Appearance: Light">
<img src="/static/icons/sun.svg" width="20" height="20" alt=""></button></header>
<h1>{escape(title)}</h1>{body}
<p><a class="primary" href="/">Return to Wayline</a></p></main>
<script src="/static/site.js"></script></body></html>"""),
        status_code=status,
    )


SUPPORT_PAGES = {
    "privacy": (
        "Privacy",
        "Privacy information and operator disclosure status.",
        """
<p class="status-label research">Operator policy pending</p>
<p>This is a disclosure scaffold, not a published privacy policy.</p>
<h2>Application data</h2><p>The workspace uses an essential sign-in cookie. Uploaded videos,
scene artifacts and job records are stored by the workspace operator. Expiring share links
allow their holders to access the selected artifact.</p>
<h2>Operator disclosures</h2>
<!-- TODO: provide approved privacy policy, controller identity, lawful bases, subprocessors,
retention periods, rights-request process and privacy contact before public launch. -->
<p>The operator must publish their identity, retention policy, processing purposes,
service providers and data-rights contact before inviting public users.</p>
<p>Optional analytics is disabled until the operator configures a collector and you opt in.
No scene contents, tokens, filenames or share URLs belong in analytics.</p>
<!-- TODO: provide approved analytics measurement ID and same-origin collector
endpoint in static/site.js. -->""",
    ),
    "terms": (
        "Terms",
        "Service terms and research restrictions disclosure status.",
        """
<p class="status-label research">Operator terms pending</p>
<p>This scaffold is not a legal agreement. Public sale is blocked
until approved terms are supplied.</p>
<!-- TODO: provide approved terms, legal entity, jurisdiction, billing/refund rules,
acceptable-use requirements and liability terms before public launch. -->
<h2>Research restrictions</h2><p>LingBot inference remains research-only. A working adapter
does not establish commercial rights to models, checkpoints, training data or outputs.</p>
<p>The bundled synthetic sample is CC0-1.0. It is a workflow test,
not a reconstruction-quality claim.</p>""",
    ),
    "contact": (
        "Contact",
        "Workspace operator contact details awaiting configuration.",
        """
<p>Contact the operator who supplied your workspace invitation for access or support.</p>
<!-- TODO: provide support email and replace this note with a mailto link. -->
<!-- TODO: provide support phone and replace this note with a tel link,
or confirm no phone support. -->
<!-- TODO: provide legal entity and physical business address. -->
<address>Operator email, phone and business address have not been supplied.</address>""",
    ),
}
