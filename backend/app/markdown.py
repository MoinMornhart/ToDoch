"""Markdown serverseitig rendern und per Allowlist bereinigen."""

from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

_md = (
    MarkdownIt("commonmark", {"html": False, "linkify": False, "breaks": True})
    .enable("strikethrough")
    .enable("table")
)

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "del", "s", "code", "pre", "blockquote", "ul", "ol", "li",
    "a", "h1", "h2", "h3", "h4", "hr", "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}, "ol": {"start"}}
URL_SCHEMES = {"http", "https", "mailto", "tel"}


def render_markdown(text: str) -> str:
    if not text:
        return ""
    html = _md.render(text)
    return str(
        nh3.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes=URL_SCHEMES,
            link_rel="noopener noreferrer nofollow",
        )
    )
