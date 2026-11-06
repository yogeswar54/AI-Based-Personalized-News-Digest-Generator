from __future__ import annotations

import html
import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTIPLE_SPACES_RE = re.compile(r"\s+")


def clean_html_text(value: str | None) -> str:
    if value is None:
        return ""

    text = html.unescape(str(value))
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _MULTIPLE_SPACES_RE.sub(" ", text)
    return text.strip()
