from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).parents[1] / "lingbot_map" / "workspace" / "static"


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []
        self.labels: set[str] = set()
        self.controls: list[tuple[str, dict[str, str | None]]] = []
        self.remote_sources: list[str] = []
        self.inline_scripts = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "label" and values.get("for"):
            self.labels.add(values["for"])
        if tag in {"input", "canvas"}:
            self.controls.append((tag, values))
        if tag in {"script", "link", "img"}:
            source = values.get("src") or values.get("href")
            if source and source.startswith(("http://", "https://", "//")):
                self.remote_sources.append(source)
        if tag == "script" and not values.get("src"):
            self.inline_scripts += 1


def audit(name: str) -> MarkupAudit:
    parser = MarkupAudit()
    parser.feed((STATIC / name).read_text(encoding="utf-8"))
    return parser


def test_main_markup_has_unique_ids_labels_and_no_remote_runtime_assets():
    parser = audit("index.html")
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.remote_sources == []
    assert parser.inline_scripts == 0
    for tag, control in parser.controls:
        if tag == "input" and control.get("type") in {"hidden", "submit", "button"}:
            continue
        assert control.get("id") in parser.labels or control.get("aria-label")
    assert any(
        tag == "canvas" and control.get("tabindex") == "0" for tag, control in parser.controls
    )


def test_share_markup_and_styles_avoid_external_fonts_and_motion_dependency():
    parser = audit("share.html")
    assert parser.remote_sources == []
    assert parser.inline_scripts == 0
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in styles
    assert "Space Grotesk" not in styles
    assert "prefers-reduced-motion" in styles
    assert ":focus-visible" in styles


def test_client_code_never_injects_html_strings():
    scripts = "\n".join(
        (STATIC / name).read_text(encoding="utf-8") for name in ("app.js", "share.js", "viewer.js")
    )
    assert ".innerHTML" not in scripts
    assert "eval(" not in scripts
    assert "new Function" not in scripts
