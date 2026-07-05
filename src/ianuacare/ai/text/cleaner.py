"""Lightweight text cleaning built on Python's standard library."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
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
    words are dropped and the remaining tokens are rejoined with single spaces.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = _WHITESPACE_RE.sub(" ", normalized).strip()
    if lowercase:
        collapsed = collapsed.lower()
    if remove_stopwords:
        tokens = _WORD_RE.findall(collapsed)
        collapsed = " ".join(
            token for token in tokens if token.lower() not in _DEFAULT_STOPWORDS
        )
    return collapsed
