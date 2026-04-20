"""Lightweight text cleaning built on Python's standard library."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str, *, lowercase: bool = False) -> str:
    """Normalize unicode form, collapse whitespace, and trim the result.

    Applies ``unicodedata.normalize('NFKC', ...)`` to unify compatibility
    characters (e.g. full-width punctuation, ligatures), replaces any run of
    whitespace (including tabs and newlines) with a single space, and strips
    leading/trailing whitespace. When ``lowercase`` is true the final string
    is lower-cased.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = _WHITESPACE_RE.sub(" ", normalized).strip()
    return collapsed.lower() if lowercase else collapsed
