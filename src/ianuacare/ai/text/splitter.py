"""Sentence and word tokenizers built on Python's standard library."""

from __future__ import annotations

import re

# Common Italian abbreviations whose trailing dot should NOT end a sentence.
# Ordered longest-first so multi-dot entries (e.g. ``S.p.A.``) are protected
# before shorter overlapping forms (``p.``).
_ITALIAN_ABBREVIATIONS: tuple[str, ...] = (
    "Dott.ssa",
    "Prof.ssa",
    "S.p.A.",
    "S.r.l.",
    "p.es.",
    "Sig.ra",
    "Sig.na",
    "a.C.",
    "d.C.",
    "N.B.",
    "Dott.",
    "Prof.",
    "Arch.",
    "cfr.",
    "ecc.",
    "Ecc.",
    "pag.",
    "Avv.",
    "Ing.",
    "Sig.",
    "Dr.",
    "es.",
    "vs.",
)

# Control character used to temporarily stand in for an abbreviation's dot so
# that the splitting regex does not break on it. SOH is never present in
# normal text, making it a safe placeholder.
_ABBREV_PLACEHOLDER = "\u0001"

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into a list of sentences.

    Uses a conservative heuristic: any ``.``, ``!``, or ``?`` followed by
    whitespace and a non-space character starts a new sentence. Known Italian
    abbreviations (``Dr.``, ``Sig.``, ``Prof.ssa``, ...) are protected so they
    do not introduce false breaks. Empty or whitespace-only input returns
    ``[]``.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        return []
    protected = text
    for abbr in _ITALIAN_ABBREVIATIONS:
        protected = protected.replace(abbr, abbr.replace(".", _ABBREV_PLACEHOLDER))
    parts = _SENTENCE_SPLIT_RE.split(protected)
    sentences = [part.replace(_ABBREV_PLACEHOLDER, ".").strip() for part in parts]
    return [sentence for sentence in sentences if sentence]


def split_words(text: str) -> list[str]:
    """Split ``text`` into unicode-aware word tokens.

    A word is any maximal run of ``\\w`` characters (letters, digits, or
    underscore, unicode-aware). Punctuation and whitespace act as separators.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _WORD_RE.findall(text)
