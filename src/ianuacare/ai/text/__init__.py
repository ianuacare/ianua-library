"""Stdlib-based text processing utilities (cleaning + splitting)."""

from ianuacare.ai.text.cleaner import clean_text
from ianuacare.ai.text.splitter import split_sentences, split_words

__all__ = [
    "clean_text",
    "split_sentences",
    "split_words",
]
