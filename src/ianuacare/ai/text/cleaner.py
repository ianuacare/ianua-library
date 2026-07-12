"""Lightweight text cleaning built on Python's standard library."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_DEFAULT_STOPWORDS = frozenset(
    {
        "a",
        "ad",
        "al",
        "alla",
        "anche",
        "che",
        "con",
        "da",
        "del",
        "della",
        "di",
        "e",
        "ho",
        "il",
        "in",
        "io",
        "la",
        "le",
        "ma",
        "mi",
        "non",
        "per",
        "piu",
        "poi",
        "se",
        "sono",
        "su",
        "tra",
        "un",
        "una",
    }
)
_STOPWORD_RE = re.compile(
    r"(?i)\b(?:"
    + "|".join(re.escape(word) for word in sorted(_DEFAULT_STOPWORDS, key=len, reverse=True))
    + r")\b"
)


def _remove_stopwords(text: str) -> str:
    """Drop Italian stop words while keeping punctuation and apostrophes intact."""
    without = _STOPWORD_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", without).strip()


def clean_text(
    text: str,
    *,
    lowercase: bool = False,
    remove_stopwords: bool = False,
) -> str:
    """Normalize unicode form, collapse whitespace, and trim the result.

    Applies ``unicodedata.normalize('NFKC', ...)`` to unify compatibility
    characters (e.g. full-width punctuation, ligatures), replaces any run of
    whitespace (including tabs and newlines) with a single space, and strips
    leading/trailing whitespace. When ``lowercase`` is true the final string
    is lower-cased. When ``remove_stopwords`` is true, common Italian stop
    words are removed by whole-word match; punctuation is preserved.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = _WHITESPACE_RE.sub(" ", normalized).strip()
    if lowercase:
        collapsed = collapsed.lower()
    if remove_stopwords:
        collapsed = _remove_stopwords(collapsed)
    return collapsed
